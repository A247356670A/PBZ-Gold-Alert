"""Uniform gold throughout the alert, with every sprite dimension scaled 1.5x."""
import hashlib,itertools,json,pathlib,shutil,struct,subprocess,sys,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from inspect_fx_vm import FXParser,TARGETS,scripts,attributes,disassemble
from fx_vm_trace import output_expressions,constants
from build_gold_alert import GOLD,impacts

BUILD=ROOT/'work/gold-alert-v030';RAW=BUILD/'raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v0.3.0'
SCALE=1.5

def sha(data):return hashlib.sha256(data).hexdigest()

def scaling_degree(expr,changed,inputs):
 """Prove each size expression scales exactly once, for arbitrary engine inputs."""
 op=expr[0]
 if op=='c':return int(expr[1] in changed)
 if op=='input':return int((expr[1],expr[2]) in inputs)
 if op in ('undefined','exec_index'):return 0
 if op=='external':
  assert all(scaling_degree(e,changed,inputs)==0 for e in expr[3]);return 0
 children=[scaling_degree(e,changed,inputs) for e in expr[1:] if isinstance(e,tuple)]
 if not any(children):return 0
 if op=='mul':return sum(children)
 if op=='div':return children[0]-children[1]
 if op in ('add','sub','min','max'):
  assert children[0]==children[1],expr;return children[0]
 if op=='lerp':
  assert children[0]==children[1] and children[2]==0,expr;return children[0]
 if op=='mad':
  assert children[0]+children[1]==children[2],expr;return children[2]
 raise AssertionError(('Cannot prove size scaling',expr))

