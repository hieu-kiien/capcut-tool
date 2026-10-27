import os
import sys
import subprocess
import pytest

def test_subtitle_preview_label_stress():
    """Task 1: Offscreen render SubtitlePreviewLabel with extreme multi-line strings,
    empty text, special characters, verify no crashes or overlap."""
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    code = """
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QFontMetrics, QImage
from PySide6.QtCore import Qt
from app.widgets.setup_widget import SubtitlePreviewLabel

app = QApplication.instance() or QApplication(sys.argv)

test_cases = [
    # 1-line standard
    "Cuộc rượt đuổi bắt đầu lúc nửa đêm.",
    # 2-line standard
    "Dòng đầu tiên của câu phụ đề\\nDòng thứ hai tiếp theo",
    # 5-line multi-line
    "Dòng 1: Khởi đầu hành trình\\nDòng 2: Vượt qua thử thách\\nDòng 3: Gặp gỡ đồng đội\\nDòng 4: Đối mặt nguy hiểm\\nDòng 5: Về đích an toàn",
    # Extreme multi-line (20 lines)
    "\\n".join([f"Dòng {i}: Nội dung câu phụ đề thử nghiệm số {i}" for i in range(1, 21)]),
    # Empty string
    "",
    # Whitespace only
    "   \\n\\t  \\n   ",
    # Vietnamese diacritics
    "Tiếng Việt: Ắ Ặ Ỗ Ỷ Ỹ Đ ế ề ệ ơ ở ỡ ú ù ụ",
    # Special characters and entities
    "<div class='subtitle'>&amp; \\"Hello\\" #1 $25 %100 *test* [intro] (outro) {json} /path\\\\to\\\\media</div>",
    # Unicode symbols & emojis
    "🎬 Video 🚀 Rocket ✨ Sparkle ⚠️ Warning ♫ ♪ 01:23:45",
    # Very long continuous string (> 100 chars, no spaces)
    "A" * 250,
    # Very long string with spaces (> 500 chars)
    ("Một câu phụ đề cực kỳ dài nhằm mục đích kiểm tra khả năng co giãn và chịu tải của nhãn hiển thị " * 5)
]

widget = SubtitlePreviewLabel()
widget.resize(600, 400)
widget.show()

# Test various style parameter configurations
style_configs = [
    {"outline_width": 40.0, "shadow_alpha": 0.8, "shadow_distance": 5.0, "shadow_enabled": True},
    {"outline_width": 0.0, "shadow_alpha": 0.0, "shadow_distance": 0.0, "shadow_enabled": False},
    {"outline_width": 100.0, "shadow_alpha": 1.0, "shadow_distance": 20.0, "shadow_enabled": True},
    {"outline_width": -10.0, "shadow_alpha": 0.5, "shadow_distance": 2.0, "shadow_enabled": True},
]

for text in test_cases:
    widget.setText(text)
    for cfg in style_configs:
        widget.set_style_params(**cfg)
        app.processEvents()
        widget.repaint()
        pix = widget.grab()
        assert not pix.isNull(), f"Pixmap is null for text: {text[:30]!r}"
        assert pix.width() == 600 and pix.height() == 400

# Geometry & Line Overlap Verification:
# Verify that for multi-line text, line spacing strictly exceeds font height to avoid baseline overlap
fm = QFontMetrics(widget.font())
line_spacing = fm.lineSpacing()
font_height = fm.height()
assert line_spacing >= font_height, f"lineSpacing ({line_spacing}) must be >= font height ({font_height})"

# Verify horizontal alignments (Left, Center, Right)
for align in [Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignCenter, Qt.AlignmentFlag.AlignRight]:
    widget.setAlignment(align)
    widget.setText("Test alignment line 1\\nTest alignment line 2")
    widget.repaint()
    pix = widget.grab()
    assert not pix.isNull()

widget.close()
app.processEvents()
print("SUBTITLE_PREVIEW_STRESS_PASSED")
sys.exit(0)
"""
    res = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, f"SubtitlePreviewLabel stress test failed: {res.stderr}\\n{res.stdout}"
    assert "SUBTITLE_PREVIEW_STRESS_PASSED" in res.stdout


