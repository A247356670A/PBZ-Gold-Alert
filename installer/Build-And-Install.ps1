param([string]$GameExe, [switch]$BuildOnly)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Select-Game.ps1')
if (-not $GameExe) { $GameExe = Select-PBZGameExe }
if (-not $GameExe) {
    Write-Host 'Cancelled. No files were changed.'
    exit 0
}
$GameRoot = Resolve-PBZGameRoot -GameExe $GameExe
Write-Host "Game: $GameRoot"
$paks = Join-Path $GameRoot 'ProjectPBZ\Content\Paks'
$recipe = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'recipe.json') -Raw | ConvertFrom-Json
$toc = Join-Path $paks 'ProjectPBZ-Windows.utoc'
if ((Get-FileHash -LiteralPath $toc -Algorithm SHA256).Hash -ne $recipe.base_toc_sha256) {
    throw 'Game data version does not match this mod. No game files were changed.'
}
if (-not $BuildOnly -and (Get-Process -Name PBZ -ErrorAction SilentlyContinue)) { throw 'Close the game first.' }
Add-Type -Path (Join-Path $PSScriptRoot 'Extract.cs')
[PBZShare]::SetDllDirectory($PSScriptRoot) | Out-Null
function Expand-Gzip([string]$Source, [string]$Destination) {
    $inputStream = [IO.File]::OpenRead($Source)
    try {
        $gzip = New-Object IO.Compression.GZipStream($inputStream, [IO.Compression.CompressionMode]::Decompress)
        try { $outputStream = [IO.File]::Create($Destination); try { $gzip.CopyTo($outputStream) } finally { $outputStream.Dispose() } }
        finally { $gzip.Dispose() }
    } finally { $inputStream.Dispose() }
}
$stage = Join-Path $PSScriptRoot ('Build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
$built = Join-Path $stage 'zz_PBZ_YellowAlert_P.ucas'
Write-Host 'Rebuilding mod audio from your original game data...'
Expand-Gzip (Join-Path $PSScriptRoot 'prefix.gz') $built
[PBZShare]::Append($paks, $recipe.bulk_cid, (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'key.txt') -Raw).Trim(), $built)
$patchFile = Join-Path $stage 'patches.bin'
Expand-Gzip (Join-Path $PSScriptRoot 'audio-patches.gz') $patchFile
$reader = New-Object IO.BinaryReader([IO.File]::OpenRead($patchFile))
$target = [IO.File]::Open($built, [IO.FileMode]::Open, [IO.FileAccess]::Write)
try {
    $count = $reader.ReadUInt32()
    for ($i=0; $i -lt $count; $i++) {
        $offset = $reader.ReadUInt64(); $size = $reader.ReadInt32(); $bytes = $reader.ReadBytes($size)
        if ($bytes.Length -ne $size) { throw 'Patch data is truncated.' }
        $target.Position = [long]$recipe.prefix_bytes + [long]$offset
        $target.Write($bytes, 0, $size)
    }
} finally { $reader.Dispose(); $target.Dispose() }
if ((Get-FileHash -LiteralPath $built -Algorithm SHA256).Hash -ne $recipe.ucas_sha256) {
    throw 'Rebuilt mod verification failed. No game files were changed.'
}
$mod = Join-Path $PSScriptRoot 'Mod'
New-Item -ItemType Directory -Path $mod -Force | Out-Null
Move-Item -LiteralPath $built -Destination (Join-Path $mod 'zz_PBZ_YellowAlert_P.ucas') -Force
foreach ($name in @('zz_PBZ_YellowAlert_P.utoc','zz_PBZ_YellowAlert_P.pak')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $mod $name) -Force
}
Remove-Item -LiteralPath $patchFile
Remove-Item -LiteralPath $stage
Write-Host 'Mod reconstructed: official v1.0 files verified.'
if (-not $BuildOnly) { & (Join-Path $PSScriptRoot 'Install-Update.ps1') -GameRoot $GameRoot }
