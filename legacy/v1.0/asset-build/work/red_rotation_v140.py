"""2.5x gold alert with opposing +/-45 degree sprite renderer bindings."""
import hashlib,json,pathlib,shutil,struct,subprocess,sys,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
import build_gold_alert_v030 as size_builder
from inspect_fx_vm import FXParser,TARGETS,scripts
from zen_fx_edit import append_names,rebuild_exports,read_fields,encode_fields,object_bytes,raw_field

BUILD=ROOT/'work/gold-alert-v040';RAW=BUILD/'raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v0.4.0'
ANGLES={'Empty':45,'Empty003':-45,'Empty005':45,'Empty006':-45,'Empty007':45,'Empty008':-45,'Empty010':45,'Empty011':-45,'Empty012':45,'Empty013':-45}
PARAMS=['User.PBZ_X_Neg','User.PBZ_X_Pos','User.Previous.PBZ_X_Neg','User.Previous.PBZ_X_Pos']
VALUES={n:(-45.0 if n.endswith('Neg') else 45.0) for n in PARAMS}

def sha(data):return hashlib.sha256(data).hexdigest()
def splice_export(q,e,lo,hi,new):
 assert e['start']<=lo<=hi<=e['start']+e['size']
 return q.b[e['start']:lo]+new+q.b[hi:e['start']+e['size']]

def rotate_asset(source,dest,rel):
 q=FXParser(source);ex=q.exports();header,delta,names=append_names(q,PARAMS);replacements={};renderer_changes=[]
 # Preserve the native float type definition, including the original import index.
 first=next(scripts(source));vm=first[3]['CachedScriptVM'];floatdef=next(a['TypeDef'] for a in vm['Attributes'] if a['Name']=='Age')
 rec=next(r for r in first[4] if r['kind']=='struct' and r['type']=='NiagaraTypeDefinition' and r['value']==floatdef)
 typebytes=q.b[rec['start']:rec['end']]
 fname=lambda n:struct.pack('<II',names[n],0)
 def varbase(n):return fname(n)+typebytes
 def store_bytes(params,user=False):
  params=sorted(params);variables=struct.pack('<I',len(params))+b''.join(varbase(n)+struct.pack('<i',i*4) for i,n in enumerate(params))
  data=b''.join(struct.pack('<f',VALUES[n]) for n in params)
  return object_bytes({2 if user else 1:variables,3 if user else 2:struct.pack('<I',len(data))+data})
 def binding_bytes(n):
  return object_bytes({0:fname(n),1:varbase(n),2:fname(n),3:b'\x04',4:b'\x01',5:b'\x00'})
 # User defaults make the four current/previous renderer angle parameters visible
 # to normal component parameter binding, without modifying any simulation script.
 systems=[e for e in ex if e['name'].startswith('NS_')];assert len(systems)==1;system=systems[0]
 q.p=system['start'];q.records=[];systemprops=q.obj('NiagaraSystem')
 assert systemprops['ExposedParameters']=={}
 rec=next(r for r in q.records if r['kind']=='struct' and r['type']=='NiagaraUserRedirectionParameterStore')
 replacements[system['index']]=splice_export(q,system,rec['start'],rec['end'],store_bytes(PARAMS,True))
 for e in ex:
  if e['name']!='NiagaraSpriteRendererProperties' or ex[e['outer']]['name']=='NE_EmitterFlare':continue
  emitter=ex[e['outer']];label=emitter['name'];angle=45 if e['outer']%2 else -45
  n='User.PBZ_X_Pos' if angle>0 else 'User.PBZ_X_Neg';pn=n.replace('User.','User.Previous.')
  # Override just the rotation bindings; every original material/colour binding
  # retains its own raw serialized field bytes.
  q.p=e['start'];fields=read_fields(q,e['name']);bodyend=q.p
  fields[32]=raw_field(binding_bytes(n));fields[51]=raw_field(binding_bytes(pn))
  replacements[e['index']]=encode_fields(fields)+q.b[bodyend:e['start']+e['size']]
  # Cooked renderer parameter stores supply matching constants immediately,
  # including the previous-frame angle, avoiding dependence on VM regeneration.
  q.p=emitter['start'];q.records=[];props=q.obj('NiagaraEmitter')
  oldstore=props['VersionData'][0]['RendererBindings']
  assert oldstore.get('SortedParameterOffsets')==[] and oldstore.get('ParameterData')==[]
  assert not oldstore.get('DataInterfaces') and not oldstore.get('UObjects')
  er=next(r for r in q.records if r['kind']=='struct' and r['type']=='NiagaraParameterStore')
  assert emitter['index'] not in replacements
  replacements[emitter['index']]=splice_export(q,emitter,er['start'],er['end'],store_bytes([n,pn]))
  renderer_changes.append({'emitter':label,'renderer_export':e['index'],'angle_degrees':angle,'current_parameter':n,'previous_parameter':pn,'material_and_non_rotation_fields_preserved':True})
 assert len(renderer_changes)>=4 and {r['angle_degrees'] for r in renderer_changes}=={-45,45}
 data=rebuild_exports(q,header,delta,replacements);dest.write_bytes(data)
 # Reparse all bindings and both constant stores using the independent reader.
 check=FXParser(dest);cex=check.exports();assert check.names[:len(q.names)]==q.names
 se=cex[system['index']];check.p=se['start'];new_system=check.obj('NiagaraSystem');user=new_system.pop('ExposedParameters')
 before=dict(systemprops);before.pop('ExposedParameters');assert new_system==before
 assert [p['Name'] for p in user['SortedParameterOffsets']]==sorted(PARAMS)
 for p in user['SortedParameterOffsets']:assert struct.unpack_from('<f',bytes(user['ParameterData']),p['Offset'])[0]==VALUES[p['Name']]
 for row in renderer_changes:
  e=cex[row['renderer_export']];check.p=e['start'];after=check.obj(e['name'])
  old=ex[e['index']];q.p=old['start'];before=q.obj(old['name'])
  for key,param in [('SpriteRotationBinding',row['current_parameter']),('PrevSpriteRotationBinding',row['previous_parameter'])]:
   binding=after.pop(key);assert binding['ParamMapVariable']['Name']==param and binding['BindingSourceMode']==4 and binding['bBindingExistsOnSource']==1 and binding['bIsCachedParticleValue']==0
   before.pop(key,None)
  assert after==before
  emitter=cex[e['outer']];check.p=emitter['start'];ev=check.obj('NiagaraEmitter');store=ev['VersionData'][0]['RendererBindings']
  for p in store['SortedParameterOffsets']:assert struct.unpack_from('<f',bytes(store['ParameterData']),p['Offset'])[0]==row['angle_degrees']
  q.p=ex[emitter['index']]['start'];ov=q.obj('NiagaraEmitter');ov['VersionData'][0].pop('RendererBindings');ev['VersionData'][0].pop('RendererBindings');assert ov==ev
 # Every non-replaced export, including all VM bytecode and all golden LUTs,
 # must be byte-for-byte identical to the correctly scaled intermediate file.
 for old,new in zip(ex,cex,strict=True):
  if old['index'] not in replacements:assert q.b[old['start']:old['start']+old['size']]==data[new['start']:new['start']+new['size']]
 return {'package':rel,'new_names':PARAMS,'header_growth_bytes':delta,'export_count_preserved':len(cex)==len(ex),'original_imports_and_dependency_tables_bit_exact':True,'no_new_external_dependencies':True,'all_colour_curve_and_vm_exports_bit_exact_with_scaled_input':True,'renderer_angles':renderer_changes,'sha256':sha(data)}
