"""Replace only original Wwise PCM samples; keep all runtime metadata unchanged."""
import array
import hashlib
import json
import pathlib
import shutil
import struct
import subprocess
import sys
import uuid
import wave

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'analysis'),str(ROOT/'work')]
from parse_fx import FXParser
from read_pbz import Reader
from build_gold_alert_v120 import with_library_store

BUILD = ROOT/'work/gold-alert-v140'
RAW = BUILD/'raw'
OUT = ROOT/'outputs/PBZ-Gold-Alert-v1.4.0'
LIB = 'ProjectPBZ/Content/Wwise/SFX_Monster.uasset'
BULK = LIB.replace('.uasset','.ubulk')
EVENT = 'ProjectPBZ/Content/Wwise/Events/SFX/Combat/VFX/Monster_VFX/Bell/SFX_Combat_VFX_Monster_YuDi_Blue.uasset'


def riff_chunks(b):
    p = 12
    result = {}
    while p < len(b):
        tag,n = struct.unpack_from('<4sI',b,p)
        assert p+8+n <= len(b)
        assert tag not in result
        result[tag] = (p+8,n)
        p += 8+n+(n%2)
    assert p == len(b)
    return result


def sources(bank):
    p = 0
    found = {}
    while p<len(bank):
        tag,n = struct.unpack_from('<4sI',bank,p)
        if tag == b'HIRC':
            h = bank[p+8:p+8+n];pos = 4
            for _ in range(struct.unpack_from('<I',h)[0]):
                kind,size = struct.unpack_from('<BI',h,pos);body = pos+5
                if kind==2:
                    assert struct.unpack_from('<I',h,body+4)[0]==0x10001
                    media,cache,prefetch = struct.unpack_from('<III',h,body+9)
                    assert h[body+8]==1 and prefetch==57696
                    found[cache] = media
                pos += size+5
            assert pos == len(h)
        p += n+8
    assert len(found) in (1,3)
    return found


def run_pack(raw,out):
    (out/'Mod').mkdir(parents=True,exist_ok=True)
    retoc = ROOT/'tools/retoc/retoc.exe'
    toc = out/'Mod/zz_PBZ_YellowAlert_P.utoc'
    subprocess.run([str(retoc),'pack-raw',str(raw),str(toc)],check=True)
    shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v1.0.1/Mod/zz_PBZ_YellowAlert_P.pak',toc.with_suffix('.pak'))
    subprocess.run([str(retoc),'verify',str(toc)],check=True)
    check = BUILD/('roundtrip-'+uuid.uuid4().hex[:8])
    subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
    expected = set(p.name for p in (raw/'chunks').iterdir())
    assert set(p.name for p in (check/'chunks').iterdir())==expected
    for name in expected:
        assert hashlib.sha256((check/'chunks'/name).read_bytes()).digest()==hashlib.sha256((raw/'chunks'/name).read_bytes()).digest()
    return str(check)


