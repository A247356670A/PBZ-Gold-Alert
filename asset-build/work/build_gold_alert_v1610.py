"""Integrated contact-trigger repair, pale purple core, and complete warning cue."""
from pathlib import Path
import json,shutil,struct,subprocess,sys,uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from build_yellow_alert_v011 import store_table
from build_gold_alert_v169 import package_header
from gauntlet_trigger_v1610 import patch
from gauntlet_counter_v169 import decode_functions,kismet
from verify_gauntlet_trigger_v1610 import verify
from purple_refine_v1610 import visual,audio_completion

BUILD=ROOT/'work/gold-alert-v1610';RAW=BUILD/'combined/raw'
OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.6.10'
PREVIOUS=ROOT/'work/gold-alert-v169/combined/raw'
RETOC=ROOT/'tools/retoc/retoc.exe'
POST='7dc2590713fc314d00000001'
ACTION='7807bc1ded4a64b800000001'
GUARD=''

def run(args,label):
    r=subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf8',errors='replace')
    (BUILD/(label+'.log')).write_text(r.stdout+r.stderr,encoding='utf8')
    if r.returncode:raise RuntimeError(f'{label}: '+r.stderr[-1500:])

def pack_check(raw,mod,label):
    mod.mkdir(parents=True,exist_ok=True)
    name='zz_PBZ_GauntletCounter_P' if label=='counter' else 'zz_PBZ_YellowAlert_P'
    toc=mod/(name+'.utoc')
    run([RETOC,'pack-raw',raw,toc],label+'-pack')
    shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v1.6.9/Mod/zz_PBZ_YellowAlert_P.pak',toc.with_suffix('.pak'))
    run([RETOC,'verify',toc],label+'-verify')
    dest=BUILD/(label+'-roundtrip-'+uuid.uuid4().hex[:8])
    run([RETOC,'unpack-raw',toc,dest],label+'-unpack')
    expected={p.name for p in (raw/'chunks').iterdir()}
    assert expected=={p.name for p in (dest/'chunks').iterdir()}
    for p in (raw/'chunks').iterdir():assert digest(p)==digest(dest/'chunks'/p.name)
    header,=list((raw/'chunks').glob('*06'))
    assert header.read_bytes()[8:16]==toc.read_bytes()[56:64]==bytes.fromhex(header.name)[:8]
    return toc,dict(verify=True,raw_roundtrip_exact=True,chunks=len(expected),roundtrip=str(dest))

def inspect_native(toc,cid,expected,label):
    dest=BUILD/(label+'-native-inspect');dest.mkdir(exist_ok=True)
    run([RETOC,'dump-test',toc,dest,str(int.from_bytes(bytes.fromhex(cid)[:8],'little'))],label+'-native-inspect')
    file,=dest.glob('*.uasset');assert digest(file)==digest(expected)
    return file

