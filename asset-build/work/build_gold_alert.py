"""Build warm-gold alert v0.2.0, retaining native Zen resource headers/imports.

Only typed colour-curve RGB samples and colour-only VM literals are changed.
No bytecode, VM cache, alpha, material, sound or timing data is rebuilt.
"""
import colorsys,hashlib,json,pathlib,shutil,struct,subprocess,sys,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'))
from inspect_fx_vm import FXParser,TARGETS,scripts,attributes,disassemble

BUILD=ROOT/'work/gold-alert-v020'
RAW=BUILD/'raw'
OUT=ROOT/'outputs/PBZ-Gold-Alert-v0.2.0'
GOLD=(1.0,0.48,0.015)  # Linear RGB; approximately sRGB #FFB820.
GOLD_HUE=colorsys.rgb_to_hsv(*GOLD)[0]

def sha(b):return hashlib.sha256(b).hexdigest()

def impacts(code):
 """Conservatively propagate constant dependencies through VM registers."""
 regs={};uses={}
 for ins in code:
  deps=set()
  for typ,ix in ins['inputs']:deps.update({ix} if typ=='c' else regs.get(ix,set()))
  if ins['op'].startswith('outputdata_'):
   for d in deps:uses.setdefault(d,set()).add((ins['op'],ins['attribute']))
  elif ins['op']=='enter_stat_scope':pass
  else:
   for dest in ins['outputs']:regs[dest]=deps.copy()
 return uses

def patch_asset(path,dest):
 q=FXParser(path);original=q.b;data=bytearray(original);exports=q.exports();allowed=set();curve_owners={};script_changes=[]
 def patch(at,values):
  packed=struct.pack('<'+'f'*len(values),*values);data[at:at+len(packed)]=packed;allowed.update(range(at,at+len(packed)))
 # Trace Initial.Color outputs, rather than guessing which floats are RGB.
 for p,ex,e,v,records in scripts(path):
  if e['name']!='SpawnScript':continue
  vm=v['CachedScriptVM'];attrs=attributes(vm);rgba=attrs.get('Initial.Color',[])
  if not rgba:continue
  code=disassemble(vm);base=code[0]['inputs'][0][1];lits=bytes(vm['ScriptLiterals']);uses=impacts(code)
  refs=[next(i['inputs'][0] for i in code if i['op']=='outputdata_float' and i['attribute']==ch) for ch in rgba[:3]]
  assert all(t=='c' for t,c in refs)
  offsets=[c-base for t,c in refs];rgb=tuple(struct.unpack_from('<f',lits,x)[0] for x in offsets)
  params=v['ScriptExecutionParamStore'];curves=[params['DataInterfaces'][a['Offset']]-1 for a in params['SortedParameterOffsets'] if '.ScaleColor.' in a['Name']]
  for ci in curves:
   assert ex[ci]['name']=='NiagaraDataInterfaceColorCurve'
   assert ci not in curve_owners
   curve_owners[ci]={'initial_rgb':rgb,'emitter':ex[e['outer']]['name']}
  blue=rgb[2]>max(rgb[:2])+1e-6
  if not blue:continue
  # Curved layers use neutral initial RGB, so the LUT alone controls hue.
  # One layer has no colour LUT: give its colour-only literals gold directly.
  peak=max(rgb);new=(peak,)*3 if curves else tuple(peak*c for c in GOLD)
  litrec=[r for r in records if r['kind']=='value' and r['type']==('Array',('Byte',)) and r['parent']=='NiagaraVMExecutableData' and r['value']==vm['ScriptLiterals']]
  assert len(litrec)==1
  literal_start=litrec[0]['start']+4
  assert original[literal_start:literal_start+len(lits)]==lits
  permitted={('outputdata_float',idx) for name in ('Color','Initial.Color') for idx in attrs[name][:3]}
  edited=[]
  for old,newvalue,off,(_,ref) in zip(rgb,new,offsets,refs):
   if struct.pack('<f',old)==struct.pack('<f',newvalue):continue
   assert uses[ref] and uses[ref]<=permitted,('Shared non-colour constant',e['index'],off,uses[ref])
   patch(literal_start+off,(newvalue,));edited.append(off)
  script_changes.append({'emitter':ex[e['outer']]['name'],'spawn_script_export':e['index'],'initial_rgb_before':rgb,'initial_rgb_after':new,'literal_offsets':edited,'all_changed_constants_affect_rgb_only':True,'colour_curve_exports':curves})
 curves=[]
 for e in exports:
  if e['name']!='NiagaraDataInterfaceColorCurve':continue
  q.p=e['start'];q.records=[];obj=q.obj(e['name']);assert q.p==e['start']+e['size']-4
  lut=obj['ShaderLUT'];samples=len(lut)//4;assert samples*4==len(lut)
  owner=curve_owners[e['index']]
  neutral=all(max(lut[i:i+3])-min(lut[i:i+3])<1e-6 for i in range(0,len(lut),4))
  # Neutral curves belong to blue-tinted emitters and need the hue here too.
  if neutral:assert owner['initial_rgb'][2]>max(owner['initial_rgb'][:2])+1e-6
  rows=[r for r in q.records if r['kind']=='value' and r['type']==('Array',('Float',)) and r['value']==lut]
  assert len(rows)==1;start=rows[0]['start']+4
  assert original[start:start+len(lut)*4]==struct.pack('<'+'f'*len(lut),*lut)
  changed=0
  for sample in range(samples):
   rgb=tuple(lut[sample*4:sample*4+3]);assert min(rgb)>=0
   if neutral:new=tuple(max(rgb)*x for x in GOLD)
   else:
    h,s,v=colorsys.rgb_to_hsv(*rgb)
    assert s<1e-5 or 0.45<=h<=0.80,('Unexpected source hue',e['index'],rgb)
    new=colorsys.hsv_to_rgb(GOLD_HUE,s,v)
   at=start+sample*16
   if struct.pack('<fff',*new)!=original[at:at+12]:patch(at,new);changed+=1
   assert data[at+12:at+16]==original[at+12:at+16]
  curves.append({'export_index':e['index'],'emitter':owner['emitter'],'samples':samples,'changed_samples':changed,'formerly_neutral':neutral,'alpha_bit_exact':True})
 hs=struct.unpack_from('<I',original,4)[0];diffs={i for i,(a,b) in enumerate(zip(original,data)) if a!=b}
 assert len(data)==len(original) and data[:hs]==original[:hs] and diffs<=allowed
 dest.write_bytes(data)
 # Reparse every script: every VM property other than these literals is identical.
 for before,after in zip(scripts(path),scripts(dest),strict=True):
  v1=before[3];v2=after[3]
  l1=v1['CachedScriptVM'].pop('ScriptLiterals',None);l2=v2['CachedScriptVM'].pop('ScriptLiterals',None)
  assert v1==v2,'Nonliteral script data changed'
  if l1!=l2:assert before[2]['index'] in {r['spawn_script_export'] for r in script_changes}
 return {'package':str(path.relative_to(ROOT/'analysis/extracted')).replace('\\','/'),'changed_bytes':len(diffs),'original_header_bytes':hs,'native_zen_header_bit_exact':True,'only_rgb_data_changed':True,'all_script_bytecode_and_optimized_caches_bit_exact':True,'original_sha256':sha(original),'gold_sha256':sha(data),'scripts':script_changes,'curves':curves}

