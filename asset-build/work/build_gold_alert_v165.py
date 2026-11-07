"""Replace the wrong cue with two confirmed native ZZZ variants, chosen at random.

Retain v164's entire visual/ability data. Reuse PBZ's existing two media IDs and
cache IDs, routing both sounds through the already-working random container.
"""
from pathlib import Path
import hashlib,json,shutil,struct,subprocess,sys,uuid,wave
import xml.etree.ElementTree as ET
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from parse_fx import FXParser
from build_gold_alert_v130 import riff_chunks
from build_gold_alert_v160 import digest

BUILD=ROOT/'work/gold-alert-v165'
RAW=BUILD/'raw'
OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.6.5'
PRIOR=ROOT/'work/gold-alert-v164/raw'
SOURCE=ROOT/'work/audio-correction-v165/verified-purple-hint'
CURRENT=ROOT/'work/black-alert-investigation/current'
MONSTER='e769c85cabe3aa8400000001'
MONSTER_BULK='e769c85cabe3aa8400000002'
LIB='5aac5b9f482230fd00000001'
LIB_BULK='5aac5b9f482230fd00000002'
EVENT=2193359531
CONTAINER=661678587
SOUNDS=[482757608,892170431]
CACHES=[2920923688,2635691332]
MEDIAS=[11815177,937778419]
ENTRIES=[145,10157]


def table(asset):
    q=FXParser(asset)
    return q.name_end+16+struct.unpack_from('<Q',q.b,q.name_end)[0]


def hirc_objects(bank):
    at=0
    while at<len(bank):
        tag,n=struct.unpack_from('<4sI',bank,at)
        if tag==b'HIRC':
            count=struct.unpack_from('<I',bank,at+8)[0];p=at+12;objects=[]
            for _ in range(count):
                kind,size=struct.unpack_from('<BI',bank,p);body=bank[p+5:p+5+size]
                assert len(body)==size
                objects.append((kind,struct.unpack_from('<I',body)[0],body))
                p+=5+size
            assert p==at+8+n
            return at,n,objects
        at+=8+n
    raise ValueError('Missing HIRC')


def random_bank(original,lengths):
    at,n,objects=hirc_objects(original);rebuilt=[];changed=[]
    for kind,oid,body in objects:
        old=body;b=bytearray(body)
        if oid in SOUNDS:
            i=SOUNDS.index(oid)
            assert kind==2 and struct.unpack_from('<I',b,9)[0]==MEDIAS[i]
            assert struct.unpack_from('<I',b,13)[0]==CACHES[i]
            assert b[8]==0 and not b[21]&2
            struct.pack_into('<I',b,4,0x10001)  # Native PCM codec, as in v164.
            struct.pack_into('<I',b,17,lengths[i])
            assert struct.unpack_from('<I',b,30)[0] in [CONTAINER,778311897]
            struct.pack_into('<I',b,30,CONTAINER)
        elif oid==CONTAINER:
            assert kind==5 and len(b)==148
            assert struct.unpack_from('<f',b,22)[0]==7.3206000328063965
            assert struct.unpack_from('<I',b,130)[0]==1
            assert struct.unpack_from('<I',b,134)[0]==SOUNDS[0]
            assert struct.unpack_from('<H',b,138)[0]==1
            assert b[128]==0  # Random, not sequence.
            struct.pack_into('<H',b,124,0)  # Independent random choices; repeats allowed.
            b=b[:130]+struct.pack('<IIIHIIII',2,*SOUNDS,2,SOUNDS[0],50000,SOUNDS[1],50000)
        elif oid==778311897:
            # Its single sound now belongs to the working primary container.
            assert kind==5
            changed.append(dict(id=oid,operation='remove unused child container'))
            continue
        elif oid==382141041:
            assert kind==9 and len(b)==57
            assert struct.unpack_from('<III',b,40)==(2,CONTAINER,778311897)
            b=b[:40]+struct.pack('<II',1,CONTAINER)+b[52:]
        elif oid==800828386:
            assert kind==3 and struct.unpack_from('<I',b,6)[0]==CONTAINER
        if bytes(b)!=old:changed.append(dict(id=oid,kind=kind,previous_bytes=len(old),new_bytes=len(b)))
        rebuilt.append((kind,oid,bytes(b)))
    assert len(rebuilt)==len(objects)-1
    payload=struct.pack('<I',len(rebuilt))+b''.join(struct.pack('<BI',k,len(b))+b for k,_,b in rebuilt)
    result=original[:at]+b'HIRC'+struct.pack('<I',len(payload))+payload+original[at+8+n:]
    assert len(result)==len(original)-80
    return result,changed


