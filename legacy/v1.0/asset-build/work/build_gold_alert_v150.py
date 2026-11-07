"""Keep all yellow visual layers at one component-local origin."""
import hashlib,json,pathlib,shutil,struct,subprocess,sys,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from parse_fx import FXParser
from inspect_fx_vm import scripts,attributes,disassemble
from fx_vm_trace import output_expressions
from zen_fx_edit import read_fields,encode_fields,raw_field,rebuild_exports

BUILD=ROOT/'work/gold-alert-v150';RAW=BUILD/'raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.5.0'


def patch(source,destination):
 from build_gold_alert import impacts
 # Scene-linear emissive colours, deliberately above 1 on the thin core layers.
 core=(1.0,0.42,0.006)
 halo=(1.0,0.22,0.002)
 gains={'Empty':0.8,'Empty003':0.65,'Empty005':0.8,'Empty006':1.4,
        'Empty007':8.0,'Empty008':0.8,'Empty010':6.0,'Empty011':10.0,'Empty013':10.0}
 core_names={'Empty007','Empty010','Empty011','Empty013'}
 owners={}
 for parser,ex,e,v,recs in scripts(source):
  if e['name']!='SpawnScript':continue
  params=v['ScriptExecutionParamStore']
  for item in params['SortedParameterOffsets']:
   if '.ScaleColor.' in item['Name']:
    ci=params['DataInterfaces'][item['Offset']]-1
    assert ci not in owners
    owners[ci]=ex[e['outer']]['name']
 q=FXParser(source);data=bytearray(q.b);allowed=set();curve_count=0;literal_count=0
 def write(at,values):
  p=struct.pack('<'+'f'*len(values),*values);data[at:at+len(p)]=p;allowed.update(range(at,at+len(p)))
 for e in q.exports():
  if e['name']!='NiagaraDataInterfaceColorCurve':continue
  q.p=e['start'];q.records=[];v=q.obj(e['name']);lut=v['ShaderLUT']
  row,=[r for r in q.records if r['kind']=='value' and r['type']==('Array',('Float',)) and r['value']==lut]
  name=owners[e['index']];gain=gains[name];colour=core if name in core_names else halo
  for i in range(0,len(lut),4):
   peak=max(lut[i:i+3]);write(row['start']+4+i*4,tuple(peak*gain*c for c in colour))
  curve_count+=1
 for parser,ex,e,v,recs in scripts(source):
  if e['name']!='SpawnScript':continue
  vm=v['CachedScriptVM'];attrs=attributes(vm);rgba=attrs.get('Initial.Color',[])
  if not rgba:continue
  params=v['ScriptExecutionParamStore'];curves=[a for a in params['SortedParameterOffsets'] if '.ScaleColor.' in a['Name']]
  if curves:continue
  code=disassemble(vm);base=code[0]['inputs'][0][1];lits=bytes(vm['ScriptLiterals']);uses=impacts(code)
  refs=[next(ins['inputs'][0] for ins in code if ins['op']=='outputdata_float' and ins['attribute']==ch) for ch in rgba[:3]]
  assert all(t=='c' for t,ref in refs)
  old=tuple(struct.unpack_from('<f',lits,ref-base)[0]for t,ref in refs);peak=max(old)
  if peak==0:continue
  # Only the existing coloured gold layer; leave any neutral/nonvisual layer alone.
  if max(old)-min(old)<1e-6:continue
  row,=[r for r in recs if r['kind']=='value' and r['type']==('Array',('Byte',)) and r['parent']=='NiagaraVMExecutableData' and r['value']==list(lits)]
  permitted={('outputdata_float',i)for n in ('Color','Initial.Color')for i in attrs[n][:3]}
  colour=halo
  for (_,ref),c in zip(refs,colour):
   assert uses[ref] and uses[ref]<=permitted
   write(row['start']+4+ref-base,(peak*c,));literal_count+=1
 assert curve_count>0 and literal_count>0
 diffs={i for i,(a,b)in enumerate(zip(q.b,data))if a!=b}
 hs=struct.unpack_from('<I',q.b,4)[0]
 assert len(data)==len(q.b) and diffs<=allowed and data[:hs]==q.b[:hs]
 destination.write_bytes(data)
 for old,new in zip(scripts(source),scripts(destination),strict=True):
  a,b=old[3],new[3];a['CachedScriptVM'].pop('ScriptLiterals',None);b['CachedScriptVM'].pop('ScriptLiterals',None);assert a==b
 check=FXParser(destination)
 for e in check.exports():
  if e['name']!='NiagaraDataInterfaceColorCurve':continue
  check.p=e['start'];after=check.obj(e['name'])['ShaderLUT']
  q.p=e['start'];before=q.obj(e['name'])['ShaderLUT']
  assert after[3::4]==before[3::4]
  name=owners[e['index']];colour=core if name in core_names else halo
  for i in range(0,len(after),4):
   assert abs(after[i]-before[i]*gains[name])<2e-5
   if after[i]>1e-9:assert all(abs(after[i+j]/after[i]-colour[j])<1e-6 for j in range(3))
 return {'core_linear_rgb':core,'halo_linear_rgb':halo,'curve_owners':owners,'emissive_gain_by_layer':gains,'core_emitters':sorted(core_names),'colour_curves':curve_count,'colour_only_literals':literal_count,'changed_bytes':len(diffs),'only_rgb_bytes_changed':True,'alpha_and_all_bytecode_and_header_bit_exact':True}


def build():
 prior=ROOT/'work/gold-alert-v143/raw';oldout=ROOT/'outputs/PBZ-Gold-Alert-v1.4.3'
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
 for name in ['Install-Update.ps1','Update-Mod.cmd']:(OUT/name).write_bytes((oldout/name).read_bytes().replace(b'v1.4.3',b'v1.5.0'))
 shutil.copytree(oldout/'Preview',OUT/'Preview',dirs_exist_ok=True)
 (OUT/'Source').mkdir(exist_ok=True);shutil.copyfile(__file__,OUT/'Source'/pathlib.Path(__file__).name)
 v={'version':'1.5.0','yellow_gold_colour':results,'audio_and_red_resources_bit_exact_v140':True,
    'position_size_rotation_alpha_and_timing_preserved':True,'container_verify':True,'roundtrip_exact':True,'in_game_tested':False}
 (OUT/'Source/validation.json').write_text(json.dumps(v,indent=2));(BUILD/'validation.json').write_text(json.dumps(v,indent=2))
 (OUT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  Mod/'+p.name+'\n' for p in sorted((OUT/'Mod').iterdir())))
 print(json.dumps({'version':'1.5.0','patched_assets':len(results),'verified':True,'in_game_tested':False}))


if __name__=='__main__':build()
