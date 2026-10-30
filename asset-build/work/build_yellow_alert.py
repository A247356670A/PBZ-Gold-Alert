"""Build a colour-only PBZ patch; never writes into the game installation."""
import colorsys, hashlib, json, pathlib, shutil, struct, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'))
from parse_wwise import Parser

BUILD=ROOT/'work'/'yellow-alert-v1'
LEGACY=BUILD/'legacy'
ASSET_ROOT='ProjectPBZ/Plugins/PBZVFXPack/Content/VFX/BattleFX'
TARGETS=[
 f'{ASSET_ROOT}/Common/NS_AttackAlert_Blue_001',
 f'{ASSET_ROOT}/Common/NS_AttackAlert_Blue_002',
 f'{ASSET_ROOT}/LeiTing/NS_LeiTing_AttackAlert_Blue_201',
]

def sha(b):return hashlib.sha256(b).hexdigest()
def golden(rgb):
 r,g,b=rgb
 # Only blue/cyan samples are recoloured. Neutral flashes and black stay intact.
 if b<=max(r,g)+1e-6 or max(rgb)-min(rgb)<1e-6:return rgb
 h,s,v=colorsys.rgb_to_hsv(r,g,b)
 if not 0.45<=h<=0.80:return rgb
 return colorsys.hsv_to_rgb(1/6,s,v)

def build():
 BUILD.mkdir(parents=True,exist_ok=True)
 result=[]
 for rel in TARGETS:
  source=ROOT/'analysis'/'extracted'/(rel+'.uasset')
  parser=Parser(source);zen=parser.b;header=parser.p
  original=(ROOT/'analysis'/'legacy'/(rel+'.uexp')).read_bytes()
  assert zen[header:]==original,'Legacy conversion changed export payload'
  data=bytearray(original);spans=[];total=0;curves=[]
  begin=struct.unpack_from('<I',zen,32)[0];end=struct.unpack_from('<I',zen,52)[0]
  for pos in range(begin,end,72):
   offset,size,ni,nn=struct.unpack_from('<QQII',zen,pos)
   name=parser.names[ni&0x3fffffff]
   if name!='NiagaraDataInterfaceColorCurve':continue
   parser.p=header+offset
   obj=parser.obj('NiagaraDataInterfaceColorCurve')
   assert parser.p==header+offset+size-4
   assert zen[parser.p:parser.p+4]==b'\0'*4
   lut=obj.get('ShaderLUT',[])
   assert lut and len(lut)%4==0
   packed=struct.pack('<'+'f'*len(lut),*lut)
   exp=zen[header+offset:header+offset+size]
   loc=exp.find(packed)
   assert loc>=0 and exp.find(packed,loc+1)<0,'Ambiguous LUT location'
   changed=0;samples=[]
   for sample in range(len(lut)//4):
    rgb=tuple(lut[sample*4:sample*4+3]);new=golden(rgb)
    at=offset+loc+sample*16
    if new==rgb:continue
    data[at:at+12]=struct.pack('<fff',*new)
    spans.append((at,at+12));changed+=1
    if len(samples)<3:samples.append({'before':rgb,'after':new,'alpha':lut[sample*4+3]})
   # Verify every alpha value bit-for-bit, including the terminal GPU LUT sample.
   for sample in range(len(lut)//4):
    at=offset+loc+sample*16
    assert data[at+12:at+16]==original[at+12:at+16]
   if changed:curves.append({'export_index':(pos-begin)//72,'rgba_samples':len(lut)//4,'changed_samples':changed,'examples':samples})
   total+=changed
  assert total>0,'No coloured blue samples found'
  allowed=set(i for lo,hi in spans for i in range(lo,hi))
  diffs=[i for i,(a,b) in enumerate(zip(original,data)) if a!=b]
  assert set(diffs)<=allowed and len(data)==len(original)
  for ext in ['.uasset','.uexp']:
   dest=LEGACY/(rel+ext);dest.parent.mkdir(parents=True,exist_ok=True)
   if ext=='.uasset':shutil.copyfile(ROOT/'analysis'/'legacy'/(rel+ext),dest)
   else:dest.write_bytes(data)
  result.append({'package':rel,'changed_samples':total,'changed_bytes':len(diffs),'original_export_sha256':sha(original),'yellow_export_sha256':sha(data),'unchanged_alpha':True,'unchanged_export_length':True,'curves':curves})
 manifest={'name':'PBZ Yellow Attack Alert','version':'0.1.0','game_build':'26266538','game_cl':'CL-301524_JKS-17219','engine':'UE5_7','hue_degrees':60,'assets':result,'in_game_tested':False}
 (BUILD/'build-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
 print(json.dumps({'assets':len(result),'samples':sum(x['changed_samples'] for x in result),'changed_bytes':sum(x['changed_bytes'] for x in result)},indent=2))

if __name__=='__main__':build()
