from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Sequence

from . import APP_NAME, APP_VERSION
from .app_paths import lock_path
from .diagnostics import run_diagnostics
from .logging_setup import configure_logging, install_exception_hook


def _configure_stdio() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def _handle_cli(args: Sequence[str]) -> int | None:
    if "--version" in args:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    if "--diagnose-json" in args:
        return run_diagnostics(as_json=True)
    if "--diagnose" in args:
        return run_diagnostics(as_json=False)
    return None


def run_app(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv)
    _configure_stdio()
    cli_result = _handle_cli(args[1:])
    if cli_result is not None:
        return cli_result

    configure_logging()
    install_exception_hook()
    logger = logging.getLogger(__name__)

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import runtime_tools

    runtime_tools.configure_environment()

    from PySide6.QtCore import QLockFile, Qt
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication, QMessageBox

    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        logger.debug("Could not set High-DPI rounding policy", exc_info=True)

    app = QApplication(args[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("CapCutTool")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

    lock = QLockFile(str(lock_path()))
    lock.setStaleLockTime(10_000)
    if not lock.tryLock(100):
        QMessageBox.information(
            None,
            APP_NAME,
            "Ứng dụng đang chạy. Hãy quay lại cửa sổ hiện có thay vì mở thêm một bản.",
        )
        return 3

    _install_default_font(app)

    from core.db import Database
    from app.gui import MainWindow

    Database.init_db()
    window = MainWindow()
    window.show()

    app.aboutToQuit.connect(lambda: logger.info("Application shutting down"))
    logger.info("Application started: version=%s", APP_VERSION)
    exit_code = app.exec()
    lock.unlock()
    return exit_code


def _install_default_font(app) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtGui import QFont, QFontDatabase

    candidates = []
    if os.name == "nt":
        fonts_root = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
        candidates.extend(fonts_root / name for name in ("segoeui.ttf", "arial.ttf", "tahoma.ttf"))

    for path in candidates:
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))
            return
