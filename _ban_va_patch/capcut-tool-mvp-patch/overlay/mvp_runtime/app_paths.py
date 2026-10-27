from __future__ import annotations

import os
from pathlib import Path

from . import APP_NAME


def _safe_name(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum() or ch in "-_ ").strip().replace(" ", "-")


def app_data_dir() -> Path:
    """Return a writable per-user application data directory."""
    override = os.environ.get("CAPCUT_TOOL_APPDATA", "").strip()
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        root = root / _safe_name(APP_NAME)
    elif sys_platform() == "darwin":
        root = Path.home() / "Library" / "Application Support" / _safe_name(APP_NAME)
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        root = root / _safe_name(APP_NAME)
    root.mkdir(parents=True, exist_ok=True)
    return root


def logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def lock_path() -> Path:
    return app_data_dir() / "app.lock"


def crash_dir() -> Path:
    path = app_data_dir() / "crashes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sys_platform() -> str:
    import sys

    return sys.platform
