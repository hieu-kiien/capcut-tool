from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

from .app_paths import crash_dir, logs_dir

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(level: int = logging.INFO) -> Path:
    """Configure idempotent console + rotating-file logging."""
    log_path = logs_dir() / "capcut-tool.log"
    root = logging.getLogger()
    root.setLevel(level)

    if not any(getattr(handler, "_capcut_mvp", False) for handler in root.handlers):
        formatter = logging.Formatter(LOG_FORMAT)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler._capcut_mvp = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)

        if not getattr(sys, "frozen", False):
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            console._capcut_mvp = True  # type: ignore[attr-defined]
            root.addHandler(console)

    logging.captureWarnings(True)
    logging.getLogger(__name__).info("Logging initialized: %s", log_path)
    return log_path


def write_crash_report(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    exc_tb: Optional[TracebackType],
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = crash_dir() / f"crash-{stamp}-{os.getpid()}.log"
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    report.write_text(text, encoding="utf-8")
    logging.getLogger(__name__).critical("Unhandled exception\n%s", text)
    return report


def install_exception_hook() -> None:
    original = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):  # type: ignore[no-untyped-def]
        if issubclass(exc_type, KeyboardInterrupt):
            original(exc_type, exc_value, exc_tb)
            return
        try:
            report = write_crash_report(exc_type, exc_value, exc_tb)
            _show_crash_dialog(exc_value, report)
        except Exception:
            original(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def _show_crash_dialog(exc: BaseException, report: Path) -> None:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            return
        message = (
            "Ứng dụng gặp lỗi ngoài dự kiến. Dữ liệu lỗi đã được lưu để chẩn đoán.\n\n"
            f"Lỗi: {exc}\n\nTệp báo cáo: {report}"
        )
        QMessageBox.critical(None, "CapCut Tool - Lỗi", message)
    except Exception:
        return
