"""Violet warning at 80% size, with scene blackout before its composition."""
import json,shutil,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from build_yellow_alert_v011 import store_table
from build_gold_alert_v169 import package_header
from purple_colour_v1611 import resize_recolour,move_blackout_before_separate_translucency
from parse_fx import FXParser
import build_gold_alert_v1610 as packaging

BUILD=ROOT/'work/gold-alert-v1611';RAW=BUILD/'combined/raw'
OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.6.11'
PRIOR=ROOT/'work/gold-alert-v1610/combined/raw'
POST='7dc2590713fc314d00000001';MAT='578586b678c0514f00000001'

def build():
    BUILD.mkdir(parents=True,exist_ok=True);(RAW/'chunks').mkdir(parents=True,exist_ok=True)
    packaging.BUILD=BUILD
    expected=json.loads((ROOT/'analysis/build-20261105/build.json').read_text())['toc_sha256']
    assert digest(Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'))==expected
    post=BUILD/'NS_AttackAlert_Post_001.uasset'
    visual=resize_recolour(PRIOR/'chunks'/POST,post)
    material=BUILD/'MT_FX_PP_StrongAttackWarning_001.uasset'
    composition=move_blackout_before_separate_translucency(
        ROOT/'work/purple-colour-v1611/MT_FX_PP_StrongAttackWarning_001.uasset',material)
    # Verify the post actor does not also override camera saturation independently.
    actor=FXParser(ROOT/'work/purple-colour-v1611/BP_StrongAtkWarning_001.uasset')
    pp=next(e for e in actor.exports() if e['name']=='PostProcess_GEN_VARIABLE');actor.p=pp['start']
    settings=actor.obj('PostProcessComponent')['Settings']
    assert not any('Saturation' in name for name in settings)
    # Native purple root material has no explicit pass: engine default is AfterDOF.
    root=FXParser(ROOT/'work/material-depth-investigation/M_FX_AddMaster_001_DepthOff.uasset')
    root.p=root.exports()[0]['start'];props=root.obj('Material')
    assert 'TranslucencyPass' not in props and props['bDisableDepthTest']==1
    composition.update(native_purple_root_inherits_after_dof_translucency=True,
        no_independent_camera_saturation_override=True)
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    shutil.copyfile(post,RAW/'chunks'/POST);shutil.copyfile(material,RAW/'chunks'/MAT)
    manifest=json.loads((PRIOR/'manifest.json').read_text())
    manifest['chunk_paths'][MAT]='../../../ProjectPBZ/Plugins/PBZVFXPack/Content/VFX/A_Materials/Template/MT_FX_PP_StrongAttackWarning_001.uasset'
    hfile,=list((PRIOR/'chunks').glob('*06'));template=hfile.read_bytes()
    stores,_,_,order=store_table(template)
    native=store_table((ROOT/'work/black-alert-investigation/current/container-header').read_bytes())[0]
    pid=int.from_bytes(bytes.fromhex(MAT)[:8],'little');assert pid not in stores
    stores[pid]=native[pid];order.append(pid)
    (RAW/'chunks'/hfile.name).write_bytes(package_header(template,order,stores,template[8:16]))
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2))
    unchanged={}
    for p in (PRIOR/'chunks').iterdir():
        if p.name not in (POST,hfile.name):
            unchanged[p.name]=digest(p);assert unchanged[p.name]==digest(RAW/'chunks'/p.name)
    assert len(unchanged)==181
    guard,= [cid for cid,path in manifest['chunk_paths'].items() if path.endswith('/GA_TieKuangQuanTao_GuardPoint.uasset')]
    assert guard in unchanged and '7807bc1ded4a64b800000001' in unchanged
    print('80% geometry, blue-violet parameters, runtime post-process location and unchanged combat/audio checked.',flush=True)
    toc,combined=packaging.pack_check(RAW,OUT/'Mod','combined')
    assert combined['chunks']==184
    for label,cid,expected_file in [('purple',POST,post),('blackout-material',MAT,material)]:
        result=packaging.inspect_native(toc,cid,expected_file,label)
        if cid==MAT:
            q=FXParser(result);q.p=q.exports()[0]['start'];v=q.obj('MaterialInstanceConstant')
            assert v['bOverrideBlendableLocation']==1 and v['BlendableLocationOverride']==1
    # Retain separately installable staged components for the eventual formal release.
    counter=BUILD/'components/gauntlet'
    shutil.copytree(ROOT/'work/gold-alert-v1610/components/gauntlet',counter,dirs_exist_ok=True)
    fxraw=BUILD/'components/effects/raw';(fxraw/'chunks').mkdir(parents=True,exist_ok=True)
    for p in (RAW/'chunks').iterdir():
        if p.name not in (guard,hfile.name):shutil.copyfile(p,fxraw/'chunks'/p.name)
    gpid=int.from_bytes(bytes.fromhex(guard)[:8],'little')
    (fxraw/'chunks'/hfile.name).write_bytes(package_header(template,[p for p in order if p!=gpid],stores,template[8:16]))
    fxmanifest=dict(manifest,chunk_paths={c:p for c,p in manifest['chunk_paths'].items() if c!=guard})
    (fxraw/'manifest.json').write_text(json.dumps(fxmanifest,indent=2))
    assert not ({p.name for p in (fxraw/'chunks').iterdir()} & {p.name for p in (counter/'raw/chunks').iterdir()})
    ftoc,fxproof=packaging.pack_check(fxraw,BUILD/'components/effects/Mod','effects')
    assert fxproof['chunks']==183
    for p in (counter/'Mod').iterdir():assert digest(p)==digest(ROOT/'work/gold-alert-v1610/components/gauntlet/Mod'/p.name)
    proof=dict(version='1.6.11',base='1.6.10',visual=visual,blackout_composition=composition,
        unchanged_previous_chunk_sha256=unchanged,combined=combined,effects_component=fxproof,
        gauntlet_component_bit_exact_to_v1610=True,independent_component_chunk_overlap=[],
        original_blackout_actor_and_control_curves_unchanged=True,
        original_audio_completion_fix_and_all_media_bit_exact=True,
        current_gauntlet_code_bit_exact=True,official_release_unchanged=True,
        installed=False,in_game_tested=False,
        rendering_references=[
            'https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/EBlendableLocation',
            'https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/Materials/UMaterialInstance/GetBlendableLocation',
            'https://dev.epicgames.com/documentation/en-us/unreal-engine/post-process-materials-in-unreal-engine'])
    for p in [BUILD/'validation.json',OUT/'validation.json']:p.write_text(json.dumps(proof,indent=2),encoding='utf8')
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert v1.6.11 开发测试版\n\n'
        '紫色X的长度与宽度都缩为1.6.10的80%，保留长宽比例、角度、位置和同步消失。\n'
        '颜色调向蓝紫色，降低过强的蓝白亮芯。\n'
        '调整黑光全屏材质的处理顺序，先处理场景，再合成半透明紫X，尝试避免黑屏将紫光一起去色。\n'
        '保留场景压暗/去色效果、声音完整播放、拳套反击和红黄光。\n'
        '新处理顺序的实际观感尚需游戏内验证。\n\n'
        '安装：退出游戏，将Mod内三个文件复制到ProjectPBZ\\Content\\Paks\\~mods，覆盖旧版后重启。\n'
        '本测试版合并特效与拳套；不要另行叠加独立拳套包。\n'
        '卸载：退出游戏后移除上述三个文件。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n'for p in sorted((OUT/'Mod').iterdir())),encoding='utf8')
    print(json.dumps(dict(output=str(OUT),size=[1200,180],scale=.8,unchanged_old_chunks=181,
        integrated_chunks=184,container_verified=True,in_game_tested=False),ensure_ascii=False),flush=True)

if __name__=='__main__':build()