def build():
 (RAW/'chunks').mkdir(parents=True,exist_ok=True);(OUT/'Mod').mkdir(parents=True,exist_ok=True)
 oldraw=ROOT/'work/yellow-alert-v011/raw';manifest=json.loads((oldraw/'manifest.json').read_text(encoding='utf8'))
 (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
 header=next((oldraw/'chunks').glob('*06'));shutil.copyfile(header,RAW/'chunks'/header.name)
 results=[]
 for cid,rel in manifest['chunk_paths'].items():
  if not rel.endswith('.uasset'):continue
  archive=rel.removeprefix('../../../');assert archive.removesuffix('.uasset') in TARGETS
  results.append(patch_asset(ROOT/'analysis/extracted'/archive,RAW/'chunks'/cid))
 assert len(results)==3
 retoc=ROOT/'tools/retoc/retoc.exe';toc=OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
 subprocess.run([str(retoc),'pack-raw',str(RAW),str(toc)],check=True)
 shutil.copyfile(ROOT/'outputs/PBZ-Yellow-Alert-v0.1.1/Mod/zz_PBZ_YellowAlert_P.pak',OUT/'Mod/zz_PBZ_YellowAlert_P.pak')
 subprocess.run([str(retoc),'verify',str(toc)],check=True)
 check=BUILD/('roundtrip-'+uuid.uuid4().hex[:8]);subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
 for p in (RAW/'chunks').iterdir():assert p.read_bytes()==(check/'chunks'/p.name).read_bytes()
 result={'name':'PBZ Gold Attack Alert','version':'0.2.0','linear_gold':GOLD,'reference_srgb':'#FFB820','game_build':'26266538','in_game_tested':False,'container_hash_verify':True,'raw_chunk_roundtrip_bit_exact':True,'dependency_header_bit_exact_with_v011':header.read_bytes()==(RAW/'chunks'/header.name).read_bytes(),'assets':results}
 (BUILD/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps({'version':'0.2.0','assets':len(results),'blue_initial_layers_fixed':sum(len(r['scripts']) for r in results),'lut_samples_changed':sum(c['changed_samples'] for r in results for c in r['curves']),'changed_bytes':sum(r['changed_bytes'] for r in results),'verified':True}))

if __name__=='__main__':build()
