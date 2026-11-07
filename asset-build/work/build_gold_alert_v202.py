"""V2.0.2: actual success PCM gain, gauntlet description, pale-gold counter FX."""
import sys,json,struct,shutil,subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from build_yellow_alert_v011 import store_table
from build_gold_alert_v169 import package_header
from success_pcm_v202 import amplify
from counter_gold_v202 import patch as gold_patch
from patch_description_v202 import patch as description_patch,strings as loc_strings,REL
import build_gold_alert_v1610 as packaging

B=ROOT/'work/gold-alert-v202';RAW=B/'combined/raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v2.0.2'
PRIOR=ROOT/'work/gold-alert-v201/combined/raw';COUNTER='aa16994f9470996900000001'

def build():
    B.mkdir(parents=True,exist_ok=True);(RAW/'chunks').mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    packaging.BUILD=B
    expected=json.loads((ROOT/'analysis/build-20261105/build.json').read_text())['toc_sha256']
    assert digest(Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'))==expected
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    audio=amplify(PRIOR,RAW,B,OUT)
    visual=gold_patch(RAW/'chunks'/COUNTER)
    text=description_patch(B/'pak-root'/REL)
    manifest=json.loads((PRIOR/'manifest.json').read_text());assert COUNTER not in manifest['chunk_paths']
    manifest['chunk_paths'][COUNTER]='../../../ProjectPBZ/Plugins/PBZVFXPack/Content/VFX/BattleFX/ShachiWeapon/TieKuangQuanTao/NS_Hun_ShaChiWeaponQuanTao_Couter_401.uasset'
    header_file,=list((PRIOR/'chunks').glob('*06'));template=header_file.read_bytes()
    stores,_,_,order=store_table(template);native=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    pid=int.from_bytes(bytes.fromhex(COUNTER)[:8],'little');assert pid not in stores
    stores[pid]=native[pid];order.append(pid)
    (RAW/'chunks'/header_file.name).write_bytes(package_header(template,order,stores,template[8:16]))
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    unchanged={p.name:digest(p)for p in (PRIOR/'chunks').iterdir()if p.name not in [audio['changed_chunk'],header_file.name]}
    assert len(unchanged)==184
    for name,sha in unchanged.items():assert digest(RAW/'chunks'/name)==sha
    assert all(c in unchanged for c in ['b1bf5d2781c0dfbe00000001','5aac5b9f482230fd00000001','5aac5b9f482230fd00000002','e769c85cabe3aa8400000002'])
    print('Description single-string edit, +6.02dB actual onset PCM and six scoped gold renderers verified. Packing V2.0.2.',flush=True)
    toc,packed=packaging.pack_check(RAW,OUT/'Mod','combined');assert packed['chunks']==187
    packaging.inspect_native(toc,COUNTER,RAW/'chunks'/COUNTER,'counter-gold')
    # IoStore handles cooked assets; a companion pak carries the localization override.
    files=[p.relative_to(B/'pak-root').as_posix()for p in (B/'pak-root').rglob('*')if p.is_file()]
    assert files==[REL],files
    repak=ROOT/'tools/repak/repak.exe';pak=toc.with_suffix('.pak')
    packaging.run([repak,'pack',B/'pak-root',pak,'--version','V11','--compression','Zlib','-q'],'description-pak-pack')
    result=subprocess.run([str(repak),'list',str(pak)],capture_output=True,text=True,check=True)
    assert result.stdout.splitlines()==[REL]
    packaging.run([repak,'unpack',pak,'-o',B/'pak-roundtrip','-q'],'description-pak-unpack')
    assert digest(B/'pak-roundtrip'/REL)==digest(B/'pak-root'/REL)
    _,localized=loc_strings((B/'pak-roundtrip'/REL).read_bytes())
    assert localized[text['localized_string_index']]['value']==text['new_description']
    # Confirm that the installed media range will contain the larger PCM, from the actual packed bytes.
    packed_raw=Path(packed['roundtrip'])
    with (packed_raw/'chunks'/audio['changed_chunk']).open('rb')as f:
        f.seek(audio['media_offset']);assert f.read(audio['media_bytes'])==(B/'success-louder.wem').read_bytes()
    proof=dict(version='2.0.2',base='2.0.1',base_volume_increase_not_perceptible_per_user=True,
        audio=audio,counter_visual=visual,description=text,combined=packed,
        unchanged_previous_chunk_sha256=unchanged,all_trigger_and_audio_positions_bit_exact=True,
        no_success_sound_rescheduling=True,existing_success_bank_gain_and_layout_bit_exact=True,
        warning_media_and_blackout_purple_red_yellow_effects_unchanged=True,
        pak_contains_only_one_localization_override=True,pak_roundtrip_exact=True,
        installed=False,in_game_tested=False,formal_release_untouched=True)
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    base=json.loads((ROOT/'outputs/PBZ-Gold-Alert-v2.0.1/audio-source.json').read_text())
    base['base_pcm_peak_normalization']=base.pop('peak_normalization',.87)
    base['additional_actual_pcm_processing']=audio
    (OUT/'audio-source.json').write_text(json.dumps(base,indent=2),encoding='utf8')
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert V2.0.2 开发测试版\n\n'
        '提高拳套成功招架音效的实际响度，保留当前触发时间和完整尾音。\n'
        '铁拳套的简体中文描述末尾追加：跟...根本没有这样的拳套!\n'
        '拳套反击气浪与亮光改为淡金色。\n'
        '保留紫光、黑屏、红黄预警和现有拳套功能。\n\n'
        '安装：完全退出游戏，将Mod内.pak、.utoc、.ucas三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods覆盖旧版，再启动游戏。\n'
        '三个文件都要替换；文字更新位于.pak中。\n'
        '本测试包合并特效与拳套功能，请勿叠加旧独立拳套包。\n'
        '卸载：退出游戏后移除这三个文件。\n\n'
        'Preview可试听旧、新成功音效。新增响度、淡金色及文字布局仍需游戏内测试。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n'for p in sorted((OUT/'Mod').iterdir())),encoding='utf8')
    print(json.dumps(dict(output=str(OUT),onset_rms_gain_db=audio['first_500ms_gain_db'],counter_renderers=6,description_string=text['localized_string_index'],chunks=187)),flush=True)

