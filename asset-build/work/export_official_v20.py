"""Official V2.0 resource split and small, locally reconstructed installer."""
from pathlib import Path
import hashlib,json,shutil,struct,subprocess,sys,zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'work'),str(ROOT/'analysis')]
from build_yellow_alert_v011 import store_table
from build_gold_alert_v169 import package_header
from read_pbz import Reader
B=ROOT/'work/official-v20'; R=ROOT/'official release'
RAW=ROOT/'work/gold-alert-v205/combined/raw'
DEV=ROOT/'outputs/PBZ-Gold-Alert-v2.0.5/Mod'
FULL=R/'PBZ-Gold-Alert-Official-V2.0-Fullpack'
INS=R/'PBZ-Gold-Alert-Official-V2.0-Installer'
RETOC=ROOT/'tools/retoc/retoc.exe'
BASE='d5c3764cdae2030361a7fa8ed1eb204787c77e767df92bbe947763b4a2d0186b'
GAUNTLET=set('b1bf5d2781c0dfbe00000001 aa16994f9470996900000001 4d769fbfd082059000000001 36b4cc2e90255bcb00000001 3dde1ed4bacb125700000001 10adee5eddeb4e3700000001 0f7ebdf755a4845700000001 f91ab85adf8cd12300000001 8302abf6e08ae99400000001'.split())
AUDIO=set('e769c85cabe3aa8400000001 e769c85cabe3aa8400000002 5aac5b9f482230fd00000001 5aac5b9f482230fd00000002 ff58522d74ff149400000001 ff58522d74ff149400000002'.split())
STEMS={g:'zz_PBZ_V20_'+g+'_P' for g in ['SharedAudio','AttackAlerts','Gauntlet']}
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def js(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def run(args,log):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True,encoding='utf8',errors='replace')
    (B/log).write_text(p.stdout+p.stderr,encoding='utf8')
    if p.returncode:raise RuntimeError(str(B/log))
def split():
    B.mkdir(parents=True,exist_ok=True)
    assert not FULL.exists() and not INS.exists(),'Release already staged; do not overwrite blindly'
    (FULL/'Mod').mkdir(parents=True);INS.mkdir()
    m=json.loads((RAW/'manifest.json').read_text());cp=m['chunk_paths']
    assert len(cp)==193 and GAUNTLET|AUDIO<=cp.keys() and not GAUNTLET&AUDIO
    groups={'SharedAudio':AUDIO,'Gauntlet':GAUNTLET,'AttackAlerts':set(cp)-AUDIO-GAUNTLET}
    hp,=list((RAW/'chunks').glob('*06'));template=hp.read_bytes();stores,_,_,order=store_table(template)
    proof={};all_ids=set()
    for group,cids in groups.items():
        print('Packing '+group,flush=True)
        raw=B/group/'raw';(raw/'chunks').mkdir(parents=True)
        for cid in sorted(cids):shutil.copyfile(RAW/'chunks'/cid,raw/'chunks'/cid)
        js(raw/'manifest.json',dict(m,chunk_paths={k:cp[k] for k in sorted(cids)}))
        toc=FULL/'Mod'/(STEMS[group]+'.utoc')
        run([RETOC,'pack-raw',raw,toc],group+'-bootstrap.log');identity=toc.read_bytes()[56:64]
        pids={int.from_bytes(bytes.fromhex(x)[:8],'little') for x in cids if x.endswith('01')}
        header=package_header(template,[p for p in order if p in pids],stores,identity)
        hc=(identity+bytes(3)+b'\x06').hex();(raw/'chunks'/hc).write_bytes(header)
        run([RETOC,'pack-raw',raw,toc],group+'-pack.log')
        pak=DEV/'zz_PBZ_YellowAlert_P.pak' if group=='Gauntlet' else ROOT/'outputs/PBZ-Gold-Alert-v1.6.9/Mod/zz_PBZ_YellowAlert_P.pak'
        shutil.copyfile(pak,toc.with_suffix('.pak'))
        run([RETOC,'verify',toc],group+'-verify.log')
        dest=B/group/'roundtrip';run([RETOC,'unpack-raw',toc,dest],group+'-roundtrip.log')
        expected={p.name:sha(p) for p in (raw/'chunks').iterdir()}
        actual={p.name:sha(p) for p in (dest/'chunks').iterdir()}
        assert expected==actual
        assert not all_ids&expected.keys();all_ids.update(expected)
        for cid in cids:assert expected[cid]==sha(RAW/'chunks'/cid)
        assert header[8:16]==toc.read_bytes()[56:64]
        proof[group]={'chunks':len(expected),'native_roundtrip_exact':True,'chunk_sha256':expected}
    assert set.union(*groups.values())==set(cp)
    js(B/'components-validation.json',dict(source_development='2.0.5',data_chunks=193,all_payloads_bit_exact=True,overlapping_chunk_ids=[],components=proof))
    print('All 193 source payload chunks preserved; components disjoint.',flush=True)

