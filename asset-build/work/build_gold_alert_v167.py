"""Discriminating audio recovery/control: exact v164 layout versus native audio.

A changes only PCM samples within the already-existing v164 WEM allocation.
B restores native black-warning bank/media while retaining the 1.1 gold alerts.
Both retain v166's visual and warning timing. No install is performed.
"""
from pathlib import Path
import json,struct,shutil,subprocess,sys,uuid,wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis'),str(ROOT/'work')]
from build_gold_alert_v160 import digest
from build_gold_alert_v165 import table

BUILD=ROOT/'work/gold-alert-v167';OUT=ROOT/'outputs/PBZ-Gold-Alert-v1.6.7-Audio-Test'
VISUAL=ROOT/'work/gold-alert-v166/raw';AUDIBLE=ROOT/'work/gold-alert-v164/raw'
NATIVE=ROOT/'work/black-alert-investigation/current'
MONSTER='e769c85cabe3aa8400000001';MONSTER_BULK='e769c85cabe3aa8400000002'
LIB='5aac5b9f482230fd00000001';LIB_BULK='5aac5b9f482230fd00000002'
POST='7dc2590713fc314d00000001'


def build_one(label,control):
    folder=OUT/label;build=BUILD/label;raw=build/'raw'
    (raw/'chunks').mkdir(parents=True,exist_ok=True);(folder/'Mod').mkdir(parents=True,exist_ok=True)
    for p in (VISUAL/'chunks').iterdir():shutil.copyfile(p,raw/'chunks'/p.name)
    shutil.copyfile(VISUAL/'manifest.json',raw/'manifest.json')
    proof=dict(version='1.6.7 audio isolation test',variant=label,visual_base='v166',
        random_playback_enabled=False,random_playback_deferred_until_silence_isolated=True,
        no_recording_samples_used=True,blackout_and_purple_head_position_and_thickness_preserved=True,
        warning_advance_100ms_preserved=True,source_game_audio_not_replaced_by_recording=True)
    if not control:
        for cid in [MONSTER,LIB,LIB_BULK]:shutil.copyfile(AUDIBLE/'chunks'/cid,raw/'chunks'/cid)
        old=(AUDIBLE/'chunks'/MONSTER_BULK).read_bytes();asset=(AUDIBLE/'chunks'/MONSTER).read_bytes()
        m=table(AUDIBLE/'chunks'/MONSTER)
        off,_,length,flags,index=struct.unpack_from('<qqqIB3x',asset,m+145*32)
        assert (off,length,flags,index)==(781392768,396896,66817,0)
        wem=old[off:off+length];assert wem[88:92]==b'data'
        assert struct.unpack_from('<I',wem,92)[0]==len(wem)-96
        approved=(ROOT/'work/gold-alert-v165/purple-variant-2.wem').read_bytes()
        assert approved[:4]==b'RIFF' and approved[88:92]==b'data'
        pcm=approved[96:];assert len(pcm)<=length-96 and len(pcm)%4==0
        pcm+=b'\0'*(length-96-len(pcm))
        replacement=wem[:96]+pcm
        result=old[:off]+replacement+old[off+length:]
        assert len(result)==len(old)
        assert result[:off+96]==old[:off+96] and result[off+length:]==old[off+length:]
        (raw/'chunks'/MONSTER_BULK).write_bytes(result)
        (build/'approved-padded.wem').write_bytes(replacement)
        preview=folder/'Preview';preview.mkdir(exist_ok=True)
        decoded=preview/'Purple-Processed.wav'
        subprocess.run([str(ROOT/'tools/vgmstream/vgmstream-cli.exe'),'-i','-o',str(decoded),str(build/'approved-padded.wem')],check=True,capture_output=True)
        with wave.open(str(decoded),'rb') as f:
            assert (f.getnchannels(),f.getframerate(),f.getsampwidth())==(2,48000,2)
            assert f.readframes(f.getnframes())==pcm
        amplitude=np.frombuffer(pcm,'<i2').astype(float)/32768
        proof.update(audio='user-confirmed processed native ZZZ purple hint, fixed single variant',
            reference_audio_base='v164 (previously reported wrong sound, rather than silent)',
            all_bank_bytes_and_native_metadata_bit_exact_v164=True,
            existing_primary_media_allocation=dict(offset=off,bytes=length,header_bytes_unchanged=96),
            only_primary_pcm_samples_changed_v164=True,total_monster_bulk_size_unchanged=True,
            independent_decoder_pcm_exact=True,peak=float(abs(amplitude).max()),
            first_500ms_rms=float(np.sqrt(np.mean(amplitude[:48000]**2))))
        unchanged_audio=[MONSTER,LIB,LIB_BULK]
        for cid in unchanged_audio:assert digest(raw/'chunks'/cid)==digest(AUDIBLE/'chunks'/cid)
    else:
        for cid,name in [(MONSTER,'SFX_Monster.uasset'),(LIB,'WwiseAssetLibrary.uasset'),(LIB_BULK,'WwiseAssetLibrary.ubulk')]:
            shutil.copyfile(NATIVE/name,raw/'chunks'/cid)
        gold=ROOT/'work/gold-alert-v157/raw/chunks'
        assert digest(gold/MONSTER)==digest(NATIVE/'SFX_Monster.uasset')
        shutil.copyfile(gold/MONSTER_BULK,raw/'chunks'/MONSTER_BULK)
        bulk=(raw/'chunks'/MONSTER_BULK).read_bytes();a=(raw/'chunks'/MONSTER).read_bytes();m=table(raw/'chunks'/MONSTER)
        original_media=[]
        for entry,cache in [(145,2920923688),(10157,2635691332)]:
            at,_,size,flags,idx=struct.unpack_from('<qqqIB3x',a,m+entry*32)
            assert flags==66817 and idx==0
            expected=(NATIVE/f'actual-purple-{cache}.wem').read_bytes()
            assert bulk[at:at+size]==expected
            original_media.append(dict(map_entry=entry,cache=cache,offset=at,bytes=size,sha256=digest(NATIVE/f'actual-purple-{cache}.wem')))
        b=(raw/'chunks'/LIB_BULK).read_bytes();assert b[155099039:155099039+1609]==(NATIVE/'pbz-ziguang-original.bnk').read_bytes()
        proof.update(audio='original PBZ black-warning audio, codecs, bank graph and metadata',
            official_v11_red_yellow_audio_preserved=True,black_media_original_exact=original_media,
            native_bank_and_library_exact=True,black_audio_modification_disabled_for_diagnosis=True)
    untouched={}
    for p in (VISUAL/'chunks').iterdir():
        if p.name not in {MONSTER,MONSTER_BULK,LIB,LIB_BULK}:
            assert digest(p)==digest(raw/'chunks'/p.name);untouched[p.name]=digest(p)
    assert len(untouched)==177
    retoc=ROOT/'tools/retoc/retoc.exe';toc=folder/'Mod/zz_PBZ_YellowAlert_P.utoc'
    subprocess.run([str(retoc),'pack-raw',str(raw),str(toc)],check=True)
    shutil.copyfile(ROOT/'outputs/PBZ-Gold-Alert-v1.6.6/Mod/zz_PBZ_YellowAlert_P.pak',toc.with_suffix('.pak'))
    subprocess.run([str(retoc),'verify',str(toc)],check=True)
    check=build/('roundtrip-'+uuid.uuid4().hex[:8]);subprocess.run([str(retoc),'unpack-raw',str(toc),str(check)],check=True)
    expected={p.name for p in (raw/'chunks').iterdir()};assert len(expected)==181
    assert expected=={p.name for p in (check/'chunks').iterdir()}
    for p in (raw/'chunks').iterdir():assert digest(p)==digest(check/'chunks'/p.name)
    proof.update(unchanged_visual_timing_chunk_sha256=untouched,container_verify=True,raw_roundtrip_exact=True,
        roundtrip_directory=str(check),in_game_tested=False,installed=False)
    (build/'validation.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    (folder/'validation.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    (folder/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  Mod/'+p.name+'\n' for p in sorted((folder/'Mod').iterdir())),encoding='utf-8')
    description=('固定播放已确认的第二种绝区零紫光提示音。' if not control else '保留原生黑光声音，用于判断声音事件是否触发。')
    (folder/'README.txt').write_text(
        'PBZ Gold Alert v1.6.7 音频定位测试 '+label+'\n\n'+description+'\n'
        '保留加粗并上移的紫色X、全屏变暗、穿透显示和提前100毫秒设置。\n'
        '保留正式版1.1红黄光效果。\n\n'
        '安装：完全退出游戏，将本目录Mod内三个文件一起复制到\n'
        'ProjectPBZ\\Content\\Paks\\~mods，替换旧版同名文件，重新启动游戏。\n'
        'A和B任选一个安装，每次切换前完全退出游戏并替换全部三个文件。\n'
        '卸载：退出游戏后移除上述三个文件。\n',encoding='utf-8-sig')
    print(json.dumps(dict(output=str(folder),audio=proof['audio'],offline_verified=True,in_game_tested=False)),flush=True)
    return proof


def build():
    a=build_one('A-Confirmed-Purple',False);b=build_one('B-Original-Black-Control',True)
    (OUT/'TEST-INSTRUCTIONS.txt').write_text(
        '1.6.7 静音定位测试\n\n'
        '先安装A：它固定播放已确认的第二种紫光声音。\n'
        'A恢复1.6.4完整银行与媒体布局，仅替换既有音频区域内的采样。\n'
        '若A仍无声，再退出游戏并换装B。B保留游戏原生黑光音频。\n'
        '两包紫光外观及触发时间相同，不能同时安装；每次需替换全部三个同名文件并重启。\n'
        '请分别记录A、B在同一招黑光攻击时是否出声。\n'
        '若两者都无声，下一步检查触发分支；若B有声A无声，继续检查替换媒体加载。\n'
        '随机播放暂留在历史版本，待固定声音恢复后再启用。\n'
        '当前仅通过离线验证，不代表已游戏内确认。\n',encoding='utf-8-sig')


if __name__=='__main__':build()
