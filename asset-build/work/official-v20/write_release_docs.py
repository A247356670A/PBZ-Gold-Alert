from pathlib import Path
import json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2];REL=ROOT/'official release'
FULL=REL/'PBZ-Gold-Alert-Official-V2.0-Fullpack';INS=REL/'PBZ-Gold-Alert-Official-V2.0-Installer'
def write(p,s):p.write_text(s.strip()+'\n',encoding='utf-8-sig')
FEATURES='''PBZ Gold Alert — Official V2.0

功能 / Features
攻击预警：参考《绝区零》风格的金色十字黄光；黑光攻击使用蓝紫色45度X形预警，两个光条同步消失，位置在头顶附近，保留原有全屏变暗效果，并替换预警音效。
拳套增强：铁拳套L1+R2成功招架黑光后进入自动反击；新增成功招架音效、淡金色招架/蓄力/出拳光效。成功招架后的杀气结算设为满槽30%，不是持续锁定；简体中文说明追加“跟...根本没有这样的拳套!”。
攻击预警与拳套增强可分别选择，也可一起安装；二者均需SharedAudio公共音频资源。此公共资源会替换相关预警和反击音频，不改变未选择组件的玩法代码。
仍需玩家把握L1+R2招架时机；本MOD不自动按键，也不扩大招架窗口。

Attack alerts: golden yellow-warning crosses inspired by Zenless Zone Zero, plus blue-violet 45-degree X warnings for black-flash attacks. Both diagonal bars fade together near the enemy's head, retain the original screen-darkening effect, and use replacement warning audio.
Gauntlet enhancement: successful L1+R2 parries against black-flash attacks enter the counterattack branch. Includes a success sound, pale-gold parry/charge/punch effects, a one-time post-parry Sha Chi settlement to 30% of maximum, and an extra line in the Simplified Chinese gauntlet description. The meter is not continuously locked.
Install either component or both. Both require SharedAudio, which replaces the associated warning and counter sounds without enabling the unselected component's gameplay code.
You must still time the L1+R2 parry yourself. The mod does not press buttons automatically or widen the parry window.
'''
COMPONENTS='''组件文件 / Component files
每个组件的 .pak、.utoc、.ucas 必须一起复制；不要混用不同版本。
Always keep each component's .pak, .utoc and .ucas together. Do not mix versions.

公共音频（必需） / Shared audio (required): zz_PBZ_V20_SharedAudio_P.*
攻击预警（可选） / Attack alerts (optional): zz_PBZ_V20_AttackAlerts_P.*
拳套增强（可选） / Gauntlet enhancement (optional): zz_PBZ_V20_Gauntlet_P.*

完整安装9个文件；仅预警或仅拳套为公共音频加对应组件，共6个文件。
Full installation uses nine files. Either component alone uses six files: SharedAudio plus that component.
'''
UPGRADE='''升级与卸载（中文）
旧版使用 zz_PBZ_YellowAlert_P.* 或 zz_PBZ_GauntletCounter_P.* 的三个资源文件。升级前请把这些旧文件移出Paks文件夹，备份到游戏根目录的ModBackups等位置，不要叠加旧正式版、测试版或换色1.2版。
切换组件时，同时移除不再使用组件的三个文件；保留公共音频。卸载时退出游戏，移除本版9个文件中已安装的文件；回退时再放回旧版备份。不要删除游戏原始资源。

Upgrade and uninstall (English)
Older builds use the three resource files named zz_PBZ_YellowAlert_P.* or zz_PBZ_GauntletCounter_P.*. Move these out of the Paks folder before upgrading, for example to ModBackups in the game root. Do not stack older official builds, development builds or the swapped-color 1.2 preset.
When switching components, remove all three files of the component you no longer want and keep SharedAudio. To uninstall, close the game and remove the installed V2.0 files; restore the previous backup to roll back. Keep all original game resources.
'''
FULLINSTALL=r'''安装方法（中文）
1. 下载Fullpack并完整解压，完全退出游戏。
2. 找到游戏安装文件夹，打开ProjectPBZ\Content\Paks；没有~mods文件夹则新建。
3. 按下面的组件说明选择文件，将Mod文件夹中所选组件的三个资源文件全部复制到~mods。
4. 升级或切换组件时先按下方说明移出旧文件，再启动游戏。Fullpack不需要运行安装程序。

Installation (English)
1. Download and fully extract Fullpack. Close the game completely.
2. Open ProjectPBZ\Content\Paks in your game installation and create ~mods if necessary.
3. Select the components described below and copy all three resource files for each selected component from Mod to ~mods.
4. Remove old files as described below when upgrading or switching components, then launch the game. Fullpack requires no installer.
'''
INSINSTALL=r'''安装方法（中文）
1. 下载Installer并完整解压到可写文件夹，预留至少4GB可用空间。
2. 完全退出游戏，双击Install.cmd。
3. 手动选择本机游戏安装目录中的PBZ.exe；没有默认游戏路径。可选platform\steam或steam子文件夹中的游戏PBZ.exe。
4. 输入1安装全部、2仅攻击预警、3仅拳套增强；公共音频会自动安装。
5. 等待本地还原、校验与安装完成，再启动游戏。需要64位Windows及Windows PowerShell 5.1，无需Python或联网下载。
6. 安装器只支持当前匹配的游戏资源版本；版本不符会停止。已有的本MOD旧文件自动备份至游戏根目录ModBackups。切换选项会移除本MOD之前选择的组件，不影响其他名称的MOD。

Installation (English)
1. Download and fully extract Installer into a writable folder with at least 4GB free space.
2. Close the game completely and run Install.cmd.
3. Manually select PBZ.exe from your game installation. No game directory is preselected. The executable may be in platform\steam or steam.
4. Enter 1 for all components, 2 for attack alerts, or 3 for gauntlet enhancement. SharedAudio is included automatically.
5. Wait for local reconstruction, verification and installation to finish, then launch the game. Requires 64-bit Windows and Windows PowerShell 5.1; no Python or online download is needed.
6. The installer supports the matching game resource build only and stops on a mismatch. Existing files belonging to this mod are backed up under ModBackups in the game root. Changing the selection removes this mod's previously selected components without touching other mod names.
'''
CHANGELOG='''PBZ Gold Alert — Official V2.0 完整更新日志 / Complete Changelog
发布日期 / Release date: 2026-11-07
正式版来源 / Release source: development V2.0.5

中文：V2.0相对于正常配色Official v1.1的全部变更

攻击预警
- 保留参考《绝区零》风格的金色十字黄光、单一中心、固定长度淡出和原有预警音效。
- 为黑光攻击加入蓝紫色45度X形预警，光效移至头顶附近，并使用穿透显示以降低人物模型遮挡。
- 调整紫光亮芯、光晕与颜色；相对于v1.6.10长度和宽度均按80%等比缩小，保留长宽比例。
- 两根斜向光条使用相同寿命并同步消失，修复其中一根提前消失的问题。
- 调整全屏黑光材质与半透明特效的处理顺序，保留场景变暗/去色，同时使紫光尽量保留蓝紫色。
- 黑光预警声音和光效相对于原时间提前100ms；原时间不足100ms的限制在招式起点。
- 采用用户确认的绝区零游戏原始紫光提示音，替换误选素材，修复紫光无声。
- 移除会截断声音的结束停止事件，保留完整约2.067秒紫光提示音。
- 最终版沿用已确认可正常播放的固定提示音；早期两种原声随机播放的实验未作为当前功能发布。
- 修复早期增加组件引起的第一章三面Boss区域闪退，保留后续稳定的原生组件布局。

铁拳套特殊招架与反击
- 使用L1+R2成功特殊招架黑光后进入自动反击分支，解除该黑光分支原有距离与飞行物排除条件。
- 调整成功接触事件的处理顺序，避免原标签/距离判断提前拦截；覆盖Success、Normal与Continuous等有效接触，排除PreAttack并防止反击重入。
- 仍需成功招架；不增加自动输入、不扩大招架窗口。不把“自动反击”理解为自动防御。
- 保留反击基础伤害、原动画时间轴、拳意与次数返还流程；普通攻击沿用其余原判定。
- 每次黑光特殊招架成功后，将杀气一次性结算为满槽30%；原杀气低于30%时也设为30%。此效果不是按当前值扣减70%，也不持续锁定后续杀气变化。
- 新增用户确认的“大狗紫光攻击被成功招架后”的后半段音效，素材取自绝区零游戏原始资源，不使用录屏混音。
- 在成功接触时触发音效，删除反击动画时间轴内的重复触发，保留完整约6.213秒声音；本版不继续移动触发时间，开头与预警仍可能重叠。
- 增强成功招架声音：先修正音频本体增益，再追加1.5倍线性增益并作柔限幅保护。限幅后实际响度增幅小于50%，不将增益参数等同于听感百分比。
- 招架、后续蓄力、拳风、出拳和命中爆发的指定光层改为淡金色；补齐出拳发光材质参数，并为拳套命中爆发使用隔离副本，避免给敌人共享特效全局染色。
- 仅简体中文铁拳套说明末尾追加：“跟...根本没有这样的拳套!”；保留原有文本及高亮。

发布与安装
- 提供Installer小体积本地还原包及Fullpack完整纯资源包，两者最终安装资源一致。
- 正式版拆分AttackAlerts和Gauntlet组件，可分别选择安装；SharedAudio作为公共依赖。
- Fullpack仅含9个.pak/.utoc/.ucas资源及说明/校验文本，不含安装脚本或DLL。
- Installer手动选择PBZ.exe，无预设目录；支持完整、仅预警、仅拳套三种选择，校验游戏资源版本及生成文件。
- Installer先还原及校验，再备份和替换旧MOD；安装失败尝试回滚。无需Python或在线下载。
- 开发V2.0.5及历史版本保留，后续开发继续V2.0.6；正式版单独命名V2.0。
- 本版沿正常红黄配色开发线；Official1.2的红黄换色预设为独立分支，不合并进本版。

测试边界
- 原生资源打包、解包逐块校验，以及Installer本地还原一致性可离线验证。
- 尚未收到V2.0.5“固定30%杀气”和V2.0.4最后一段出拳补色的实机确认，也未完成所有Boss/所有黑光招式的实机覆盖。远距离反击是否命中仍受原动作和命中范围约束。
- 对使用相同音频库、攻击预警、相关敌人招式、拳套能力/特效或简体中文Game.locres的其他MOD可能冲突。

English: all changes from the standard-color Official v1.1 branch

Attack warnings
- Retains the Zenless Zone Zero-inspired golden yellow-warning cross, shared center, fixed-length fade and existing warning audio.
- Adds blue-violet 45-degree X warnings for black-flash attacks, positioned near the head with depth-independent rendering to reduce model occlusion.
- Refines the violet core, glow and color. Both length and width are scaled to 80% of v1.6.10 while preserving proportions.
- Synchronizes the two diagonal bars' lifetimes and disappearance.
- Reorders the blackout material and translucent effects to retain scene darkening/desaturation while helping the X keep its violet color.
- Advances black-flash warning audio and visuals by 100ms, clamping events to the start of the move where necessary.
- Uses the confirmed original Zenless Zone Zero warning asset, replaces incorrect candidates, and fixes silent warnings.
- Removes end-of-effect stop events that truncated playback; retains the full approximately 2.067-second warning sound.
- Ships the fixed warning sound confirmed to play correctly. The early random two-sound experiment is not a current release feature.
- Fixes the early Chapter 1 three-faced Boss-area crash caused by an added component, retaining the later stable native component layout.

Iron gauntlet parry and counterattack
- Successful L1+R2 special parries against black-flash attacks enter the counterattack branch without that branch's previous distance/projectile exclusions.
- Dispatches valid success contacts before the old tag/distance gates; handles Success, Normal and Continuous contacts, ignores PreAttack, and prevents counter re-entry.
- Still requires a successful player-timed parry. Does not automate defensive input or widen the parry window.
- Preserves base counter damage, animation timing, fist-spirit gain and charge-refund flow; other incoming attacks retain their remaining original rules.
- Sets Sha Chi once to 30% of maximum after each successful black-flash special parry, including raising a lower value to 30%. This is neither a 70% deduction from the current value nor a continuous meter lock.
- Adds the confirmed follow-up sound from the large dog's successfully parried violet attack, using original Zenless Zone Zero game assets rather than recorded audio.
- Triggers success audio on contact, removes the duplicate animation-timeline event, and retains the full approximately 6.213-second sound. Trigger timing is unchanged in this release, so its beginning may still overlap the warning.
- Boosts the actual success audio, then applies a further 1.5x linear gain with soft peak limiting. Actual loudness increases by less than 50% after limiting; gain settings are not presented as exact perceived-volume percentages.
- Recolors selected parry, charge, wind, punch and impact layers pale gold. Adds the missed punch emissive override and an isolated impact-effect copy instead of globally recoloring shared enemy effects.
- Appends “跟...根本没有这样的拳套!” to the Simplified Chinese gauntlet description, preserving the original text and highlights.

Distribution and installation
- Supplies a compact local-reconstruction Installer and a complete resource-only Fullpack, producing the same installed resources.
- Separates AttackAlerts and Gauntlet for independent selection, with SharedAudio required by either.
- Fullpack contains nine .pak/.utoc/.ucas resources plus documentation/checksums, without installer scripts or DLLs.
- Installer asks for PBZ.exe without a preselected directory and offers All, Alerts and Gauntlet modes, with game-version and output verification.
- Reconstructs and verifies before backing up/replacing old mod files, with rollback on installation failure. Requires no Python or online download.
- Preserves development V2.0.5 and historical outputs. Subsequent development continues at V2.0.6; this release is separately named V2.0.
- Follows the standard-color branch. The Official1.2 swapped-color preset remains a separate branch.

Validation scope
- Native container round trips, per-chunk equality and local Installer reconstruction can be checked offline.
- The final V2.0.5 fixed-30% settlement and V2.0.4 final punch-color additions have not yet received in-game confirmation. All Bosses/moves have not been exhaustively tested. Actual ranged counter hits remain limited by the original animation and hit range.
- Other mods that replace the same audio libraries, attack alerts, affected enemy moves, gauntlet abilities/effects or Simplified Chinese Game.locres may conflict.

开发版本沿革 / Development lineage
v1.6.0: 黑光紫X与专用音频原型 / Initial black-flash violet X and dedicated-audio prototype.
v1.6.1: 早期紫光显示与声音基线 / Early working display/audio baseline.
v1.6.2: 音量及黑屏保留实验，出现三面Boss区域闪退 / Volume/blackout experiment; introduced the Boss-area crash.
v1.6.3: 恢复原生组件布局，修复闪退 / Restored native component layout to address the crash.
v1.6.4: 提升实际声音、放大紫光、穿透显示、提前100ms / Audio gain, larger X, depth-independent display, 100ms advance.
v1.6.5–1.6.6: 原始音频随机候选实验、加粗及头顶位置 / Random original-audio experiments, thicker bars and head offset.
v1.6.7: 音频A/B定位，选定可正常播放的固定版本 / Audio A/B diagnosis; selected the working fixed version.
v1.6.8: 紫X同步消失 / Synchronized X disappearance.
v1.6.9: 黑光拳套自动反击初版 / Initial black-flash gauntlet counter branch.
v1.6.10: 修复接触触发分支，预警声音完整播放 / Contact-dispatch fix and complete warning playback.
v1.6.11: 紫光80%缩放、颜色及黑屏材质顺序 / 80% X scaling, violet color and blackout-material order.
v1.6.12: 确认并加入成功招架原始音频，移除重复触发 / Confirmed success audio and duplicate-event removal.
V2.0.1: 成功招架音频Bank增益尝试 / Success-sound bank-gain adjustment.
V2.0.2: 实际PCM增益、拳套文字、首段淡金色 / PCM gain, gauntlet description and initial pale-gold phase.
V2.0.3: 后续蓄力/出拳资源补色、成功音追加增益及柔限幅 / Follow-up FX recoloring and further soft-limited success gain.
V2.0.4: 补出拳发光参数、隔离金色命中爆发 / Punch emissive override and isolated golden impact effect.
V2.0.5: 黑光拳套特殊招架后固定满槽30% / Fixed 30%-of-maximum post-parry Sha Chi settlement.
Official V2.0: 保留V2.0.5资源，拆分组件并制作两种安装包 / V2.0.5 payload snapshot, modular release and two distribution formats.

历史正式版 / Earlier official releases
Official v1.0: 基于开发v1.5.0的最初正式版 / Initial release based on development v1.5.0.
Official v1.1: 基于开发v1.5.7，黄光形状、固定长度淡出与金色色调细调；Installer及纯资源封装 / Development v1.5.7 snapshot with refined yellow cross, fixed-size fade, golden color, and Installer/resource distributions.
Official1.2: 指定编辑器预设的红黄预警换色，模仿燕云十六声操作逻辑；独立于V2.0正常配色线 / Separate swapped red/yellow editor preset inspired by Where Winds Meet, outside the V2.0 standard-color branch.
'''
NEXUS='''PBZ Gold Alert — Official V2.0 / Nexus Mods 上传信息
现有页面 / Existing page: https://www.nexusmods.com/phantombladezero/mods/150
版本字段 / Version: 2.0
游戏 / Game: Phantom Blade Zero
分类 / Category: 若有Visuals and Graphics可选择；否则选择最贴近战斗/玩法的现有分类。 / Select an available visuals/graphics or suitable combat/gameplay category.

MOD名称 / Mod name
PBZ Gold Alert - ZZZ Style Warnings and Gauntlet Counter

短描述 / Short description (combined Chinese + English, under 350 characters)
参考绝区零风格的金色十字黄光与紫色X形黑光预警，加入原声提示音。可选拳套黑光招架反击、淡金色光效及成功音效。ZZZ-inspired gold and violet attack warnings with replacement audio. Optional gauntlet counters, pale-gold effects and parry success sound. Installer and resource-only Fullpack included.

文件1 / File 1
显示名称 / Display name: PBZ Gold Alert Official V2.0 - Fullpack
版本 / Version: 2.0
文件 / Archive: PBZ-Gold-Alert-Official-V2.0-Fullpack.7z
说明 / Description:
完整纯资源包，无安装器、脚本或DLL。手动安装SharedAudio加AttackAlerts、Gauntlet中的一个或两个组件。完整安装9个文件；单组件安装6个文件。与Installer二选一。
Complete resource-only package; no installer, scripts or DLLs. Install SharedAudio plus AttackAlerts, Gauntlet, or both. Nine files for all components; six for either component alone. Choose this OR Installer.

文件2 / File 2
显示名称 / Display name: PBZ Gold Alert Official V2.0 - Installer
版本 / Version: 2.0
文件 / Archive: PBZ-Gold-Alert-Official-V2.0-Installer.zip
说明 / Description:
小体积本地还原安装包。运行Install.cmd，手动选择PBZ.exe，再选择全部、仅预警或仅拳套。需要匹配版本的本机游戏资源及64位Windows PowerShell 5.1。与Fullpack最终文件一致，二选一下载。
Compact local-reconstruction installer. Run Install.cmd, select PBZ.exe, then choose All, Alerts or Gauntlet. Requires matching local game resources and 64-bit Windows PowerShell 5.1. Produces the same resources as Fullpack; download either package.

完整描述 / Full description — 以下可直接复制 / Copy below

PBZ Gold Alert — Official V2.0

中文介绍
将黄光攻击预警替换为参考《绝区零》风格的金色十字，为黑光攻击加入头顶附近的蓝紫色45度X形预警，保留原有全屏变暗效果，并使用替换后的提示音。
可选安装铁拳套增强：L1+R2成功招架黑光后自动进入反击，加入淡金色招架/蓄力/出拳光效和成功招架音效；成功后的杀气结算为满槽30%。仍需玩家准确招架，不会自动按键，也不会扩大招架窗口。
本版使用正常预警配色，不包含旧Official1.2的红黄换色预设。

English description
Replaces yellow attack warnings with golden crosses inspired by Zenless Zone Zero, and adds blue-violet 45-degree X warnings near the head for black-flash attacks. Retains the original screen-darkening effect and supplies replacement warning audio.
The optional iron-gauntlet component enters the counterattack branch after a successful L1+R2 black-flash parry. It adds pale-gold parry/charge/punch effects and a success sound, and settles Sha Chi to 30% of maximum after success. You must still time the parry yourself; the mod does not automate input or widen the parry window.
This release uses standard warning colors and does not include the older Official1.2 swapped-color preset.

安装方法（中文）
方式一：Fullpack
1. 下载并完整解压Fullpack，完全退出游戏。
2. 打开游戏安装目录中的ProjectPBZ\\Content\\Paks\\~mods，没有~mods则新建。
3. 将Mod内SharedAudio的三个文件与需要的AttackAlerts或Gauntlet组件的三个文件一起复制进去。全部安装为9个文件；仅预警或仅拳套为6个文件。
4. 把旧版zz_PBZ_YellowAlert_P.*及zz_PBZ_GauntletCounter_P.*的资源三件套移出Paks，再启动游戏。

方式二：Installer（与Fullpack二选一）
1. 完整解压到可写文件夹，预留至少4GB空间，完全退出游戏。
2. 双击Install.cmd，在窗口中手动选择游戏安装目录里的PBZ.exe，无预设游戏目录。
3. 输入1安装全部、2仅预警或3仅拳套；公共音频自动安装。
4. 等待本地还原、校验和安装完成，再启动游戏。旧版文件备份在游戏根目录ModBackups。

Installation (English)
Option A: Fullpack
1. Download and fully extract Fullpack. Close the game completely.
2. Open ProjectPBZ\\Content\\Paks\\~mods in your game installation; create ~mods if necessary.
3. Copy SharedAudio's three files plus all three files for AttackAlerts, Gauntlet, or both from Mod into ~mods. Use nine files for everything or six for one component.
4. Move the old zz_PBZ_YellowAlert_P.* and zz_PBZ_GauntletCounter_P.* resource triplets out of Paks before launching the game.

Option B: Installer (choose this OR Fullpack)
1. Fully extract to a writable folder with at least 4GB free space and close the game completely.
2. Run Install.cmd and manually select PBZ.exe from your game installation. No game directory is preselected.
3. Enter 1 for All, 2 for Alerts or 3 for Gauntlet. SharedAudio is included automatically.
4. Wait for reconstruction, verification and installation to finish, then launch the game. Previous mod files are backed up under ModBackups in the game root.

组件与依赖 / Components and requirements
SharedAudio为公共音频依赖，会替换相关预警及反击声音；AttackAlerts负责预警视觉和时间，Gauntlet负责拳套玩法、光效及简体中文文本。组件可以分别安装，但不是完全隔离的声音预设。无需另装绝区零、Python或MOD加载器。
SharedAudio is required and replaces the associated warning/counter audio. AttackAlerts supplies warning visuals/timing; Gauntlet supplies gauntlet gameplay, effects and Simplified Chinese text. Components are independently selectable, but do not provide completely isolated sound presets. No separate Zenless Zone Zero installation, Python or additional mod loader is required.
Installer需要64位Windows、Windows PowerShell 5.1及匹配的游戏资源版本。游戏更新后若版本校验失败，请等待更新包，不要自行绕过校验；Fullpack也不保证兼容后续游戏更新。
Installer requires 64-bit Windows, Windows PowerShell 5.1 and matching game resources. If a game update causes a version mismatch, wait for an updated package rather than bypassing the check. Fullpack is also not guaranteed compatible with future game updates.

升级、冲突与卸载 / Upgrading, conflicts and uninstalling
不要与旧正式版、测试版、Official1.2换色版同时加载。其他修改同一预警、敌人招式、拳套能力/光效、Wwise音频库或简体中文Game.locres的MOD可能冲突。切换组件时移除不再使用组件的完整三个文件。
Do not stack this with earlier official/test builds or the Official1.2 swapped-color preset. Mods replacing the same alerts, affected enemy moves, gauntlet abilities/effects, Wwise audio libraries or Simplified Chinese Game.locres may conflict. Remove all three files of an unused component when changing selections.
卸载时退出游戏，删除已安装的zz_PBZ_V20_SharedAudio_P.*、zz_PBZ_V20_AttackAlerts_P.*、zz_PBZ_V20_Gauntlet_P.*资源文件；回退时放回旧版备份。不要删除游戏原始资源。
To uninstall, close the game and remove the installed zz_PBZ_V20_SharedAudio_P.*, zz_PBZ_V20_AttackAlerts_P.* and zz_PBZ_V20_Gauntlet_P.* resource files. Restore your previous backup to roll back. Keep the original game resources.

当前测试范围 / Current validation scope
已进行原生资源及本地还原校验；最后的30%杀气结算及出拳补色仍待实机反馈，未宣称所有Boss/招式均已验证。反击动作的实际命中受原有位移和攻击范围限制。成功声音保持完整，起音与预警仍可能重叠。
Native resources and local reconstruction are verified offline. The final 30% Sha Chi settlement and final punch-color changes still await in-game feedback; not every Boss/move has been tested. Actual counter hits remain subject to the original movement/hit range. The full success sound is retained and may still overlap the warning at its start.

致谢 / Credits
《影之刃零》 / Phantom Blade Zero — S-GAME
《绝区零》风格参考及原始提示音素材 / Zenless Zone Zero visual inspiration and original sound assets — HoYoverse
感谢参与试听、测试和反馈的玩家。 / Thanks to everyone who provided audio selection, testing and feedback.

更新日志 / Changelog
使用随包CHANGELOG.txt的V2.0条目；完整中英日志另附PBZ-Gold-Alert-Official-V2.0-CHANGELOG.txt。
Use the V2.0 entry in the included CHANGELOG.txt. The full bilingual log is also supplied as PBZ-Gold-Alert-Official-V2.0-CHANGELOG.txt.
'''
REVIEW=r'''PBZ Gold Alert Official V2.0 — Packaging / Review notes

Source snapshot: development V2.0.5, dated 2026-11-07. Official1.2 is a separate swapped-color branch.
Fullpack contains .pak/.utoc/.ucas resources and text documentation only. Installer contains readable CMD, PowerShell and C# source, local reconstruction data, resource metadata, a game-resource key and the existing third-party oo2core_9_win64.dll decoder. No custom compiled executable is bundled, no download occurs, and no startup/service/registry persistence is created.
The C# helper is compiled locally by Windows PowerShell Add-Type. It reads/decrypts/decompresses the installed game's matching audio chunks and applies the supplied delta recipe. It does not modify original game containers. The Oodle DLL is third-party compiled code; its source is not included. Do not represent it as our open-source code or claim a verified redistribution licence. This is the same decoder used in prior installer packages.

Review/reproduction (64-bit Windows PowerShell 5.1)
1. Fully extract the Installer archive.
2. Read Extract.cs, Build-And-Install.ps1, Select-Game.ps1, recipe.json and inputs.json. SHA256SUMS.txt lists public package inputs.
3. With the supported game installed, run:
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Build-And-Install.ps1 -GameExe "<actual path to PBZ.exe>" -Components All -BuildOnly -OutputDirectory "<new writable output folder>"
4. Repeat with -Components Alerts or -Components Gauntlet and separate new output folders if needed.
5. Compare generated resource hashes with Fullpack/SHA256SUMS.txt. BuildOnly does not write to the game directory.
Normal installation first reconstructs and verifies in a temporary local folder, then backs up known previous files outside Paks and installs only the selected components. On copy/verification failure it attempts to restore those backup files. It does not remove unrelated mod filenames.
Supported original ProjectPBZ-Windows.utoc SHA256:
d5c3764cdae2030361a7fa8ed1eb204787c77e767df92bbe947763b4a2d0186b

Nexus packaging guidance
No nested archives, passwords or file-type disguises are used. payload.bin is plain uncompressed reconstruction data; ZIP performs outer compression only. Fullpack is the simpler resource-only distribution. Installer scripts and its decoder DLL may still require moderation. No antivirus clearance or guaranteed Nexus approval is claimed; no upload or external scan was performed.
Nexus official guidance: https://help.nexusmods.com/article/117-why-has-my-mod-been-quarantined
If quarantined, retain the quarantined upload for review and contact support@nexusmods.com with the mod page and source/build information. The existing GitHub repository has not been updated for this release; do not label its old snapshot as the V2.0 source.

验证范围（中文）
本次为V2.0.5资源发布快照，不新增玩法补丁。完整资源块逐字节保留，三组件分别原生打包/解包校验。Installer从压缩包解压后按三种选择进行本地还原，再与Fullpack哈希比对。安装流程另用隔离测试目录验证备份和组件切换。
固定30%杀气及最后出拳补色仍待实机确认。未改本机已安装的V2.0.5，不上传Nexus或更新GitHub。
'''
def main():
    write(FULL/'README.txt',FEATURES+'\n'+FULLINSTALL+'\n'+COMPONENTS+'\n'+UPGRADE)
    write(INS/'README.txt',FEATURES+'\n'+INSINSTALL+'\n'+COMPONENTS+'\n'+UPGRADE)
    for dest in [FULL/'CHANGELOG.txt',INS/'CHANGELOG.txt',REL/'PBZ-Gold-Alert-Official-V2.0-CHANGELOG.txt']:write(dest,CHANGELOG)
    write(REL/'PBZ-Gold-Alert-Official-V2.0-NEXUS-INFO.txt',NEXUS)
    write(INS/'REVIEW-NOTES.txt',REVIEW)
    write(REL/'PBZ-Gold-Alert-Official-V2.0-REVIEW-NOTES.txt',REVIEW)
    short=NEXUS.split('under 350 characters)\n')[1].split('\n')[0];assert len(short)<350;print('Bilingual short description characters:',len(short))
    for folder in [FULL,INS]:
        lines=[]
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p.name!='SHA256SUMS.txt':
                with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
                lines.append(h+'  '+p.relative_to(folder).as_posix())
        (folder/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf8')
if __name__=='__main__':main()
