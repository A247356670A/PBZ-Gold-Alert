# Runtime behavior and third-party dependency

## Entry point

Install.cmd launches local Windows PowerShell with -STA and -ExecutionPolicy Bypass to run the bundled local Build-And-Install.ps1. It does not change the persisted execution policy. It does not download or execute remote scripts.

## Behavior

1. Show a local file picker for PBZ.exe, or accept -GameExe for reproducible testing.
2. Find the game resource directory by walking parent directories. No fixed default game path is used.
3. Verify the game TOC SHA-256 against recipe.json; stop on a different build.
4. Compile Extract.cs with PowerShell Add-Type and set the DLL search directory to the unpacked package folder.
5. Read the original game's IoStore TOC and split UCAS files. Decrypt selected blocks with .NET AES and decompress Oodle blocks through OodleLZ_Decompress.
6. Reconstruct a staged UCAS from local data, apply binary audio patches, and verify the entire result's SHA-256.
7. In normal installation, back up the existing three named mod files under the game's ModBackups directory, then copy the verified files into ProjectPBZ/Content/Paks/~mods. BuildOnly stops before that step.
8. Remove the installer-generated patch temporary file and empty staging directory on success.

The bundled scripts contain no network requests, telemetry, scheduled tasks, services, registry persistence, privilege-elevation request, credential access or process injection. The selected game executable is used to locate resources; it is not launched by the installer. Get-Process is used to check whether the game is running. These statements describe the provided first-party source; they are not an independent security certification of the native dependency.

## Precompiled third-party dependency

Filename: oo2core_9_win64.dll
SHA-256: 6f5d41a7892ea6b2db420f2458dad2f84a63901c9a93ce9497337b16c195f457
Size: 637952 bytes
Authenticode inspection on this machine: NotSigned.
Purpose: call OodleLZ_Decompress to read compressed local game resource blocks.

This binary was copied from the project's existing tools/oo2core_9_win64.dll. Its original upstream download provenance and redistribution permission have not been independently established in this review preparation. It is not contained in the original retoc.zip inspected here, and retoc's license is not being asserted to cover this DLL. Its source is not available as part of this project. The native DLL remains a separate item for moderator review.

## Compressed payload disclosure

The uploaded package includes two gzip-compressed raw data blobs. Nexus lists nested archives among quarantine causes. No VirusTotal result or exact scanner reason has been obtained here; this report does not assert that the quarantine is a false positive. Please review the original upload and advise whether uncompressed data or a different distribution format is required.

## Local verification

The release reconstruction was previously tested with BuildOnly against the matching local game build. The three resulting files matched the complete development build's SHA-256. Package identity is recorded in RELEASE-INVENTORY.json. This is integrity/reproduction evidence, not evidence of an antivirus clean verdict.
