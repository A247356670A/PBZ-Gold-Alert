"""Release the unchanged V2.0.5 triplet. No native container repacking or gameplay edits."""
from pathlib import Path
import sys,json,hashlib,shutil,zipfile,struct,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'work'),str(ROOT/'analysis'),str(ROOT/'work/official-v20')]
from export_official_v20 import physical,BASE,AUDIO
from read_pbz import Reader
import write_release_docs as olddocs
B=ROOT/'work/official-v20-combined';REL=ROOT/'official release'
DEV=ROOT/'outputs/PBZ-Gold-Alert-v2.0.5/Mod';RAW=ROOT/'work/gold-alert-v205/combined/raw'
FULL=REL/'PBZ-Gold-Alert-Official-V2.0-Combined-Fullpack';INS=REL/'PBZ-Gold-Alert-Official-V2.0-Combined-Installer'
STEM='zz_PBZ_YellowAlert_P'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def js(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def txt(p,s):p.write_text(s.strip()+'\n',encoding='utf-8-sig')
def stage():
    assert not FULL.exists() and not INS.exists()
    B.mkdir(parents=True);(FULL/'Mod').mkdir(parents=True);INS.mkdir()
    expected={n.split('  Mod/')[1]:n.split('  Mod/')[0] for n in (DEV.parent/'SHA256SUMS.txt').read_text().splitlines()}
    assert len(expected)==3
    for p in DEV.iterdir():
        assert sha(p)==expected[p.name];shutil.copyfile(p,FULL/'Mod'/p.name)
        assert sha(FULL/'Mod'/p.name)==expected[p.name]
    r=Reader();assert sha(Path(r'G:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'))==BASE
    idx={r.toc[144+i*12:156+i*12].hex():i for i in range(r.n)}
    toc=FULL/'Mod'/(STEM+'.utoc');ucas=toc.with_suffix('.ucas')
    ranges=sorted((physical(toc,c)[0],c,physical(toc,c)[1])for c in AUDIO if c.endswith('02'))
    parts=[];stats=[]
    with (INS/'payload.bin').open('wb') as payload,ucas.open('rb') as packed:
        def lit(data):
            at=payload.tell();payload.write(data);return dict(payload_offset=at,bytes=len(data))
        cursor=0
        for pos,cid,size in ranges:
            if pos>cursor:
                packed.seek(cursor);parts.append(dict(kind='literal',**lit(packed.read(pos-cursor))))
            base_size=r.info(idx[cid])[1];assert size>=base_size;patches=[];changed=0
            with (RAW/'chunks'/cid).open('rb') as target:
                assert (RAW/'chunks'/cid).stat().st_size==size
                for start in range(0,base_size,1024*1024):
                    length=min(1024*1024,base_size-start);a=r.read(idx[cid],start,length);b=target.read(length)
                    dif=np.flatnonzero(np.frombuffer(a,dtype=np.uint8)!=np.frombuffer(b,dtype=np.uint8))
                    if len(dif):
                        changed+=len(dif);cuts=np.flatnonzero(np.diff(dif)>256)
                        for lo,hi in zip(np.r_[dif[0],dif[cuts+1]],np.r_[dif[cuts]+1,dif[-1]+1]):
                            patches.append(dict(offset=start+int(lo),**lit(b[int(lo):int(hi)])))
                tail=lit(target.read())
            parts.append(dict(kind='base',cid=cid,base_bytes=base_size,target_bytes=size,tail=tail,patches=patches))
            cursor=pos+size;stats.append(dict(cid=cid,changed_bytes=changed,tail_bytes=tail['bytes'],patches=len(patches)))
        if cursor<ucas.stat().st_size:
            packed.seek(cursor);parts.append(dict(kind='literal',**lit(packed.read())))
    for extension in ['.pak','.utoc']:shutil.copyfile(DEV/(STEM+extension),INS/(STEM+extension))
    files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in DEV.iterdir()}
    js(INS/'recipe.json',dict(version='2.0',distribution='combined',source_development='2.0.5',base_toc_sha256=BASE,
        files=files,reconstructed_file=ucas.name,parts=parts))
    for name in ['Extract.cs','Select-Game.ps1','oo2core_9_win64.dll','key.txt','Install.cmd']:
        shutil.copyfile(REL/'PBZ-Gold-Alert-Official-V2.0-Installer'/name,INS/name)
    source=(ROOT/'work/official-v20/Build-And-Install.ps1').read_text(encoding='utf8')
    source=source.replace("    [ValidateSet('All','Alerts','Gauntlet')][string]$Components,\n",'')
    start=source.index('    if ([string]::IsNullOrWhiteSpace($Components)) {')
    end=source.index('    if ($BuildOnly -and (Test-Path',start)
    source=source[:start]+source[end:]
    start=source.index("    $groups = @('SharedAudio')");end=source.index('    if ($BuildOnly) {',start)
    source=source[:start]+'''    $selected = @($recipe.files.PSObject.Properties.Name)
    if ($selected.Count -ne 3) { throw 'Expected the unchanged V2.0.5 resource triplet.' }
    foreach ($name in $selected) {
        if ($name -ne $shared) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $stage $name) }
        Assert-File (Join-Path $stage $name) $recipe.files.$name
    }
'''+source[end:]
    source=source.replace("components=$Components;", "distribution='combined';")
    source=source.replace('Installed and verified: $Components','Installed and verified: Official V2.0 Combined')
    assert '$Components' not in source and '$groups' not in source
    txt(INS/'Build-And-Install.ps1',source);txt(B/'Build-And-Install.ps1',source)
    inputs={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in INS.iterdir()if p.is_file()}
    js(INS/'inputs.json',inputs)
    js(B/'staging-validation.json',dict(fullpack_triplet_exact_V205=expected,delta_stats=stats,payload_bytes=(INS/'payload.bin').stat().st_size,
        native_containers_not_repacked=True,audio_and_trigger_timing_unchanged=True,gameplay_bytes_unchanged=True))
    print(json.dumps(dict(staged=True,triplet=expected,payload_bytes=(INS/'payload.bin').stat().st_size)),flush=True)

