# Runtime behavior — Official V2.0 Combined

## Entry and workflow

`Install.cmd` launches the system's Windows PowerShell in STA mode with a process-local `ExecutionPolicy Bypass` and the bundled local script. It does not change the persisted execution policy. The first-party source makes no network requests.

1. Ask the user to select PBZ.exe, or accept `-GameExe`. Walk parent directories to locate the original game TOC; no default game path is configured. The chosen executable is not launched.
2. Verify the TOC SHA256. Normal installation stops if PBZ is running. Validate the supplied source/data using `inputs.json` before compiling/loading the extraction helper.
3. Compile `Extract.cs` with `Add-Type`. Set this process's DLL search directory to the extracted release folder.
4. Read original IoStore TOC/UCAS partitions, decrypt blocks with .NET AES, and call the third-party decoder only for Oodle-compressed blocks.
5. Reconstruct a new UCAS in a GUID-named staging folder under the extracted installer. Apply literal/tail/sparse patch data from the uncompressed payload and verify the full output hashes.
6. `-BuildOnly` copies the three verified files to the explicitly requested new output directory and does not install to the game.
7. Normal installation checks PBZ again, then copies and verifies known previous mod files into a unique `ModBackups/PBZ-Gold-Alert-V2.0-*` directory in the game root, outside Paks. It removes those known previous files and installs exactly the combined triplet under `ProjectPBZ/Content/Paks/~mods`.
8. On installation-copy/verification failure, attempt restoration from the backups, checking restored hashes. If a file cannot be restored, report the backup location. Clean the GUID-named local staging folder on exit.

## Exact overwrite/removal scope

Only `.pak`, `.utoc` and `.ucas` files using these exact stems are backed up/replaced/removed:

- `zz_PBZ_YellowAlert_P`
- `zz_PBZ_GauntletCounter_P`
- `zz_PBZ_V20_SharedAudio_P`
- `zz_PBZ_V20_AttackAlerts_P`
- `zz_PBZ_V20_Gauntlet_P`

The last three remove the superseded split V2.0 package. Other mod filenames and original game containers are not modified. The installer reads the original game containers; it does not patch PBZ.exe, saves, registry startup items, services or scheduled tasks, request elevation, collect credentials, inject into a process or download code. `Get-Process` is used only for the running-game guard. These are statements about the first-party scripts, not an independent certification of the native DLL.

## Third-party native binary

`oo2core_9_win64.dll`: 637,952 bytes; SHA256:

`6f5d41a7892ea6b2db420f2458dad2f84a63901c9a93ce9497337b16c195f457`.

It exposes `OodleLZ_Decompress` for reading the matching local game. This is the same existing project decoder identified in the earlier V1.0 review. It is third-party closed-source code, not a first-party build output. Its source, original upstream provenance and redistribution permission are not independently established by this repository. Do not infer a licence for this binary from any source-file licence. Fullpack does not contain it.

## Packaging and validation

The current Installer uses uncompressed `payload.bin` and a single outer ZIP, replacing the earlier V1.0 gzip payload layout. No nested archives, passwords or renamed compressed blobs are used. The complete Fullpack contains only the original V2.0.5 resource triplet and text files, without scripts or DLLs.

`RELEASE-INVENTORY.json` records all archive and installer-file hashes. Local reconstruction of the extracted Installer matched every V2.0.5 resource hash. Isolated fixture tests covered backups of the old nine split files and old combined triplet, installation of exactly three files, unrelated mod preservation, locked-file rollback, game-running/version-mismatch/tampered-payload rejection and staging cleanup. Fixture game-process queries were simulated; no actual game installation was performed by those checks.

This does not assert a clean antivirus verdict, identify an unverified quarantine cause, or treat the previous V1.0 approval as approval of V2.0. Both the updated installer and its native dependency remain subject to Nexus's review.
