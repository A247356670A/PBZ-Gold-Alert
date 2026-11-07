"""V2.0.3: complete Couter follow-up palette and +50% protected success PCM gain."""
import sys,json,shutil,subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from build_yellow_alert_v011 import store_table
from build_gold_alert_v169 import package_header
from success_pcm_v203 import amplify
from followup_gold_v203 import patch_all
import build_gold_alert_v1610 as packaging
B=ROOT/'work/gold-alert-v203';RAW=B/'combined/raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v2.0.3'
PRIOR=ROOT/'work/gold-alert-v202/combined/raw';PRIOR_OUT=ROOT/'outputs/PBZ-Gold-Alert-v2.0.2'

def build():
    B.mkdir(parents=True,exist_ok=True);(RAW/'chunks').mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True);packaging.BUILD=B
    expected=json.loads((ROOT/'analysis/build-20261105/build.json').read_text())['toc_sha256']
    assert digest(Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'))==expected
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    audio=amplify(PRIOR,RAW,B,OUT);visual=patch_all(RAW)
    (B/'followup-gold-proof.json').write_text(json.dumps(visual,indent=2),encoding='utf8')
    manifest=json.loads((PRIOR/'manifest.json').read_text());hfile,=list((PRIOR/'chunks').glob('*06'));template=hfile.read_bytes()
    stores,_,_,order=store_table(template);native=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    changed=[a['cid']for a in visual['assets']]
    for a in visual['assets']:
        cid=a['cid'];assert cid not in manifest['chunk_paths'];manifest['chunk_paths'][cid]='../../../'+a['path']
        pid=int.from_bytes(bytes.fromhex(cid)[:8],'little');assert pid not in stores
        stores[pid]=native[pid];order.append(pid)
    (RAW/'chunks'/hfile.name).write_bytes(package_header(template,order,stores,template[8:16]))
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    untouched={p.name:digest(p)for p in (PRIOR/'chunks').iterdir()if p.name not in [audio['changed_chunk'],hfile.name]}
    assert len(untouched)==185
    for name,sha in untouched.items():assert digest(RAW/'chunks'/name)==sha
    for cid in ['b1bf5d2781c0dfbe00000001','aa16994f9470996900000001','5aac5b9f482230fd00000001','5aac5b9f482230fd00000002','e769c85cabe3aa8400000002']:assert cid in untouched
    print('Twelve follow-up renderers, +50% PCM gain with peak protection, and 185 unchanged previous chunks checked. Packing V2.0.3.',flush=True)
    toc,packed=packaging.pack_check(RAW,OUT/'Mod','combined');assert packed['chunks']==191
    for a in visual['assets']:packaging.inspect_native(toc,a['cid'],RAW/'chunks'/a['cid'],Path(a['path']).stem)
    # Preserve the current localized description pak, instead of pack_check's legacy empty pak.
    pak=toc.with_suffix('.pak');shutil.copyfile(PRIOR_OUT/'Mod'/pak.name,pak);assert digest(pak)==digest(PRIOR_OUT/'Mod'/pak.name)
    packed_raw=Path(packed['roundtrip'])
    with (packed_raw/'chunks'/audio['changed_chunk']).open('rb')as f:
        f.seek(audio['media_offset']);assert f.read(audio['media_bytes'])==(B/'success-louder.wem').read_bytes()
    proof=dict(version='2.0.3',base='2.0.2',user_confirmed_v202_first_phase_gold_and_acceptable_audio=True,
        audio=audio,followup_visual=visual,combined=packed,unchanged_previous_chunk_sha256=untouched,
        all_guardpoint_trigger_bytecode_and_timeline_positions_bit_exact=True,
        no_success_audio_rescheduling_or_trimming=True,existing_success_banks_and_native_media_metadata_bit_exact=True,
        warning_media_and_blackout_purple_red_yellow_effects_unchanged=True,
        existing_first_phase_gold_and_description_pak_bit_exact=True,installed=False,in_game_tested=False,formal_release_untouched=True)
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    base=json.loads((PRIOR_OUT/'audio-source.json').read_text());base['previous_actual_pcm_processing']=base.pop('additional_actual_pcm_processing');base['additional_actual_pcm_processing']=audio
    (OUT/'audio-source.json').write_text(json.dumps(base,indent=2),encoding='utf8')
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert V2.0.3 开发测试版\n\n'
        '补齐拳套反击后续的蓄力、出拳、风圈与轨迹淡金色，沿用V2.0.2首段招架的配色。\n'
        '成功招架原声在V2.0.2基础上增加50%线性增益，并进行峰值保护；不改变播放位置和完整尾音。\n'
        '峰值保护会压低超出范围的波峰，实际听感与平均响度不等于精确增加50%。\n'
        '保留现有铁拳套描述、紫光、黑屏、红黄预警及拳套逻辑。\n\n'
        '安装：完全退出游戏，将Mod内.pak、.utoc、.ucas三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods覆盖旧版，再启动游戏。\n'
        '本测试包合并特效与拳套功能，请勿叠加旧独立拳套包。\n'
        '卸载：退出游戏后移除上述三个文件。\n\n'
        '测试：连续观察招架瞬间、蓄力环绕和出拳气浪三个阶段的淡金色。\n'
        'Preview提供V2.0.2与V2.0.3成功原声对比；实际游戏观感和音量需测试。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n'for p in sorted((OUT/'Mod').iterdir())),encoding='utf8')
    print(json.dumps(dict(output=str(OUT),changed_followup_renderers=visual['changed_renderers'],audio_gain=1.5,actual_onset_rms_ratio=audio['actual_rms_ratio'],chunks=191)),flush=True)

def install():
    query=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process | Where-Object {$_.ProcessName -like 'PBZ*'}).Count"],capture_output=True,text=True,check=True)
    if int(query.stdout.strip()):print('Game running; installation deferred.',flush=True);return
    target=Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\~mods');files=sorted((OUT/'Mod').iterdir())
    assert len(files)==3 and {p.suffix for p in files}=={'.pak','.utoc','.ucas'}
    before={p.name:digest(target/p.name)for p in files};expected={p.name:digest(PRIOR_OUT/'Mod'/p.name)for p in files}
    assert before==expected,'Installed files changed; re-audit before overwriting.'
    now=datetime.now(ZoneInfo('Australia/Sydney'));backup=B/('install-backup-'+now.strftime('%Y%m%d-%H%M%S'));backup.mkdir()
    for p in files:shutil.copy2(target/p.name,backup/p.name);assert digest(backup/p.name)==before[p.name]
    try:
        for p in files:shutil.copyfile(p,target/p.name)
        after={p.name:digest(target/p.name)for p in files};assert all(after[p.name]==digest(p)for p in files)
    except BaseException:
        for p in files:shutil.copyfile(backup/p.name,target/p.name)
        raise
    record=dict(version='2.0.3',installed_at=now.isoformat(),timezone='Australia/Sydney',target=str(target),backup=str(backup),previous_sha256=before,installed_sha256=after,verified=True,game_was_running=False,in_game_tested=False)
    for p in [B/'installation.json',OUT/'installation.json']:p.write_text(json.dumps(record,indent=2),encoding='utf8')
    proof=json.loads((B/'validation.json').read_text());proof['installed']=True
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    print('INSTALLED '+json.dumps(record),flush=True)
if __name__=='__main__':build();install()
