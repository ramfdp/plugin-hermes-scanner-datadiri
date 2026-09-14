# Run locally after OCR verification; these locations are outside the agent workspace.
$ErrorActionPreference = 'Stop'
if (-not $env:HERMES_HOME) { throw 'HERMES_HOME belum disetel.' }
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

# Only remove the two identified legacy OCR model directories, never the cache root.
$cacheRoot = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE '.paddlex/official_models'))
foreach ($name in @('PaddleOCR-VL-1.6', 'PP-DocLayoutV3')) {
    $target = [IO.Path]::GetFullPath((Join-Path $cacheRoot $name))
    if ([IO.Path]::GetDirectoryName($target) -ne $cacheRoot) { throw "Target tidak valid: $target" }
    if (Test-Path -LiteralPath $target) {
        if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Tidak menghapus link/junction: $target"
        }
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
Write-Host 'Plugin MinerU diperbarui dan dua cache model lama dihapus. Restart Hermes.'
