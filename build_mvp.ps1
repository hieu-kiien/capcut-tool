param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.11 -m venv .venv
}

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt -r requirements-dev.txt
& $Python main.py --diagnose
& $Python -m compileall app core pyJianYingDraft mvp_runtime main.py capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py -q

if (-not $SkipTests) {
    & $Python -m pytest -q tests
}

& $Python -m PyInstaller --noconfirm --clean capcut_mvp.spec
Write-Host "`nBuild completed: dist\CapCutLongStoryStudio\CapCutLongStoryStudio.exe" -ForegroundColor Green