def physical(toc,cid):
    t=toc.read_bytes();n=struct.unpack_from('<I',t,24)[0];bs=struct.unpack_from('<I',t,44)[0]
    i=next(i for i in range(n) if t[144+i*12:156+i*12].hex()==cid)
    e=144+n*12+i*10;off=int.from_bytes(t[e:e+5],'big');size=int.from_bytes(t[e+5:e+10],'big')
    table=144+n*22+struct.unpack_from('<I',t,84)[0]*4+struct.unpack_from('<I',t,96)[0]*4
    first=None;end=None
    for bi in range(off//bs,(off+size+bs-1)//bs):
        p=table+bi*12;d=int.from_bytes(t[p:p+5],'little');cs=int.from_bytes(t[p+5:p+8],'little');us=int.from_bytes(t[p+8:p+11],'little')
        assert t[p+11]==0 and cs==us
        start=max(off,bi*bs);stop=min(off+size,bi*bs+us)
        disk=d+start-bi*bs
        if first is None:first=disk
        if end is not None:assert disk==end
        end=d+stop-bi*bs
    assert end-first==size
    return first,size

def recipe():
    r=Reader();assert sha(Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'))==BASE
    idx={r.toc[144+i*12:156+i*12].hex():i for i in range(r.n)}
    toc=FULL/'Mod'/(STEMS['SharedAudio']+'.utoc');ucas=toc.with_suffix('.ucas')
    ranges=sorted((physical(toc,cid)[0],cid,physical(toc,cid)[1]) for cid in AUDIO if cid.endswith('02'))
    parts=[];stats=[]
    with (INS/'payload.bin').open('wb') as payload,ucas.open('rb') as packed:
        def literal(data):
            p=payload.tell();payload.write(data);return {'payload_offset':p,'bytes':len(data)}
        cursor=0
        for pos,cid,size in ranges:
            if pos>cursor:
                packed.seek(cursor);parts.append(dict(kind='literal',**literal(packed.read(pos-cursor))))
            base_size=r.info(idx[cid])[1];assert size>=base_size
            source=RAW/'chunks'/cid;assert source.stat().st_size==size
            patches=[];changed=0
            with source.open('rb') as target:
                # Compare one MiB at a time; merge nearby edits, preserving all bytes.
                for start in range(0,base_size,1024*1024):
                    length=min(1024*1024,base_size-start)
                    a=r.read(idx[cid],start,length);b=target.read(length)
                    dif=np.flatnonzero(np.frombuffer(a,dtype=np.uint8)!=np.frombuffer(b,dtype=np.uint8))
                    if len(dif):
                        changed+=len(dif);cuts=np.flatnonzero(np.diff(dif)>256)
                        starts=np.r_[dif[0],dif[cuts+1]];ends=np.r_[dif[cuts]+1,dif[-1]+1]
                        for lo,hi in zip(starts,ends):patches.append(dict(offset=start+int(lo),**literal(b[int(lo):int(hi)])))
                tail=literal(target.read())
            parts.append(dict(kind='base',cid=cid,base_bytes=base_size,target_bytes=size,tail=tail,patches=patches))
            stats.append(dict(cid=cid,original_bytes=base_size,target_bytes=size,changed_bytes=changed,patch_spans=len(patches),tail_bytes=tail['bytes']))
            cursor=pos+size
            print('Audio delta '+cid+': '+str(changed)+' changed bytes, '+str(tail['bytes'])+' appended.',flush=True)
        if cursor<ucas.stat().st_size:
            packed.seek(cursor);parts.append(dict(kind='literal',**literal(packed.read())))
    for p in (FULL/'Mod').iterdir():
        if p==ucas:continue
        shutil.copyfile(p,INS/p.name)
    shutil.copyfile(ROOT/'tools/oo2core_9_win64.dll',INS/'oo2core_9_win64.dll')
    shutil.copyfile(ROOT/'analysis/aes-key.txt',INS/'key.txt')
    files={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted((FULL/'Mod').iterdir())}
    js(INS/'recipe.json',dict(version='2.0',source_development='2.0.5',base_toc_sha256=BASE,stems=STEMS,files=files,reconstructed_file=ucas.name,parts=parts))
    js(B/'delta-validation.json',dict(parts=len(parts),audio=stats,payload_bytes=(INS/'payload.bin').stat().st_size))
    print('Installer raw payload bytes: '+str((INS/'payload.bin').stat().st_size),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='split':split()
    elif sys.argv[1]=='recipe':recipe()
