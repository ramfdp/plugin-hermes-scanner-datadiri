# Run locally after OCR verification; these locations are outside the agent workspace.
$ErrorActionPreference = 'Stop'
if (-not $env:HERMES_HOME) { throw 'HERMES_HOME belum disetel.' }
foreach ($name in @('__init__.py', 'tools.py', 'schemas.py', 'plugin.yaml', 'desktop/plugin.js', 'templates/daftar_tenaga_ahli/schema.json', '.venv/Scripts/python.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $name) -PathType Leaf)) {
        throw "File runtime belum tersedia: $name"
    }
}
$pluginTarget = Join-Path $env:HERMES_HOME 'plugins/hermes-scanner-datadiri'
if (-not (Test-Path -LiteralPath $pluginTarget -PathType Container)) {
    throw "Plugin tidak ditemukan: $pluginTarget"
}
$backup = Join-Path $PSScriptRoot ('output/plugin-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup | Out-Null
foreach ($name in @('__init__.py', 'tools.py', 'schemas.py', 'plugin.yaml')) {
    $installed = Join-Path $pluginTarget $name
    if (Test-Path -LiteralPath $installed) { Copy-Item -LiteralPath $installed -Destination $backup }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $installed -Force
}
# Desktop plugins use a separate loader from Python tool plugins.
$desktopTarget = Join-Path $env:HERMES_HOME 'desktop-plugins/hermes-scanner-datadiri'
New-Item -ItemType Directory -Path $desktopTarget -Force | Out-Null
$desktopPlugin = Join-Path $desktopTarget 'plugin.js'
if (Test-Path -LiteralPath $desktopPlugin) {
    Copy-Item -LiteralPath $desktopPlugin -Destination (Join-Path $backup 'desktop-plugin.js')
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'desktop/plugin.js') -Destination $desktopPlugin -Force
Write-Host 'Plugin diperbarui. Restart Hermes; runtime menggunakan HERMES_SCANNER_PROJECT.'
