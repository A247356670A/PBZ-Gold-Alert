# PBZ Gold Alert official v1.0 — source for review

Mod page: https://www.nexusmods.com/phantombladezero/mods/150

This is review material for the existing quarantined release, not a replacement installer. The uploaded release has not been changed. `installer/` contains byte-identical copies of all executable scripts and the C# source shipped in that release. `RELEASE-INVENTORY.json` lists every uploaded file and its SHA-256.

## Contents

- `installer/`: all first-party runtime source (.cmd, .ps1, .cs).
- `BUILD.md`: exact compilation, reconstruction and verification steps.
- `SECURITY-REVIEW.md`: runtime behavior and dependency disclosure.
- `asset-build/`: supporting Python asset-development scripts and local imports. These are not run by the distributed installer. The original game assets and development intermediates are not included.
- `RELEASE-INVENTORY.json`: uploaded release checksums and archive identity.

## Scope and third-party code

The only precompiled native DLL shipped in the uploaded archive is `oo2core_9_win64.dll`. It is a third-party Oodle decompression library, not built from Extract.cs. Its proprietary source is not available in this repository. We do not represent this dependency as open source or claim to have rebuilt or independently audited it. See SECURITY-REVIEW.md for the hash and provenance limits.

Compressed patch payloads and the native DLL are not copied into this source archive. Reviewers can obtain those exact files from the quarantined upload. This source archive does not make a licensing claim for third-party assets or code.
