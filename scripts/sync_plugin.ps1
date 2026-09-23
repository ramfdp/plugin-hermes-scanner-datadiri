# Preview and sync both plugin locations. Run with -WhatIf before applying.
[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
param(
    [string]$HermesHome = $env:HERMES_HOME,
    [string]$DesktopHome,
    [string]$PluginDir,
    [string]$DesktopPluginDir,
    [string]$PythonExe,
    [switch]$AdoptDesktop
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $PythonExe) {
    $PythonExe = Join-Path $root '.venv/Scripts/python.exe'
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python proyek tidak ditemukan: $PythonExe. Gunakan -PythonExe untuk interpreter yang benar."
}
$arguments = @((Join-Path $PSScriptRoot 'sync_plugin.py'))
foreach ($item in @(
    @('--hermes-home', $HermesHome), @('--desktop-home', $DesktopHome),
    @('--plugin-dir', $PluginDir), @('--desktop-plugin-dir', $DesktopPluginDir)
)) {
    if ($item[1]) { $arguments += $item }
}
if ($AdoptDesktop) { $arguments += '--adopt-desktop' }
# Preview is read-only, including under -WhatIf; no backup directory is created.
& $PythonExe @arguments
if ($LASTEXITCODE -ne 0) { throw 'Preview gagal; tidak ada sinkronisasi dilakukan.' }
if ($PSCmdlet.ShouldProcess('Paket backend dan salinan app-level Desktop pada preview', 'Backup lalu sinkronkan Scanner')) {
    & $PythonExe @arguments --apply
    if ($LASTEXITCODE -ne 0) { throw 'Sync gagal. Baca pesan dan lokasi backup di atas sebelum mencoba lagi.' }
}
