"""Keep bank location/size and every existing Wwise ID while repairing v165."""
import json,struct,subprocess,shutil,sys,uuid
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from build_gold_alert_v165 import hirc_objects,table,CONTAINER,SOUNDS,MEDIAS,CACHES,EVENT
from purple_visual_v166 import patch as patch_visual

BUILD=ROOT/'work/gold-alert-v166';RAW=BUILD/'raw';OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.6.6'
PRIOR=ROOT/'work/gold-alert-v165/raw';STABLE=ROOT/'work/gold-alert-v164/raw'
MONSTER='e769c85cabe3aa8400000001';MONSTER_BULK='e769c85cabe3aa8400000002'
LIB='5aac5b9f482230fd00000001';LIB_BULK='5aac5b9f482230fd00000002';POST='7dc2590713fc314d00000001'


def same_size_bank(original,lengths):
    at,n,objects=hirc_objects(original);rebuilt=[]
    for kind,oid,body in objects:
        b=bytearray(body)
        if oid in SOUNDS:
            i=SOUNDS.index(oid)
            assert kind==2 and struct.unpack_from('<I',b,9)[0]==MEDIAS[i]
            assert struct.unpack_from('<I',b,13)[0]==CACHES[i]
            struct.pack_into('<I',b,4,0x10001);struct.pack_into('<I',b,17,lengths[i])
            struct.pack_into('<I',b,30,CONTAINER)
        elif oid==CONTAINER:
            assert kind==5 and len(b)==148
            assert b[128]==0 and struct.unpack_from('<I',b,130)[0]==1
            struct.pack_into('<H',b,124,0)
            b=b[:130]+struct.pack('<IIIHIIII',2,*SOUNDS,2,SOUNDS[0],50000,SOUNDS[1],50000)
        elif oid==778311897:
            assert kind==5 and len(b)==83
            assert struct.unpack_from('<I',b,65)[0]==1 and struct.unpack_from('<H',b,73)[0]==1
            # Keep its identity and parent link, but transfer its sound to the
            # active random container. Removing its child+playlist saves 12 B,
            # exactly balancing the 12 B added to the active random container.
            struct.pack_into('<H',b,59,0)
            b=b[:65]+struct.pack('<IH',0,0)
        elif oid==800828386:assert struct.unpack_from('<I',b,6)[0]==CONTAINER
        rebuilt.append((kind,oid,bytes(b)))
    assert [(k,i) for k,i,_ in objects]==[(k,i) for k,i,_ in rebuilt]
    payload=struct.pack('<I',len(rebuilt))+b''.join(struct.pack('<BI',k,len(b))+b for k,_,b in rebuilt)
    assert len(payload)==n
    result=original[:at]+b'HIRC'+struct.pack('<I',n)+payload+original[at+8+n:]
    assert len(result)==len(original)==1609
    return result


def validate(bank):
    path=BUILD/'purple-bank.bnk';path.write_bytes(bank)
    subprocess.run([sys.executable,str(ROOT/'tools/wwiser/wwiser.py'),'-d','xml','-dn',str(BUILD/'bank-check'),str(path)],check=True,capture_output=True)
    root=ET.parse(BUILD/'bank-check.xml').getroot();assert not list(root.iter('error'))
    objects=root.findall('.//list[@name="listLoadedItem"]/object')
    nodes={int(f.get('value')):o for o in objects if (f:=o.find('field[@name="ulID"]')) is not None}
    def values(node,name):return [f.get('value') for f in node.iter('field') if f.get('name')==name]
    active=nodes[CONTAINER]
    assert values(active,'eMode')==['0'] and values(active,'sLoopCount')==['1']
    assert values(active,'ulNumChilds')==['2'] and values(active,'ulPlayListItem')==['2']
    assert list(map(int,values(active,'ulChildID')))==SOUNDS and list(map(int,values(active,'ulPlayID')))==SOUNDS
    assert values(active,'weight')==['50000','50000']
    assert values(nodes[800828386],'idExt')==[str(CONTAINER)]
    assert values(nodes[EVENT],'ulActionID')==['800828386']
    assert values(nodes[778311897],'ulNumChilds')==['0'] and values(nodes[778311897],'ulPlayListItem')==['0']
    assert list(map(int,values(nodes[382141041],'ulChildID')))==[CONTAINER,778311897]
    for sid,mid,cache in zip(SOUNDS,MEDIAS,CACHES,strict=True):
        assert values(nodes[sid],'ulPluginID')==['65537']
        assert values(nodes[sid],'sourceID')==[str(mid)] and values(nodes[sid],'cacheID')==[str(cache)]
        assert values(nodes[sid],'DirectParentID')==[str(CONTAINER)]
    # A sound belongs to one parent only; each declared parent's child list agrees.
    for oid,node in nodes.items():
        for child in values(node,'ulChildID'):
            child=int(child)
            if child in nodes:assert values(nodes[child],'DirectParentID')==[str(oid)]
    return dict(wwiser_parse=True,equal_random_weights=[50000,50000],one_variant_per_trigger=True,
        bank_bytes=1609,all_original_object_ids_retained=True,parent_child_links_consistent=True,
        original_bank_offset_and_size_preserved=True,random_mode=0)