def find_hash(wem):
    assert wem[:4]==b'RIFF' and struct.unpack_from('<I',wem,4)[0]+8==len(wem)
    at=12
    while at+8<=len(wem):
        tag,size=struct.unpack_from('<4sI',wem,at);at+=8
        assert at+size<=len(wem)
        if tag==b'hash':
            assert size==16
            return wem[at:at+size]
        at+=size+(size%2)
    raise ValueError('Missing native cache hash')


def make_media(old_bulk,asset):
    raw=asset.read_bytes();m=table(asset)
    off,_,length,flags,index=struct.unpack_from('<qqqIB3x',raw,m+ENTRIES[0]*32)
    assert (off,length,flags,index)==(781392768,396896,66817,0)
    old_wem=old_bulk[off:off+length]
    reference=np.frombuffer(old_wem[96:],'<i2').reshape(-1,2).astype(float)/32768
    target=float(np.sqrt(np.mean(reference[:24000]**2)))
    header=old_wem[:96];hash_at,hash_size=riff_chunks(header+old_wem[96:])[b'hash']
    inputs=[ROOT/'work/audio-correction-v165/vesper-attack-sources/108729793.wem.wav',SOURCE/'bank-settings-float.wav']
    wems=[];reports=[]
    preview=OUT/'Preview';preview.mkdir(exist_ok=True)
    for i,path in enumerate(inputs):
        rate,samples=wavfile.read(path)
        assert samples.dtype==np.float32 and samples.ndim==2 and samples.shape[1]==2
        a=resample_poly(samples.astype(np.float64),48000,rate)
        # Only eliminate edge discontinuities, retaining the approved duration/timbre.
        a[:96]*=np.linspace(0,1,min(96,len(a)))[:,None]
        a[-480:]*=np.linspace(1,0,min(480,len(a)))[:,None]
        before=float(np.sqrt(np.mean(a[:24000]**2)))
        knee,cap=.82,.96
        def limited(gain):
            magnitude=np.abs(a)*gain
            magnitude=np.where(magnitude<=knee,magnitude,knee+(cap-knee)*np.tanh((magnitude-knee)/(cap-knee)))
            return np.copysign(magnitude,a)
        lo,hi=0.,32.
        assert np.sqrt(np.mean(limited(hi)[:24000]**2))>target
        for _ in range(60):
            mid=(lo+hi)/2
            if np.sqrt(np.mean(limited(mid)[:24000]**2))<target:lo=mid
            else:hi=mid
        pcm=np.rint(limited((lo+hi)/2)*32768).astype('<i2')
        measured=pcm.astype(float)/32768
        assert abs(float(np.sqrt(np.mean(measured[:24000]**2)))-target)<1e-6
        assert np.max(np.abs(measured))<.961
        rec_at=m+ENTRIES[i]*32
        previous_off,_,previous_len,previous_flags,previous_index=struct.unpack_from('<qqqIB3x',raw,rec_at)
        previous=old_bulk[previous_off:previous_off+previous_len]
        cache_hash=find_hash(previous);assert struct.unpack_from('<I',cache_hash)[0]==CACHES[i]
        h=bytearray(header);h[hash_at:hash_at+hash_size]=cache_hash
        payload=pcm.tobytes();struct.pack_into('<I',h,4,len(payload)+88);struct.pack_into('<I',h,92,len(payload))
        wem=bytes(h)+payload;wems.append(wem)
        wem_path=BUILD/f'purple-variant-{i+1}.wem';wem_path.write_bytes(wem)
        wav_path=preview/('Purple-Original.wav' if i==0 else 'Purple-Processed.wav')
        wavfile.write(wav_path,48000,pcm)
        decoded=BUILD/f'decoded-{i+1}.wav'
        subprocess.run([str(ROOT/'tools/vgmstream/vgmstream-cli.exe'),'-i','-o',str(decoded),str(wem_path)],check=True,capture_output=True)
        with wave.open(str(decoded),'rb') as f:
            assert (f.getnchannels(),f.getframerate(),f.getsampwidth())==(2,48000,2)
            assert f.readframes(f.getnframes())==payload
        reports.append(dict(variant=i+1,name='native original' if i==0 else 'confirmed game-parameter approximation',
            source=str(path),source_sha256=digest(path),source_media_id=108729793,media_id=MEDIAS[i],cache_id=CACHES[i],
            duration_seconds=len(pcm)/48000,gain_before_limiter=(lo+hi)/2,first_500ms_rms_before=before,
            first_500ms_rms_after=float(np.sqrt(np.mean(measured[:24000]**2))),target_from_v164_first_500ms_rms=target,
            peak_pcm=float(np.max(np.abs(measured))),hard_clipped_samples=int(np.sum(np.abs(measured)>=1)),
            pcm_format='Wwise fmt24 / 48000 Hz / stereo / 16-bit',independent_decoder_bit_exact=True))
    return wems,reports