FEATURES='''PBZ Gold Alert — Official V2.0（合并版 / Combined）

功能 / Features
参考《绝区零》风格的金色十字黄光；黑光攻击使用头顶附近的蓝紫色45度X预警，保留全屏变暗并使用替换音效。
包含铁拳套黑光特殊招架反击、成功招架声音、淡金色招架/蓄力/出拳特效，以及成功后杀气结算为满槽30%的改动。简体中文铁拳套说明追加“跟...根本没有这样的拳套!”。
全部功能合并为一个资源三件套，仍需玩家自行把握L1+R2招架时机。

Golden yellow-warning crosses inspired by Zenless Zone Zero, plus blue-violet 45-degree X warnings for black-flash attacks, retaining screen darkening and replacement audio.
Includes the iron-gauntlet black-flash counter changes, parry-success audio, pale-gold parry/charge/punch effects, a post-success Sha Chi settlement to 30% of maximum, and an extra line in the Simplified Chinese gauntlet description.
All features are combined in one resource triplet. Players must still time L1+R2 themselves.
'''
UPGRADE=r'''升级与卸载（中文）
升级前，将旧版zz_PBZ_YellowAlert_P和zz_PBZ_GauntletCounter_P的.pak/.utoc/.ucas三件套，以及之前拆分V2.0的以下全部资源文件备份移出Paks：
zz_PBZ_V20_SharedAudio_P.pak / .utoc / .ucas
zz_PBZ_V20_AttackAlerts_P.pak / .utoc / .ucas
zz_PBZ_V20_Gauntlet_P.pak / .utoc / .ucas
请备份到游戏根目录ModBackups等Paks之外的位置。本版不要与旧拆分包、旧合并包或换色1.2同时加载。
卸载时退出游戏，移除本版zz_PBZ_YellowAlert_P.pak/.utoc/.ucas三个文件。回退时再放回之前备份；不要删除游戏原始文件。

Upgrade and uninstall (English)
Before upgrading, back up and move the old zz_PBZ_YellowAlert_P and zz_PBZ_GauntletCounter_P resource triplets, plus all nine files of the earlier split V2.0 package listed above, out of Paks. Use a location such as ModBackups in the game root. Do not stack this with split packages, older combined builds or the swapped-color 1.2 preset.
To uninstall, close the game and remove only zz_PBZ_YellowAlert_P.pak, zz_PBZ_YellowAlert_P.utoc and zz_PBZ_YellowAlert_P.ucas. Restore your previous backup to roll back. Keep the original game resources.
'''
FULLINSTALL=r'''安装方法（中文）
1. 下载Fullpack并完整解压，完全退出游戏。
2. 按下方说明备份并移出旧MOD文件。
3. 打开游戏安装目录ProjectPBZ\Content\Paks\~mods，没有~mods则新建。
4. 将Mod文件夹内zz_PBZ_YellowAlert_P.pak、zz_PBZ_YellowAlert_P.utoc、zz_PBZ_YellowAlert_P.ucas三个文件一起复制到~mods，再启动游戏。

Installation (English)
1. Download and fully extract Fullpack. Close the game completely.
2. Back up and remove older mod files as described below.
3. Open ProjectPBZ\Content\Paks\~mods in your game installation; create ~mods if necessary.
4. Copy all three files named zz_PBZ_YellowAlert_P.pak, zz_PBZ_YellowAlert_P.utoc and zz_PBZ_YellowAlert_P.ucas from Mod into ~mods, then launch the game.
'''
INSINSTALL=r'''安装方法（中文）
1. 下载Installer并完整解压到可写文件夹，预留至少4GB可用空间。
2. 完全退出游戏，双击Install.cmd。
3. 在弹出的窗口中手动选择游戏安装目录中的PBZ.exe，不设置默认目录。
4. 等待本地还原、校验、旧文件备份与安装完成，再启动游戏。本版一次安装全部合并内容。
5. 需要64位Windows和Windows PowerShell 5.1，以及匹配版本的本机游戏资源；无需Python或在线下载。游戏资源版本不符时停止安装。
6. 已知的旧合并包及旧V2.0拆分文件自动备份至游戏根目录ModBackups，并移出Paks；其他名称的MOD保持原样。

Installation (English)
1. Download and fully extract Installer into a writable folder with at least 4GB free space.
2. Close the game completely and run Install.cmd.
3. Manually select PBZ.exe from your game installation. No game directory is preselected.
4. Wait for reconstruction, verification, backup and installation to finish, then launch the game. All combined features install together.
5. Requires 64-bit Windows, Windows PowerShell 5.1 and matching local game resources. No Python or online download is needed. Installation stops on a game-resource version mismatch.
6. Known older combined/split mod files are backed up under ModBackups in the game root and removed from Paks. Other mod filenames are left alone.
'''
def docs():
    changelog=olddocs.CHANGELOG
    replacements={
      '- 正式版拆分AttackAlerts和Gauntlet组件，可分别选择安装；SharedAudio作为公共依赖。':'- 按用户最新要求，直接使用开发V2.0.5原始三件套，预警与拳套增强合并安装。',
      '- Fullpack仅含9个.pak/.utoc/.ucas资源及说明/校验文本，不含安装脚本或DLL。':'- Fullpack仅含V2.0.5原始3个.pak/.utoc/.ucas资源及说明/校验文本，不含安装脚本或DLL。',
      '- Installer手动选择PBZ.exe，无预设目录；支持完整、仅预警、仅拳套三种选择，校验游戏资源版本及生成文件。':'- Installer手动选择PBZ.exe，无预设目录；一次还原并安装原始三个文件，校验游戏资源版本及生成文件。',
      '- Separates AttackAlerts and Gauntlet for independent selection, with SharedAudio required by either.':'- Uses the original development V2.0.5 triplet unchanged, installing alerts and gauntlet features together as requested.',
      '- Fullpack contains nine .pak/.utoc/.ucas resources plus documentation/checksums, without installer scripts or DLLs.':'- Fullpack contains the three original V2.0.5 .pak/.utoc/.ucas files plus documentation/checksums, without installer scripts or DLLs.',
      '- Installer asks for PBZ.exe without a preselected directory and offers All, Alerts and Gauntlet modes, with game-version and output verification.':'- Installer asks for PBZ.exe without a preselected directory and reconstructs/installs the original triplet with game-version and output verification.',
      'Official V2.0: 保留V2.0.5资源，拆分组件并制作两种安装包 / V2.0.5 payload snapshot, modular release and two distribution formats.':'Official V2.0 Combined: 直接使用V2.0.5原始三件套，制作两种安装包 / Original V2.0.5 triplet unchanged, combined release in two distribution formats.'}
    for a,b in replacements.items():assert a in changelog;a_count=changelog.count(a);changelog=changelog.replace(a,b)
    changelog=changelog.replace('发布日期 / Release date: 2026-11-07','发布日期 / Release date: 2026-11-07\n封装 / Distribution: Combined（合并三件套）')
    change_note='''封装修订说明 / Packaging revision
用户反馈拆分正式版仍有拳套反击/特效触发和声音时序问题，最新要求暂停修复并直接打包V2.0.5。本合并版不修改V2.0.5任何资源字节、声音、时间或代码，不宣称修复上述运行问题。Fullpack直接复制原文件，Installer还原后必须与原文件SHA256一致。
Following feedback about counter/effect triggering and audio timing, the user requested packaging V2.0.5 unchanged before further fixes. This combined build changes no V2.0.5 resource bytes, sounds, timing or code and does not claim to fix those runtime issues. Fullpack copies the original files; Installer output must match their SHA256 hashes exactly.
'''
    changelog=change_note+'\n'+changelog
    for folder,installation in [(FULL,FULLINSTALL),(INS,INSINSTALL)]:
        txt(folder/'README.txt',FEATURES+'\n'+installation+'\n'+UPGRADE)
        txt(folder/'CHANGELOG.txt',changelog)
    txt(REL/'PBZ-Gold-Alert-Official-V2.0-Combined-CHANGELOG.txt',changelog)
    nexus='''PBZ Gold Alert — Official V2.0 Combined / Nexus Mods 上传信息
页面 / Page: https://www.nexusmods.com/phantombladezero/mods/150
版本 / Version: 2.0
Mod名称 / Mod name: PBZ Gold Alert - ZZZ Style Warnings and Gauntlet Counter

短描述 / Short description (under 350 characters)
参考绝区零风格的金色十字黄光、紫色X形黑光预警及替换音效，包含拳套黑光招架反击与淡金色光效。ZZZ-inspired gold and violet warnings with replacement audio, gauntlet counter changes and pale-gold effects. Combined V2.0.5 triplet, available as Installer or resource-only Fullpack.

文件1 / File 1
名称 / Name: PBZ Gold Alert Official V2.0 - Combined Fullpack
文件 / File: PBZ-Gold-Alert-Official-V2.0-Combined-Fullpack.7z
版本 / Version: 2.0
完整纯资源合并包，直接包含V2.0.5原始.pak/.utoc/.ucas三个文件，预警与拳套增强一起安装。无安装脚本或DLL。与Installer二选一。
Complete combined resource-only package containing the three original V2.0.5 .pak/.utoc/.ucas files. Alerts and gauntlet features install together. No installer scripts or DLLs. Download this OR Installer.

文件2 / File 2
名称 / Name: PBZ Gold Alert Official V2.0 - Combined Installer
文件 / File: PBZ-Gold-Alert-Official-V2.0-Combined-Installer.zip
版本 / Version: 2.0
小体积本地还原安装包，手动选择PBZ.exe，一次安装全部合并内容。生成的三个文件与V2.0.5及Fullpack完全一致。需要匹配版本的游戏资源，64位Windows和Windows PowerShell 5.1。
Compact local-reconstruction installer. Manually select PBZ.exe to install all combined features. Reconstructed files exactly match V2.0.5 and Fullpack. Requires matching game resources, 64-bit Windows and Windows PowerShell 5.1.

完整描述 / Full description — 以下可直接复制 / Copy below
'''+FEATURES+'\n'+FULLINSTALL+'\n'+INSINSTALL+'\n'+UPGRADE+'''
兼容与已知情况 / Compatibility and current limitations
本包直接使用V2.0.5原始内容，不包含后续拳套触发或声音时序修复。反击/光效未覆盖所有Boss实测，成功音效保留原触发时间；游戏更新或其他覆盖相同资源的MOD可能影响效果。
This is the original V2.0.5 content without subsequent counter-trigger or audio-timing fixes. All Bosses/moves have not been exhaustively tested, and success audio retains its existing timing. Game updates or other mods replacing the same resources may affect behavior.
不要同时安装旧拆分V2.0；修改同一预警、相关敌人招式、拳套能力/特效、Wwise音频库或简体中文Game.locres的MOD可能冲突。游戏更新后Installer版本校验失败时，请等待更新包。Fullpack也不保证兼容后续更新。
Do not stack the earlier split V2.0 package. Mods replacing the same warnings, affected enemy moves, gauntlet abilities/effects, Wwise audio libraries or Simplified Chinese Game.locres may conflict. Wait for an updated Installer if its game-version check fails. Future game updates are not guaranteed compatible with Fullpack either.

致谢 / Credits
《影之刃零》 / Phantom Blade Zero — S-GAME
《绝区零》风格参考及原始提示音素材 / Zenless Zone Zero visual inspiration and original sound assets — HoYoverse
感谢参与试听、测试和反馈的玩家。 / Thanks to players who provided audio selection, testing and feedback.

更新日志见随包CHANGELOG.txt。 / See the included CHANGELOG.txt for the full bilingual history.
'''
    short=nexus.split('under 350 characters)\n')[1].split('\n')[0];assert len(short)<350
    txt(REL/'PBZ-Gold-Alert-Official-V2.0-Combined-NEXUS-INFO.txt',nexus)
    review=r'''PBZ Gold Alert Official V2.0 Combined — Review and reproduction
Source is the unchanged outputs/PBZ-Gold-Alert-v2.0.5/Mod triplet. No native containers were repacked and no audio/gameplay/visual/timing edits were made. This does not claim to fix the reported runtime issues.
Fullpack contains three resources and text documentation only. Installer contains readable CMD/PowerShell/C# source, uncompressed delta data, resource metadata, a game-resource key and the existing third-party oo2core_9_win64.dll decoder. No custom compiled executable is bundled; no download occurs. Extract.cs is compiled locally using Windows PowerShell Add-Type. The third-party decoder is closed-source; its source and a verified redistribution licence are not supplied.
To reconstruct without installing, fully extract Installer and run under 64-bit Windows PowerShell 5.1:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Build-And-Install.ps1 -GameExe "<actual PBZ.exe path>" -BuildOnly -OutputDirectory "<new writable output directory>"
Compare the three output hashes with Fullpack/SHA256SUMS.txt and development V2.0.5/SHA256SUMS.txt.
Supported original ProjectPBZ-Windows.utoc SHA256:
d5c3764cdae2030361a7fa8ed1eb204787c77e767df92bbe947763b4a2d0186b
Normal installation reconstructs/verifies before backing up known previous combined/split mod files under the game root's ModBackups and installing the triplet. It attempts rollback on copy/verification failure. BuildOnly does not install to the game. Original game containers are not changed.
payload.bin is uncompressed data, not a disguised archive. No passwords or nested archives are used. Scripts/DLLs may still require Nexus moderation. No antivirus or guaranteed approval claim is made. Official guidance: https://help.nexusmods.com/article/117-why-has-my-mod-been-quarantined
This release has not been uploaded to Nexus or GitHub. The old public repository has not been updated to V2.0.
'''
    # Keep actual command quotes rather than C-style backslash quoting.
    review=review.replace('\\"','"')
    txt(INS/'REVIEW-NOTES.txt',review);txt(REL/'PBZ-Gold-Alert-Official-V2.0-Combined-REVIEW-NOTES.txt',review)
    for folder in [FULL,INS]:
        sums=[]
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p.name!='SHA256SUMS.txt':sums.append(sha(p)+'  '+p.relative_to(folder).as_posix())
        (folder/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='utf8')
    print('Combined documentation prepared. Short description: '+str(len(short))+' characters.',flush=True)
def installer_zip():
    dest=REL/(INS.name+'.zip');assert not dest.exists()
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(INS.rglob('*')):
            if p.is_file():
                assert '.build-' not in str(p);z.write(p,INS.name+'/'+p.relative_to(INS).as_posix())
    with zipfile.ZipFile(dest) as z:assert z.testzip() is None
    print('Installer archive bytes: '+str(dest.stat().st_size),flush=True)
if __name__=='__main__':
    {'stage':stage,'docs':docs,'zip':installer_zip}[sys.argv[1]]()
