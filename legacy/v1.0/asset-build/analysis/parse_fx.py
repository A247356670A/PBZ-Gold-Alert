"""Targeted cooked FX reader with byte spans for editing explicitly typed colour data."""
import pathlib,struct
from parse_wwise import Parser

class FXParser(Parser):
 def __init__(self,path):
  super().__init__(path);self.records=[];self.stack=[]
 def obj(self,name):
  start=self.p;self.stack.append(name)
  try:value=super().obj(name)
  finally:self.stack.pop()
  self.records.append({'kind':'struct','type':name,'start':start,'end':self.p,'value':value})
  return value
 def value(self,t):
  start=self.p;typ=t[0]
  if typ in ['Object','WeakObject','Interface','Class']:v=self.take('i')
  elif typ=='UInt16':v=self.take('H')
  elif typ=='Int16':v=self.take('h')
  elif typ=='Int8':v=self.take('b')
  elif typ=='SoftObject':
   v={'asset':self.value(('Name',)),'subpath':self.string()}
  elif typ=='Str':v=self.string()
  elif typ=='Text':
   flags=self.take('I');history=self.take('b')
   if history!=-1:raise ValueError(('Unsupported nonempty FText history',history))
   has_text=self.take('I');assert has_text in (0,1)
   v={'flags':flags,'history':history,'text':self.string() if has_text else None}
  elif typ=='Struct' and t[1] in ['NiagaraVariable','NiagaraVariableBase','NiagaraVariableWithOffset']:
   v={'Name':self.value(('Name',)),'TypeDef':self.obj('NiagaraTypeDefinition')}
   if t[1]=='NiagaraVariableWithOffset':v['Offset']=self.take('i')
   elif t[1]=='NiagaraVariable':
    n=self.take('I');v['VarData']=list(self.raw(n))
  elif typ=='Struct' and t[1]=='Box':
   v={'Min':self.take('ddd'),'Max':self.take('ddd'),'IsValid':self.take('B')}
  elif typ=='Struct' and t[1] in ['LinearColor','Vector4f','Vector4','Vector','Vector3f','Vector2D','Vector2f','Quat','Rotator','Guid','Color','IntPoint']:
   fmt={'LinearColor':'ffff','Vector4f':'ffff','Vector4':'dddd','Vector':'ddd','Vector3f':'fff','Vector2D':'dd','Vector2f':'ff','Quat':'dddd','Rotator':'ddd','Guid':'IIII','Color':'BBBB','IntPoint':'ii'}[t[1]]
   v=self.take(fmt)
  else:v=super().value(t)
  self.records.append({'kind':'value','type':t,'start':start,'end':self.p,'parent':self.stack[-1] if self.stack else None,'value':v})
  return v
 def string(self):
  n=self.take('i');return self.raw(abs(n)*(2 if n<0 else 1)).decode('utf-16-le' if n<0 else 'utf8').rstrip('\0')
 def exports(self):
  b=self.b;begin=struct.unpack_from('<I',b,32)[0];end=struct.unpack_from('<I',b,52)[0];hs=struct.unpack_from('<I',b,4)[0]
  out=[]
  for p in range(begin,end,72):
   off,n,ni,nn=struct.unpack_from('<QQII',b,p)
   out.append({'index':(p-begin)//72,'name':self.names[ni&0x3fffffff],'number':nn,'start':hs+off,'size':n,'outer':struct.unpack_from('<Q',b,p+24)[0],'class':struct.unpack_from('<Q',b,p+32)[0]})
  return out
