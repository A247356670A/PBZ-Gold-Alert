"""Gold cross 2.5x + local ZZZ incoming-attack cue, PCM streamed media."""
import pathlib,sys,struct,json,shutil,subprocess,uuid,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from parse_fx import FXParser
from zen_fx_edit import read_fields,encode_fields,raw_field
from build_yellow_alert_v011 import store_table
from read_pbz import Reader
BUILD=ROOT/'work/gold-alert-v100';RAW=BUILD/'raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.0.0'
def cross(src,dst):
 q=FXParser(src);b=bytearray(q.b);count=0
 for e in q.exports():
  typ='NiagaraEmitter' if e['name'].startswith('Empty') else 'NiagaraSystem' if e['name'].startswith('NS_') else None
  if not typ:continue
  q.p=e['start'];q.records=[];q.obj(typ)
  for rec in q.records:
   if rec['kind']!='struct' or rec['type'] not in ('NiagaraParameterStore','NiagaraUserRedirectionParameterStore'):continue
   val=rec['value'];params=val.get('SortedParameterOffsets') or []
   if not any('PBZ_X_' in v['Name'] for v in params):continue
   rows=[r for r in q.records if r['kind']=='value' and r['type']==('Array',('Byte',)) and r['start']>=rec['start'] and r['end']<=rec['end'] and r['value']==val['ParameterData']];assert len(rows)==1
   for p in params:
    if 'PBZ_X_' not in p['Name']:continue
    value=90.0 if p['Name'].endswith('Neg') else 0.0;struct.pack_into('<f',b,rows[0]['start']+4+p['Offset'],value);count+=1
 assert count==24;dst.write_bytes(b);return count
def audio_asset(reader):
 rel='ProjectPBZ/Content/Wwise/Events/SFX/Combat/VFX/Monster_VFX/Bell/SFX_Combat_VFX_Monster_YuDi_Blue.uasset'
 idx=reader.by_path[rel]['index'];cid=reader.toc[144+idx*12:144+(idx+1)*12].hex();orig=reader.read(idx)
 temp=BUILD/'audio-original.uasset';temp.write_bytes(orig);q=FXParser(temp);e=q.exports()[0]
 q.p=e['start'];q.obj('AkAudioEvent');assert q.take('I')==0;q.records=[];q.obj('WwiseLocalizedEventCookedData');end=q.p
 changes=[]
 for rec in q.records:
  if rec['kind']=='struct' and rec['type']=='WwisePackagedFile' and rec['value'].get('Hash') in (1697160190,4265238988,339271491):
   q.p=rec['start'];fields=read_fields(q,'WwisePackagedFile');fields[0]=raw_field(b'\x03');new=encode_fields(fields);changes.append((rec['start'],rec['end'],new))
 assert len(changes)==3
 metadata=orig[e['start']:end]
 for a,z,new in sorted(changes,reverse=True):metadata=metadata[:a-e['start']]+new+metadata[z-e['start']:]
 wem=(ROOT/'work/audio-v1/zzz-warning-pcm.wem').read_bytes();assert wem[:4]==b'RIFF' and len(wem)>57696
 parts=[wem[:57696],wem[57696:]]*3
 # Native Zen bulk table entries point to force-inline PCM prefixes/remainders.
 oldhs=struct.unpack_from('<I',orig,4)[0];imp=struct.unpack_from('<I',orig,24)[0];assert struct.unpack_from('<Q',orig,imp-8)[0]==0
 delta=32*len(parts);hs=oldhs+delta;bulk=bytearray();resources=[]
 for i,part in enumerate(parts):
  at=hs+len(metadata)+len(bulk)+4;resources.append(struct.pack('<qqqIB3x',at,-1,len(part),0x40,0));bulk.extend(struct.pack('<i',i));bulk.extend(part)
 body=metadata+bulk+orig[end:e['start']+e['size']]
 header=bytearray(orig[:imp-8]+struct.pack('<Q',delta)+b''.join(resources)+orig[imp:oldhs])
 for off in (4,24,28,32,36,40,44,48,52,56):struct.pack_into('<I',header,off,struct.unpack_from('<I',orig,off)[0]+delta)
 em=struct.unpack_from('<I',header,32)[0];struct.pack_into('<QQ',header,em,0,len(body));data=bytes(header)+body
 (RAW/'chunks'/cid).write_bytes(data)
 # Independent metadata parse and six complete bulk-payload checks.
 check=FXParser(RAW/'chunks'/cid);check.obj('AkAudioEvent');check.take('I');v=check.obj('WwiseLocalizedEventCookedData');p=check.p
 for i,part in enumerate(parts):assert struct.unpack_from('<i',data,p)[0]==i;p+=4;assert data[p:p+len(part)]==part;p+=len(part)
 assert p+16==len(data)
 media=v['EventLanguageMap'][0]['value']['Media'];assert len(media)==3 and all(m['PackagedFile']['PackagingStrategy']==3 for m in media)
 return cid,rel,int.from_bytes(bytes.fromhex(cid)[:8],'little')
