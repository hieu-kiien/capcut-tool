from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PATCH_VERSION = "0.1.0-mvp"
BUNDLE_ROOT = Path(__file__).resolve().parent
OVERLAY_ROOT = BUNDLE_ROOT / "overlay"

PIPELINE_OLD = "report = run_preflight(self.config)"
PIPELINE_NEW = "report = run_preflight(self.config, fast_mode=True)"

PREFLIGHT_OLD = '''            # Check media dir write permission (optional warning, but original did error)
            try:
                test_file = media_dir / f".write_test_{int(time.time())}"
                test_file.write_text("test", encoding="utf-8")
                test_file.unlink()
                media_ok = True
            except Exception as exc:
                issues.append(PreflightIssue(
                    code="media",
                    severity="error",
                    message=f"Không có quyền ghi vào thư mục video/hình nền: {exc}",
                    blocks_run=True
                ))

            # Scan and count media files
'''


VOICE_FAST_OLD = '''            if fast_mode:
                voice_ok = True
                voice_duration_sec = 0.0
            else:
                voice_asset = media_probe.probe_media(voice_path)
                if voice_asset.error:
                    issues.append(PreflightIssue(
                        code="voice",
                        severity="error",
                        message=f"Không thể đọc thông tin tệp giọng đọc: {voice_asset.error}",
                        blocks_run=True
                    ))
                else:
                    voice_duration_sec = voice_asset.duration_us / 1e6
                    voice_ok = True
'''

VOICE_FAST_NEW = '''            # Fast mode skips expensive background-library probes only.
            # The single voice file is still validated so preflight errors stay accurate.
            voice_asset = media_probe.probe_media(voice_path)
            if voice_asset.error:
                issues.append(PreflightIssue(
                    code="voice",
                    severity="error",
                    message=f"Không thể đọc thông tin tệp giọng đọc: {voice_asset.error}",
                    blocks_run=True
                ))
            else:
                voice_duration_sec = voice_asset.duration_us / 1e6
                voice_ok = True
'''

PREFLIGHT_NEW = '''            # Media is an input source. Requiring write access rejects valid
            # read-only libraries and creates unnecessary temporary files.
            # Actual read/list errors are handled by the scan block below.
            media_ok = True
            # Scan and count media files
'''


@dataclass(frozen=True)
class Change:
    path: str
    action: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply CapCut Tool MVP hardening patch")
    parser.add_argument("repo", nargs="?", default=".", help="Path to capcut-tool repository")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show changes only")
    parser.add_argument("--test", action="store_true", help="Run compileall and pytest after patch")
    parser.add_argument("--restore-latest", action="store_true", help="Restore most recent backup")
    return parser.parse_args()


def validate_repo(root: Path) -> None:
    required = [
        root / "app" / "pipeline.py",
        root / "app" / "preflight.py",
        root / "app" / "gui.py",
        root / "capcut_draft_creator.py",
        root / "runtime_tools.py",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Không đúng repository hoặc thiếu file: " + ", ".join(missing))


def iter_overlay_files() -> Iterable[Path]:
    yield from sorted(
        path
        for path in OVERLAY_ROOT.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix.lower() not in {".pyc", ".pyo"}
    )


def backup_paths(root: Path, backup: Path, relative_paths: Iterable[Path]) -> None:
    for rel in relative_paths:
        source = root / rel
        if not source.exists():
            continue
        destination = backup / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def patch_text(path: Path, old: str, new: str, *, dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    old = old.replace("\r\n", "\n")
    new = new.replace("\r\n", "\n")
    if new in text:
        return False
    if old not in text:
        raise RuntimeError(f"Không tìm thấy đoạn mã dự kiến trong {path}")
    if not dry_run:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def apply_patch(root: Path, *, dry_run: bool, run_tests: bool) -> int:
    validate_repo(root)
    overlay_rel = [path.relative_to(OVERLAY_ROOT) for path in iter_overlay_files()]
    touched = set(overlay_rel) | {Path("app/pipeline.py"), Path("app/preflight.py")}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = root / ".mvp-backup" / stamp

    changes: list[Change] = []
    if not dry_run:
        backup_paths(root, backup, touched)
        backup.mkdir(parents=True, exist_ok=True)
        created_files = [str(rel) for rel in overlay_rel if not (root / rel).exists()]
        (backup / ".mvp-backup-manifest.json").write_text(
            json.dumps({"created_files": created_files}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    for source in iter_overlay_files():
        rel = source.relative_to(OVERLAY_ROOT)
        destination = root / rel
        changes.append(Change(str(rel), "create" if not destination.exists() else "replace"))
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    if patch_text(root / "app" / "pipeline.py", PIPELINE_OLD, PIPELINE_NEW, dry_run=dry_run):
        changes.append(Change("app/pipeline.py", "fast preflight"))
    preflight_path = root / "app" / "preflight.py"
    if patch_text(preflight_path, VOICE_FAST_OLD, VOICE_FAST_NEW, dry_run=dry_run):
        changes.append(Change("app/preflight.py", "accurate fast preflight voice validation"))
    if patch_text(preflight_path, PREFLIGHT_OLD, PREFLIGHT_NEW, dry_run=dry_run):
        changes.append(Change("app/preflight.py", "read-only media support"))

    manifest = {
        "patch_version": PATCH_VERSION,
        "applied_at": stamp,
        "backup": str(backup),
        "changes": [change.__dict__ for change in changes],
    }

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if dry_run:
        return 0

    (root / "MVP_PATCH_APPLIED.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    commands = [
        [sys.executable, "-m", "compileall", "mvp_runtime", "main.py", "app/pipeline.py", "app/preflight.py", "-q"],
    ]
    if run_tests:
        commands.append([sys.executable, "-m", "pytest", "-q", "tests"])

    for command in commands:
        print("+", " ".join(command))
        subprocess.run(command, cwd=root, check=True)
    return 0


def restore_latest(root: Path) -> int:
    backup_root = root / ".mvp-backup"
    backups = sorted(path for path in backup_root.glob("*") if path.is_dir())
    if not backups:
        raise SystemExit("Không tìm thấy backup trong .mvp-backup")
    backup = backups[-1]
    manifest_path = backup / ".mvp-backup-manifest.json"
    created_files = []
    if manifest_path.is_file():
        created_files = json.loads(manifest_path.read_text(encoding="utf-8")).get("created_files", [])

    removed = 0
    for rel_text in created_files:
        target = root / rel_text
        if target.is_file():
            target.unlink()
            removed += 1

    restored = 0
    for source in backup.rglob("*"):
        if not source.is_file() or source == manifest_path:
            continue
        rel = source.relative_to(backup)
        destination = root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        restored += 1
    print(f"Đã khôi phục {restored} file và xóa {removed} file mới từ {backup}")
    return 0


def main() -> int:
    args = parse_args()
    root = Path(args.repo).expanduser().resolve()
    if args.restore_latest:
        return restore_latest(root)
    return apply_patch(root, dry_run=args.dry_run, run_tests=args.test)


if __name__ == "__main__":
    raise SystemExit(main())
