function Resolve-PBZGameRoot {
    param([Parameter(Mandatory=$true)][string]$GameExe)
    $exe = Get-Item -LiteralPath $GameExe -ErrorAction Stop
    if ($exe.PSIsContainer -or $exe.Name -ine 'PBZ.exe') {
        throw 'Please select the Phantom Blade Zero game executable: PBZ.exe.'
    }
    $folder = $exe.Directory
    while ($null -ne $folder) {
        $toc = Join-Path $folder.FullName 'ProjectPBZ\Content\Paks\ProjectPBZ-Windows.utoc'
        if (Test-Path -LiteralPath $toc -PathType Leaf) { return $folder.FullName }
        $folder = $folder.Parent
    }
    throw 'Game resources were not found above this PBZ.exe. Please select the executable in the complete game installation.'
}

function Select-PBZGameExe {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    try {
        $dialog.Title = '请选择《影之刃零》的 PBZ.exe'
        $dialog.Filter = '影之刃零游戏程序 (PBZ.exe)|PBZ.exe'
        $dialog.CheckFileExists = $true
        $dialog.CheckPathExists = $true
        $dialog.Multiselect = $false
        $dialog.RestoreDirectory = $true
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { return $null }
        return $dialog.FileName
    } finally { $dialog.Dispose() }
}