def extend_container(b,pid):
 stores,base,size,pids=store_table(b);assert pid not in pids;pids.append(pid);stores[pid]=(b'',b'')
 entries=bytearray(len(pids)*16);tail=bytearray()
 for i,p in enumerate(pids):
  packages,shaders=stores[p]
  for k,item,stride in ((0,packages,8),(8,shaders,20)):
   if item:struct.pack_into('<II',entries,i*16+k,len(item)//stride,len(entries)+len(tail)-(i*16+k));tail.extend(item)
 buf=entries+tail;new=bytearray(b[:16]+struct.pack('<I',len(pids))+struct.pack('<'+'Q'*len(pids),*pids)+struct.pack('<I',len(buf))+buf+b[base+size:]);struct.pack_into('<q',new,len(new)-20,len(new)-4)
 out,_,_,_=store_table(new);assert out==stores;return new
def build():
 (RAW/'chunks').mkdir(parents=True,exist_ok=True);(OUT/'Mod').mkdir(parents=True,exist_ok=True)
 old=ROOT/'work/gold-alert-v040/raw';manifest=json.loads((old/'manifest.json').read_text(encoding='utf8'));counts=[]
 for cid,rel in manifest['chunk_paths'].items():
  if rel.endswith('.uasset'):counts.append(cross(old/'chunks'/cid,RAW/'chunks'/cid))
 r=Reader();cid,rel,pid=audio_asset(r);manifest['chunk_paths'][cid]='../../../'+rel
 header=next((old/'chunks').glob('*06'));(RAW/'chunks'/header.name).write_bytes(extend_container(header.read_bytes(),pid));(RAW/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
 retoc=ROOT/'tools/retoc/retoc.exe';toc=OUT/'Mod/zz_PBZ_YellowAlert_P.utoc';subprocess.run([str(retoc),'pack-raw',str(RAW),str(toc)],check=True);subprocess.run([str(retoc),'verify',str(toc)],check=True)
 shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v0.4.0/Mod/zz_PBZ_YellowAlert_P.pak',OUT/'Mod/zz_PBZ_YellowAlert_P.pak')
 check=BUILD/('roundtrip-'+uuid.uuid4().hex[:8]);subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
 for p in (RAW/'chunks').iterdir():assert p.read_bytes()==(check/'chunks'/p.name).read_bytes()
 v={'version':'1.0.0','cross_angles':[0,90],'size_vs_original':2.5,'colour_unchanged':True,'audio_source':'Local ZZZ SoundBank_SFX_15.pck / bank 4245690530 / media 411682766','codec':'PCM16 mono 44100Hz, matching PBZ PCM sound sources','media_variants_replaced':3,'native_inline_prefetch_and_remaining_bulk_entries':6,'container_verify':True,'raw_roundtrip':True,'in_game_tested':False};(BUILD/'validation.json').write_text(json.dumps(v,indent=2),encoding='utf8');print(json.dumps(v))
if __name__=='__main__':build()
