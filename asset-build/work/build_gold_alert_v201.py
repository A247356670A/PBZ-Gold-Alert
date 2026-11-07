"""V2.0.1: raise only the confirmed success cue's own Wwise playback gain."""
import sys,json,struct,shutil,subprocess,math,wave
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from build_gold_alert_v165 import hirc_objects,table
import build_gold_alert_v1610 as packaging

B=ROOT/'work/gold-alert-v201';RAW=B/'combined/raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v2.0.1'
PRIOR=ROOT/'work/gold-alert-v1612/combined/raw'
LIB='5aac5b9f482230fd00000001';BULK='5aac5b9f482230fd00000002'
GAIN_DB=8.0;SOUND=552257437

def bank_gain():
    old=(ROOT/'work/gold-alert-v1612/parry-success-bank.bnk').read_bytes()
    tree=ET.parse(ROOT/'work/gold-alert-v1612/parry-success-bank.xml').getroot()
    sound,=[x for x in tree.iter('object')if x.get('name')=='CAkSound']
    bundle,=[x for x in sound.iter('object')if x.get('name')=='AkPropBundle<AkPropValue,unsigned char>']
    count,=list(bundle.iter('field'));assert count.get('name')=='cProps' and count.get('value')=='0'
    at=int(count.get('offset'));assert old[at]==0
    hirc,size,objects=hirc_objects(old);p=hirc+12
    while True:
        kind,n=struct.unpack_from('<BI',old,p);oid=struct.unpack_from('<I',old,p+5)[0]
        if oid==SOUND:assert kind==2;break
        p+=n+5
    assert p+5<at<p+5+n
    new=bytearray(old);struct.pack_into('<I',new,p+1,n+5);struct.pack_into('<I',new,hirc+4,size+5)
    new[at]=1;new[at+1:at+1]=b'\x00'+struct.pack('<f',GAIN_DB)
    assert len(new)==len(old)+5
    restored=bytearray(new);del restored[at+1:at+6];restored[at]=0
    struct.pack_into('<I',restored,p+1,n);struct.pack_into('<I',restored,hirc+4,size)
    assert restored==old
    after=hirc_objects(new)[2]
    assert len(after)==len(objects)
    for before,later in zip(objects,after,strict=True):
        assert before[:2]==later[:2]
        if before[1]!=SOUND:assert before[2]==later[2]
    file=B/'success-gain-bank.bnk';file.write_bytes(new)
    subprocess.run([sys.executable,str(ROOT/'tools/wwiser/wwiser.py'),'-d','xml','-dn',str(file.with_suffix('')),str(file)],check=True,capture_output=True)
    parsed=ET.parse(file.with_suffix('.xml')).getroot();s,=[x for x in parsed.iter('object')if x.get('name')=='CAkSound']
    b,=[x for x in s.iter('object')if x.get('name')=='AkPropBundle<AkPropValue,unsigned char>']
    values={f.get('name'):f.get('value')for f in b.iter('field')}
    assert values=={'cProps':'1','pID':'0','pValue':'8.0'}
    return old,bytes(new)

def parent_gains(xml,start):
    nodes={}
    for x in ET.parse(xml).iter('object'):
        own=x.find("field[@name='ulID']")
        if own is not None and x.get('name','').startswith('CAk'):nodes[int(own.get('value'))]=x
    result=[];seen=set()
    while start:
        assert start not in seen;seen.add(start);x=nodes[start]
        parent=next((int(f.get('value'))for f in x.iter('field')if f.get('name')=='DirectParentID'),0)
        bundle=next((p for p in x.iter('object')if p.get('name')=='AkPropBundle<AkPropValue,unsigned char>'),None)
        gain=0.
        if bundle is not None:
            ids=[int(f.get('value'))for f in bundle.iter('field')if f.get('name')=='pID']
            vals=[float(f.get('value'))for f in bundle.iter('field')if f.get('name')=='pValue']
            assert len(ids)==len(vals)
            gain=dict(zip(ids,vals)).get(0,0.)
        result.append(dict(id=start,type=x.get('name'),volume_db=gain));start=parent
    return result

