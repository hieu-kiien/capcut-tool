# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)

datas = []
for source, destination in (
    (ROOT / "assets", "assets"),
    (ROOT / "profiles", "profiles"),
    (ROOT / "pyJianYingDraft" / "assets", "pyJianYingDraft/assets"),
    (ROOT / "pyJianYingDraft" / "metadata", "pyJianYingDraft/metadata"),
):
    if source.exists():
        datas.append((str(source), destination))
for filename in ("profiles.json",):
    path = ROOT / filename
    if path.exists():
        datas.append((str(path), "."))

binaries = []
for candidate in (
    ROOT / "ffmpeg.exe",
    ROOT / "ffprobe.exe",
    ROOT / "tools" / "ffmpeg.exe",
    ROOT / "tools" / "ffprobe.exe",
):
    if candidate.exists():
        binaries.append((str(candidate), "."))

hiddenimports = []
for package in ("app", "core", "pyJianYingDraft"):
    hiddenimports.extend(collect_submodules(package))

excluded = [
    "torch",
    "tensorflow",
    "cv2",
    "matplotlib",
    "scipy",
    "pandas",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CapCutLongStoryStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CapCutLongStoryStudio",
)
