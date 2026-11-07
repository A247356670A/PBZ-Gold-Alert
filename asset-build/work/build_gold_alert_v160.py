"""Build the 1.1 development-line black-warning visual test, without installing it."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'analysis'), str(ROOT/'work')]
from build_yellow_alert_v011 import store_table
from purple_warning_v160 import patch

BUILD = ROOT/'work/gold-alert-v160'
RAW = BUILD/'raw'
OUT = ROOT/'outputs/PBZ-Gold-Alert-v1.6.0-Visual-Test'
POST = '7dc2590713fc314d00000001'
BLUE = 'b21b224afd0ed4a800000001'


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def add_clone_store(header, new_cid, template_cid):
    stores, base, size, pids = store_table(header)
    new_pid = int.from_bytes(bytes.fromhex(new_cid)[:8], 'little')
    template_pid = int.from_bytes(bytes.fromhex(template_cid)[:8], 'little')
    assert new_pid not in stores
    stores[new_pid] = stores[template_pid]
    pids.append(new_pid)
    entries = bytearray(len(pids)*16)
    tail = bytearray()
    for i, pid in enumerate(pids):
        packages, shaders = stores[pid]
        for at, data, stride in ((0, packages, 8), (8, shaders, 20)):
            if data:
                struct.pack_into('<II', entries, i*16+at, len(data)//stride,
                                 len(entries)+len(tail)-(i*16+at))
                tail.extend(data)
    payload = entries+tail
    result = bytearray(header[:16]+struct.pack('<I', len(pids))
                       +struct.pack('<'+'Q'*len(pids), *pids)
                       +struct.pack('<I', len(payload))+payload+header[base+size:])
    struct.pack_into('<q', result, len(result)-20, len(result)-4)
    assert store_table(result)[0] == stores
    return bytes(result)


def build():
    prior = ROOT/'work/gold-alert-v157/raw'
    (RAW/'chunks').mkdir(parents=True, exist_ok=True)
    (OUT/'Mod').mkdir(parents=True, exist_ok=True)
    visual = patch(BUILD/'purple-post.uasset')
    manifest = json.loads((prior/'manifest.json').read_text())
    baseline = {}
    for source in (prior/'chunks').iterdir():
        destination = RAW/'chunks'/source.name
        if source.name.endswith('06'):
            destination.write_bytes(add_clone_store(source.read_bytes(), POST, BLUE))
        else:
            shutil.copyfile(source, destination)
            baseline[source.name] = digest(source)
            assert digest(destination) == baseline[source.name]
    shutil.copyfile(BUILD/'purple-post.uasset', RAW/'chunks'/POST)
    manifest['chunk_paths'][POST] = '../../../ProjectPBZ/Plugins/PBZVFXPack/Content/VFX/BattleFX/Common/NS_AttackAlert_Post_001.uasset'
    (RAW/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    expected = set(baseline) | {POST} | {p.name for p in (prior/'chunks').glob('*06')}
    assert {p.name for p in (RAW/'chunks').iterdir()} == expected
    retoc = ROOT/'tools/retoc/retoc.exe'
    toc = OUT/'Mod/zz_PBZ_YellowAlert_P.utoc'
    subprocess.run([str(retoc), 'pack-raw', str(RAW), str(toc)], check=True)
    shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v1.5.7/Mod/zz_PBZ_YellowAlert_P.pak', toc.with_suffix('.pak'))
    subprocess.run([str(retoc), 'verify', str(toc)], check=True)
    roundtrip = BUILD/'roundtrip'
    subprocess.run([str(retoc), 'unpack-raw', str(toc), str(roundtrip)], check=True)
    assert {p.name for p in (roundtrip/'chunks').iterdir()} == expected
    for p in (RAW/'chunks').iterdir():
        assert digest(p) == digest(roundtrip/'chunks'/p.name), p.name
    evidence = {
        'version': '1.6.0 visual test',
        'base': 'official v1.1 / development v1.5.7',
        'purple_visual': visual,
        'unchanged_baseline_chunk_sha256': baseline,
        'template_import_dependency_order_preserved': True,
        'container_verify': True,
        'raw_roundtrip_exact': True,
        'audio_status': 'Original PBZ black-warning sound retained; requested Vesper purple cue not yet identified.',
        'in_game_tested': False,
        'installed': False,
    }
    (BUILD/'validation.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
    (OUT/'validation.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
    (OUT/'README.txt').write_text(
        'PBZ Gold Alert v1.6.0 - 紫色 X 形黑光预警：视觉测试版\n\n'
        '以正式版 1.1 为基础，保留原有红黄光；将黑光预警替换为紫色 X 形光条。\n'
        '当前仍使用游戏原有黑光音效，尚未加入叛律孤歌的紫光提示音。\n'
        '此版本仅完成离线资源和封装校验，仍需游戏内测试。\n\n'
        '安装：退出游戏，将 Mod 文件夹内三个同名文件一起放入游戏的\n'
        'ProjectPBZ\\Content\\Paks\\~mods 文件夹。\n'
        '用它替换已有的 zz_PBZ_YellowAlert_P 三个文件，不要同时安装旧版。\n'
        '卸载：退出游戏后移除这三个文件。\n', encoding='utf-8-sig')
    (OUT/'SHA256SUMS.txt').write_text(''.join(
        digest(p)+'  Mod/'+p.name+'\n' for p in sorted((OUT/'Mod').iterdir())), encoding='utf8')
    print(json.dumps({'output': str(OUT), 'verified': True, 'baseline_preserved': len(baseline),
                      'requested_audio_pending': True}, ensure_ascii=False))


if __name__ == '__main__':
    build()
