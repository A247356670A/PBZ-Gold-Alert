"""Dimension-only VM edits and established native cross bindings for red warnings."""
import itertools,json,pathlib,struct,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'work'),str(ROOT/'analysis')]
from inspect_fx_vm import scripts,attributes,disassemble
from build_gold_alert import impacts
from build_gold_alert_v030 import scaling_degree
from fx_vm_trace import output_expressions
from red_rotation_v140 import rotate_asset
from build_gold_alert_v120 import with_library_store
from build_gold_alert_v100 import cross


def scale(src,dst,factor):
 data=bytearray(src.read_bytes());edits=[];variable_edits=[]
 for q,ex,e,v,recs in scripts(src):
  vm=v['CachedScriptVM']
  if not vm.get('ByteCode'):continue
  attrs=attributes(vm);sizeattrs={i for name,ids in attrs.items() if name.endswith('SpriteSize') for i in ids}
  if not sizeattrs or e['name']!='SpawnScript':continue
  code=disassemble(vm);expressions=output_expressions(code);base=code[0]['inputs'][0][1];lits=bytes(vm.get('ScriptLiterals') or []);uses=impacts(code)
  rows=[r for r in recs if r['kind']=='value' and r['type']==('Array',('Byte',)) and r['parent']=='NiagaraVMExecutableData' and r['value']==list(lits)]
  assert len(rows)==1
  permitted={('outputdata_float',i) for i in sizeattrs}
  candidates=[ref for ref,out in uses.items() if out and out<=permitted and 0<=ref-base<=len(lits)-4 and struct.unpack_from('<f',lits,ref-base)[0]>0]
  selected=None
  for count in range(1,len(candidates)+1):
   for choice in itertools.combinations(candidates,count):
    try:valid=all(scaling_degree(expressions['outputdata_float',0,ch],set(choice),set())==1 for ch in sizeattrs)
    except AssertionError:valid=False
    if valid:selected=choice;break
   if selected:break
  if selected is None:
   if ex[e['outer']]['name'] in ('Star001','Star002','NE_EmitterFlare'):continue
   outs=[i for i in code if i['op']=='outputdata_float' and i['attribute'] in sizeattrs]
   assert outs
   bc=bytes(vm['ByteCode']['Data']);newlits=bytearray(lits);factorref=base+len(newlits);newlits.extend(struct.pack('<f',factor))
   from inspect_fx_vm import OPS
   mulop=next(k for k,vv in OPS.items() if vv[0]=='mul')
   vmrec=next(rr for rr in recs if rr['kind']=='struct' and rr['type']=='NiagaraVMExecutableData')
   from zen_fx_edit import read_fields
   q.p=vmrec['start'];fields=read_fields(q,'NiagaraVMExecutableData')
   tf=next(f for f in fields.values() if f['name']=='NumTempRegisters')
   temp=tf['value'];newbc=bytearray();cursor=0;count=0
   for ins in outs:
    newbc.extend(bc[cursor:ins['at']]);kind,ref=ins['inputs'][0];reg=temp+count;count+=1
    newbc.extend(struct.pack('<BBHHH',mulop,3 if kind=='c' else 2,ref,factorref,reg))
    output=bytearray(bc[ins['at']:ins['end']]);output[1]=0;struct.pack_into('<H',output,6,reg);newbc.extend(output);cursor=ins['end']
   newbc.extend(bc[cursor:]);struct.pack_into('<i',data,tf['start'],temp+count)
   br,=[rr for rr in recs if rr['kind']=='value' and rr['type']==('Array',('Byte',)) and rr['value']==list(bc)]
   variable_edits.extend([(br['start'],br['end'],struct.pack('<I',len(newbc))+newbc),(rows[0]['start'],rows[0]['end'],struct.pack('<I',len(newlits))+newlits)])
   edits.append(('isolated-size-literals',len(outs)));continue
  for ref in selected:
   at=rows[0]['start']+4+ref-base;old=struct.unpack_from('<f',data,at)[0];struct.pack_into('<f',data,at,old*factor);edits.append((at,old,old*factor))
 assert edits
 if variable_edits:
  from parse_fx import FXParser
  from zen_fx_edit import rebuild_exports
  parser=FXParser(src);replacements={}
  for exp in parser.exports():
   inside=[x for x in variable_edits if exp['start']<=x[0]<exp['start']+exp['size']]
   if not inside:continue
   body=bytes(data[exp['start']:exp['start']+exp['size']])
   for a,z,v in sorted(inside,reverse=True):body=body[:a-exp['start']]+v+body[z-exp['start']:]
   replacements[exp['index']]=body
  hs=struct.unpack_from('<I',data,4)[0];data=rebuild_exports(parser,bytearray(data[:hs]),0,replacements)
 dst.write_bytes(data)
 for before,after in zip(scripts(src),scripts(dst),strict=True):
  b,a=before[3],after[3];b['CachedScriptVM'].pop('ScriptLiterals',None);a['CachedScriptVM'].pop('ScriptLiterals',None)
  if variable_edits:
   for k in ('ByteCode','NumTempRegisters'):b['CachedScriptVM'].pop(k,None);a['CachedScriptVM'].pop(k,None)
  assert b==a
 return len(edits)