def measure():
    with wave.open(str(ROOT/'outputs/PBZ-Gold-Alert-v1.6.12/Preview/Gauntlet-Parry-Success.wav'),'rb')as f:
        success=f.readframes(f.getnframes())
    with (PRIOR/'chunks/e769c85cabe3aa8400000002').open('rb')as f:
        f.seek(781392768);warning=f.read(396896)[96:]
    sx=np.frombuffer(success,'<i2').astype(float).reshape(-1,2)/32768
    wx=np.frombuffer(warning,'<i2').astype(float).reshape(-1,2)/32768
    sc=parent_gains(ROOT/'work/gold-alert-v1612/parry-success-bank.xml',SOUND)
    wc=parent_gains(ROOT/'work/gold-alert-v164/bank-check.xml',482757608)
    sd=sum(x['volume_db']for x in sc);wd=sum(x['volume_db']for x in wc)
    sr=float(np.sqrt(np.mean(sx[:24000]**2)));wr=float(np.sqrt(np.mean(wx[:24000]**2)))
    before=20*math.log10(sr/wr)+sd-wd;after=before+GAIN_DB
    assert 2<after<6,(before,after)
    preview=OUT/'Preview';preview.mkdir(parents=True,exist_ok=True)
    clips=[wx*10**(wd/20),sx*10**(sd/20),sx*10**((sd+GAIN_DB)/20)]
    scale=.85/max(abs(x).max()for x in clips)
    combined=[]
    for i,x in enumerate(clips):
        combined.append(np.rint(x*scale*32767).astype('<i2'))
        if i<2:combined.append(np.zeros((28800,2),dtype='<i2'))
    with wave.open(str(preview/'Warning-OldSuccess-NewSuccess.wav'),'wb')as f:
        f.setparams((2,2,48000,0,'NONE','not compressed'));f.writeframes(np.concatenate(combined).tobytes())
    return dict(success_gain_added_db=GAIN_DB,linear_amplitude_multiplier=10**(GAIN_DB/20),
        first_500ms_success_pcm_rms=sr,first_500ms_warning_pcm_rms=wr,
        success_parent_volume_chain=sc,warning_parent_volume_chain=wc,
        success_old_parent_gain_db=sd,warning_parent_gain_db=wd,
        estimated_success_minus_warning_before_db=before,estimated_success_minus_warning_after_db=after,
        estimate_excludes_runtime_bus_gain_distance_attenuation_and_game_mix=True,
        preview_order=['purple warning','old success','new success'],preview_shared_output_scale=scale)

