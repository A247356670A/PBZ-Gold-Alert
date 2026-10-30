"""Read legacy VectorVM instructions and trace typed colour outputs to constants."""
import json,pathlib,struct,sys
from parse_fx import FXParser
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work'))
from build_yellow_alert import TARGETS
OPS={int(i):tuple(v) for i,v in json.loads((ROOT/'analysis/vectorvm-opcodes.json').read_text(encoding='utf8')).items()}

def disassemble(vm):
 b=bytes(vm['ByteCode']['Data'] if isinstance(vm['ByteCode'],dict) else vm['ByteCode']);p=0;out=[]
 def u16():
  nonlocal p
  v=struct.unpack_from('<H',b,p)[0];p+=2;return v
 while p<len(b):
  start=p;op=b[p];p+=1;name,cat,n=OPS[op];row={'at':start,'op':name,'inputs':[],'outputs':[]}
  if cat=='Op' and op!=88:
   flags=b[p];p+=1;args=[u16() for _ in range(n)]
   row['inputs']=[('c' if flags&(1<<i) else 'r',x) for i,x in enumerate(args[:-1])];row['outputs']=[args[-1]]
  elif cat=='Input':row['dataset']=u16();row['attribute']=u16();row['outputs']=[u16()]
  elif cat=='Output':
   flags=b[p];p+=1;row['dataset']=u16();row['index']=u16();row['inputs']=[('c' if flags else 'r',u16())];row['attribute']=u16()
  elif op==86:
   flags=b[p];p+=1;row['dataset']=u16();row['inputs']=[('c' if flags else 'r',u16())];row['outputs']=[u16()]
  elif op==87:
   idx=u16();f=vm['CalledVMExternalFunctions'][idx];ni=len(f.get('InputParamLocations') or []);no=f.get('NumOutputs',0)
   row['function']=f['Name'];row['inputs']=[('r' if (x:=u16())&0x8000 else 'c',x&0x7fff) for _ in range(ni)];row['outputs']=[u16() for _ in range(no)]
  elif op==88:row['outputs']=[u16()]
  elif op==91:row['inputs']=[('c',u16())]
  elif op in (93,94):row['raw']=[u16() for _ in range(3)]
  elif op not in (0,92):raise ValueError((start,op,name))
  row['end']=p;out.append(row)
  if op==0:
   assert not any(b[p:]),(p,len(b));break
 return out

def scripts(path):
 q=FXParser(path);ex=q.exports()
 for e in ex:
  if e['name'] not in ('SpawnScript','UpdateScript'):continue
  q.p=e['start'];q.records=[];v=q.obj('NiagaraScript');assert q.p==e['start']+e['size']-4
  yield q,ex,e,v,list(q.records)

def attributes(vm):
 floats={};i=0
 allattrs=vm.get('Attributes') or []
 base=next((a['TypeDef']['ClassStructOrEnum'] for a in allattrs if a['Name']=='Age'),-44)
 sizes={base:1,base+5:4,base+2:4,base-2:3,base+4:2,base+3:3}
 for a in vm.get('Attributes') or []:
  typ=a['TypeDef']['ClassStructOrEnum']
  if typ in (base-1,base+1):continue
  assert typ in sizes,(a,typ)
  size=sizes[typ];floats[a['Name']]=list(range(i,i+size));i+=size
 return floats

def inspect():
 results=[]
 for rel in TARGETS:
  for q,ex,e,v,recs in scripts(ROOT/'analysis/extracted'/(rel+'.uasset')):
   vm=v['CachedScriptVM'];code=disassemble(vm);literals=bytes(vm.get('ScriptLiterals') or []);base=code[0]['inputs'][0][1]
   attrs=attributes(vm);want=attrs.get('Particles.Initial.Color',attrs.get('Initial.Color',[]))
   color=[]
   for ins in code:
    if ins['op']=='outputdata_float' and ins['attribute'] in want:
     t,x=ins['inputs'][0];f=struct.unpack_from('<f',literals,x-base)[0] if t=='c' and 0<=x-base<=len(literals)-4 else None
     color.append({'channel':want.index(ins['attribute']),'source':[t,x],'literal_offset':x-base,'value':f})
   outer=ex[e['outer']]['name'] if e['outer']<len(ex) else str(e['outer'])
   # Outer is a package index encoded as zero-based export index in Zen.
   rows={'package':rel,'script':e['index'],'outer':outer,'name':e['name'],'base':base,'color':color,'instructions':code}
   results.append(rows)
   if e['name']=='SpawnScript':print(json.dumps({k:val for k,val in rows.items() if k!='instructions'}))
 (ROOT/'work/fx-vm-analysis.json').write_text(json.dumps(results,indent=2),encoding='utf8')

if __name__=='__main__':inspect()
