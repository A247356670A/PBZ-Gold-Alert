"""Replace the verified original bank in its real library; preserve event identity."""
import hashlib
import json
import pathlib
import shutil
import struct
import subprocess
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'analysis'), str(ROOT/'work')]
from parse_fx import FXParser
from read_pbz import Reader
from zen_fx_edit import read_fields, encode_fields, raw_field
from build_yellow_alert_v011 import store_table

BUILD = ROOT/'work/gold-alert-v120'
RAW = BUILD/'raw'
OUT = ROOT/'outputs/PBZ-Gold-Alert-v1.2.0'
EVENT_ID = 3631941836
MEDIA_IDS = {61540465, 460074534, 665551823}
EVENT_PATH = 'ProjectPBZ/Content/Wwise/Events/SFX/Combat/VFX/Monster_VFX/Bell/SFX_Combat_VFX_Monster_YuDi_Blue.uasset'
LIBRARY_PATH = 'ProjectPBZ/Content/Wwise/WwiseAssetLibrary.uasset'
BULK_PATH = 'ProjectPBZ/Content/Wwise/WwiseAssetLibrary.ubulk'


def uid(label):
    h = 2166136261
    for c in ('pbz_gold_alert_v120_'+label).encode('ascii'):
        h = ((h * 16777619) ^ c) & 0xffffffff
    return h


def bank_chunks(data):
    p = 0
    out = []
    while p < len(data):
        tag, n = struct.unpack_from('<4sI', data, p)
        assert p+8+n <= len(data)
        out.append((tag, data[p+8:p+8+n]))
        p += 8+n
    assert p == len(data)
    return out


def make_bank(original, wem):
    chunks = dict(bank_chunks(original))
    assert set(chunks) == {b'BKHD', b'HIRC'}
    assert struct.unpack_from('<II', chunks[b'BKHD']) == (154, EVENT_ID)
    hirc = bytearray(chunks[b'HIRC'])
    pos = 4
    found = set()
    for _ in range(struct.unpack_from('<I', hirc)[0]):
        kind, n = struct.unpack_from('<BI', hirc, pos)
        body = pos+5
        if kind == 2:
            assert struct.unpack_from('<I', hirc, body+4)[0] == 0x10001
            assert hirc[body+8] == 1
            old_media = struct.unpack_from('<I', hirc, body+9)[0]
            assert old_media in MEDIA_IDS and old_media not in found
            found.add(old_media)
            hirc[body+8] = 0
            struct.pack_into('<III', hirc, body+9, uid('media_'+str(old_media)),
                             uid('cache_'+str(old_media)), len(wem))
            hirc[body+21] &= ~2
        pos += n+5
    assert pos == len(hirc) and found == MEDIA_IDS
    audio = bytearray()
    didx = bytearray()
    data_base = 8+len(chunks[b'BKHD'])+8+3*12+8
    for media in sorted(MEDIA_IDS):
        audio.extend(b'\0' * ((-(data_base+len(audio))) % 16))
        didx.extend(struct.pack('<III', uid('media_'+str(media)), len(audio), len(wem)))
        audio.extend(wem)
    parts = [(b'BKHD', chunks[b'BKHD']), (b'DIDX', didx), (b'DATA', audio), (b'HIRC', hirc)]
    return b''.join(struct.pack('<4sI', tag, len(data))+data for tag,data in parts)


