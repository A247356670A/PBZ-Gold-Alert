param(
    [string]$GameExe,
    [switch]$BuildOnly,
    [string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
. (Join-Path $PSScriptRoot 'Select-Game.ps1')
function Hash([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Assert-File([string]$Path, $Spec) {
    if ((Get-Item -LiteralPath $Path).Length -ne [long]$Spec.bytes -or (Hash $Path) -ne $Spec.sha256) { throw "File verification failed: $Path" }
}
$stage = $null
try {
    if (-not [Environment]::Is64BitProcess) { throw 'Please use 64-bit Windows PowerShell.' }
    # Use the modules belonging to this PowerShell, even when launched by another shell.
    Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -Force
    Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Management\Microsoft.PowerShell.Management.psd1') -Force
    if ($BuildOnly -and ([string]::IsNullOrWhiteSpace($GameExe) -or [string]::IsNullOrWhiteSpace($OutputDirectory))) { throw 'BuildOnly requires GameExe and a new OutputDirectory.' }
    if ([string]::IsNullOrWhiteSpace($GameExe)) { $GameExe = Select-PBZGameExe }
    if ([string]::IsNullOrWhiteSpace($GameExe)) { Write-Host '已取消 / Cancelled.'; exit 0 }
    $root = Resolve-PBZGameRoot $GameExe
    $paks = Join-Path $root 'ProjectPBZ\Content\Paks'
    $recipe = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'recipe.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ((Hash (Join-Path $paks 'ProjectPBZ-Windows.utoc')) -ne $recipe.base_toc_sha256) { throw '游戏资源版本不匹配，请勿强制安装。 / Unsupported game resource version. Installation stopped.' }
    if (-not $BuildOnly -and @(Get-Process -Name 'PBZ*' -ErrorAction SilentlyContinue).Count -gt 0) { throw '请完全退出游戏。 / Close the game completely.' }
    if ($BuildOnly -and (Test-Path -LiteralPath $OutputDirectory)) { throw 'OutputDirectory must not already exist.' }
    # Verify the shipped inputs before compiling or loading the extraction helper.
    $inputs = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'inputs.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in $inputs.PSObject.Properties) { Assert-File (Join-Path $PSScriptRoot $entry.Name) $entry.Value }
    Add-Type -Path (Join-Path $PSScriptRoot 'Extract.cs')
    if (-not [PBZRelease]::SetDllDirectory($PSScriptRoot)) { throw 'Could not set audio decoder location.' }
    $stage = Join-Path $PSScriptRoot ('.build-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    $shared = $recipe.reconstructed_file
    $built = Join-Path $stage $shared
    Write-Host '正在从本机游戏还原音频资源，请稍候… / Reconstructing audio from the local game…'
    $payload = [IO.File]::OpenRead((Join-Path $PSScriptRoot 'payload.bin'))
    $output = [IO.File]::Create($built)
    try {
        $key = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'key.txt') -Raw).Trim()
        foreach ($part in $recipe.parts) {
            if ($part.kind -eq 'literal') {
                [PBZRelease]::CopyRange($payload, $output, [long]$part.payload_offset, [long]$part.bytes)
            } elseif ($part.kind -eq 'base') {
                $start = $output.Position
                [PBZRelease]::AppendBase($paks, $part.cid, $key, $output, [long]$part.base_bytes)
                [PBZRelease]::CopyRange($payload, $output, [long]$part.tail.payload_offset, [long]$part.tail.bytes)
                if ($output.Position -ne $start + [long]$part.target_bytes) { throw 'Reconstruction length mismatch.' }
                $end = $output.Position
                foreach ($patch in $part.patches) {
                    if ([long]$patch.offset -lt 0 -or [long]$patch.offset + [long]$patch.bytes -gt [long]$part.base_bytes) { throw 'Invalid audio patch range.' }
                    $output.Position = $start + [long]$patch.offset
                    [PBZRelease]::CopyRange($payload, $output, [long]$patch.payload_offset, [long]$patch.bytes)
                }
                $output.Position = $end
            } else { throw 'Unknown recipe operation.' }
        }
    } finally { $output.Dispose(); $payload.Dispose() }
    $key = $null
    Assert-File $built $recipe.files.$shared
    $selected = @($recipe.files.PSObject.Properties.Name)
    if ($selected.Count -ne 3) { throw 'Expected the unchanged V2.0.5 resource triplet.' }
    foreach ($name in $selected) {
        if ($name -ne $shared) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $stage $name) }
        Assert-File (Join-Path $stage $name) $recipe.files.$name
    }
    if ($BuildOnly) {
        New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
        foreach ($name in $selected) { Copy-Item -LiteralPath (Join-Path $stage $name) -Destination (Join-Path $OutputDirectory $name) }
        Write-Host "生成并校验完成 / Build verified: $OutputDirectory"
    } else {
        if (@(Get-Process -Name 'PBZ*' -ErrorAction SilentlyContinue).Count -gt 0) { throw 'Game started during reconstruction. Close it and retry.' }
        $mods = Join-Path $paks '~mods'
        New-Item -ItemType Directory -Path $mods -Force | Out-Null
        $backup = Join-Path $root ('ModBackups\PBZ-Gold-Alert-V2.0-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
        New-Item -ItemType Directory -Path $backup | Out-Null
        $old = @()
        $knownStems = @('zz_PBZ_YellowAlert_P','zz_PBZ_GauntletCounter_P','zz_PBZ_V20_SharedAudio_P','zz_PBZ_V20_AttackAlerts_P','zz_PBZ_V20_Gauntlet_P')
        foreach ($stem in $knownStems) { foreach ($extension in @('.pak','.utoc','.ucas')) {
            $name = $stem + $extension; $path = Join-Path $mods $name
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                Copy-Item -LiteralPath $path -Destination (Join-Path $backup $name)
                if ((Hash $path) -ne (Hash (Join-Path $backup $name))) { throw 'Backup verification failed; installed files untouched.' }
                $old += $name
            }
        } }
        $attempted = @()
        try {
            foreach ($name in $old) { Remove-Item -LiteralPath (Join-Path $mods $name) }
            foreach ($name in $selected) {
                $attempted += $name
                Copy-Item -LiteralPath (Join-Path $stage $name) -Destination (Join-Path $mods $name)
                Assert-File (Join-Path $mods $name) $recipe.files.$name
            }
            @{version='2.0'; distribution='combined'; installed=$selected; previous=$old} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backup 'installation.json') -Encoding UTF8
        } catch {
            $failure = $_
            $rollbackErrors = @()
            foreach ($name in $attempted) {
                try { $path=Join-Path $mods $name; if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path } }
                catch { $rollbackErrors += $_.Exception.Message }
            }
            foreach ($name in $old) {
                try {
                    $path = Join-Path $mods $name; $saved = Join-Path $backup $name
                    # A file that could not be deleted can already be the intact original.
                    if ((Test-Path -LiteralPath $path) -and (Hash $path) -eq (Hash $saved)) { continue }
                    Copy-Item -LiteralPath $saved -Destination $path -Force
                    if ((Hash $path) -ne (Hash $saved)) { throw "Restore verification failed: $name" }
                } catch { $rollbackErrors += $_.Exception.Message }
            }
            if ($rollbackErrors.Count -gt 0) { throw ("Installation failed; restore any remaining files from $backup . " + ($rollbackErrors -join '; ')) }
            throw $failure
        }
        Write-Host "安装并校验完成 / Installed and verified: Official V2.0 Combined"
        Write-Host "旧版备份 / Previous files: $backup"
    }
} catch {
    Write-Host ('安装停止 / Stopped: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    if ($null -ne $stage -and (Test-Path -LiteralPath $stage)) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
