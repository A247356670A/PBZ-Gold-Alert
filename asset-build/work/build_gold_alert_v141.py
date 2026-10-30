"""Keep all yellow visual layers at one component-local origin."""
import hashlib,json,pathlib,shutil,struct,subprocess,sys,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from parse_fx import FXParser
from inspect_fx_vm import scripts,attributes,disassemble
from fx_vm_trace import output_expressions
from zen_fx_edit import read_fields,encode_fields,raw_field,rebuild_exports

BUILD=ROOT/'work/gold-alert-v141';RAW=BUILD/'raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.4.1'


def patch(source,destination):
 q=FXParser(source);ex=q.exports();replacements={};local_changes=[];vm_changes=[]
 visuals={e['outer'] for e in ex if e['name']=='NiagaraSpriteRendererProperties'}
 assert len(visuals)==10
 for i in visuals:
  e=ex[i];q.p=e['start'];q.records=[];props=q.obj('NiagaraEmitter')
  if props['VersionData'][0].get('bLocalSpace'):continue
  rec,=[r for r in q.records if r['kind']=='struct' and r['type']=='VersionedNiagaraEmitterData']
  q.p=rec['start'];fields=read_fields(q,rec['type'])
  k,=[k for k,f in fields.items() if f['name']=='bLocalSpace'];fields[k]=raw_field(b'\x01')
  replacements[i]=q.b[e['start']:rec['start']]+encode_fields(fields)+q.b[rec['end']:e['start']+e['size']]
  local_changes.append(e['name'])
 assert set(local_changes)=={'Empty011','Empty012','Empty013'}
 for parser,exports,e,v,recs in scripts(source):
  if e['outer'] not in visuals:continue
  vm=v['CachedScriptVM'];code=disassemble(vm);base=code[0]['inputs'][0][1];lits=bytes(vm['ScriptLiterals'])
  zero=next(base+j for j in range(0,len(lits),4) if lits[j:j+4]==b'\0'*4)
  names=attributes(vm);pos={i for n,ids in names.items() if n in ('Position','Previous.Position') for i in ids}
  bc=bytes(vm['ByteCode']['Data']);changed=bytearray(bc);count=0
  for ins in code:
   if ins['op']!='outputdata_float' or ins['attribute'] not in pos:continue
   assert ins['dataset']==0
   changed[ins['at']+1]=1;struct.pack_into('<H',changed,ins['at']+6,zero);count+=1
  assert count==6
  row,=[r for r in recs if r['kind']=='value' and r['type']==('Array',('Byte',)) and r['value']==list(bc)]
  body=bytearray(q.b[e['start']:e['start']+e['size']]);offset=row['start']+4-e['start'];body[offset:offset+len(changed)]=changed
  assert e['index'] not in replacements;replacements[e['index']]=bytes(body)
  # Independent symbolic traces: every non-position output is unchanged.
  before=output_expressions(code);after=output_expressions(disassemble(dict(vm,ByteCode={'Data':list(changed)})))
  for key,value in before.items():
   if key[0]=='outputdata_float' and key[2] in pos:assert after[key]==('c',zero)
   else:assert after[key]==value
  vm_changes.append({'emitter':exports[e['outer']]['name'],'script':e['name'],'position_outputs':count})
 hs=struct.unpack_from('<I',q.b,4)[0]
 data=rebuild_exports(q,bytearray(q.b[:hs]),0,replacements);destination.write_bytes(data)
 check=FXParser(destination);cex=check.exports()
 for i in visuals:
  check.p=cex[i]['start'];assert check.obj('NiagaraEmitter')['VersionData'][0]['bLocalSpace']==1
 for a,b in zip(ex,cex,strict=True):
  if a['index'] not in replacements:assert q.b[a['start']:a['start']+a['size']]==data[b['start']:b['start']+b['size']]
 for old,new in zip(scripts(source),scripts(destination),strict=True):
  if old[2]['outer'] not in visuals:assert old[3]==new[3];continue
  a,b=old[3],new[3];a['CachedScriptVM'].pop('ByteCode');b['CachedScriptVM'].pop('ByteCode');assert a==b
 assert len(vm_changes)==20
 return {'local_space_changes':local_changes,'visual_emitters_at_local_origin':10,'scripts':vm_changes,
         'all_non_position_vm_outputs_unchanged':True,'unmodified_exports_bit_exact':True,
         'native_imports_dependencies_preserved':True}


def build():
 prior=ROOT/'work/gold-alert-v140/raw';oldout=ROOT/'outputs/PBZ-Gold-Alert-v1.4.0'
 (RAW/'chunks').mkdir(parents=True,exist_ok=True);(OUT/'Mod').mkdir(parents=True,exist_ok=True)
 manifest=json.loads((prior/'manifest.json').read_text());results={}
 for p in (prior/'chunks').iterdir():
  path=manifest['chunk_paths'].get(p.name,'')
  if 'Plugins/PBZVFXPack' in path and 'Blue' in path:results[path]=patch(p,RAW/'chunks'/p.name)
  else:shutil.copyfile(p,RAW/'chunks'/p.name)
 assert len(results)==3
 (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2))
 retoc=ROOT/'tools/retoc/retoc.exe';toc=OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
 subprocess.run([str(retoc),'pack-raw',str(RAW),str(toc)],check=True)
 shutil.copyfile(oldout/'Mod/zz_PBZ_YellowAlert_P.pak',toc.with_suffix('.pak'))
 subprocess.run([str(retoc),'verify',str(toc)],check=True)
 check=BUILD/('roundtrip-'+uuid.uuid4().hex[:8]);subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
 for p in (RAW/'chunks').iterdir():assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((check/'chunks'/p.name).read_bytes()).digest()
 for name in ['Install-Update.ps1','Update-Mod.cmd']:(OUT/name).write_bytes((oldout/name).read_bytes().replace(b'v1.4.0',b'v1.4.1'))
 shutil.copytree(oldout/'Preview',OUT/'Preview',dirs_exist_ok=True)
 (OUT/'Source').mkdir(exist_ok=True);shutil.copyfile(__file__,OUT/'Source'/pathlib.Path(__file__).name)
 v={'version':'1.4.1','yellow_center_unified':results,'audio_and_red_resources_bit_exact_v140':True,
    'colour_size_rotation_and_timing_preserved':True,'container_verify':True,'roundtrip_exact':True,'in_game_tested':False}
 (OUT/'Source/validation.json').write_text(json.dumps(v,indent=2));(BUILD/'validation.json').write_text(json.dumps(v,indent=2))
 (OUT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  Mod/'+p.name+'\n' for p in sorted((OUT/'Mod').iterdir())))
 print(json.dumps({'version':'1.4.1','patched_assets':len(results),'verified':True,'in_game_tested':False}))


if __name__=='__main__':build()
