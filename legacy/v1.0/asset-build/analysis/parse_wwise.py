"""Decode the targeted unversioned Wwise metadata with the matching community usmap."""
import json,pathlib,struct,sys
from read_pbz import ROOT
sys.path.insert(0,str(ROOT.parent/'tools'))
import usmap_io
u=usmap_io.read(ROOT.parent/'tools'/'ProjectPBZ-5.7.4-301524-full.usmap')
schemas={s.name:s for s in u.structs}
class Parser:
 def __init__(self,path):
  self.b=path.read_bytes();self.p=60
  count=self.take('I');self.take('I');self.take('Q');self.p+=count*8
  lengths=[self.take('>H') for _ in range(count)];self.names=[]
  for ln in lengths:
   n=ln&0x7fff;wide=bool(ln&0x8000);self.names.append(self.b[self.p:self.p+n*(2 if wide else 1)].decode('utf-16-le' if wide else 'utf8'));self.p+=n*(2 if wide else 1)
  self.name_end=self.p
  self.p=struct.unpack_from('<I',self.b,4)[0]
 def take(self,fmt):
  fmt=fmt if fmt.startswith('>') else '<'+fmt
  n=struct.calcsize(fmt);v=struct.unpack_from(fmt,self.b,self.p);self.p+=n;return v[0] if len(v)==1 else v
 def schema(self,name):
  s=schemas[name];ps=[]
  for p in s.props:
   for i in range(p.array_dim):ps.append((p.index+i,p.name,p.type))
  ps=sorted(ps)
  if s.super:
   n=max((p[0]+1 for p in ps),default=0)
   ps.extend((i+n,k,t) for i,k,t in self.schema(s.super))
  return ps
 def obj(self,name):
  props={i:(k,t) for i,k,t in self.schema(name)};frags=[];idx=0;zcount=0
  while True:
   h=self.take('H');skip=h&127;zero=bool(h&128);last=bool(h&256);num=h>>9
   idx+=skip;frags.extend((idx+i,zero) for i in range(num));idx+=num
   if zero:zcount+=num
   if last:break
  mask=self.take('B') if 0<zcount<=8 else self.take('H') if zcount<=16 and zcount else int.from_bytes(self.raw((zcount+31)//32*4),'little') if zcount else 0
  out={};zi=0
  for i,z in frags:
   iszero=z and bool(mask&(1<<zi));zi+=int(z)
   key,t=props[i]
   out[key]=None if iszero else self.value(t)
  return out
 def raw(self,n):b=self.b[self.p:self.p+n];self.p+=n;return b
 def value(self,t):
  typ=t[0]
  if typ=='Struct':return self.obj(t[1])
  if typ in ['Array','Set']:
   if typ=='Set':assert self.take('I')==0
   n=self.take('I');assert n<100000,(n,self.p,t)
   return [self.value(t[1]) for _ in range(n)]
  if typ=='Map':
   assert self.take('I')==0
   n=self.take('I');assert n<10000
   return [{'key':self.value(t[1]),'value':self.value(t[2])} for _ in range(n)]
  if typ=='Name':
   i,n=self.take('II');return self.names[i&0x3fffffff]+(f'_{n-1}' if n else '')
  if typ=='Enum':return self.value(t[1])
  fmt={'Int':'i','UInt32':'I','Float':'f','Double':'d','Bool':'B','Byte':'B','Object':'Q','Int64':'q','UInt64':'Q'}
  if typ in fmt:return self.take(fmt[typ])
  raise ValueError(t)

if __name__=='__main__':
 results=[]
 base=ROOT/'extracted'/'ProjectPBZ'/'Content'/'Wwise'/'Events'/'SFX'/'Combat'/'VFX'/'Monster_VFX'/'Bell'
 for path in base.glob('*.uasset'):
  if path.name.endswith('Bell_L_04.uasset'):continue
  p=Parser(path)
  try:
   props=p.obj('AkAudioEvent');guid=p.take('I');assert guid==0
   event=p.obj('WwiseLocalizedEventCookedData')
   results.append({'file':path.name,'names':p.names,'properties':props,'event':event,'end':p.p,'size':len(p.b)})
  except Exception as e:results.append({'file':path.name,'position':p.p,'error':repr(e)})
 (ROOT/'audio-metadata.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(results,ensure_ascii=True,indent=2))