def install():
    query=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process | Where-Object {$_.ProcessName -like 'PBZ*'}).Count"],capture_output=True,text=True,check=True)
    if int(query.stdout.strip()):print('Game running; installation deferred.',flush=True);return
    target=Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\~mods');prior=ROOT/'outputs/PBZ-Gold-Alert-v2.0.1/Mod'
    files=sorted((OUT/'Mod').iterdir());assert len(files)==3 and {p.suffix for p in files}=={'.pak','.utoc','.ucas'}
    before={p.name:digest(target/p.name)for p in files}
    if before=={p.name:digest(p)for p in files}:
        proof=json.loads((B/'validation.json').read_text());proof['installed']=True
        for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
        print('Identical V2.0.2 files already installed.',flush=True);return
    expected={p.name:digest(prior/p.name)for p in files}
    rebuild_record=B/'pre-rebuild-installed-manifest.json'
    audited_rebuild=json.loads(rebuild_record.read_text())['installed_sha256'] if rebuild_record.exists()else None
    assert before==expected or before==audited_rebuild,'Installed files changed; re-audit before overwriting.'
    now=datetime.now(ZoneInfo('Australia/Sydney'));backup=B/('install-backup-'+now.strftime('%Y%m%d-%H%M%S'));backup.mkdir()
    for p in files:shutil.copy2(target/p.name,backup/p.name);assert digest(backup/p.name)==before[p.name]
    try:
        for p in files:shutil.copyfile(p,target/p.name)
        after={p.name:digest(target/p.name)for p in files};assert all(after[p.name]==digest(p)for p in files)
    except BaseException:
        for p in files:shutil.copyfile(backup/p.name,target/p.name)
        raise
    record=dict(version='2.0.2',installed_at=now.isoformat(),timezone='Australia/Sydney',target=str(target),backup=str(backup),
        previous_sha256=before,installed_sha256=after,verified=True,game_was_running=False,in_game_tested=False)
    if rebuild_record.exists():
        first=json.loads(rebuild_record.read_text())
        if first['previous_sha256']==expected:
            record['original_v201_backup']=first['backup'];record['original_v201_sha256']=expected
    for p in [B/'installation.json',OUT/'installation.json']:p.write_text(json.dumps(record,indent=2),encoding='utf8')
    proof=json.loads((B/'validation.json').read_text());proof['installed']=True
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    print('INSTALLED '+json.dumps(record),flush=True)

if __name__=='__main__':build();install()
