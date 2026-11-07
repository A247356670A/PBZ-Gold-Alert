"""Build the yellow patch without converting original Zen headers or material imports."""
import hashlib,json,pathlib,struct,sys,shutil,subprocess,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'))
from read_pbz import Reader

BUILD=ROOT/'work'/'yellow-alert-v011'
OUT=ROOT/'outputs'/'PBZ-Yellow-Alert-v0.1.1'
RAW=BUILD/'raw'
def sha(b):return hashlib.sha256(b).hexdigest()
def store_table(b):
 assert b[:4]==b'nCoI' and struct.unpack_from('<I',b,4)[0]==5
 n=struct.unpack_from('<I',b,16)[0]
 ids=struct.unpack_from('<'+'Q'*n,b,20)
 size=struct.unpack_from('<I',b,20+n*8)[0];base=24+n*8
 result={}
 for i,pid in enumerate(ids):
  p=base+i*16;pn,po,sn,so=struct.unpack_from('<IIII',b,p)
  result[pid]=(b[p+po:p+po+pn*8] if pn else b'',b[p+8+so:p+8+so+sn*20] if sn else b'')
 return result,base,size,list(ids)

def build():
 (RAW/'chunks').mkdir(parents=True,exist_ok=True);(OUT/'Mod').mkdir(parents=True,exist_ok=True)
 r=Reader()
 oldmanifest=json.loads((ROOT/'work/yellow-alert-v1/build-manifest.json').read_text(encoding='utf8'))
 rawmanifest=json.loads((ROOT/'work/yellow-alert-v1/raw-v010/manifest.json').read_text(encoding='utf8'))
 headeridx=next(i for i in range(r.n) if r.toc[144+i*12+11]==6)
 original_store=r.read(headeridx);stores,_,_,_=store_table(original_store)
 oldheaderpath=next((ROOT/'work/yellow-alert-v1/raw-v010/chunks').glob('*06'))
 oldheader=oldheaderpath.read_bytes();oldstores,base,oldsize,pids=store_table(oldheader)
 entries=bytearray(len(pids)*16);tail=bytearray();validation=[]
 for i,pid in enumerate(pids):
  packages,shaders=stores[pid]
  if packages:
   relative=len(entries)+len(tail)-i*16
   struct.pack_into('<II',entries,i*16,len(packages)//8,relative);tail.extend(packages)
  if shaders:
   relative=len(entries)+len(tail)-(i*16+8)
   struct.pack_into('<II',entries,i*16+8,len(shaders)//20,relative);tail.extend(shaders)
 newbuffer=entries+tail
 header=bytearray(oldheader[:base-4]+struct.pack('<I',len(newbuffer))+newbuffer+oldheader[base+oldsize:])
 # UE's v5 container header stores an absolute soft-reference section offset.
 # The empty section is a serialized uint32 bool. Relocate its serial-info too.
 soft_offset,soft_size=struct.unpack_from('<qq',oldheader,len(oldheader)-20)
 assert soft_offset==len(oldheader)-4 and soft_size==4
 assert oldheader[-4:]==b'\0'*4
 struct.pack_into('<q',header,len(header)-20,len(header)-4)
 assert struct.unpack_from('<qq',header,len(header)-20)==(len(header)-4,4)
 check,_,_,_=store_table(header)
 for pid in pids:assert check[pid]==stores[pid]
 (RAW/'chunks'/oldheaderpath.name).write_bytes(header)
 for a in oldmanifest['assets']:
  rel=a['package'];original=(ROOT/'analysis/extracted'/(rel+'.uasset')).read_bytes()
  hs=struct.unpack_from('<I',original,4)[0]
  modified=(ROOT/'work/yellow-alert-v1/legacy'/(rel+'.uexp')).read_bytes()
  assert len(original)-hs==len(modified)
  data=original[:hs]+modified
  i=r.by_path[rel+'.uasset']['index'];cid=r.toc[144+i*12:144+(i+1)*12];pid=int.from_bytes(cid[:8],'little')
  assert pid in pids
  (RAW/'chunks'/cid.hex()).write_bytes(data)
  prior=(ROOT/'work/yellow-alert-v1/raw-v010/chunks'/cid.hex()).read_bytes()
  validation.append({'package':rel,'original_resource_header_preserved_exactly':data[:hs]==original[:hs],
   'original_header_bytes':hs,'v010_header_bytes':struct.unpack_from('<I',prior,4)[0],
   'original_dependency_count':len(stores[pid][0])//8,'v010_dependency_count':len(oldstores[pid][0])//8,
   'v011_dependency_ids_exact_match':True,'original_shader_dependencies_preserved':True,
   'patched_zen_sha256':sha(data),'yellow_export_sha256':sha(modified)})
 (RAW/'manifest.json').write_text(json.dumps(rawmanifest,indent=2),encoding='utf8')
 retoc=ROOT/'tools/retoc/retoc.exe'
 outtoc=OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
 subprocess.run([str(retoc),'pack-raw',str(RAW),str(outtoc)],check=True)
 shutil.copyfile(ROOT/'outputs/PBZ-Yellow-Alert-v0.1.0/Mod/zz_PBZ_YellowAlert_P.pak',OUT/'Mod/zz_PBZ_YellowAlert_P.pak')
 subprocess.run([str(retoc),'verify',str(outtoc)],check=True)
 repack=BUILD/('repacked-check-'+uuid.uuid4().hex[:8])
 subprocess.run([str(retoc),'unpack-raw',str(outtoc),str(repack)],check=True)
 for p in (RAW/'chunks').iterdir():assert p.read_bytes()==(repack/'chunks'/p.name).read_bytes()
 result={'version':'0.1.1','fix':'Preserve original Zen resource headers and exact original material dependency IDs; patch RGB payload only',
  'in_game_tested':False,'container_verify':True,'raw_chunk_roundtrip_exact_match':True,'container_soft_reference_offset_valid':True,'assets':validation}
 (BUILD/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps(result,indent=2))

if __name__=='__main__':build()
