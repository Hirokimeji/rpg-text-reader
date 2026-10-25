$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
py -m PyInstaller --noconfirm textlight.spec
if ($LASTEXITCODE -ne 0) { throw '打包失败。' }
Write-Output '已生成 dist\台词拾光.exe'
