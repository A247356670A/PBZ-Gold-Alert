# Build and reproduction — Official V2.0 Combined

## Requirements

64-bit Windows, Windows PowerShell 5.1 and its .NET Framework C# compiler. Full reconstruction additionally needs the matching local Phantom Blade Zero game build and the data/DLL from `PBZ-Gold-Alert-Official-V2.0-Combined-Installer.zip`. No Python, downloaded compiler or internet access is needed by the installer.

## 1. Compile the exact shipped C# source

Run from the repository root in **Windows PowerShell 5.1**:

```powershell
Add-Type -Path .\installer\Extract.cs
[PBZRelease].FullName
```

Expected output: `PBZRelease`. This compile-only step does not call the decoder, read game resources or install anything. `Build-And-Install.ps1` performs the same local `Add-Type` compilation in normal use. There is no first-party compiled executable or DLL to rebuild separately.

## 2. Match the source to the release

Fully extract the corresponding Installer ZIP into a **new writable folder** with at least 4 GB free space. Compare these four files with `installer/` using `RELEASE-INVENTORY.json`:

`Build-And-Install.ps1`, `Extract.cs`, `Install.cmd`, `Select-Game.ps1`.

Keep the archive's `payload.bin`, `recipe.json`, `inputs.json`, `key.txt`, `oo2core_9_win64.dll`, `.pak` and `.utoc` beside the scripts. `inputs.json` validates the shipped source and data before compilation/reconstruction. Source files use their original BOM and line endings; do not normalize them before hash comparison.

## 3. Reconstruct without installing

From the **extracted release folder**, run the following in Windows PowerShell 5.1. Set your actual PBZ.exe path and a new, nonexistent output directory:

```powershell
.\Build-And-Install.ps1 -GameExe 'D:\Games\PBZ\platform\steam\PBZ.exe' -BuildOnly -OutputDirectory 'D:\PBZ-review-output'
```

The paths above are examples only; no game directory is preselected. `-BuildOnly` requires both paths, creates exactly three files in the requested output directory, and skips game installation and backup steps. It cleans its private `.build-<GUID>` staging folder afterward. An existing output directory is rejected.

The required original `ProjectPBZ-Windows.utoc` SHA256 is:

`d5c3764cdae2030361a7fa8ed1eb204787c77e767df92bbe947763b4a2d0186b`.

The script refuses a different TOC. The AES key is release data, not a credential; it is intentionally not copied into this source repository. Never bypass the game-build check to test a different game version.

## 4. Verify the reconstructed resources

```powershell
Get-FileHash 'D:\PBZ-review-output\zz_PBZ_YellowAlert_P.pak' -Algorithm SHA256
Get-FileHash 'D:\PBZ-review-output\zz_PBZ_YellowAlert_P.utoc' -Algorithm SHA256
Get-FileHash 'D:\PBZ-review-output\zz_PBZ_YellowAlert_P.ucas' -Algorithm SHA256
```

| File | SHA256 |
| --- | --- |
| `.pak` | `b74dcd4f5e6d115877df2210d934aa226a56d30beda7f6547608565cbf8cc5b5` |
| `.utoc` | `2c09850735d5479635b2d5f50dc608a82f174e008050c04e180d27b1f86bb4f4` |
| `.ucas` | `c9370e773026ed7c2c05f50b3a0c38e592a8b405132eabfb6a2153adfabad5f9` |

These match the unmodified V2.0.5 outputs and Fullpack. Reproduction here means byte-identical installed resources, not identical ZIP/7z timestamp/compression metadata.

## Delta format

`payload.bin` is **8,481,144 bytes of uncompressed literal data**. It is not a renamed or nested archive. `recipe.json` provides ordered `literal` parts and `base` parts. Literal parts copy a checked offset/length from the payload. Base parts extract one original audio chunk, append its specified tail, then apply sparse replacement spans relative to that chunk. Three original audio bulk chunks are used. The complete generated UCAS and all three output files must pass their size/SHA256 checks.

## Asset-development source

`asset-build/work/build_gold_alert_v205.py` and its local helpers show the final gameplay change. Earlier `build_gold_alert_v201` through `v204` and `v1610` through `v1612` show sound, visuals and contact handling. `asset-build/work/export_official_v20_combined.py` shows the unchanged-triplet packaging. It imports helper functions from the older split exporter; the current entry point still copies the existing V2.0.5 containers unchanged.

These archived development scripts contain workstation-relative paths and expect original extracted Zen assets, current `.usmap`, script-object metadata, previous raw build directories and external retoc/vgmstream/wwiser tools. Python work additionally uses PyCryptodome, NumPy, SciPy and cityhash; optional earlier tools may require their own dependencies. Game/audio assets, mapping data, intermediate outputs and third-party binaries are not supplied here. This is reviewable development source, not a clean-room self-contained asset build from an empty directory.

Some historical `build_gold_alert_*.py` command-line entry points also call their `install()` routines. **Do not run those entry points merely to review source.** Use the shipped Installer's `-BuildOnly` route above for the reproducible, non-installing review.

The checked release reconstruction and isolated backup/rollback tests are recorded under `validation/`. Runtime parry/FX timing is not simulated by those integrity checks.
