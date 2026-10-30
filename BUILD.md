# Build and reproduction

## Requirements

64-bit Windows and Windows PowerShell 5.1 with the .NET Framework C# compiler available to Add-Type. Reconstructing the mod also requires the exact game resource build accepted by recipe.json, the quarantined release payloads and its Oodle DLL. No Python, internet access or downloaded compiler is needed for the installer.

## 1. Compile the shipped first-party C# source

From this source directory, run:

```powershell
powershell.exe -NoProfile -Command "Add-Type -Path '.\installer\Extract.cs'; [PBZShare].FullName"
```

This should print PBZShare. This compile-only step does not load Oodle or read game files. The release itself uses `Add-Type -Path Extract.cs` at runtime. It does not ship a precompiled PBZShare executable. Add-Type may use temporary compilation files managed by PowerShell/.NET; there is no separately supplied first-party DLL to rebuild.

## 2. Reconstruct the exact mod without installing it

Extract the original quarantined release into a new writable folder. Compare the five source files in that folder with installer/ using the hashes in RELEASE-INVENTORY.json. Run from the release folder, replacing the example path with an actual game executable:

```powershell
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File .\Build-And-Install.ps1 -GameExe "D:\Games\PBZ\platform\steam\PBZ.exe" -BuildOnly
```

`-BuildOnly` creates the complete Mod/ files in that folder, but does not invoke Install-Update.ps1 or write the game installation. The scripts verify the base TOC and reconstructed UCAS hashes before reporting success.

## 3. Verify the reconstructed files

```powershell
Get-FileHash .\Mod\zz_PBZ_YellowAlert_P.pak -Algorithm SHA256
Get-FileHash .\Mod\zz_PBZ_YellowAlert_P.utoc -Algorithm SHA256
Get-FileHash .\Mod\zz_PBZ_YellowAlert_P.ucas -Algorithm SHA256
```

Compare these values to the release's SHA256SUMS.txt. This reproduces the installed MOD bytes, rather than a byte-identical ZIP container (ZIP timestamps/compression metadata may differ).

## Data formats

`prefix.gz` is a gzip-compressed raw UCAS prefix. `audio-patches.gz` decompresses to a little-endian uint32 patch count, followed by records: uint64 offset relative to the original bulk chunk, int32 byte length, then that many replacement bytes. The installer writes each patch at recipe.prefix_bytes + offset in the staged UCAS. These blobs are data, not commands or bundled ZIP installers. Their presence may nevertheless be relevant to Nexus's nested-archive screening rules.

## Supporting asset-development code

asset-build/ includes local Python scripts used to create the visual/audio data. Recreating those edits from scratch additionally requires original extracted Zen assets, the matching usmap, the original warning audio, previous build intermediates, PyCryptodome and external retoc/vgmstream tools. Those assets/tools/intermediates are not supplied here. See the scripts for exact paths; this source archive is not a self-contained SDK for generating all proprietary assets from an empty directory.
