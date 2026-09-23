# Back up first, then sync the whole plugin package. Never remove model caches or user outputs.
[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'
if (-not $env:HERMES_HOME) { throw 'HERMES_HOME belum disetel.' }
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $env:HERMES_HOME 'plugins/hermes-scanner-datadiri'
if (-not (Test-Path -LiteralPath $target -PathType Container)) { throw "Plugin tidak ditemukan: $target" }
if ([IO.Path]::GetFullPath($root) -eq [IO.Path]::GetFullPath($target)) { throw 'Source dan target sama; tidak perlu sync.' }
if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Target plugin berupa link/junction; gunakan instalasi langsung yang terkontrol.' }
$backup = Join-Path $root ('output/plugin-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
$copyNames = @('__init__.py', 'plugin.yaml', 'scanner', 'desktop', 'docs', 'requirements', 'requirements.txt')
$legacyNames = @('tools.py', 'schemas.py', 'ocr_runner.py', 'exporter.py', 'cv_report.py', 'download_model.py', 'finish_migration.ps1', 'local_only_report.py')
foreach ($name in $copyNames) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $name))) { throw "Source tidak lengkap: $name" }
}
if ($PSCmdlet.ShouldProcess($target, 'Backup lalu sync plugin 0.4')) {
    New-Item -ItemType Directory -Path $backup | Out-Null
    foreach ($name in ($copyNames + $legacyNames)) {
        $old = Join-Path $target $name
        if (Test-Path -LiteralPath $old) { Copy-Item -LiteralPath $old -Destination $backup -Recurse }
    }
    foreach ($name in $copyNames) {
        $source = Join-Path $root $name
        Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
    }
    foreach ($name in $legacyNames) {
        $old = Join-Path $target $name
        if (Test-Path -LiteralPath $old -PathType Leaf) { Remove-Item -LiteralPath $old -Force }
    }
    Write-Host "Backup: $backup"
    Write-Host 'Sync selesai. Periksa HERMES_SCANNER_PROJECT, restart Hermes/gateway dan reload plugin Desktop.'
}
