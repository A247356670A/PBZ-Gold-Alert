# PBZ Gold Alert — Official V2.0 Combined

Source and review material for [Phantom Blade Zero mod 150 on Nexus Mods](https://www.nexusmods.com/phantombladezero/mods/150).

This release is the **unchanged development V2.0.5 resource triplet**. Attack warnings, replacement audio and gauntlet changes install together. The previously prepared split V2.0 distribution is superseded. No new counter-trigger or sound-timing fix is claimed by this packaging update.

The mod supplies ZZZ-inspired golden yellow-warning crosses, blue-violet X warnings for black-flash attacks, and gauntlet counter/visual/audio changes. See [CHANGELOG.txt](CHANGELOG.txt) for the complete bilingual history and validation limits.

## Review entry points

- [BUILD.md](BUILD.md): C# compilation, exact local reconstruction and hash verification.
- [installer/](installer/): all four first-party source files shipped in the current installer, with **byte-identical contents**.
- [RELEASE-INVENTORY.json](RELEASE-INVENTORY.json): both archive identities, every installer file and all three reconstructed hashes.
- [SECURITY-REVIEW.md](SECURITY-REVIEW.md): behavior, delta format, backup/rollback and third-party decoder disclosure.
- [release-data/](release-data/): the shipped recipe, input checksums and documentation, without the proprietary payload or decoder.
- [asset-build/](asset-build/): supporting development/packaging scripts, including the V2.0.5 gameplay/FX/audio changes and the Combined export entry point. These require external original assets and existing intermediates; they are not a standalone game-asset SDK.
- [validation/](validation/): archive/reconstruction checks and isolated installer tests.

## Packages

Choose one from the Nexus file page:

- `PBZ-Gold-Alert-Official-V2.0-Combined-Installer.zip`: 4,377,405 bytes. Select your own PBZ.exe; reconstructs the matching local game resources and installs the combined triplet.
- `PBZ-Gold-Alert-Official-V2.0-Combined-Fullpack.7z`: 929,358,746 bytes. Three ready-to-copy resources plus text documentation; no scripts or DLLs.

Both produce the same `.pak`, `.utoc` and `.ucas` files. Installation and upgrade instructions are in [release-data/README.txt](release-data/README.txt). The Installer backs up/removes known old split or combined files before replacement. Fullpack users must remove the earlier split triplets manually.

## Source scope

No precompiled first-party executable is shipped. `Extract.cs` is compiled locally with PowerShell `Add-Type`. The shipped `oo2core_9_win64.dll` is a **separate third-party closed-source Oodle decoder**; its source is not supplied or claimed as ours. The game-derived payload, key and native resource files are not added to this source repository. Reproduction uses those data files from the corresponding release archive and the matching installed game.

The prior V1.0 source is preserved under [legacy/v1.0/](legacy/v1.0/) and in Git history. There is no project-wide licence claim over proprietary game/audio assets or the decoder; retained third-party source notices apply to their respective files.

---

中文：当前源码对应正式V2.0合并版，直接保留测试V2.0.5原始三件套。安装脚本与发行包逐字节一致；编译、还原和哈希校验方法见BUILD.md。旧拆分版不是当前发布内容。此仓库更新不包含新的拳套触发或声音时序修复，也不代表已通过新版Nexus审查。