def patch_event(original):
    path = BUILD/'event-original.uasset'
    path.write_bytes(original)
    q = FXParser(path)
    q.obj('AkAudioEvent')
    assert q.take('I') == 0
    q.obj('WwiseLocalizedEventCookedData')
    assert len(original)-q.p == 16
    rec, = [r for r in q.records if r['kind']=='struct' and r['type']=='WwiseSoundBankCookedData']
    q.p = rec['start']
    fields = read_fields(q, 'WwiseSoundBankCookedData')
    contains_index, = [i for i,f in fields.items() if f['name']=='bContainsMedia']
    fields[contains_index] = raw_field(b'\x01')
    media, = [r for r in q.records if r['kind']=='value' and r['type']==('Array',('Struct','WwiseMediaCookedData'))]
    changes = [(rec['start'],rec['end'],encode_fields(fields)),
               (media['start'],media['end'],struct.pack('<I',0))]
    hs = q.exports()[0]['start']
    body = original[hs:]
    for a,b,data in sorted(changes, reverse=True):
        body = body[:a-hs]+data+body[b-hs:]
    header = bytearray(original[:hs])
    export_map = struct.unpack_from('<I', header, 32)[0]
    struct.pack_into('<Q', header, export_map+8, len(body))
    return bytes(header)+body


def with_library_store(header, original, library_pid):
    stores, base, size, pids = store_table(header)
    original_stores, _, _, _ = store_table(original)
    assert library_pid not in stores
    stores[library_pid] = original_stores[library_pid]
    pids.append(library_pid)
    entries = bytearray(len(pids)*16)
    tail = bytearray()
    for i,pid in enumerate(pids):
        packages, shaders = stores[pid]
        for at,data,stride in ((0,packages,8),(8,shaders,20)):
            if data:
                struct.pack_into('<II', entries, i*16+at, len(data)//stride,
                                 len(entries)+len(tail)-(i*16+at))
                tail.extend(data)
    data = entries+tail
    result = bytearray(header[:16]+struct.pack('<I',len(pids))+struct.pack('<'+'Q'*len(pids),*pids)
                       +struct.pack('<I',len(data))+data+header[base+size:])
    struct.pack_into('<q',result,len(result)-20,len(result)-4)
    assert store_table(result)[0] == stores
    return bytes(result)


