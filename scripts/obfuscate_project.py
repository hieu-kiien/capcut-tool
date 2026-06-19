import os
import shutil
from pathlib import Path
from python_obfuscator.obfuscator import Obfuscator
from python_obfuscator.config import ObfuscationConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT
OBF_DIR = PROJECT_ROOT / "obfuscated"

def main():
    if OBF_DIR.exists():
        shutil.rmtree(OBF_DIR)
    OBF_DIR.mkdir()

    # Re-create folders
    (OBF_DIR / "app").mkdir()
    (OBF_DIR / "pyJianYingDraft").mkdir()

    # Disable variable_renamer, exec_wrapper, and dead_code_injector to preserve imports and prevent TypeError on Enum classes.
    config = ObfuscationConfig.all_enabled().without("variable_renamer", "exec_wrapper", "dead_code_injector")
    obfuscator = Obfuscator(config)

    # 1. Obfuscate top-level files
    top_level_files = [
        "main.py",
        "capcut_draft_creator.py",
        "capcut_keyframe_tool.py",
        "draft_doctor.py",
        "media_probe.py",
        "runtime_tools.py",
        "video_mixer.py"
    ]
    for filename in top_level_files:
        src_file = SRC_DIR / filename
        dest_file = OBF_DIR / filename
        if src_file.exists():
            obfuscate_file(src_file, dest_file, obfuscator)

    # 2. Obfuscate app folder files
    app_dir = SRC_DIR / "app"
    for file in app_dir.glob("*.py"):
        dest_file = OBF_DIR / "app" / file.name
        obfuscate_file(file, dest_file, obfuscator)

    # 3. Obfuscate pyJianYingDraft folder recursively
    py_draft_dir = SRC_DIR / "pyJianYingDraft"
    for file in py_draft_dir.rglob("*.py"):
        rel_path = file.relative_to(py_draft_dir)
        dest_file = OBF_DIR / "pyJianYingDraft" / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        obfuscate_file(file, dest_file, obfuscator)

    # 4. Copy assets folder (pyJianYingDraft/assets) as they are static template files needed at runtime
    src_assets = SRC_DIR / "pyJianYingDraft" / "assets"
    dest_assets = OBF_DIR / "pyJianYingDraft" / "assets"
    if src_assets.exists():
        shutil.copytree(src_assets, dest_assets, dirs_exist_ok=True)

    print("[SUCCESS] Project successfully obfuscated under 'obfuscated/' directory!")

def obfuscate_file(src: Path, dest: Path, obfuscator: Obfuscator):
    try:
        content = src.read_text(encoding="utf-8")
        # Ensure we don't crash on empty files
        if not content.strip():
            dest.write_text("", encoding="utf-8")
            return
        obfuscated = obfuscator.obfuscate(content)
        dest.write_text(obfuscated, encoding="utf-8")
        print(f"Obfuscated: {src.relative_to(PROJECT_ROOT)} -> {dest.relative_to(PROJECT_ROOT)}")
    except Exception as e:
        print(f"Error obfuscating {src.relative_to(PROJECT_ROOT)}: {e}")
        # fallback copy if obfuscation fails for syntax reasons
        shutil.copy2(src, dest)

if __name__ == "__main__":
    main()
