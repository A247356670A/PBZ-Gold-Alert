"""Integrated dev test plus separately packable gauntlet component.

No official release folders are changed. Native dependencies are copied from
the matching original game, while all v1.6.8 FX/audio chunks stay bit exact.
"""
from pathlib import Path
import json,shutil,struct,subprocess,sys,uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from build_yellow_alert_v011 import store_table
from gauntlet_counter_v169 import patch,decode_functions,kismet
from verify_gauntlet_counter_v169 import verify
from read_pbz import Reader

BUILD=ROOT/'work/gold-alert-v169'
RAW=BUILD/'combined/raw'
OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.6.9'
PRIOR=ROOT/'work/gold-alert-v168/raw'
RETOC=ROOT/'tools/retoc/retoc.exe'
ORIGINAL_HEADER=ROOT/'work/black-alert-investigation/current/container-header'
GAME_PAKS=Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks')

def run(args,log):
    r=subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf8',errors='replace')
    log.parent.mkdir(parents=True,exist_ok=True)
    log.write_text(r.stdout+r.stderr,encoding='utf8')
    if r.returncode:raise RuntimeError(f'{args[1]} failed: {log}')

def package_header(template,ordered_ids,stores,container_id):
    old_stores,base,size,_=store_table(template)
    table=bytearray(len(ordered_ids)*16);tail=bytearray()
    for i,pid in enumerate(ordered_ids):
        for offset,data,stride in [(0,stores[pid][0],8),(8,stores[pid][1],20)]:
            if data:
                struct.pack_into('<II',table,i*16+offset,len(data)//stride,len(table)+len(tail)-(i*16+offset))
                tail.extend(data)
    payload=table+tail
    header=bytearray(template[:8]+container_id+struct.pack('<I',len(ordered_ids))
        +struct.pack('<'+'Q'*len(ordered_ids),*ordered_ids)+struct.pack('<I',len(payload))
        +payload+template[base+size:])
    # Both patch containers use the verified empty localization/redirect sections.
    assert template[base+size:-20]==bytes(20)
    assert template[-4:]==bytes(4)
    struct.pack_into('<q',header,len(header)-20,len(header)-4)
    assert store_table(header)[0]=={p:stores[p] for p in ordered_ids}
    assert header[8:16]==container_id
    return bytes(header)

def verify_container(raw,toc,label):
    run([RETOC,'verify',toc],BUILD/(label+'-verify.log'))
    dest=BUILD/(label+'-roundtrip-'+uuid.uuid4().hex[:8])
    run([RETOC,'unpack-raw',toc,dest],BUILD/(label+'-roundtrip.log'))
    a={p.name:p for p in (raw/'chunks').iterdir()};b={p.name:p for p in (dest/'chunks').iterdir()}
    assert a.keys()==b.keys()
    hashes={}
    for cid,p in a.items():
        hashes[cid]=digest(p);assert hashes[cid]==digest(b[cid]),cid
    header,=list((raw/'chunks').glob('*06'))
    assert header.read_bytes()[8:16]==toc.read_bytes()[56:64]
    assert bytes.fromhex(header.name)[:8]==toc.read_bytes()[56:64]
    return dict(container_verified=True,raw_roundtrip_exact=True,chunks=len(a),sha256=hashes)

def build():
    OUT.mkdir(parents=True,exist_ok=True);BUILD.mkdir(parents=True,exist_ok=True)
    expected=json.loads((ROOT/'analysis/build-20261105/build.json').read_text())['toc_sha256']
    assert digest(GAME_PAKS/'ProjectPBZ-Windows.utoc')==expected
    prior_proof=json.loads((ROOT/'outputs/PBZ-Gold-Alert-v1.6.8/validation.json').read_text())
    original,= [x for x in json.loads((ROOT/'work/gauntlet-parry-investigation/manifest.json').read_text())
                 if x['path'].endswith('/GA_TieKuangQuanTao_GuardPoint.uasset')]
    cid=original['cid'];pid=int.from_bytes(bytes.fromhex(cid)[:8],'little')
    source=ROOT/original['file'];assert digest(source)==original['sha256']
    r=Reader();assert digest_bytes(r.read(original['index']))==original['sha256']
    modified=BUILD/'GA_TieKuangQuanTao_GuardPoint.uasset'
    before,after,patch_proof=patch(source,modified)
    flow=verify(before,after)
    (BUILD/'guardpoint-bytecode-patched.json').write_text(json.dumps(after,indent=2),encoding='utf8')
    text=[]
    for fn in after:
        text.append('\n'+fn['function'])
        text.extend(f"{n['offset']:04x}: {kismet.render(n)}" for n in fn['expressions'])
    (BUILD/'guardpoint-bytecode-patched.txt').write_text('\n'.join(text),encoding='utf8')
    print('Native gauntlet patch and 320 bytecode scenarios verified.',flush=True)

    # Create the actual independent resource component now, staged in work only.
    standalone=BUILD/'gauntlet-component';sraw=standalone/'raw';smod=standalone/'Mod'
    (sraw/'chunks').mkdir(parents=True,exist_ok=True);smod.mkdir(exist_ok=True)
    (sraw/'chunks'/cid).write_bytes(modified.read_bytes())
    manifest=json.loads((PRIOR/'manifest.json').read_text());spath='../../../'+original['path']
    smanifest=dict(manifest,chunk_paths={cid:spath})
    (sraw/'manifest.json').write_text(json.dumps(smanifest,indent=2),encoding='utf8')
    stoc=smod/'zz_PBZ_GauntletCounter_P.utoc'
    # Bootstrap obtains retoc's exact UTF16 CityHash container identity.
    run([RETOC,'pack-raw',sraw,stoc],BUILD/'standalone-bootstrap.log')
    sid=stoc.read_bytes()[56:64]
    old_header,=list((PRIOR/'chunks').glob('*06'));template=old_header.read_bytes()
    stores,_,_,order=store_table(template);native=store_table(ORIGINAL_HEADER.read_bytes())[0]
    assert pid not in stores
    sheader=package_header(template,[pid],native,sid)
    schunk=(sid+bytes(3)+b'\x06').hex();(sraw/'chunks'/schunk).write_bytes(sheader)
    run([RETOC,'pack-raw',sraw,stoc],BUILD/'standalone-pack.log')
    shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v1.6.8/Mod/zz_PBZ_YellowAlert_P.pak',stoc.with_suffix('.pak'))
    standalone_proof=verify_container(sraw,stoc,'standalone')
    assert set(store_table(sheader)[0])=={pid}

    # Integrated development build: one additional gameplay package; old FX untouched.
    (RAW/'chunks').mkdir(parents=True,exist_ok=True);(OUT/'Mod').mkdir(exist_ok=True)
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    shutil.copyfile(modified,RAW/'chunks'/cid)
    stores[pid]=native[pid];order.append(pid)
    header=package_header(template,order,stores,template[8:16])
    (RAW/'chunks'/old_header.name).write_bytes(header)
    manifest['chunk_paths'][cid]=spath
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    unchanged={}
    for p in (PRIOR/'chunks').iterdir():
        if p.name==old_header.name:continue
        unchanged[p.name]=digest(p);assert unchanged[p.name]==digest(RAW/'chunks'/p.name)
    assert len(unchanged)==180
    toc=OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
    print('Packing integrated v1.6.9, preserving all previous FX/audio resources.',flush=True)
    run([RETOC,'pack-raw',RAW,toc],BUILD/'combined-pack.log')
    shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v1.6.8/Mod/zz_PBZ_YellowAlert_P.pak',toc.with_suffix('.pak'))
    combined_proof=verify_container(RAW,toc,'combined')
    assert combined_proof['chunks']==182
    # The separately installable gauntlet and original FX container have no overlapping chunks.
    assert not ({p.name for p in (PRIOR/'chunks').iterdir()} & {p.name for p in (sraw/'chunks').iterdir()})
    for label,pack in [('combined',toc),('standalone',stoc)]:
        dest=BUILD/(label+'-native-inspect');dest.mkdir(exist_ok=True)
        run([RETOC,'dump-test',pack,dest,str(pid)],BUILD/(label+'-native-inspect.log'))
        result,=dest.glob('*.uasset');assert digest(result)==digest(modified)
        _,decoded=decode_functions(result);assert verify(before,decoded)==flow
    proof=dict(version='1.6.9',base='v1.6.8',source_game_toc_sha256=expected,
        changed_gameplay_asset=original['path'],gauntlet_patch=patch_proof,bytecode_flow=flow,
        unchanged_v168_fx_audio_and_timing_chunk_sha256=unchanged,
        combined=combined_proof,standalone=standalone_proof,
        independent_component_staged=str(standalone),fx_and_gauntlet_chunk_overlap=[],
        original_native_gauntlet_dependency_and_shader_tables_preserved=True,
        all_official_release_directories_untouched=True,installed=False,in_game_tested=False)
    (BUILD/'validation.json').write_text(json.dumps(proof,indent=2),encoding='utf8')
    (OUT/'validation.json').write_text(json.dumps(proof,indent=2),encoding='utf8')
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert v1.6.9 开发测试版\n\n'
        '拳套：使用L1+R2成功招架黑光攻击后自动进入反击，不再受原反击距离和飞行物排除限制。\n'
        '仍需按原有时机完成招架；不自动按键，不扩大招架窗口。其他攻击沿用原反击规则。\n'
        '保留拳套原反击伤害、拳意和暗源返还流程。远距离反击实际位移和命中尚需游戏内测试。\n'
        '特效：保留1.6.8全部红黄光、紫色45度X形预警、同步消失、头顶位置、穿透显示、黑屏与声音。\n\n'
        '安装：完全退出游戏，将Mod内三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods，覆盖旧版同名文件后启动游戏。\n'
        '本测试版将拳套改动与预警特效合并；请不要叠加独立拳套包。\n'
        '卸载：退出游戏后移除上述三个文件。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n' for p in sorted((OUT/'Mod').iterdir())),encoding='utf8')
    (OUT/'CHANGELOG.txt').write_text(
        'v1.6.9\n- 新增拳套成功招架黑光后的自动反击，解除该分支的距离和飞行物限制。\n'
        '- 保留其他来招规则、拳套伤害、拳意和返还次数逻辑。\n'
        '- 完整保留v1.6.8预警特效与音频。\n'
        '- 正式版可独立封装预警特效与拳套反击；当前仅生成合并开发测试版。\n',encoding='utf-8-sig')
    print(json.dumps(dict(output=str(OUT),flow_cases=flow['bytecode_control_flow_cases'],
        combined_chunks=combined_proof['chunks'],standalone_chunks=standalone_proof['chunks'],
        standalone_bytes=sum(p.stat().st_size for p in smod.iterdir()),
        verified=True,in_game_tested=False),ensure_ascii=False),flush=True)

def digest_bytes(b):
    import hashlib
    return hashlib.sha256(b).hexdigest()

if __name__=='__main__':build()