def build():
    BUILD.mkdir(parents=True,exist_ok=True);(RAW/'chunks').mkdir(parents=True,exist_ok=True)
    original,= [x for x in json.loads((ROOT/'work/gauntlet-parry-investigation/manifest.json').read_text())
                 if x['path'].endswith('/GA_TieKuangQuanTao_GuardPoint.uasset')]
    guard=original['cid'];gpid=int.from_bytes(bytes.fromhex(guard)[:8],'little')
    gp=BUILD/'GA_TieKuangQuanTao_GuardPoint.uasset'
    before,after,trigger=patch(ROOT/original['file'],gp);flow=verify(before,after)
    post=BUILD/'NS_AttackAlert_Post_001.uasset'
    fx=visual(PREVIOUS/'chunks'/POST,post)
    action=BUILD/'GAAction_PowerAttackParticle.uasset'
    audio=audio_completion(ROOT/'work/black-alert-investigation/current/GAAction_PowerAttackParticle.uasset',action)
    assert flow['contact_control_flow_cases']==1024
    print('Actual contact-frame cases, native timeline lookup, purple FX and end-stop removal checked.',flush=True)
    for p in (PREVIOUS/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    for file,cid in [(gp,guard),(post,POST),(action,ACTION)]:shutil.copyfile(file,RAW/'chunks'/cid)
    manifest=json.loads((PREVIOUS/'manifest.json').read_text())
    manifest['chunk_paths'][ACTION]='../../../ProjectPBZ/Plugins/Secret/PBZCombatAsset/Content/Prototypes/Actions/GAAction_PowerAttackParticle.uasset'
    native=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    hfile,=list((PREVIOUS/'chunks').glob('*06'));template=hfile.read_bytes()
    stores,_,_,order=store_table(template);apid=int.from_bytes(bytes.fromhex(ACTION)[:8],'little')
    assert apid not in stores;stores[apid]=native[apid];order.append(apid)
    (RAW/'chunks'/hfile.name).write_bytes(package_header(template,order,stores,template[8:16]))
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2))
    untouched={}
    for p in (PREVIOUS/'chunks').iterdir():
        if p.name not in (guard,POST,hfile.name):
            untouched[p.name]=digest(p);assert untouched[p.name]==digest(RAW/'chunks'/p.name)
    assert len(untouched)==179
    # Prepare independently installable future components without touching official release.
    counter=BUILD/'components/gauntlet';craw=counter/'raw'
    prior_counter=ROOT/'work/gold-alert-v169/gauntlet-component/raw'
    shutil.copytree(prior_counter,craw,dirs_exist_ok=True);shutil.copyfile(gp,craw/'chunks'/guard)
    ctoc,cproof=pack_check(craw,counter/'Mod','counter')
    plain=BUILD/'components/effects';fraw=plain/'raw';(fraw/'chunks').mkdir(parents=True,exist_ok=True)
    for p in (RAW/'chunks').iterdir():
        if p.name not in (guard,hfile.name):shutil.copyfile(p,fraw/'chunks'/p.name)
    fxorder=[p for p in order if p!=gpid]
    (fraw/'chunks'/hfile.name).write_bytes(package_header(template,fxorder,stores,template[8:16]))
    fmanifest=dict(manifest,chunk_paths={c:p for c,p in manifest['chunk_paths'].items() if c!=guard})
    (fraw/'manifest.json').write_text(json.dumps(fmanifest,indent=2))
    assert not ({p.name for p in (fraw/'chunks').iterdir()} & {p.name for p in (craw/'chunks').iterdir()})
    print('Packing separate effects component and integrated test build.',flush=True)
    ftoc,fproof=pack_check(fraw,plain/'Mod','effects')
    toc,combined=pack_check(RAW,OUT/'Mod','combined')
    assert combined['chunks']==183 and fproof['chunks']==182 and cproof['chunks']==2
    for label,pack in [('combined',toc),('counter',ctoc)]:
        file=inspect_native(pack,guard,gp,label+'-guard')
        _,decoded=decode_functions(file);assert verify(before,decoded)==flow
    for label,pack in [('combined',toc),('effects',ftoc)]:
        file=inspect_native(pack,ACTION,action,label+'-audio-action');_,decoded=decode_functions(file)
        fn=next(f for f in decoded if f['function']=='Received_ActionEnd')
        assert not any(n.get('expr',{}).get('call')=='PBZStopPlayingID' for n in fn['expressions'])
        inspect_native(pack,POST,post,label+'-purple')
    sounds=['e769c85cabe3aa8400000001','e769c85cabe3aa8400000002','5aac5b9f482230fd00000001','5aac5b9f482230fd00000002']
    assert all(cid in untouched for cid in sounds)
    proof=dict(version='1.6.10',base='1.6.9 test reported never countering',trigger=trigger,
        contact_validation=flow,purple_visual=fx,audio_completion=audio,
        unchanged_previous_chunk_sha256=untouched,combined=combined,
        separate_components=dict(counter=cproof,effects=fproof,chunk_overlap=[]),
        audio_media_and_bank_bit_exact=True,all_official_release_directories_untouched=True,
        original_failure_runtime_cause_not_proven=True,in_game_tested=False,installed=False)
    OUT.mkdir(exist_ok=True)
    for path in [OUT/'validation.json',BUILD/'validation.json']:path.write_text(json.dumps(proof,indent=2),encoding='utf8')
    for name,value in [('contact-flow-validation.json',flow),('gauntlet-trigger-proof.json',trigger),('purple-refinement-proof.json',dict(visual=fx,audio_completion=audio))]:
        (BUILD/name).write_text(json.dumps(value,indent=2),encoding='utf8')
    lines=[]
    for fn in after:
        lines.append('\n'+fn['function']);lines.extend(f"{n['offset']:04x}: {kismet.render(n)}" for n in fn['expressions'])
    (BUILD/'guardpoint-bytecode-patched.txt').write_text('\n'.join(lines),encoding='utf8')
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert v1.6.10 开发测试版\n\n'
        '拳套L1+R2接住黑光攻击后自动进入反击，覆盖成功、普通防御与连续招架事件。\n'
        '按名称取得反击动作，避免依赖缓存；反击进行中不重复启动，不改变原防御窗口。\n'
        '紫色45度X形光条加粗50%，提高淡紫亮芯亮度，保留头顶位置、穿透显示、同步消失与黑屏。\n'
        '取消预警结束时的主动停音，让原有约2.07秒的单次提示音自然结束。\n'
        '红黄光与音频素材保持不变。以上改动尚需游戏内验证，不能把离线通过当作实机成功。\n\n'
        '安装：完全退出游戏，将Mod内三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods，覆盖旧版同名文件后重新启动游戏。\n'
        '本版合并拳套与特效，请勿同时加载独立拳套版本。\n'
        '卸载：退出游戏后移除上述三个文件。\n',encoding='utf-8-sig')
    (OUT/'TEST-INSTRUCTIONS.txt').write_text(
        '优先在第一张地图三面Boss上测试：\n'
        '1. 重启游戏后，用拳套L1+R2接黑光；先确认产生拳意及返还次数，再观察是否自动出拳反击。\n'
        '2. 分别测试刚举手接住与架势稍晚接住，观察普通防御段是否也能接反击。\n'
        '3. 反击进行中再次接触同一多段黑光，不应反复从头播放反击。\n'
        '4. 观察紫X亮芯和两条同时消失；听提示音是否在光效结束后仍有自然尾音。\n'
        '仍不触发时请保留一次完整的举手、接招、拳意变化和收招过程，继续定位实际运行入口。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n' for p in sorted((OUT/'Mod').iterdir())),encoding='utf8')
    print(json.dumps(dict(output=str(OUT),combined_chunks=combined['chunks'],contact_cases=1024,
        previous_unchanged_chunks=len(untouched),independent_components_verified=True,in_game_tested=False),ensure_ascii=False),flush=True)

if __name__=='__main__':build()
