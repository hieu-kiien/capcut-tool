import os
import sys
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

# Adjust path to find modules properly
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure environment and inject resolved ffmpeg/ffprobe to PATH
import runtime_tools
runtime_tools.configure_environment()

from app.gui import MainWindow


def _install_default_font(app: QApplication) -> None:
    fonts_root = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    for name in ["segoeui.ttf", "arial.ttf", "tahoma.ttf"]:
        path = fonts_root / name
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))
            return


def main() -> int:
    # High-DPI rounding policy must be set before QApplication is created.
    # PassThrough gives crisp UI on fractional-scale Windows displays (125%, 150%).
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass

    app = QApplication(sys.argv[:1])
    
    # Enable high-DPI scaling styling if available
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
    
    _install_default_font(app)
    
    # Initialize SQLite Database
    from core.db import Database
    Database.init_db()
    
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