def installer(out,version):
    for name in ['Update-Mod.cmd','Install-Update.ps1']:
        (out/name).write_bytes((ROOT/'outputs/PBZ-Gold-Alert-v1.0.1'/name).read_bytes().replace(b'v1.0.1',version.encode()))
    (out/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  Mod/'+p.name+'\n' for p in sorted((out/'Mod').iterdir())),encoding='utf8')


def build():
    (RAW/'chunks').mkdir(parents=True,exist_ok=True)
    r = Reader()
    def cid(path):
        i=r.by_path[path]['index'];return r.toc[144+i*12:144+(i+1)*12].hex()
    lib = r.read(r.by_path[LIB]['index'])
    original = r.read(r.by_path[BULK]['index'])
    (BUILD/'library-original.uasset').write_bytes(lib)
    q=FXParser(BUILD/'library-original.uasset')
    map_at=q.name_end+16+struct.unpack_from('<Q',lib,q.name_end)[0]
    count=struct.unpack_from('<Q',lib,map_at-8)[0]//32
    targets=sources((ROOT/'work/audio-v1/pbz-blue-correct.bnk').read_bytes());targets.update(sources((ROOT/'work/audio-v1/red-Red.bnk').read_bytes()))
    matches={cache:[] for cache in targets}
    for i in range(count):
        off,_,size,flags,index=struct.unpack_from('<qqqIB3x',lib,map_at+i*32)
        if original[off:off+4]!=b'RIFF':continue
        head=original[off:off+min(size,256)];h=head.find(b'hash')
        if h<0:continue
        cache=struct.unpack_from('<I',head,h+8)[0]
        if cache in targets:
            matches[cache].append({'index':i,'offset':off,'size':size,'riff_size':struct.unpack_from('<I',head,4)[0]+8})
    with wave.open(str(ROOT/'outputs/PBZ-Gold-Alert-v1.0.1/Preview/ZZZ-Incoming-Attack-Warning.wav'),'rb') as f:
        assert (f.getframerate(),f.getnchannels(),f.getsampwidth())==(44100,1,2)
        mono=array.array('h',f.readframes(f.getnframes()))
        import math
        mono=array.array('h',(round(math.copysign(30000+2767*math.tanh((abs(v*1.3)-30000)/2767),v)) if abs(v*1.3)>30000 else round(v*1.3) for v in mono))
    patched=bytearray(original)
    evidence=[]
    (OUT/'Preview').mkdir(parents=True,exist_ok=True)
    for cache,records in matches.items():
        assert len(records)==2,records
        full,=[x for x in records if x['size']==x['riff_size']]
        prefix,=[x for x in records if x['size']==57696]
        old=original[full['offset']:full['offset']+full['size']]
        chunks=riff_chunks(old)
        fmt_at,fmt_n=chunks[b'fmt ']
        assert fmt_n==24 and struct.unpack_from('<HHIIHH',old,fmt_at)==(0xfffe,2,48000,192000,4,16)
        data_at,data_n=chunks[b'data']
        assert data_at==96 and data_n%4==0
        assert original[prefix['offset']:prefix['offset']+prefix['size']]==old[:57696]
        # Preserve pitch and onset. Only the very quiet tail is shortened to fit the original duration.
        frames=data_n//4;audio=array.array('h')
        for j in range(frames):
            position=j*44100/48000;left=int(position);fraction=position-left
            a=mono[left] if left<len(mono) else 0;b=mono[left+1] if left+1<len(mono) else 0
            value=round(a+(b-a)*fraction)
            if j>=frames-480:value=round(value*(frames-1-j)/479)
            audio.extend((value,value))
        new=bytearray(old);new[data_at:data_at+data_n]=audio.tobytes()
        assert len(new)==len(old) and new[:data_at]==old[:data_at]
        media=targets[cache]
        (BUILD/f'media-{media}.wem').write_bytes(new)
        with wave.open(str(OUT/f'Preview/ZZZ-Variant-{media}.wav'),'wb') as f:
            f.setparams((2,2,48000,frames,'NONE','not compressed'));f.writeframes(audio.tobytes())
        for item in records:
            off=item['offset'];n=item['size'];patched[off:off+n]=new[:n]
        dropped=sum(v*v for v in mono[min(len(mono),int(frames*44100/48000)):])/sum(v*v for v in mono)
        evidence.append({'media_id':media,'cache_id':cache,'records':records,'frames':frames,
                         'duration':frames/48000,'discarded_source_tail_energy_fraction':dropped,
                         'original_header_sha256':hashlib.sha256(old[:data_at]).hexdigest()})
    # Every byte outside the six verified RIFF ranges must remain original.
    cursor=0
    spans=sorted((rec['offset'],rec['size']) for rows in matches.values() for rec in rows)
    for off,n in spans:
        assert off>=cursor and original[cursor:off]==patched[cursor:off]
        cursor=off+n
    assert original[cursor:]==patched[cursor:] and len(original)==len(patched)
    prior=ROOT/'work/gold-alert-v101/raw';manifest=json.loads((prior/'manifest.json').read_text())
    for key in manifest['chunk_paths']:
        data=r.read(r.by_path[EVENT]['index']) if key==cid(EVENT) else (prior/'chunks'/key).read_bytes()
        (RAW/'chunks'/key).write_bytes(data)
    (RAW/'chunks'/cid(LIB)).write_bytes(lib)
    (RAW/'chunks'/cid(BULK)).write_bytes(patched)
    manifest['chunk_paths'][cid(LIB)]='../../../'+LIB
    manifest['chunk_paths'][cid(BULK)]='../../../'+BULK
    header,=(prior/'chunks').glob('*06')
    hi=next(i for i in range(r.n) if r.toc[144+i*12+11]==6)
    (RAW/'chunks'/header.name).write_bytes(with_library_store(header.read_bytes(),r.read(hi),int.from_bytes(bytes.fromhex(cid(LIB))[:8],'little')))
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    from visuals_v140 import update_visuals
    update_visuals(r,RAW,manifest)
    roundtrip=run_pack(RAW,OUT)
    installer(OUT,'v1.4.0')
    (OUT/'Source').mkdir(exist_ok=True)
    shutil.copyfile(__file__,OUT/'Source'/pathlib.Path(__file__).name)
    result={'version':'1.4.0','format':'Original Wwise PCM 0xfffe, fmt size 24, stereo 48000Hz',
            'event_asset_bit_exact_original':True,'library_asset_bit_exact_original':True,'bank_not_overridden':True,
            'media_ids_cache_ids_prefetch_and_metadata_unchanged':True,'original_bulk_size':len(original),
            'patched_bulk_size':len(patched),'bulk_cid':cid(BULK),'library_cid':cid(LIB),'event_cid':cid(EVENT),
            'outside_target_riff_spans_bit_exact':True,'gain_vs_v130':1.3,'size_vs_original':3,'red_cross':True,'media':evidence,'container_verify':True,
            'raw_roundtrip_exact':True,'roundtrip_path':roundtrip,'in_game_tested':False}
    (BUILD/'build-evidence.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':build()
