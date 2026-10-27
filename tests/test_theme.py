import os
import sys
import subprocess
import pytest

def test_theme_tokens():
    from app.theme import (
        DARK_BG, SURFACE_BG, GRADIENT_PRIMARY, FONT_CONSOLE, FONT_FAMILY,
        get_application_stylesheet
    )
    
    # 3-Layer Design Tokens
    assert DARK_BG == "#121214", f"Expected Dark Obsidian #121214, got {DARK_BG}"
    assert SURFACE_BG == "#1E1E22", f"Expected Surface #1E1E22, got {SURFACE_BG}"
    assert "#00F2FE" in GRADIENT_PRIMARY and "#7F00FF" in GRADIENT_PRIMARY
    
    # Typography: Inter for UI, JetBrains Mono for Console
    assert "Inter" in FONT_FAMILY
    assert "JetBrains Mono" in FONT_CONSOLE
    
    # Verify Stylesheet contains primary CTAs with gradient
    ss = get_application_stylesheet()
    assert "#btnRun" in ss
    assert "#btnBuildNow" in ss
    assert "#btnAddQueue" in ss
    assert GRADIENT_PRIMARY in ss
    assert "JetBrains Mono" in ss
    
    # Verify old teal / indigo tokens are purged
    assert "#0dd3ba" not in ss
    assert "rgba(13, 211, 186" not in ss
    assert "#312e81" not in ss

def test_theme_file_no_legacy_tokens():
    theme_file = os.path.join(os.path.dirname(__file__), "..", "app", "theme.py")
    with open(theme_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "#0dd3ba" not in content
    assert "rgba(13, 211, 186" not in content
    assert "#312e81" not in content

def test_svg_icons_and_info():
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    code = """
import sys
from PySide6.QtWidgets import QApplication
from app.icons import get_svg_icon, SVG_ICONS

app = QApplication.instance() or QApplication(sys.argv)

assert "info" in SVG_ICONS, "info icon missing from SVG_ICONS"
icon = get_svg_icon("info", color="#00F2FE", size=16)
assert not icon.isNull(), "info icon is null"

icon_capcut = get_svg_icon("capcut", color="#ffffff", size=16)
assert not icon_capcut.isNull(), "capcut icon is null"

icon_sparkles = get_svg_icon("sparkles", color="#00F2FE", size=14)
assert not icon_sparkles.isNull(), "sparkles icon is null"

sys.exit(0)
"""
    res = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=20)
    assert res.returncode == 0, f"Error in test_svg_icons: {res.stderr}\\n{res.stdout}"