def update_visuals(reader,raw,manifest):
 build=raw.parent;counts=[]
 for cid,path in list(manifest['chunk_paths'].items()):
  if 'Plugins/PBZVFXPack' in path:
   temp=build/('before-'+cid);temp.write_bytes((raw/'chunks'/cid).read_bytes())
   counts.append({'path':path,'factor':1.2,'size_constants':scale(temp,raw/'chunks'/cid,1.2)})
 header,=(raw/'chunks').glob('*06');hb=header.read_bytes()
 hi=next(i for i in range(reader.n) if reader.toc[144+i*12+11]==6);original=reader.read(hi)
 for name in ['NS_AttackAlert_Red_001','NS_AttackAlert_Red_004']:
  rel='ProjectPBZ/Plugins/PBZVFXPack/Content/VFX/BattleFX/Common/'+name+'.uasset'
  idx=reader.by_path[rel]['index'];cid=reader.toc[144+idx*12:144+(idx+1)*12].hex()
  src=build/(name+'-original.uasset');src.write_bytes(reader.read(idx));scaled=build/(name+'-scaled.uasset')
  num=scale(src,scaled,3.0);rotated=build/(name+'-rotated.uasset');rotation=rotate_asset(scaled,rotated,rel)
  # Set the proven current/previous rotation parameter stores to 0/90.
  from parse_fx import FXParser
  q=FXParser(rotated);data=bytearray(q.b);angle_edits=0
  for e in q.exports():
   typ='NiagaraSystem' if e['name'].startswith('NS_') else 'NiagaraEmitter' if e['name'].startswith(('Empty','Star','NE_')) else None
   if not typ:continue
   q.p=e['start'];q.records=[];q.obj(typ)
   for rec in q.records:
    if rec['kind']!='struct' or rec['type'] not in ('NiagaraParameterStore','NiagaraUserRedirectionParameterStore'):continue
    val=rec['value'];params=val.get('SortedParameterOffsets') or []
    if not any('PBZ_X_' in p['Name'] for p in params):continue
    rows=[r for r in q.records if r['kind']=='value' and r['type']==('Array',('Byte',)) and r['start']>=rec['start'] and r['end']<=rec['end'] and r['value']==val['ParameterData']];assert len(rows)==1
    for p in params:
     if 'PBZ_X_' in p['Name']:struct.pack_into('<f',data,rows[0]['start']+4+p['Offset'],90.0 if p['Name'].endswith('Neg') else 0.0);angle_edits+=1
  assert angle_edits>0
  (raw/'chunks'/cid).write_bytes(data);manifest['chunk_paths'][cid]='../../../'+rel
  hb=with_library_store(hb,original,int.from_bytes(bytes.fromhex(cid)[:8],'little'))
  counts.append({'path':rel,'factor':3,'size_constants':num,'cross_angles':[0,90],'rotation_stores':angle_edits,'rotation':rotation})
 header.write_bytes(hb);(raw/'manifest.json').write_text(json.dumps(manifest,indent=2))
 (build/'visual-validation.json').write_text(json.dumps(counts,indent=2))
