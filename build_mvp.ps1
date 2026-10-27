param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Python = if (Test-Path ".venv\Scripts\python.exe") {
    Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
} else {
    (Get-Command python).Source
}

Write-Host "Using Python: $Python" -ForegroundColor Cyan
& $Python main.py --diagnose
& $Python -m compileall app core pyJianYingDraft mvp_runtime main.py capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py -q

if (-not $SkipTests) {
    & $Python -m pytest -q tests
}

& $Python -m PyInstaller --noconfirm --clean capcut_mvp.spec
$OutputExe = "dist\CapCutLongStoryStudio\CapCutLongStoryStudio.exe"

if (Test-Path $OutputExe) {
    Write-Host "`nBuild completed: $OutputExe" -ForegroundColor Green
    if (Test-Path "scripts\sign_exe.ps1") {
        Write-Host "Applying Authenticode Code Signature..." -ForegroundColor Cyan
        & pwsh -NoProfile -File "scripts\sign_exe.ps1" -TargetExe $OutputExe
    }
} else {
    Write-Error "Build failed: Output executable not found at $OutputExe"
}