def build():
    (RAW/'chunks').mkdir(parents=True,exist_ok=True)
    (OUT/'Mod').mkdir(parents=True,exist_ok=True)
    r = Reader()
    def cid(path):
        idx = r.by_path[path]['index']
        return r.toc[144+idx*12:144+(idx+1)*12].hex()
    library_id = cid(LIBRARY_PATH)
    bulk_id = cid(BULK_PATH)
    event_id = cid(EVENT_PATH)
    library = r.read(r.by_path[LIBRARY_PATH]['index'])
    (BUILD/'library-original.uasset').write_bytes(library)
    q = FXParser(BUILD/'library-original.uasset')
    pad = struct.unpack_from('<Q',library,q.name_end)[0]
    bulk_map = q.name_end+16+pad
    bulk_size = struct.unpack_from('<Q',library,bulk_map-8)[0]
    assert bulk_size % 32 == 0
    original_bulk = r.read(r.by_path[BULK_PATH]['index'])
    matches = []
    for i in range(bulk_size//32):
        offset,duplicate,n,flags,index = struct.unpack_from('<qqqIB3x',library,bulk_map+i*32)
        if n>=16 and original_bulk[offset:offset+4] == b'BKHD' and struct.unpack_from('<I',original_bulk,offset+12)[0] == EVENT_ID:
            matches.append((i,offset,n,flags,index))
    match, = matches
    i,offset,n,flags,index = match
    assert flags == 66817 and index == 0
    original_bank = original_bulk[offset:offset+n]
    assert original_bank == (ROOT/'work/audio-v1/pbz-blue-correct.bnk').read_bytes()
    (BUILD/'bank-original.bnk').write_bytes(original_bank)
    wem = (ROOT/'outputs/PBZ-Gold-Alert-v1.0.1/Preview/ZZZ-Incoming-Attack-Warning.wav').read_bytes()
    assert wem[:4] == b'RIFF' and len(wem) == struct.unpack_from('<I',wem,4)[0]+8
    bank = make_bank(original_bank,wem)
    (BUILD/'library-warning.bnk').write_bytes(bank)
    new_offset = (len(original_bulk)+15)//16*16
    new_bulk = original_bulk+b'\0'*(new_offset-len(original_bulk))+bank
    new_library = bytearray(library)
    struct.pack_into('<q',new_library,bulk_map+i*32,new_offset)
    struct.pack_into('<q',new_library,bulk_map+i*32+16,len(bank))
    # No library metadata/native serialization/imports/flags change; only two integers.
    restored = bytearray(new_library)
    restored[bulk_map+i*32:bulk_map+(i+1)*32] = library[bulk_map+i*32:bulk_map+(i+1)*32]
    assert restored == library and new_bulk[:len(original_bulk)] == original_bulk
    prior = ROOT/'work/gold-alert-v101/raw'
    manifest = json.loads((prior/'manifest.json').read_text())
    assert event_id in manifest['chunk_paths']
    for key in manifest['chunk_paths']:
        if key == event_id:
            data = patch_event(r.read(r.by_path[EVENT_PATH]['index']))
        else:
            data = (prior/'chunks'/key).read_bytes()
        (RAW/'chunks'/key).write_bytes(data)
    (RAW/'chunks'/library_id).write_bytes(new_library)
    (RAW/'chunks'/bulk_id).write_bytes(new_bulk)
    manifest['chunk_paths'][library_id] = '../../../'+LIBRARY_PATH
    manifest['chunk_paths'][bulk_id] = '../../../'+BULK_PATH
    header, = (prior/'chunks').glob('*06')
    header_idx = next(j for j in range(r.n) if r.toc[144+j*12+11] == 6)
    library_pid = int.from_bytes(bytes.fromhex(library_id)[:8],'little')
    original_header = r.read(header_idx)
    (RAW/'chunks'/header.name).write_bytes(with_library_store(header.read_bytes(),original_header,library_pid))
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    expected = set(manifest['chunk_paths']) | {header.name}
    assert set(p.name for p in (RAW/'chunks').iterdir()) == expected
    retoc = ROOT/'tools/retoc/retoc.exe'
    toc = OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
    subprocess.run([str(retoc),'pack-raw',str(RAW),str(toc)],check=True)
    shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v1.0.1/Mod/zz_PBZ_YellowAlert_P.pak',toc.with_suffix('.pak'))
    subprocess.run([str(retoc),'verify',str(toc)],check=True)
    check = BUILD/('roundtrip-'+uuid.uuid4().hex[:8])
    subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
    assert set(p.name for p in (check/'chunks').iterdir()) == expected
    for key in expected:
        assert (RAW/'chunks'/key).read_bytes() == (check/'chunks'/key).read_bytes()
    evidence = {'library_cid':library_id,'bulk_cid':bulk_id,'event_cid':event_id,
                'library_bulk_map_entry':i,'bank_original_offset':offset,'bank_original_size':n,
                'bank_original_sha256':hashlib.sha256(original_bank).hexdigest(),
                'original_bulk_bytes':len(original_bulk),'original_bulk_sha256':hashlib.sha256(original_bulk).hexdigest(),
                'replacement_bank_offset':new_offset,'replacement_bank_bytes':len(bank),
                'bulk_prefix_unchanged':True,'container_verify':True,'raw_roundtrip_exact':True,
                'original_library_store_entry_preserved':True,'in_game_tested':False}
    (BUILD/'build-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')
    (OUT/'Preview').mkdir(exist_ok=True)
    (OUT/'Preview/ZZZ-Incoming-Attack-Warning.wav').write_bytes(wem)
    for name in ['Install-Update.ps1','Update-Mod.cmd']:
        data = (ROOT/'outputs/PBZ-Gold-Alert-v1.0.1'/name).read_bytes().replace(b'v1.0.1',b'v1.2.0')
        (OUT/name).write_bytes(data)
    (OUT/'Source').mkdir(exist_ok=True)
    shutil.copyfile(__file__,OUT/'Source'/pathlib.Path(__file__).name)
    (OUT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  Mod/'+p.name+'\n'
                                            for p in sorted((OUT/'Mod').iterdir())),encoding='utf8')
    print(json.dumps(evidence))


if __name__ == '__main__':
    build()
