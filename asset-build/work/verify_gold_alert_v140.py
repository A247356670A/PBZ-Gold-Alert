"""Independent byte-preservation and Wwise-format decoder checks."""
import hashlib,json,pathlib,struct,subprocess,sys,wave
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'))
from read_pbz import Reader
from parse_fx import FXParser


def verify():
 b=ROOT/'work/gold-alert-v140';out=ROOT/'outputs/PBZ-Gold-Alert-v1.4.0'
 e=json.loads((b/'build-evidence.json').read_text());raw=b/'raw'
 r=Reader();original=r.read(r.by_path['ProjectPBZ/Content/Wwise/SFX_Monster.ubulk']['index'])
 # Read the post-pack, re-extracted chunk, so this checks the delivered container as well.
 patched=(pathlib.Path(e['roundtrip_path'])/'chunks'/e['bulk_cid']).read_bytes()
 assert len(patched)==len(original)==781392766
 assert (raw/'chunks'/e['bulk_cid']).stat().st_size==len(original)
 spans=sorted((x['offset'],x['size']) for row in e['media'] for x in row['records'])
 cursor=0
 for off,n in spans:
  assert patched[cursor:off]==original[cursor:off];cursor=off+n
 assert patched[cursor:]==original[cursor:]
 decoded=[]
 for row in e['media']:
  full,=[x for x in row['records'] if x['size']==x['riff_size']]
  pre,=[x for x in row['records'] if x['size']==57696]
  old=original[full['offset']:full['offset']+full['size']]
  new=patched[full['offset']:full['offset']+full['size']]
  assert new[:96]==old[:96] and new[96:]!=old[96:]
  assert new[:57696]==patched[pre['offset']:pre['offset']+pre['size']]
  assert new[:4]==b'RIFF' and struct.unpack_from('<I',new,4)[0]+8==len(new)
  assert struct.unpack_from('<IHHIIHH',new,16)==(24,0xfffe,2,48000,192000,4,16)
  assert new[44:48]==b'hash' and struct.unpack_from('<I',new,52)[0]==row['cache_id']
  wem=b/f'checked-{row["media_id"]}.wem';wem.write_bytes(new)
  wav=wem.with_suffix('.wav')
  proc=subprocess.run([str(ROOT/'tools/vgmstream/vgmstream-cli.exe'),'-o',str(wav),str(wem)],check=True,capture_output=True,text=True)
  assert 'Wwise' in proc.stdout,proc.stdout
  with wave.open(str(wav),'rb') as f:
   assert (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes())==(2,2,48000,row['frames'])
   samples=f.readframes(f.getnframes());assert any(samples)
  with wave.open(str(out/f'Preview/ZZZ-Variant-{row["media_id"]}.wav'),'rb') as f:
   assert samples==f.readframes(f.getnframes())
  decoded.append({'media_id':row['media_id'],'frames':row['frames'],'decoder':'Wwise RIFF header',
                  'pcm_sha256':hashlib.sha256(samples).hexdigest()})
 event_path='ProjectPBZ/Content/Wwise/Events/SFX/Combat/VFX/Monster_VFX/Bell/SFX_Combat_VFX_Monster_YuDi_Blue.uasset'
 assert (raw/'chunks'/e['event_cid']).read_bytes()==r.read(r.by_path[event_path]['index'])
 lib_path='ProjectPBZ/Content/Wwise/SFX_Monster.uasset'
 assert (raw/'chunks'/e['library_cid']).read_bytes()==r.read(r.by_path[lib_path]['index'])
 q=FXParser(raw/'chunks'/e['event_cid']);q.obj('AkAudioEvent');q.take('I');event=q.obj('WwiseLocalizedEventCookedData')
 ev=event['EventLanguageMap'][0]['value']
 assert ev['EventID']&0xffffffff==3631941836 and len(ev['Media'])==3
 assert all(x['PackagedFile']['PackagingStrategy']==4 and x['PackagedFile']['PrefetchSize']==57696 for x in ev['Media'])
 manifest=json.loads((raw/'manifest.json').read_text())
 assert not any('WwiseAssetLibrary' in path for path in manifest['chunk_paths'].values())
 for cid,path in manifest['chunk_paths'].items():
  if 'Plugins/PBZVFXPack' in path:
   assert (raw/'chunks'/cid).exists()
 result=dict(e);result['independent_decoder_results']=decoded
 result['independent_outside_target_spans_comparison']=True
 result['test_scope']='Offline only; v1.2.0 user-confirmed silent; v1.4.0 pending in-game test'
 (b/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 (out/'Source/validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps({'version':'1.4.0','checks_passed':True,'decoded':decoded,'in_game_tested':False}))


if __name__=='__main__':verify()
