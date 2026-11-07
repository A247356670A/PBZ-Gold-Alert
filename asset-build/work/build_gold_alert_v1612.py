"""Add the user-confirmed native ZZZ parry-success cue to gauntlet contact."""
import sys,json,struct,shutil,subprocess,wave,hashlib
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy import signal
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from read_pbz import Reader
from parse_fx import FXParser
from build_gold_alert_v160 import digest
from build_gold_alert_v165 import table,hirc_objects
from build_yellow_alert_v011 import store_table
from build_gold_alert_v169 import package_header
from parry_success_hook_v1612 import prepare as stage_hook
import build_gold_alert_v1610 as packaging

B=ROOT/'work/gold-alert-v1612';S=ROOT/'work/parry-success-v1612'
RAW=B/'combined/raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.6.12'
PRIOR=ROOT/'work/gold-alert-v1611/combined/raw'
LIB_BULK='5aac5b9f482230fd00000002';GUARD='b1bf5d2781c0dfbe00000001'

def audio():
    r=Reader();rows=json.loads((ROOT/'analysis/build-20261105/asset-index.json').read_text());by={x['path']:x for x in rows}
    meta=by['ProjectPBZ/Content/Wwise/SFX_All.uasset'];bulk=by['ProjectPBZ/Content/Wwise/SFX_All.ubulk']
    def cid(row):return r.toc[144+row['index']*12:144+(row['index']+1)*12].hex()
    meta_cid,bulk_cid=cid(meta),cid(bulk)
    asset=(S/'SFX_All.uasset').read_bytes();assert asset==r.read(meta['index'])
    location,=json.loads((S/'counter-media-location.json').read_text());assert location['entry']==6399 and location['size']==65139
    original=(S/'SFX_All.ubulk');assert original.stat().st_size==r.info(bulk['index'])[1]
    old_wem=(S/'counter-cast-native-6399.wem').read_bytes();h=old_wem.find(b'hash')
    assert 12<=h<200 and struct.unpack_from('<I',old_wem,h+4)[0]==16
    assert struct.unpack_from('<I',old_wem,h+8)[0]==4196689316
    # Source bytes are re-read from their original ZZZ package, not the recording.
    sources=json.loads((ROOT/'work/audio-correction-v165/game-media-index-expanded.json').read_text())
    source=next(x for x in sources if x['media_id']==773049091)
    native=Path(source['path']);pck=Path(r'D:\ZenlessZoneZero Game\ZenlessZoneZero_Data\StreamingAssets\Audio\Windows\Full')/source['pck']
    with pck.open('rb')as f:f.seek(source['offset']);assert f.read(source['size'])==native.read_bytes()
    subprocess.run([str(ROOT/'tools/vgmstream/vgmstream-cli.exe'),'-i','-o',str(B/'native-source.wav'),str(native)],check=True,capture_output=True)
    sr,a=wavfile.read(B/'native-source.wav');assert sr==44100 and a.shape[1]==2
    a=a.astype(np.float64)/32768.;a=signal.resample_poly(a,160,147,axis=0)
    gain=.87/max(abs(a).max(),1e-9);a*=gain
    pcm=np.round(np.clip(a,-1,1)*32767).astype('<i2').tobytes()
    template=(ROOT/'work/gold-alert-v167/A-Confirmed-Purple/approved-padded.wem').read_bytes()
    header=bytearray(template[:96]);assert header[88:92]==b'data'
    nh=header.find(b'hash');assert nh>=12 and struct.unpack_from('<I',header,nh+4)[0]==16
    header[nh+8:nh+24]=old_wem[h+8:h+24]
    struct.pack_into('<I',header,4,len(pcm)+88);struct.pack_into('<I',header,92,len(pcm))
    wem=bytes(header)+pcm;(B/'parry-success.wem').write_bytes(wem)
    preview=OUT/'Preview';preview.mkdir(parents=True,exist_ok=True)
    with wave.open(str(preview/'Gauntlet-Parry-Success.wav'),'wb')as f:
        f.setparams((2,2,48000,len(pcm)//4,'NONE','not compressed'));f.writeframes(pcm)
    subprocess.run([str(ROOT/'tools/vgmstream/vgmstream-cli.exe'),'-i','-o',str(B/'decoded-check.wav'),str(B/'parry-success.wem')],check=True,capture_output=True)
    with wave.open(str(B/'decoded-check.wav'),'rb')as f:assert f.readframes(f.getnframes())==pcm
    dest=RAW/'chunks'/bulk_cid;shutil.copyfile(original,dest)
    with dest.open('ab')as f:
        offset=(f.tell()+15)//16*16;f.write(bytes(offset-f.tell()));f.write(wem)
    data=bytearray(asset);entry=table(S/'SFX_All.uasset')+location['entry']*32
    assert struct.unpack_from('<qqqIB3x',data,entry)==(location['offset'],-1,location['size'],66817,0)
    struct.pack_into('<q',data,entry,offset);struct.pack_into('<q',data,entry+16,len(wem))
    restored=bytearray(data);restored[entry:entry+32]=asset[entry:entry+32];assert restored==asset
    (RAW/'chunks'/meta_cid).write_bytes(data)
    loc,=json.loads((S/'counter-bank-location.json').read_text());bank=(S/'pbz-counter-cast-original.bnk').read_bytes()
    at,n,objects=hirc_objects(bank);patched=bytearray(bank);changes=[];pos=at+12
    for kind,oid,body in objects:
        # hirc_objects() returns the id separately while its body still includes it.
        size=struct.unpack_from('<I',bank,pos+1)[0];start=pos+5
        if kind==2:
            assert oid==552257437
            assert struct.unpack_from('<I',bank,start+4)[0]==0x40001
            assert bank[start+8]==0
            assert struct.unpack_from('<III',bank,start+9)==(1002030643,4196689316,65139)
            struct.pack_into('<I',patched,start+4,0x10001);struct.pack_into('<I',patched,start+17,len(wem))
            changes.extend(range(start+4,start+8));changes.extend(range(start+17,start+21))
        pos+=5+size
    assert pos==at+8+n and len(patched)==len(bank)
    assert {i for i,(x,y)in enumerate(zip(bank,patched))if x!=y}<=set(changes)
    lib_dest=RAW/'chunks'/LIB_BULK;shutil.copyfile(PRIOR/'chunks'/LIB_BULK,lib_dest)
    with lib_dest.open('r+b')as f:
        f.seek(loc['offset']);assert f.read(loc['size'])==bank
        f.seek(loc['offset']);f.write(patched)
    (B/'parry-success-bank.bnk').write_bytes(patched)
    subprocess.run([sys.executable,str(ROOT/'tools/wwiser/wwiser.py'),'-d','xml','-dn',str(B/'parry-success-bank'),str(B/'parry-success-bank.bnk')],check=True,capture_output=True)
    provenance=dict(native_source=source,native_source_sha256=digest(native),user_confirmation='就是这个声音',
        source_reference='17.53.00.01.mp4 15.854–16.654 seconds; comparison only',
        source_description='New Bagel Plan large dog purple-attack parry success, confirmed by user',
        no_recording_samples_used=True,pitch_unchanged=True,sample_rate=48000,channels=2,
        duration_seconds=len(pcm)/192000.,peak_normalization=.87,normalization_gain=gain,
        complete_source_duration_preserved=True,independent_decode_exact=True,
        native_pbz_event_id=3804814305,native_pbz_media_id=1002030643,native_cache_id=4196689316,
        media_library_entry=location,appended_media_offset=offset,appended_wem_bytes=len(wem),
        bank_location=loc,bank_native_graph_ids_and_length_preserved=True,
        only_bank_codec_and_media_length_changed=True)
    return {meta_cid:meta['path'],bulk_cid:bulk['path']},provenance

def build():
    B.mkdir(parents=True,exist_ok=True);(RAW/'chunks').mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    packaging.BUILD=B
    expected=json.loads((ROOT/'analysis/build-20261105/build.json').read_text())['toc_sha256']
    assert digest(Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'))==expected
    stage_hook()
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    added,provenance=audio()
    shutil.copyfile(S/'GA_TieKuangQuanTao_GuardPoint-success-hook.uasset',RAW/'chunks'/GUARD)
    manifest=json.loads((PRIOR/'manifest.json').read_text());manifest['chunk_paths'].update({c:'../../../'+p for c,p in added.items()})
    hfile,=list((PRIOR/'chunks').glob('*06'));template=hfile.read_bytes();stores,_,_,order=store_table(template)
    native=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    for c in added:
        if not c.endswith('01'):continue
        pid=int.from_bytes(bytes.fromhex(c)[:8],'little');assert pid not in stores
        stores[pid]=native[pid];order.append(pid)
    (RAW/'chunks'/hfile.name).write_bytes(package_header(template,order,stores,template[8:16]))
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2))
    unchanged={p.name:digest(p)for p in (PRIOR/'chunks').iterdir() if p.name not in (GUARD,LIB_BULK,hfile.name)}
    assert len(unchanged)==181
    for c,h in unchanged.items():assert digest(RAW/'chunks'/c)==h
    # Compare the entire shared bank archive outside the one fixed-size bank.
    before=(PRIOR/'chunks'/LIB_BULK).read_bytes();after=(RAW/'chunks'/LIB_BULK).read_bytes();loc=provenance['bank_location']
    assert len(before)==len(after) and before[:loc['offset']]==after[:loc['offset']] and before[loc['offset']+loc['size']:]==after[loc['offset']+loc['size']:]
    assert digest(PRIOR/'chunks'/'e769c85cabe3aa8400000002')==digest(RAW/'chunks'/'e769c85cabe3aa8400000002')
    print('Confirmed native source, complete cue, contact hook and unchanged warning/visual/combat logic checked.',flush=True)
    toc,packed=packaging.pack_check(RAW,OUT/'Mod','combined');assert packed['chunks']==186
    packaging.inspect_native(toc,GUARD,RAW/'chunks'/GUARD,'guard-success')
    meta_cid=next(c for c in added if c.endswith('01'))
    packaging.inspect_native(toc,meta_cid,RAW/'chunks'/meta_cid,'success-media-library')
    hook=json.loads((S/'success-hook-proof.json').read_text());hook['final_audio_not_selected']=False
    proof=dict(version='1.6.12',base='1.6.11',success_audio=provenance,hook=hook,combined=packed,
        unchanged_previous_chunk_sha256=unchanged,all_warning_media_unchanged=True,
        all_visuals_blackout_timing_and_counter_bytecode_unchanged=True,
        native_shared_bank_archive_changed_only_inside_counter_cast_bank=True,
        formal_release_untouched=True,in_game_tested=False,installed=False,
        component_note='Integrated development build. Counter and effects both use WwiseAssetLibrary; separate formal releases require composing bank deltas, not stacking full shared-library overrides.')
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    (OUT/'audio-source.json').write_text(json.dumps(provenance,indent=2),encoding='utf8')
    (S/'confirmed-source.json').write_text(json.dumps(provenance,indent=2),encoding='utf8')
    (OUT/'README.txt').write_text('PBZ Gold Alert v1.6.12 开发测试版\n\n拳套L1+R2成功招架时播放用户确认的绝区零大狗紫光招架成功音效。\n音效来自绝区零原始游戏素材，保留完整起音和尾音；不依赖反击动画是否启动。\n移除该音效原来位于反击动画内的一次播放，避免重复。\n保留1.6.11紫色X、黑屏、预警声音、红黄光及现有拳套反击逻辑。\n\n安装：完全退出游戏，将Mod内的三个文件复制到ProjectPBZ\\Content\\Paks\\~mods覆盖旧版，重新启动游戏。\n本开发测试包合并特效与拳套功能，请勿叠加旧版独立拳套包。\n卸载：退出游戏后移除这三个文件。\n新增成功音效尚需游戏内确认。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n'for p in sorted((OUT/'Mod').iterdir())),encoding='utf8')
    print(json.dumps(dict(output=str(OUT),chunks=186,duration_seconds=provenance['duration_seconds'],in_game_tested=False)),flush=True)

if __name__=='__main__':build()
