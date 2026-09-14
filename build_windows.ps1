param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

Set-Location $projectRoot

if (-not (Test-Path -LiteralPath $python)) {
    python -m venv .venv
}

if (-not $SkipInstall) {
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements\base.txt -r requirements\packaging.txt
}

& $python -m PyInstaller --noconfirm --clean packaging\IMH-Oreka.spec

$executable = Join-Path $projectRoot "dist\IMH-Oreka\IMH-Oreka.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "No se ha generado $executable"
}

Write-Host "IMH Oreka generado correctamente: $executable"