def append_bulk(asset_path,bulk_path,entries,payloads):
    asset=asset_path.read_bytes();b=bytearray(asset);m=table(asset_path);old=bulk_path.read_bytes();new=old;changes=[]
    for index,payload in zip(entries,payloads,strict=True):
        record=m+index*32;oldrec=struct.unpack_from('<qqqIB3x',b,record)
        assert oldrec[1]==-1 and oldrec[3:]==(66817,0)
        offset=(len(new)+15)//16*16;new+=b'\0'*(offset-len(new))+payload
        struct.pack_into('<q',b,record,offset);struct.pack_into('<q',b,record+16,len(payload))
        changes.append(dict(entry=index,old_offset=oldrec[0],old_size=oldrec[2],new_offset=offset,new_size=len(payload)))
    restored=bytearray(b)
    for index in entries:restored[m+index*32:m+(index+1)*32]=asset[m+index*32:m+(index+1)*32]
    assert restored==asset and new[:len(old)]==old
    asset_path.write_bytes(b);bulk_path.write_bytes(new)
    return changes


def validate_bank(bank):
    path=BUILD/'purple-random-bank.bnk';path.write_bytes(bank)
    subprocess.run([sys.executable,str(ROOT/'tools/wwiser/wwiser.py'),'-d','xml','-dn',str(BUILD/'bank-check'),str(path)],check=True,capture_output=True)
    root=ET.parse(BUILD/'bank-check.xml').getroot();assert not list(root.iter('error'))
    objects=root.findall('.//list[@name="listLoadedItem"]/object')
    nodes={int(o.find('field[@name="ulID"]').get('value')):o for o in objects if o.find('field[@name="ulID"]') is not None}
    def values(node,name):return [f.get('value') for f in node.iter('field') if f.get('name')==name]
    random=nodes[CONTAINER]
    assert random.get('name')=='CAkRanSeqCntr'
    assert values(random,'eMode')==['0'] and values(random,'sLoopCount')==['1']
    assert values(random,'wAvoidRepeatCount')==['0']
    assert values(random,'ulNumChilds')==['2'] and values(random,'ulPlayListItem')==['2']
    assert list(map(int,values(random,'ulChildID')))==SOUNDS
    assert list(map(int,values(random,'ulPlayID')))==SOUNDS
    assert values(random,'weight')==['50000','50000']
    assert values(nodes[800828386],'idExt')==[str(CONTAINER)]
    assert values(nodes[EVENT],'ulActionID')==['800828386']
    for sid,mid,cache in zip(SOUNDS,MEDIAS,CACHES,strict=True):
        assert values(nodes[sid],'ulPluginID')==['65537']
        assert values(nodes[sid],'sourceID')==[str(mid)]
        assert values(nodes[sid],'cacheID')==[str(cache)]
        assert values(nodes[sid],'DirectParentID')==[str(CONTAINER)]
    assert 778311897 not in nodes
    return dict(independent_wwiser_parse=True,random_container_id=CONTAINER,equal_weights=[50000,50000],
        mode='independent random, one variant per trigger',repeat_allowed=True,event_id_unchanged=EVENT,
        sound_ids=SOUNDS,media_ids=MEDIAS,cache_ids=CACHES,no_new_wwise_object_ids=True)


