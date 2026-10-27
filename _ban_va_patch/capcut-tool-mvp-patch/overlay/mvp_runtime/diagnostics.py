from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from . import APP_NAME, APP_VERSION
from .app_paths import app_data_dir


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    required: bool = True


@dataclass(frozen=True)
class DiagnosticReport:
    app: str
    version: str
    python: str
    platform: str
    checks: List[Check]

    @property
    def ok(self) -> bool:
        return all(item.status == "ok" for item in self.checks if item.required)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["ok"] = self.ok
        return data


def _module_check(name: str, *, required: bool = True) -> Check:
    found = importlib.util.find_spec(name) is not None
    return Check(
        name=f"python_module:{name}",
        status="ok" if found else "error",
        detail="available" if found else "missing",
        required=required,
    )


def _binary_check(name: str, resolved: Optional[str] = None, *, required: bool = True) -> Check:
    path = resolved or shutil.which(name)
    return Check(
        name=f"binary:{name}",
        status="ok" if path else "error",
        detail=str(path or "not found"),
        required=required,
    )


def _path_check(path: Path, label: str, *, required: bool = True) -> Check:
    exists = path.exists()
    return Check(label, "ok" if exists else "error", str(path), required)


def _writable_check(path: Path) -> Check:
    try:
        path.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="capcut-mvp-", dir=path)
        os.close(fd)
        Path(temp_name).unlink(missing_ok=True)
        return Check("app_data_writable", "ok", str(path))
    except Exception as exc:
        return Check("app_data_writable", "error", f"{path}: {exc}")


def collect_diagnostics(project_root: Optional[Path] = None) -> DiagnosticReport:
    root = (project_root or Path(__file__).resolve().parents[1]).resolve()
    checks: List[Check] = [
        _path_check(root / "app" / "gui.py", "source:app/gui.py"),
        _path_check(root / "app" / "pipeline.py", "source:app/pipeline.py"),
        _path_check(root / "capcut_draft_creator.py", "source:capcut_draft_creator.py"),
        _module_check("PySide6"),
        _module_check("psutil", required=False),
        _module_check("pymediainfo", required=False),
        _writable_check(app_data_dir()),
    ]

    ffmpeg = None
    ffprobe = None
    try:
        import runtime_tools

        ffmpeg = runtime_tools.resolve_ffmpeg()
        ffprobe = runtime_tools.resolve_ffprobe()
    except Exception as exc:
        checks.append(Check("runtime_tools", "error", str(exc)))

    checks.extend(
        [
            _binary_check("ffmpeg", ffmpeg),
            _binary_check("ffprobe", ffprobe, required=False),
        ]
    )

    return DiagnosticReport(
        app=APP_NAME,
        version=APP_VERSION,
        python=sys.version.split()[0],
        platform=f"{platform.system()} {platform.release()} ({platform.machine()})",
        checks=checks,
    )


def render_text(report: DiagnosticReport) -> str:
    lines = [
        f"{report.app} {report.version}",
        f"Python: {report.python}",
        f"Platform: {report.platform}",
        "",
    ]
    for item in report.checks:
        marker = "OK" if item.status == "ok" else ("WARN" if not item.required else "ERROR")
        lines.append(f"[{marker}] {item.name}: {item.detail}")
    lines.append("")
    lines.append("RESULT: READY" if report.ok else "RESULT: NOT READY")
    return "\n".join(lines)


def run_diagnostics(*, as_json: bool = False, project_root: Optional[Path] = None) -> int:
    report = collect_diagnostics(project_root)
    if as_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 0 if report.ok else 2
