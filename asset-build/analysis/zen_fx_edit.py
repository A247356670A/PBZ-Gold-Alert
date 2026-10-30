"""Small native Zen edits: preserve import/dependency bytes and old name indices."""
import struct

MASK=(1<<64)-1;K0=0xc3a5c85c97cb3127;K1=0xb492b66fbe98f273;K2=0x9ae16a3b2f90404f
def rot(v,n):return ((v>>n)|(v<<(64-n)))&MASK
def hash16(u,v,m):
 a=((u^v)*m)&MASK;a^=a>>47;b=((v^a)*m)&MASK;b^=b>>47;return (b*m)&MASK
def name_hash(name):
 s=name.lower().encode('ascii');n=len(s);m=(K2+n*2)&MASK
 f64=lambda p:struct.unpack_from('<Q',s,p)[0]
 f32=lambda p:struct.unpack_from('<I',s,p)[0]
 if 17<=n<=32:
  a=f64(0)*K1&MASK;b=f64(8);c=f64(n-8)*m&MASK;d=f64(n-16)*K2&MASK
  return hash16((rot((a+b)&MASK,43)+rot(c,30)+d)&MASK,(a+rot((b+K2)&MASK,18)+c)&MASK,m)
 if 8<=n<=16:
  a=(f64(0)+K2)&MASK;b=f64(n-8);return hash16((rot(b,37)*m+a)&MASK,((rot(a,25)+b)*m)&MASK,m)
 if 4<=n<8:return hash16(n+(f32(0)<<3),f32(n-4),m)
 if n:
  y=s[0]+(s[n>>1]<<8);z=n+(s[n-1]<<2);v=((y*K2)&MASK)^((z*K0)&MASK);return ((v^(v>>47))*K2)&MASK
 return K2

def read_fields(q,name):
 """Return raw field payloads while preserving explicit zero/default fields."""
 props={i:(k,t) for i,k,t in q.schema(name)};frags=[];index=0;zcount=0
 while True:
  h=q.take('H');index+=h&127;zero=bool(h&128);last=bool(h&256);count=h>>9
  frags.extend((index+i,zero) for i in range(count));index+=count
  if zero:zcount+=count
  if last:break
 mask=q.take('B') if 0<zcount<=8 else q.take('H') if 8<zcount<=16 else int.from_bytes(q.raw((zcount+31)//32*4),'little') if zcount else 0
 fields={};zi=0
 for index,z in frags:
  iszero=z and bool(mask&(1<<zi));zi+=int(z);key,t=props[index];start=q.p
  value=None if iszero else q.value(t)
  fields[index]={'name':key,'value':value,'zero':iszero,'data':q.b[start:q.p],'start':start,'end':q.p}
 return fields

def encode_fields(fields):
 """Serialize only the unversioned header; keep existing field payload bytes."""
 if not fields:return struct.pack('<H',0x100)
 headers=[];payload=[];cursor=0;zeros=[]
 for index,f in sorted(fields.items()):
  skip=index-cursor
  while skip>127:headers.append(127);skip-=127;cursor+=127
  z=f.get('zero',False);headers.append(skip|0x200|(0x80 if z else 0));cursor=index+1
  if z:zeros.append(1)
  else:payload.append(f['data'])
 headers[-1]|=0x100
 zlen=1 if 0<len(zeros)<=8 else 2 if len(zeros)<=16 and zeros else ((len(zeros)+31)//32*4)
 mask=((1<<len(zeros))-1).to_bytes(zlen,'little')
 return struct.pack('<'+'H'*len(headers),*headers)+mask+b''.join(payload)

def raw_field(data):return {'data':data,'zero':False}
def object_bytes(values):return encode_fields({i:raw_field(b) for i,b in values.items()})

def append_names(q,names):
 """Append ASCII names with verified CityHash64 hashes and native bulk padding."""
 b=q.b;n=len(q.names);old_end=q.name_end;assert struct.unpack_from('<I',b,60)[0]==n
 hashes=b[76:76+n*8];lengths=b[76+n*8:76+n*10];strings=b[76+n*10:old_end]
 checks=0
 for i,s in enumerate(q.names):
  if s.isascii() and len(s)<=32:
   assert name_hash(s)==struct.unpack_from('<Q',hashes,i*8)[0],('FName hash mismatch',s);checks+=1
 assert checks>50
 assert all(s not in q.names and s.isascii() and len(s)<=32 for s in names)
 extra=b''.join(s.encode('ascii') for s in names)
 batch=struct.pack('<IIQ',n+len(names),len(strings)+len(extra),struct.unpack_from('<Q',b,68)[0])+hashes+b''.join(struct.pack('<Q',name_hash(s)) for s in names)+lengths+b''.join(struct.pack('>H',len(s)) for s in names)+strings+extra
 old_pad=struct.unpack_from('<Q',b,old_end)[0];bulk_at=old_end+8+old_pad
 bulk_size=struct.unpack_from('<Q',b,bulk_at)[0];assert bulk_size==0
 new_end=60+len(batch);pad=(-new_end)%8
 prefix=b[:60]+batch+struct.pack('<Q',pad)+b'\0'*pad+struct.pack('<Q',0)
 old_imports=struct.unpack_from('<I',b,24)[0];assert bulk_at+8==old_imports
 delta=len(prefix)-old_imports;assert delta%8==0
 hs=struct.unpack_from('<I',b,4)[0];header=bytearray(prefix+b[old_imports:hs])
 for off in (4,24,28,32,36,40,44,48,52,56):struct.pack_into('<I',header,off,struct.unpack_from('<I',b,off)[0]+delta)
 return header,delta,{s:n+i for i,s in enumerate(names)}

def rebuild_exports(q,header,delta,replacements):
 """Retain original export indices and every native import/dependency table."""
 b=q.b;hs=struct.unpack_from('<I',b,4)[0];payload=bytearray();cursor=hs;layout={}
 for e in sorted(q.exports(),key=lambda x:x['start']):
  assert e['start']>=cursor
  payload.extend(b[cursor:e['start']]);part=replacements.get(e['index'],b[e['start']:e['start']+e['size']])
  layout[e['index']]=(len(payload),len(part));payload.extend(part);cursor=e['start']+e['size']
 payload.extend(b[cursor:]);map_start=struct.unpack_from('<I',header,32)[0]
 for index,(off,size) in layout.items():struct.pack_into('<QQ',header,map_start+index*72,off,size)
 # Only known offsets/sizes/name batch changed. Preserve native linkage verbatim.
 oldi=struct.unpack_from('<I',b,28)[0];olde=struct.unpack_from('<I',b,32)[0]
 newi=struct.unpack_from('<I',header,28)[0];newe=struct.unpack_from('<I',header,32)[0]
 assert b[oldi:olde]==header[newi:newe]
 dep=struct.unpack_from('<I',b,36)[0];newdep=struct.unpack_from('<I',header,36)[0]
 assert b[dep:hs]==header[newdep:]
 return bytes(header+payload)
