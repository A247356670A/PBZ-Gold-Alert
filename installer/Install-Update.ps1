param([switch]$CheckOnly, [string]$GameRoot)
$ErrorActionPreference = 'Stop'
$gameRoot = $GameRoot
$targetDir = Join-Path $gameRoot 'ProjectPBZ\Content\Paks\~mods'
$sourceDir = Join-Path $PSScriptRoot 'Mod'
$names = @('zz_PBZ_YellowAlert_P.pak', 'zz_PBZ_YellowAlert_P.utoc', 'zz_PBZ_YellowAlert_P.ucas')
$expected = @{}
foreach ($line in Get-Content -LiteralPath (Join-Path $PSScriptRoot 'SHA256SUMS.txt')) {
    if ($line -match '^([a-fA-F0-9]{64})\s+Mod/(.+)$') { $expected[$Matches[2]] = $Matches[1].ToUpperInvariant() }
}
if (-not (Test-Path -LiteralPath (Join-Path $gameRoot 'ProjectPBZ\Content\Paks') -PathType Container)) {
    throw "Game folder not found: $gameRoot"
}
foreach ($name in $names) {
    $source = Join-Path $sourceDir $name
    if (-not $expected.ContainsKey($name)) { throw "Missing checksum: $name" }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $expected[$name]) {
        throw "Source verification failed: $name. Extract the complete update package again."
    }
    $dest = Join-Path $targetDir $name
    $status = 'not installed'
    if (Test-Path -LiteralPath $dest -PathType Leaf) {
        $status = 'outdated'
        if ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash -eq $expected[$name]) { $status = 'current' }
    }
    Write-Host "$name : $status"
}
if ($CheckOnly) {
    Write-Host 'Read-only check completed. No files were changed.'
    exit 0
}
if (Get-Process -Name PBZ -ErrorAction SilentlyContinue) {
    throw 'Close Phantom Blade Zero completely, then run this updater again.'
}
$backupDir = Join-Path $gameRoot ('ModBackups\GoldAlert-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
foreach ($name in $names) {
    $dest = Join-Path $targetDir $name
    if (Test-Path -LiteralPath $dest -PathType Leaf) {
        Copy-Item -LiteralPath $dest -Destination (Join-Path $backupDir $name)
    }
}
try {
    foreach ($name in $names) {
        Copy-Item -LiteralPath (Join-Path $sourceDir $name) -Destination (Join-Path $targetDir $name) -Force
    }
    foreach ($name in $names) {
        if ((Get-FileHash -LiteralPath (Join-Path $targetDir $name) -Algorithm SHA256).Hash -ne $expected[$name]) {
            throw "Installed file verification failed: $name"
        }
    }
} catch {
    foreach ($name in $names) {
        $backup = Join-Path $backupDir $name
        if (Test-Path -LiteralPath $backup -PathType Leaf) {
            Copy-Item -LiteralPath $backup -Destination (Join-Path $targetDir $name) -Force
        }
    }
    throw
}
Write-Host ''
Write-Host 'PBZ Gold Alert official v1.0 installed and all three file hashes verified.' -ForegroundColor Green
Write-Host "Target: $targetDir"
Write-Host "Previous files backed up to: $backupDir"
