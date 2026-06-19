from __future__ import annotations

import os
import re
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


BACKUP_DIR_RE = re.compile(r"^(.+)_bak_\d{8}_\d{6}(?:_\d+)?$")
PARTIAL_DIR_RE = re.compile(r"^_partial_(.+)_\d{8}_\d{6}(?:_\d+)?$")


@dataclass
class CleanupArtifact:
    path: str
    name: str
    type: str
    size: int
    age_days: float


@dataclass
class CleanupResult:
    dry_run: bool = False
    planned: int = 0
    deleted: int = 0
    skipped: int = 0
    bytes_planned: int = 0
    bytes_removed: int = 0
    artifacts: list[CleanupArtifact] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def list_cleanup_artifacts(
    draft_root: str | Path,
    *,
    project_name: str | None = None,
    keep_days: int = 7,
) -> CleanupResult:
    return cleanup_draft_artifacts(
        draft_root,
        project_name=project_name,
        keep_days=keep_days,
        dry_run=True,
    )


def cleanup_draft_artifacts(
    draft_root: str | Path,
    *,
    project_name: str | None = None,
    keep_days: int = 7,
    dry_run: bool = False,
) -> CleanupResult:
    root = Path(draft_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Draft root khong hop le: {root}")

    cutoff = time.time() - max(0, int(keep_days)) * 86400
    now = time.time()
    result = CleanupResult(dry_run=bool(dry_run))

    for candidate in _iter_safe_artifacts(root, project_name):
        try:
            resolved = candidate.resolve()
            if not _is_relative_to(resolved, root):
                result.skipped += 1
                result.errors.append(f"Skipped outside draft root: {candidate}")
                continue
            if candidate.stat().st_mtime >= cutoff:
                result.skipped += 1
                continue

            size = _path_size(candidate)
            artifact = _artifact_info(candidate, root, size, now)
            result.artifacts.append(artifact)
            result.planned += 1
            result.bytes_planned += size

            if dry_run:
                continue

            if candidate.is_dir():
                shutil.rmtree(candidate)
            else:
                candidate.unlink()
            result.deleted += 1
            result.bytes_removed += size
        except Exception as exc:
            result.skipped += 1
            result.errors.append(f"{candidate}: {exc}")

    return result


def _iter_safe_artifacts(root: Path, project_name: str | None):
    project_names = {project_name} if project_name else None

    for child in root.iterdir():
        if not child.is_dir():
            continue
        match = BACKUP_DIR_RE.match(child.name)
        if match and (project_names is None or match.group(1) in project_names):
            yield child
            continue
        match = PARTIAL_DIR_RE.match(child.name)
        if match and (project_names is None or match.group(1) in project_names):
            yield child

    if project_name:
        project_dir = root / project_name
        if project_dir.exists() and project_dir.is_dir():
            yield from _iter_project_bak_files(project_dir)


def _iter_project_bak_files(project_dir: Path):
    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [name for name in dirnames if name not in {"__pycache__"}]
        base = Path(dirpath)
        for name in filenames:
            if name.endswith(".bak"):
                yield base / name


def _path_size(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat().st_size
        total = 0
        for file in path.rglob("*"):
            try:
                if file.is_file():
                    total += file.stat().st_size
            except OSError:
                pass
        return total
    except OSError:
        return 0


def _artifact_info(path: Path, root: Path, size: int, now: float) -> CleanupArtifact:
    try:
        rel_path = path.resolve().relative_to(root).as_posix()
    except Exception:
        rel_path = str(path)
    try:
        age_days = max(0.0, (now - path.stat().st_mtime) / 86400)
    except OSError:
        age_days = 0.0
    return CleanupArtifact(
        path=rel_path,
        name=path.name,
        type=_artifact_type(path),
        size=size,
        age_days=round(age_days, 1),
    )


def _artifact_type(path: Path) -> str:
    if path.is_file() and path.name.endswith(".bak"):
        return "bak_file"
    if path.is_dir() and BACKUP_DIR_RE.match(path.name):
        return "backup_dir"
    if path.is_dir() and PARTIAL_DIR_RE.match(path.name):
        return "partial_dir"
    return "unknown"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