def build():
    B.mkdir(parents=True,exist_ok=True);(RAW/'chunks').mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    packaging.BUILD=B
    expected=json.loads((ROOT/'analysis/build-20261105/build.json').read_text())['toc_sha256']
    assert digest(Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'))==expected
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    shutil.copyfile(PRIOR/'manifest.json',RAW/'manifest.json')
    old,new=bank_gain();base=json.loads((ROOT/'outputs/PBZ-Gold-Alert-v1.6.12/audio-source.json').read_text())
    loc=base['bank_location'];assert loc['size']==len(old)==1020
    with (PRIOR/'chunks'/BULK).open('rb')as f:f.seek(loc['offset']);assert f.read(loc['size'])==old
    with (RAW/'chunks'/BULK).open('ab')as f:
        offset=(f.tell()+15)//16*16;f.write(bytes(offset-f.tell()));f.write(new)
    data=bytearray((PRIOR/'chunks'/LIB).read_bytes());entry=table(PRIOR/'chunks'/LIB)+loc['entry']*32
    assert struct.unpack_from('<qqqIB3x',data,entry)==(loc['offset'],-1,loc['size'],66817,0)
    struct.pack_into('<q',data,entry,offset);struct.pack_into('<q',data,entry+16,len(new))
    (RAW/'chunks'/LIB).write_bytes(data)
    restored=bytearray(data);restored[entry:entry+32]=(PRIOR/'chunks'/LIB).read_bytes()[entry:entry+32]
    assert restored==(PRIOR/'chunks'/LIB).read_bytes()
    unchanged={p.name:digest(p)for p in (PRIOR/'chunks').iterdir()if p.name not in [LIB,BULK]}
    assert len(unchanged)==184
    for name,sha in unchanged.items():assert digest(RAW/'chunks'/name)==sha
    # No timing, waveform, fade, actor or attack changes: every such chunk is unchanged.
    assert 'b1bf5d2781c0dfbe00000001' in unchanged
    balance=measure()
    print('Only success-sound Volume +8dB; all media and trigger/timing chunks exact. Packing V2.0.1.',flush=True)
    toc,packed=packaging.pack_check(RAW,OUT/'Mod','combined');assert packed['chunks']==186
    packed_raw=Path(packed['roundtrip'])
    packaging.inspect_native(toc,LIB,RAW/'chunks'/LIB,'success-bank-library')
    with (packed_raw/'chunks'/BULK).open('rb')as f:
        remaining=(PRIOR/'chunks'/BULK).stat().st_size
        with (PRIOR/'chunks'/BULK).open('rb')as oldf:
            while remaining:
                n=min(8*1024*1024,remaining);assert f.read(n)==oldf.read(n);remaining-=n
        f.seek(offset);assert f.read(len(new))==new
    proof=dict(version='2.0.1',base='1.6.12',user_confirmed_base_playback=True,
        volume=balance,bank_location_before=loc,bank_location_after=dict(loc,offset=offset,size=len(new)),
        changed_chunk_ids=[LIB,BULK],unchanged_previous_chunk_sha256=unchanged,
        trigger_and_all_time_positions_bit_exact=True,all_pcm_and_media_metadata_bit_exact=True,
        purple_warning_sound_visuals_blackout_and_counter_unchanged=True,
        only_unique_success_sound_volume_property_added=True,
        unrelated_wwise_objects_and_original_bank_archive_prefix_bit_exact=True,
        combined=packed,in_game_tested=False,installed=False,formal_release_untouched=True)
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    base.update(playback_gain_added_db=GAIN_DB,bank_location=proof['bank_location_after'],
        base_success_playback_confirmed=True,all_source_samples_and_timing_unchanged=True)
    (OUT/'audio-source.json').write_text(json.dumps(base,indent=2),encoding='utf8')
    (OUT/'README.txt').write_text('PBZ Gold Alert V2.0.1 开发测试版\n\n拳套特殊招架成功音效提高8dB，目标比紫光预警声略响。\n保留原始音效、完整尾音及当前播放时机。\n保留紫光、黑屏、红黄预警和现有拳套功能。\n\n安装：完全退出游戏，将Mod内三个文件复制到ProjectPBZ\\Content\\Paks\\~mods覆盖旧版，再启动游戏。\n本测试包合并特效与拳套功能，请勿叠加旧独立拳套包。\n卸载：退出游戏后移除这三个文件。\n\nPreview中的音量对比依次为紫光预警、旧版成功音效、新版成功音效；实际游戏响度还需测试。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n'for p in sorted((OUT/'Mod').iterdir())),encoding='utf8')
    print(json.dumps(dict(version='2.0.1',gain_db=GAIN_DB,estimated_above_warning_db=balance['estimated_success_minus_warning_after_db'],output=str(OUT))),flush=True)

def install():
    query=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process | Where-Object {$_.ProcessName -like 'PBZ*'}).Count"],capture_output=True,text=True,check=True)
    if int(query.stdout.strip()):print('Game running; installation deferred.',flush=True);return
    target=Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\~mods');prior=ROOT/'outputs/PBZ-Gold-Alert-v1.6.12/Mod'
    files=sorted((OUT/'Mod').iterdir());assert len(files)==3 and {p.suffix for p in files}=={'.pak','.utoc','.ucas'}
    before={p.name:digest(target/p.name)for p in files}
    assert all(before[p.name]==digest(prior/p.name)for p in files),'Installed files changed; re-audit before overwriting.'
    now=datetime.now(ZoneInfo('Australia/Sydney'));backup=B/('install-backup-'+now.strftime('%Y%m%d-%H%M%S'));backup.mkdir()
    for p in files:shutil.copy2(target/p.name,backup/p.name);assert digest(backup/p.name)==before[p.name]
    try:
        for p in files:shutil.copyfile(p,target/p.name)
        after={p.name:digest(target/p.name)for p in files};assert all(after[p.name]==digest(p)for p in files)
    except BaseException:
        for p in files:shutil.copyfile(backup/p.name,target/p.name)
        raise
    record=dict(version='2.0.1',installed_at=now.isoformat(),timezone='Australia/Sydney',target=str(target),backup=str(backup),
        previous_sha256=before,installed_sha256=after,verified=True,game_was_running=False,in_game_tested=False)
    for p in [B/'installation.json',OUT/'installation.json']:p.write_text(json.dumps(record,indent=2),encoding='utf8')
    proof=json.loads((B/'validation.json').read_text());proof['installed']=True
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    print('INSTALLED '+json.dumps(record),flush=True)

if __name__=='__main__':build();install()