def patch_asset(source,dest,rel):
 q=FXParser(source);original=q.b;data=bytearray(original);allowed=set();curve_changes=[];layer_changes=[];size_proofs=[];intensity_changes=[]
 def patch(at,values):
  packed=struct.pack('<'+'f'*len(values),*values);data[at:at+len(packed)]=packed;allowed.update(range(at,at+len(packed)))
 for e in q.exports():
  if e['name']!='NiagaraDataInterfaceColorCurve':continue
  q.p=e['start'];q.records=[];obj=q.obj(e['name']);lut=obj['ShaderLUT'];assert len(lut)%4==0
  recs=[r for r in q.records if r['kind']=='value' and r['type']==('Array',('Float',)) and r['value']==lut]
  assert len(recs)==1;start=recs[0]['start']+4;changed=0
  for i in range(0,len(lut),4):
   rgb=lut[i:i+3];peak=max(rgb);assert min(rgb)>=0
   new=tuple(peak*c for c in GOLD);at=start+i*4
   if struct.pack('<fff',*new)!=original[at:at+12]:patch(at,new);changed+=1
   assert data[at+12:at+16]==original[at+12:at+16]
  curve_changes.append({'export':e['index'],'samples':len(lut)//4,'changed_samples':changed,'uniform_linear_rgb_ratio':GOLD,'all_alpha_bit_exact':True})
 for p,ex,e,v,recs in scripts(source):
  vm=v['CachedScriptVM'];attrs=attributes(vm);sizeattrs={i for name,ids in attrs.items() if name.endswith('SpriteSize') for i in ids}
  if not sizeattrs:continue
  code=disassemble(vm);expressions=output_expressions(code);base=code[0]['inputs'][0][1];lits=bytes(vm.get('ScriptLiterals') or []);uses=impacts(code)
  floatrows=[r for r in recs if r['kind']=='value' and r['type']==('Array',('Byte',)) and r['parent']=='NiagaraVMExecutableData' and r['value']==list(lits)]
  assert len(floatrows)==1;literal_start=floatrows[0]['start']+4
  assert original[literal_start:literal_start+len(lits)]==lits
  changed_sizes=set();edited=[]
  if e['name']=='SpawnScript':
   permitted={('outputdata_float',i) for i in sizeattrs}
   # Some spawn scripts use a separate first-frame width (for example 7500)
   # and lifetime base width (2500). Cover every size output exactly once.
   candidates=[ref for ref,outputs in uses.items() if outputs and outputs<=permitted and 0<=ref-base<=len(lits)-4 and struct.unpack_from('<f',lits,ref-base)[0]>0]
   assert len(candidates)<=12,('Unexpected dimension candidates',candidates)
   selected=None
   for count in range(1,len(candidates)+1):
    for choice in itertools.combinations(candidates,count):
     try:valid=all(scaling_degree(expressions['outputdata_float',0,ch],set(choice),set())==1 for ch in sizeattrs)
     except AssertionError:valid=False
     if valid:selected=choice;break
    if selected is not None:break
   assert selected is not None,('No exact uniform size scaling found',e['index'],candidates)
   for ref in selected:
    assert uses[ref] and uses[ref]<=permitted,('Shared dimension',e['index'],ref,uses[ref])
    old=struct.unpack_from('<f',lits,ref-base)[0];assert old>0
    patch(literal_start+ref-base,(old*SCALE,));changed_sizes.add(ref)
    edited.append({'literal_offset':ref-base,'before':old,'after':old*SCALE})
   layer_changes.append({'emitter':ex[e['outer']]['name'],'script_export':e['index'],'dimension_constants':edited,'factor':SCALE,'only_size_outputs_affected':True})
   # The previous build's single HDR colour layer has RGB=(5,5,5).
   # Bring its initial RGB to (1,1,1), retaining Alpha and colour-curve hue.
   color=attrs['Initial.Color'];refs=[next(ins['inputs'][0] for ins in code if ins['op']=='outputdata_float' and ins['attribute']==ch) for ch in color[:3]]
   assert all(t=='c' for t,ref in refs)
   rgb=tuple(struct.unpack_from('<f',lits,ref-base)[0] for t,ref in refs)
   params=v['ScriptExecutionParamStore'];curves=[a for a in params['SortedParameterOffsets'] if '.ScaleColor.' in a['Name']]
   if curves:assert max(rgb)-min(rgb)<1e-6,('Unexpected initial tint',rgb)
   else:assert all(abs(rgb[i]/rgb[0]-GOLD[i])<1e-6 for i in range(3))
   if max(rgb)>1:
    assert curves and len({ref for t,ref in refs})==3
    permitted_color={('outputdata_float',i) for name in ('Color','Initial.Color') for i in attrs[name][:3]}
    for t,ref in refs:
     assert uses[ref]<=permitted_color
     patch(literal_start+ref-base,(1.0,))
    intensity_changes.append({'emitter':ex[e['outer']]['name'],'before':rgb,'after':[1,1,1],'alpha_unchanged':True})
  # All size outputs must scale exactly once. Update scripts carry scaled sizes
  # from their incoming particle attributes; no per-frame multiplier is inserted.
  scaled_inputs={(0,i) for i in sizeattrs} if e['name']=='UpdateScript' else set()
  proof={}
  for key,expr in expressions.items():
   op,ds,attr=key
   if op!='outputdata_float' or ds!=0:continue
   degree=scaling_degree(expr,changed_sizes,scaled_inputs)
   assert degree==int(attr in sizeattrs),(rel,e['index'],attr,degree)
   if attr in sizeattrs:proof[str(attr)]=degree
  size_proofs.append({'emitter':ex[e['outer']]['name'],'script':e['name'],'export':e['index'],'all_size_outputs_have_scale_degree_one':True,'all_non_size_outputs_have_scale_degree_zero':True,'size_output_degrees':proof})
 hs=struct.unpack_from('<I',original,4)[0];diffs={i for i,(a,b) in enumerate(zip(original,data)) if a!=b}
 assert len(data)==len(original) and data[:hs]==original[:hs] and diffs<=allowed
 dest.write_bytes(data)
 # No script properties other than the selected literal bytes may differ.
 for before,after in zip(scripts(source),scripts(dest),strict=True):
  b,a=before[3],after[3];b['CachedScriptVM'].pop('ScriptLiterals',None);a['CachedScriptVM'].pop('ScriptLiterals',None)
  assert b==a
 # Reparse final curves and check their entire RGB history, including highlights.
 r=FXParser(dest)
 for e in r.exports():
  if e['name']!='NiagaraDataInterfaceColorCurve':continue
  r.p=e['start'];lut=r.obj(e['name'])['ShaderLUT']
  for i in range(0,len(lut),4):
   rgb=lut[i:i+3]
   if rgb[0]>1e-9:assert all(abs(rgb[j]/rgb[0]-GOLD[j])<1e-6 for j in range(3))
 return {'package':rel,'source_sha256':sha(original),'output_sha256':sha(data),'changed_bytes':len(diffs),'native_zen_header_bit_exact':True,'length_bit_exact':True,'vm_bytecode_and_optimized_cache_bit_exact':True,'edits_only_typed_curve_rgb_and_proven_rgb_or_size_literals':True,'curves':curve_changes,'scaled_layers':layer_changes,'size_scaling_proofs':size_proofs,'hdr_intensity_changes':intensity_changes}

def build():
 (RAW/'chunks').mkdir(parents=True,exist_ok=True);(OUT/'Mod').mkdir(parents=True,exist_ok=True)
 source=ROOT/'work/gold-alert-v020/raw';manifest=json.loads((source/'manifest.json').read_text(encoding='utf8'))
 (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
 header=next((source/'chunks').glob('*06'));shutil.copyfile(header,RAW/'chunks'/header.name)
 results=[]
 for cid,archive in manifest['chunk_paths'].items():
  if not archive.endswith('.uasset'):continue
  rel=archive.removeprefix('../../../');assert rel.removesuffix('.uasset') in TARGETS
  results.append(patch_asset(source/'chunks'/cid,RAW/'chunks'/cid,rel))
 assert len(results)==3 and all(len(r['scaled_layers'])==10 for r in results)
 retoc=ROOT/'tools/retoc/retoc.exe';toc=OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
 subprocess.run([str(retoc),'pack-raw',str(RAW),str(toc)],check=True)
 shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v0.2.0/Mod/zz_PBZ_YellowAlert_P.pak',OUT/'Mod/zz_PBZ_YellowAlert_P.pak')
 subprocess.run([str(retoc),'verify',str(toc)],check=True)
 check=BUILD/('roundtrip-'+uuid.uuid4().hex[:8]);subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
 for p in (RAW/'chunks').iterdir():assert p.read_bytes()==(check/'chunks'/p.name).read_bytes()
 validation={'version':'0.3.0','base':'0.2.0','uniform_gold_rgb':GOLD,'reference_srgb':'#FFB820','sprite_width_height_scale':SCALE,'game_build':'26266538','in_game_tested':False,'container_verify':True,'chunk_roundtrip_bit_exact':True,'dependency_header_bit_exact_with_v020':True,'assets':results}
 (BUILD/'validation.json').write_text(json.dumps(validation,indent=2),encoding='utf8')
 print(json.dumps({'version':'0.3.0','assets':len(results),'scaled_sprite_layers':sum(len(r['scaled_layers']) for r in results),'size_factor':SCALE,'uniform_colour_curves':sum(len(r['curves']) for r in results),'hdr_layers_reduced':sum(len(r['hdr_intensity_changes']) for r in results),'verified':True}))

if __name__=='__main__':build()