def build():
    (RAW/'chunks').mkdir(parents=True,exist_ok=True);(OUT/'Mod').mkdir(parents=True,exist_ok=True)
    provenance=json.loads((SOURCE/'provenance.json').read_text(encoding='utf-8'))
    assert digest(SOURCE/'108729793.wem')==provenance['sha256']=='016c2018a9d6d977ebe573e6974777e8de7437e8a87d4e3bcfe32ec6689821b9'
    assert (SOURCE/'108729793.wem').read_bytes()==(ROOT/'work/audio-correction-v165/vesper-attack-sources/108729793.wem').read_bytes()
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    shutil.copyfile(PRIOR/'manifest.json',RAW/'manifest.json')
    old_bulk=(PRIOR/'chunks'/MONSTER_BULK).read_bytes()
    wems,audio=make_media(old_bulk,PRIOR/'chunks'/MONSTER)
    media_maps=append_bulk(RAW/'chunks'/MONSTER,RAW/'chunks'/MONSTER_BULK,ENTRIES,wems)
    info=json.loads((CURRENT/'pbz-ziguang-bank-location.json').read_text());row,=info['matches']
    lib_bulk=(PRIOR/'chunks'/LIB_BULK).read_bytes();old_bank=lib_bulk[row['offset']:row['offset']+row['size']]
    bank,bank_changes=random_bank(old_bank,[len(w) for w in wems]);bank_check=validate_bank(bank)
    bank_maps=append_bulk(RAW/'chunks'/LIB,RAW/'chunks'/LIB_BULK,[row['entry']],[bank])
    unchanged={};modified={MONSTER,MONSTER_BULK,LIB,LIB_BULK}
    for p in (PRIOR/'chunks').iterdir():
        if p.name not in modified:
            assert digest(p)==digest(RAW/'chunks'/p.name)
            unchanged[p.name]=digest(p)
    assert len(unchanged)==177
    manifest=json.loads((RAW/'manifest.json').read_text());native,=list((RAW/'chunks').glob('*06'))
    ids=set(manifest['chunk_paths'])|{native.name};assert ids=={p.name for p in (RAW/'chunks').iterdir()}
    retoc=ROOT/'tools/retoc/retoc.exe';toc=OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
    subprocess.run([str(retoc),'pack-raw',str(RAW),str(toc)],check=True)
    shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v1.6.4/Mod/zz_PBZ_YellowAlert_P.pak',toc.with_suffix('.pak'))
    subprocess.run([str(retoc),'verify',str(toc)],check=True)
    check=BUILD/('roundtrip-'+uuid.uuid4().hex[:8])
    subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
    assert ids=={p.name for p in (check/'chunks').iterdir()}
    for p in (RAW/'chunks').iterdir():assert digest(p)==digest(check/'chunks'/p.name),p.name
    for cid in [MONSTER,LIB]:
        dest=BUILD/('inspect-'+cid);dest.mkdir(exist_ok=True)
        subprocess.run([str(retoc),'dump-test',str(toc),str(dest),str(int.from_bytes(bytes.fromhex(cid)[:8],'little'))],check=True,capture_output=True)
        extracted,=dest.glob('*.uasset');assert digest(extracted)==digest(RAW/'chunks'/cid)
    proof=dict(version='1.6.5',base='v1.6.4, official v1.1 development line',
        user_confirmation='两段都是, 混合随机使用',source_provenance=provenance,
        no_recording_samples_used=True,audio_variants=audio,bank=bank_check,bank_changed_objects=bank_changes,
        monster_bulk_maps=media_maps,bank_bulk_maps=bank_maps,old_bulk_prefixes_bit_exact=True,
        visual_and_timing_v164_bit_exact=True,unchanged_chunk_sha256=unchanged,container_verify=True,
        raw_roundtrip_exact=True,roundtrip_directory=str(check),native_package_header_parser_checked=True,
        in_game_tested=False,installed=False)
    (BUILD/'validation.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False),encoding='utf-8')
    (OUT/'validation.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False),encoding='utf-8')
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert v1.6.5 开发测试版\n\n'
        '黑光攻击显示紫色45度X形预警，并保留全屏变暗效果。\n'
        '采用绝区零原始紫光提示音；每次预警随机播放原声或经游戏参数处理的版本，各约50%。\n'
        '紫光沿用放大后的尺寸、穿透显示和提前100毫秒设置。红黄光沿用正式版1.1。\n'
        'Preview文件夹可试听两种音效。\n\n'
        '安装：完全退出游戏，将Mod文件夹内三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods，替换旧版同名三个文件，再启动游戏。\n'
        '卸载：退出游戏后移除上述三个文件。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n' for p in sorted((OUT/'Mod').iterdir())),encoding='utf-8')
    print(json.dumps(dict(output=str(OUT),random_bank=bank_check,media=audio,verified=True,in_game_tested=False),ensure_ascii=False),flush=True)


if __name__=='__main__':build()