def build():
    (RAW/'chunks').mkdir(parents=True,exist_ok=True);(OUT/'Mod').mkdir(parents=True,exist_ok=True)
    for p in (PRIOR/'chunks').iterdir():shutil.copyfile(p,RAW/'chunks'/p.name)
    shutil.copyfile(PRIOR/'manifest.json',RAW/'manifest.json')
    visual=patch_visual(PRIOR/'chunks'/POST,RAW/'chunks'/POST)
    # Restore native library metadata and bank placement from the audible build.
    original=(STABLE/'chunks'/LIB_BULK).read_bytes();offset=155099039;length=1609
    media=[(ROOT/f'work/gold-alert-v165/purple-variant-{i}.wem').read_bytes() for i in [1,2]]
    bank=same_size_bank(original[offset:offset+length],[len(x) for x in media]);bank_check=validate(bank)
    result=original[:offset]+bank+original[offset+length:]
    assert len(result)==len(original)
    assert result[:offset]==original[:offset] and result[offset+length:]==original[offset+length:]
    (RAW/'chunks'/LIB_BULK).write_bytes(result)
    shutil.copyfile(STABLE/'chunks'/LIB,RAW/'chunks'/LIB)
    # Confirm both approved media are reached through the native cache map.
    q=(RAW/'chunks'/MONSTER).read_bytes();m=table(RAW/'chunks'/MONSTER)
    bulk=(RAW/'chunks'/MONSTER_BULK).read_bytes()
    for index,wem in zip([145,10157],media,strict=True):
        at,_,size,flags,idx=struct.unpack_from('<qqqIB3x',q,m+index*32)
        assert flags==66817 and idx==0 and size==len(wem) and bulk[at:at+size]==wem
    assert digest(RAW/'chunks'/LIB)==digest(STABLE/'chunks'/LIB)
    unchanged={}
    for p in (PRIOR/'chunks').iterdir():
        if p.name not in {POST,LIB,LIB_BULK}:
            assert digest(p)==digest(RAW/'chunks'/p.name);unchanged[p.name]=digest(p)
    assert len(unchanged)==178
    retoc=ROOT/'tools/retoc/retoc.exe';toc=OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
    subprocess.run([str(retoc),'pack-raw',str(RAW),str(toc)],check=True)
    shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v1.6.5/Mod/zz_PBZ_YellowAlert_P.pak',toc.with_suffix('.pak'))
    subprocess.run([str(retoc),'verify',str(toc)],check=True)
    check=BUILD/('roundtrip-'+uuid.uuid4().hex[:8]);subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
    expected={p.name for p in (RAW/'chunks').iterdir()};assert expected=={p.name for p in (check/'chunks').iterdir()}
    for p in (RAW/'chunks').iterdir():assert digest(p)==digest(check/'chunks'/p.name),p.name
    for cid in [POST,LIB]:
        dest=BUILD/('inspect-'+cid);dest.mkdir(exist_ok=True)
        subprocess.run([str(retoc),'dump-test',str(toc),str(dest),str(int.from_bytes(bytes.fromhex(cid)[:8],'little'))],check=True,capture_output=True)
        extracted,=dest.glob('*.uasset');assert digest(extracted)==digest(RAW/'chunks'/cid)
    proof=dict(version='1.6.6',base='official v1.1 development line / v1.6.5 audio-correction',
        reported_regression='v1.6.5 is completely silent in game',
        audio_fix_hypothesis='Restore bank in-place layout and metadata from audible v164; preserve every Wwise object ID. Runtime cause remains unconfirmed.',
        bank=bank_check,approved_v165_media_pcm_bit_exact=True,media_source='native ZZZ media108729793, two user-approved variants',
        library_metadata_bit_exact_v164=True,visual=visual,unchanged_chunk_sha256=unchanged,
        container_verify=True,raw_roundtrip_exact=True,roundtrip_directory=str(check),
        native_package_header_parser_checked=True,in_game_tested=False,installed=False)
    (BUILD/'validation.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    (OUT/'validation.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    shutil.copytree(ROOT/'outputs/PBZ-Gold-Alert-v1.6.5/Preview',OUT/'Preview',dirs_exist_ok=True)
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert v1.6.6 开发测试版\n\n'
        '黑光攻击显示紫色45度X形预警，保留全屏变暗效果。\n'
        '紫色光条加粗25%，中心向上移动到头顶附近。\n'
        '使用两种已确认的绝区零紫光提示音，每次随机播放其中一种。\n'
        '保留增强音量、穿透显示、提前100毫秒和正式版1.1的红黄光效果。\n\n'
        '安装：完全退出游戏，将Mod内三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods，替换旧版同名文件，随后重启游戏。\n'
        '卸载：退出游戏后移除上述三个文件。\n',encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n' for p in sorted((OUT/'Mod').iterdir())),encoding='utf-8')
    print(json.dumps(dict(output=str(OUT),bank=bank_check,visual=visual,verified=True,in_game_tested=False)),flush=True)


if __name__=='__main__':build()
