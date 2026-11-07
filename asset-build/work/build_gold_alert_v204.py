"""V2.0.4: missed punch emission and isolated gold contact burst; audio untouched."""
import sys,json,shutil,subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from build_yellow_alert_v011 import store_table
from build_gold_alert_v169 import package_header
from punch_gold_v204 import patch,ATTACK
import build_gold_alert_v1610 as packaging
B=ROOT/'work/gold-alert-v204';RAW=B/'combined/raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v2.0.4'
PRIOR=ROOT/'work/gold-alert-v203/combined/raw';PRIOR_OUT=ROOT/'outputs/PBZ-Gold-Alert-v2.0.3'

def build():
    B.mkdir(parents=True,exist_ok=True);(RAW/'chunks').mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True);packaging.BUILD=B
    expected=json.loads((ROOT/'analysis/build-20261105/build.json').read_text())['toc_sha256']
    assert digest(Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'))==expected
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    visual=patch(PRIOR,RAW,B);bullet_store=visual.pop('bullet_store')
    (B/'punch-proof.json').write_text(json.dumps(visual,indent=2),encoding='utf8')
    manifest=json.loads((PRIOR/'manifest.json').read_text());hfile,=list((PRIOR/'chunks').glob('*06'));template=hfile.read_bytes()
    stores,_,_,order=store_table(template);native=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    new=visual['clone_cid'];bullet=visual['bullet_cid'];source=visual['clone_template_cid']
    for cid,path,value in [(new,visual['clone_path'],native[int.from_bytes(bytes.fromhex(source)[:8],'little')]),(bullet,visual['bullet_path'],bullet_store)]:
        assert cid not in manifest['chunk_paths'];manifest['chunk_paths'][cid]='../../../'+path
        pid=int.from_bytes(bytes.fromhex(cid)[:8],'little');assert pid not in stores;stores[pid]=value;order.append(pid)
    assert source not in manifest['chunk_paths'],'The original enemy hit effect must remain in the base game.'
    (RAW/'chunks'/hfile.name).write_bytes(package_header(template,order,stores,template[8:16]))
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    untouched={p.name:digest(p)for p in (PRIOR/'chunks').iterdir()if p.name not in [ATTACK,hfile.name]};assert len(untouched)==189
    for name,sha in untouched.items():assert digest(RAW/'chunks'/name)==sha
    for cid in ['b1bf5d2781c0dfbe00000001','aa16994f9470996900000001','4d769fbfd082059000000001','ff58522d74ff149400000002','5aac5b9f482230fd00000001','5aac5b9f482230fd00000002','e769c85cabe3aa8400000002']:assert cid in untouched
    print('Missed emissive wave and eight scoped hit renderers verified. All sound and accepted charge/guard effects bit-exact. Packing V2.0.4.',flush=True)
    toc,packed=packaging.pack_check(RAW,OUT/'Mod','combined');assert packed['chunks']==193
    for cid,label in [(ATTACK,'punch-wave'),(new,'scoped-gold-hit'),(bullet,'counter-bullet')]:packaging.inspect_native(toc,cid,RAW/'chunks'/cid,label)
    pak=toc.with_suffix('.pak');shutil.copyfile(PRIOR_OUT/'Mod'/pak.name,pak);assert digest(pak)==digest(PRIOR_OUT/'Mod'/pak.name)
    proof=dict(version='2.0.4',base='2.0.3',user_confirmed_v203_charge_gold=True,user_reported_v203_punch_still_white=True,
        punch_visual=visual,combined=packed,unchanged_previous_chunk_sha256=untouched,
        all_audio_media_banks_metadata_and_success_timing_bit_exact=True,
        entire_guardpoint_code_timeline_and_previous_charge_gold_bit_exact=True,
        original_enemy_hit_effect_not_overridden=True,
        bullet_damage_geometry_timing_event_payloads_bit_exact=True,
        description_pak_bit_exact=True,purple_blackout_red_yellow_unchanged=True,
        installed=False,in_game_tested=False,formal_release_untouched=True)
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    shutil.copyfile(PRIOR_OUT/'audio-source.json',OUT/'audio-source.json')
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert V2.0.4 开发测试版\n\n'
        '补上拳套出拳冲击波遗漏的白色发光层，改为与蓄力一致的淡金色。\n'
        '命中爆发采用拳套专用的淡金色副本，保留敌人原有特效。\n'
        '保留V2.0.3已确认的蓄力颜色、当前成功招架音量、完整尾音和播放时间。\n'
        '保留已有铁拳套描述、紫光、黑屏、红黄预警及拳套逻辑。\n\n'
        '安装：完全退出游戏，将Mod内.pak、.utoc、.ucas三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods覆盖旧版，再启动游戏。\n'
        '本测试包合并特效与拳套功能，请勿叠加旧独立拳套包。\n'
        '卸载：退出游戏后移除上述三个文件。\n\n'
        '测试：重点观察蓄力结束后的出拳气浪和命中爆发，确认淡金色是否覆盖残留白光。\n'
        '本版已完成文件校验，实机观感仍需测试。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n'for p in sorted((OUT/'Mod').iterdir())),encoding='utf8')
    print(json.dumps(dict(output=str(OUT),modified_wave_renderers=1,gold_hit_renderers=len(visual['hit']['edits']),chunks=193)),flush=True)

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
    record=dict(version='2.0.4',installed_at=now.isoformat(),timezone='Australia/Sydney',target=str(target),backup=str(backup),previous_sha256=before,installed_sha256=after,verified=True,game_was_running=False,in_game_tested=False)
    for p in [B/'installation.json',OUT/'installation.json']:p.write_text(json.dumps(record,indent=2),encoding='utf8')
    proof=json.loads((B/'validation.json').read_text());proof['installed']=True
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    print('INSTALLED '+json.dumps(record),flush=True)
if __name__=='__main__':build();install()
