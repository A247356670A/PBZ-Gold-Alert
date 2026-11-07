"""V2.0.5: fixed 30% maximum Shachi after black gauntlet counter contact."""
import sys,json,shutil,subprocess,struct
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from build_yellow_alert_v011 import store_table
from build_gold_alert_v169 import package_header
from shachi_fixed_v205 import effect,guard_patch,GUARD,GE_CID,GE_PID
from verify_shachi_v205 import verify
import build_gold_alert_v1610 as packaging
B=ROOT/'work/gold-alert-v205';RAW=B/'combined/raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v2.0.5'
PRIOR=ROOT/'work/gold-alert-v204/combined/raw';PRIOR_OUT=ROOT/'outputs/PBZ-Gold-Alert-v2.0.4'

def build():
    B.mkdir(parents=True,exist_ok=True);(RAW/'chunks').mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True);packaging.BUILD=B
    expected=json.loads((ROOT/'analysis/build-20261105/build.json').read_text())['toc_sha256']
    assert digest(Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'))==expected
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    ge=effect(RAW/'chunks'/GE_CID);functions,guard=guard_patch(PRIOR/'chunks'/GUARD,RAW/'chunks'/GUARD,B,ge)
    flow=verify(PRIOR,RAW);(B/'shachi-flow-validation.json').write_text(json.dumps(flow,indent=2))
    (B/'shachi-proof.json').write_text(json.dumps(dict(effect=ge,guard=guard),indent=2))
    manifest=json.loads((PRIOR/'manifest.json').read_text());hfile,=list((PRIOR/'chunks').glob('*06'));template=hfile.read_bytes()
    stores,_,_,order=store_table(template);native=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    assert GE_CID not in manifest['chunk_paths'];manifest['chunk_paths'][GE_CID]='../../../'+ge['path']
    assert GE_PID not in stores;stores[GE_PID]=native[int.from_bytes(bytes.fromhex(ge['template_cid'])[:8],'little')];order.append(GE_PID)
    gpid=int.from_bytes(bytes.fromhex(GUARD)[:8],'little');deps,shaders=stores[gpid]
    assert len(deps)//8==guard['original_dependency_count'];stores[gpid]=(deps+struct.pack('<Q',GE_PID),shaders)
    (RAW/'chunks'/hfile.name).write_bytes(package_header(template,order,stores,template[8:16]))
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    untouched={p.name:digest(p)for p in (PRIOR/'chunks').iterdir()if p.name not in [GUARD,hfile.name]};assert len(untouched)==191
    for name,sha in untouched.items():assert digest(RAW/'chunks'/name)==sha
    for cid in ['ff58522d74ff149400000002','5aac5b9f482230fd00000001','5aac5b9f482230fd00000002','e769c85cabe3aa8400000002','aa16994f9470996900000001','4d769fbfd082059000000001','3dde1ed4bacb125700000001','f91ab85adf8cd12300000001','0f7ebdf755a4845700000001']:assert cid in untouched
    print('1024 decoded contact cases passed; fixed 30% maximum via one delayed override. All audio/FX unchanged. Packing V2.0.5.',flush=True)
    toc,packed=packaging.pack_check(RAW,OUT/'Mod','combined');assert packed['chunks']==194
    for cid,label in [(GUARD,'guard-shachi-settlement'),(GE_CID,'shachi-30-effect')]:packaging.inspect_native(toc,cid,RAW/'chunks'/cid,label)
    pak=toc.with_suffix('.pak');shutil.copyfile(PRIOR_OUT/'Mod'/pak.name,pak);assert digest(pak)==digest(PRIOR_OUT/'Mod'/pak.name)
    proof=dict(version='2.0.5',base='2.0.4',user_requested_fixed_remaining_fraction_not_reduced_cost=True,
        effect=ge,guard=guard,control_flow=flow,combined=packed,unchanged_previous_chunk_sha256=untouched,
        all_audio_media_banks_metadata_visual_chunks_and_pak_bit_exact=True,
        original_ordinary_yellow_blue_nonblack_guard_rules_preserved=True,
        no_global_damage_calculator_or_enemy_meter_override=True,
        current_maximum_including_upgrades_captured=True,enemy_damage_and_counter_timeline_unchanged=True,
        installed=False,in_game_tested=False,formal_release_untouched=True)
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    shutil.copyfile(PRIOR_OUT/'audio-source.json',OUT/'audio-source.json')
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert V2.0.5 开发测试版\n\n'
        '拳套特殊招架接住黑光并触发反击后，将玩家杀气固定为当前满槽上限的30%。\n'
        '即使招架前不足30%，也按当前上限回到30%；杀气上限升级后自动适配。\n'
        '在原接触扣减后约50ms结算一次；持续反击中的重复接触不反复补充。\n'
        '不改变其他颜色的招架规则、反击动作、伤害、次数返还、拳意、当前音量和特效。\n\n'
        '安装：完全退出游戏，将Mod内.pak、.utoc、.ucas三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods覆盖旧版，再启动游戏。\n'
        '本测试包合并特效与拳套功能，请勿叠加旧独立拳套包。\n'
        '卸载：退出游戏后移除上述三个文件。\n\n'
        '测试：分别以满杀气和低杀气使用拳套接住三面Boss黑光，观察接触后杀气是否回到30%。\n'
        '本版已完成文件与控制流校验；实际游戏时序和恢复比例仍需实测。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n'for p in sorted((OUT/'Mod').iterdir())),encoding='utf8')
    print(json.dumps(dict(output=str(OUT),fixed_maximum_fraction=.3,contact_cases=1024,chunks=194)),flush=True)

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
    record=dict(version='2.0.5',installed_at=now.isoformat(),timezone='Australia/Sydney',target=str(target),backup=str(backup),previous_sha256=before,installed_sha256=after,verified=True,game_was_running=False,in_game_tested=False)
    for p in [B/'installation.json',OUT/'installation.json']:p.write_text(json.dumps(record,indent=2),encoding='utf8')
    proof=json.loads((B/'validation.json').read_text());proof['installed']=True
    for p in [B/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    print('INSTALLED '+json.dumps(record),flush=True)
if __name__=='__main__':build();install()