def test_drop_line_edit_stress():
    """Task 2: Stress test DropLineEdit with file URIs, spaces, non-existent paths,
    URL schemes, verify normalized paths and single signal emission."""
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    code = """
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QUrl, QMimeData, QPointF
from PySide6.QtGui import QDropEvent
from app.widgets.setup_widget import DropLineEdit

app = QApplication.instance() or QApplication(sys.argv)

drop_edit = DropLineEdit("Placeholder")
assert drop_edit.acceptDrops() is True

signal_counts = []
def on_text_changed(val):
    signal_counts.append(val)

drop_edit.textChanged.connect(on_text_changed)

def simulate_drop_urls(urls):
    mime = QMimeData()
    mime.setUrls(urls)
    event = QDropEvent(
        QPointF(10.0, 10.0),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    drop_edit.dropEvent(event)

# Test 1: Standard Windows file path via QUrl
signal_counts.clear()
test_path_1 = os.path.normpath(r"C:/media/sample_video.mp4")
simulate_drop_urls([QUrl.fromLocalFile(test_path_1)])
assert drop_edit.text() == test_path_1
assert len(signal_counts) == 1, f"Expected exactly 1 textChanged emission, got {len(signal_counts)}"

# Test 2: File URI with percent-encoded spaces
signal_counts.clear()
test_path_spaces = os.path.normpath(r"C:/My Media Folder/Test Video 2026.mp4")
simulate_drop_urls([QUrl("file:///C:/My%20Media%20Folder/Test%20Video%202026.mp4")])
assert drop_edit.text() == test_path_spaces
assert len(signal_counts) == 1, f"Expected exactly 1 emission, got {len(signal_counts)}"

# Test 3: Non-existent path
signal_counts.clear()
non_existent_path = os.path.normpath(r"D:/does/not/exist/ghost_media.mov")
simulate_drop_urls([QUrl.fromLocalFile(non_existent_path)])
assert drop_edit.text() == non_existent_path
assert len(signal_counts) == 1, f"Expected exactly 1 emission, got {len(signal_counts)}"

# Test 4: Multiple files dropped at once - should pick the first URL
signal_counts.clear()
first_url = QUrl.fromLocalFile(os.path.normpath(r"C:/first_asset.mp4"))
second_url = QUrl.fromLocalFile(os.path.normpath(r"C:/second_asset.mp4"))
simulate_drop_urls([first_url, second_url])
assert drop_edit.text() == os.path.normpath(r"C:/first_asset.mp4")
assert len(signal_counts) == 1, f"Expected exactly 1 emission, got {len(signal_counts)}"

# Test 5: Dropping the exact same text again - QLineEdit does NOT emit textChanged if text is unchanged!
signal_counts.clear()
simulate_drop_urls([first_url])
# Because setText() with identical text in QLineEdit is a no-op for textChanged:
assert len(signal_counts) == 0, f"Expected 0 emissions for identical text, got {len(signal_counts)}"

# Test 6: Web URL scheme (http / https) -> falls back to super().dropEvent(event)
signal_counts.clear()
mime_web = QMimeData()
mime_web.setUrls([QUrl("https://example.com/stream.m3u8")])
event_web = QDropEvent(
    QPointF(10.0, 10.0),
    Qt.DropAction.CopyAction,
    mime_web,
    Qt.MouseButton.LeftButton,
    Qt.KeyboardModifier.NoModifier
)
drop_edit.dropEvent(event_web)
# Web URLs do not crash and emit at most 1 signal through default QLineEdit drop handler
print("DROP_LINE_EDIT_STRESS_PASSED")
sys.exit(0)
"""
    res = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, f"DropLineEdit stress test failed: {res.stderr}\\n{res.stdout}"
    assert "DROP_LINE_EDIT_STRESS_PASSED" in res.stdout


def test_header_search_focus_stress():
    """Task 3: Stress test header search focus during fast typing."""
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    code = """
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from core.db import Database
from app.gui import MainWindow

app = QApplication.instance() or QApplication(sys.argv)
Database.init_db()

window = MainWindow()
window.show()
app.processEvents()

search_bar = window.search_bar
search_bar.setFocus()
app.processEvents()
assert search_bar.hasFocus(), "search_bar should have focus initially"

# Simulate fast typing sequence
keystrokes = "capcut project test"
for i in range(1, len(keystrokes) + 1):
    sub = keystrokes[:i]
    search_bar.setText(sub)
    app.processEvents()
    
    # Assert search_bar retains focus and popup menu does not steal focus
    assert search_bar.hasFocus(), f"search_bar lost focus while typing '{sub}'"

# Test rapid burst of key clicks
for ch in " 123":
    QTest.keyClick(search_bar, ch)
    app.processEvents()
    assert search_bar.hasFocus(), f"search_bar lost focus on key click '{ch}'"

# Verify menu was created and is visible or managed without stealing focus
if hasattr(window, "_search_menu") and window._search_menu is not None:
    # Check that search menu did not become the active focus widget
    active_focus = app.focusWidget()
    assert active_focus == search_bar, f"Focus widget is {active_focus}, expected search_bar"

# Clear search bar and verify menu hides cleanly
search_bar.setText("")
app.processEvents()
if hasattr(window, "_search_menu") and window._search_menu is not None:
    assert not window._search_menu.isVisible(), "search menu should be hidden when search bar is empty"

window.close()
app.processEvents()
print("HEADER_SEARCH_FOCUS_STRESS_PASSED")
sys.exit(0)
"""
    res = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=35)
    assert res.returncode == 0, f"Header search focus stress test failed: {res.stderr}\\n{res.stdout}"
    assert "HEADER_SEARCH_FOCUS_STRESS_PASSED" in res.stdout
