"""Double purple warning size/gain and advance its original ability timeline events."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from parse_fx import FXParser
from inspect_fx_vm import scripts
from build_gold_alert_v160 import digest
from build_yellow_alert_v011 import store_table
from black_timing_v164 import patch_all
from purple_playback_v164 import depth_off,amplify,MONSTER_BULK

BUILD=ROOT/'work/gold-alert-v164'
RAW=BUILD/'raw'
OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.6.4'
POST='7dc2590713fc314d00000001'
LIB_BULK='5aac5b9f482230fd00000002'


def resize(source,destination):
    q=FXParser(source);data=bytearray(q.b);allowed=set();count=0
    for e in q.exports():
        typ='NiagaraSystem'if e['name']=='NS_AttackAlert_Post_001'else'NiagaraEmitter'if e['index']in [10,11]else None
        if not typ:continue
        q.p=e['start'];q.records=[];q.obj(typ)
        for store in [r for r in q.records if r['kind']=='struct'and r['type']in ['NiagaraParameterStore','NiagaraUserRedirectionParameterStore']]:
            value=store['value'];params=value.get('SortedParameterOffsets')or[]
            p=next((p for p in params if p['Name']=='User.PBZ_PSize'),None)
            if p is None:continue
            row=next(r for r in q.records if r['kind']=='value'and r['type']==('Array',('Byte',))
                     and store['start']<=r['start']<r['end']<=store['end']and r['value']==value['ParameterData'])
            at=row['start']+4+p['Offset'];assert struct.unpack_from('<ff',data,at)==(750,60)
            struct.pack_into('<ff',data,at,1500,120);allowed.update(range(at,at+8));count+=1
    assert count==3
    assert all(a==b or i in allowed for i,(a,b)in enumerate(zip(q.b,data)))
    destination.write_bytes(data)
    c=FXParser(destination);assert len(c.exports())==len(q.exports())==24
    for a,b in zip(scripts(source),scripts(destination),strict=True):assert a[3]==b[3]
    for index in [0,1,8,9,12,17,18,19,20]:
        a=q.exports()[index];b=c.exports()[index];assert q.b[a['start']:a['start']+a['size']]==c.b[b['start']:b['start']+b['size']]
    return {'previous_size':[750,60],'new_size':[1500,120],'linear_size_ratio':2,
            'stores_updated':count,'native_export_count_preserved':24,
            'all_original_vm_scripts_and_blackout_curves_bit_exact_v163':True}


def add_stores(header,original,pids_to_add,material_pid):
    stores,base,size,pids=store_table(header);originals=store_table(original)[0]
    post_pid=int.from_bytes(bytes.fromhex(POST)[:8],'little')
    deps,shaders=stores[post_pid];assert len(deps)==32
    stores[post_pid]=(deps[:24]+struct.pack('<Q',material_pid),shaders)
    for pid in pids_to_add:
        assert pid not in stores
        stores[pid]=originals[pid];pids.append(pid)
    entries=bytearray(len(pids)*16);tail=bytearray()
    for i,pid in enumerate(pids):
        for at,data,stride in [(0,stores[pid][0],8),(8,stores[pid][1],20)]:
            if data:
                struct.pack_into('<II',entries,i*16+at,len(data)//stride,len(entries)+len(tail)-(i*16+at));tail.extend(data)
    payload=entries+tail
    b=bytearray(header[:16]+struct.pack('<I',len(pids))+struct.pack('<'+'Q'*len(pids),*pids)
                +struct.pack('<I',len(payload))+payload+header[base+size:])
    struct.pack_into('<q',b,len(b)-20,len(b)-4)
    assert store_table(b)[0]==stores
    return bytes(b)


def build():
    # Timing assets were extracted against this exact game build, not the stale index.
    expected=json.loads((ROOT/'analysis/build-20261105/build.json').read_text())['toc_sha256']
    assert digest(Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'))==expected
    (RAW/'chunks').mkdir(parents=True,exist_ok=True);(OUT/'Mod').mkdir(parents=True,exist_ok=True)
    prior=ROOT/'work/gold-alert-v163/main/raw'
    manifest=json.loads((prior/'manifest.json').read_text())
    for p in (prior/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    visual=resize(prior/'chunks'/POST,RAW/'chunks'/POST)
    visual['visibility']=depth_off(RAW/'chunks'/POST)
    timing=patch_all(RAW/'chunks')
    for row in timing['assets']:manifest['chunk_paths'][row['cid']]='../../../'+row['path']
    native,=list((prior/'chunks').glob('*06'))
    (RAW/'chunks'/native.name).write_bytes(add_stores(native.read_bytes(),(ROOT/'work/black-alert-investigation/current/container-header').read_bytes(),[x['package_id']for x in timing['assets']],visual['visibility']['material_package_id']))
    # Increase the actual media, keeping the stable build's existing bank gain.
    audio=amplify(prior,RAW,BUILD,OUT)
    info=json.loads((ROOT/'work/black-alert-investigation/current/pbz-ziguang-bank-location.json').read_text())
    row,=info['matches'];offset=row['offset'];size=row['size']
    original=(prior/'chunks'/LIB_BULK).read_bytes();bank=bytearray(original[offset:offset+size])
    at=695;bank_gain=struct.unpack_from('<f',bank,at)[0];assert abs(bank_gain-7.3206000328)<1e-5
    assert (RAW/'chunks'/LIB_BULK).read_bytes()==original
    (BUILD/'purple-bank.bnk').write_bytes(bank)
    subprocess.run([sys.executable,str(ROOT/'tools/wwiser/wwiser.py'),'-d','xml','-dn',str(BUILD/'bank-check'),str(BUILD/'purple-bank.bnk')],check=True,capture_output=True)
    tree=ET.parse(BUILD/'bank-check.xml').getroot()
    cn=next(o for o in tree.iter('object')if o.get('name')=='CAkRanSeqCntr'and any(f.get('name')=='ulID'and f.get('value')=='661678587'for f in o.iter('field')))
    vol=next(o for o in cn.iter('object')if o.get('name')=='AkPropBundle'and any(f.get('name')=='pID'and f.get('valuefmt')=='0x00 [Volume]'for f in o.iter('field')))
    assert abs(float(next(f.get('value')for f in vol.iter('field')if f.get('name')=='pValue'))-bank_gain)<1e-6
    assert not list(tree.iter('error'))
    (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2))
    ids=set(manifest['chunk_paths'])|{native.name};assert {p.name for p in (RAW/'chunks').iterdir()}==ids
    unchanged={}
    for p in (prior/'chunks').iterdir():
        if p.name not in {POST,MONSTER_BULK,native.name}:
            assert digest(p)==digest(RAW/'chunks'/p.name);unchanged[p.name]=digest(p)
    retoc=ROOT/'tools/retoc/retoc.exe';toc=OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
    subprocess.run([str(retoc),'pack-raw',str(RAW),str(toc)],check=True)
    shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v1.6.3/Mod/zz_PBZ_YellowAlert_P.pak',toc.with_suffix('.pak'))
    subprocess.run([str(retoc),'verify',str(toc)],check=True)
    check=BUILD/('roundtrip-'+uuid.uuid4().hex[:8]);subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
    assert {p.name for p in (check/'chunks').iterdir()}==ids
    for p in (RAW/'chunks').iterdir():assert digest(p)==digest(check/'chunks'/p.name),p.name
    # Original ability headers are exact; inspect a complete boss timeline plus the FX root independently.
    sample=next(x for x in timing['assets']if x['path'].endswith('GA_LuanShi_SpecialAttack_She_03A.uasset'))
    for label,cid in [('post',POST),('boss-timeline',sample['cid'])]:
        dest=BUILD/('inspect-'+label);dest.mkdir(exist_ok=True)
        subprocess.run([str(retoc),'dump-test',str(toc),str(dest),str(int.from_bytes(bytes.fromhex(cid)[:8],'little'))],check=True,capture_output=True)
        extracted,=dest.glob('*.uasset');assert digest(extracted)==digest(RAW/'chunks'/cid)
    evidence={'version':'1.6.4','base':'v1.6.3, confirmed no longer crashing by user',
              'visual':visual,'audio':audio,'audio_bank_gain_db':bank_gain,
              'timing':timing,'unchanged_base_chunk_sha256':unchanged,'container_verify':True,
              'raw_roundtrip_exact':True,'native_package_header_parser_checked':True,
              'source_game_toc_sha256':expected,'roundtrip_directory':str(check),'in_game_tested':False,'installed':False}
    (BUILD/'validation.json').write_text(json.dumps(evidence,indent=2));(OUT/'validation.json').write_text(json.dumps(evidence,indent=2))
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert v1.6.4 开发测试版\n\n'
        '基于已确认不闪退的1.6.3，保留黑光全屏变暗和紫色45度X形预警。\n'
        '紫光音效实际音频平均幅度为1.6.3的2倍，使用柔和峰值限制避免爆音。\n'
        '紫光长度和宽度均为1.6.3的2倍，采用穿透显示材质以免被人物模型遮挡。\n'
        '黑光预警的声音和光效触发时间整体提前100ms；原本距招式起点不足100ms的预警提前到起点。\n'
        '红黄光保持正式版1.1的外观和声音，攻击伤害、格挡判定及动画不变。\n'
        '当前通过离线校验，尚需游戏内测试。\n\n'
        '安装：完全退出游戏，将Mod内三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods，替换旧版同名文件，然后重新启动游戏。\n'
        '卸载：退出游戏后移除这三个文件。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n'for p in sorted((OUT/'Mod').iterdir())))
    print(json.dumps({'output':str(OUT),'audio_pcm_rms_ratio':audio['actual_pcm_rms_ratio'],'size_ratio':2,'timing_assets':len(timing['assets']),
                      'full_100ms_events':timing['full_100ms_events'],'limited_to_start':len(timing['limited_events']),
                      'already_at_start':len(timing['already_at_start_events']),'verified':True,'in_game_tested':False},ensure_ascii=False))


if __name__=='__main__':build()
