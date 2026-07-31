import sys
import subprocess
import os

def test_subtitle_preview_label_render():
    # Process cha (parent process) must NOT import PySide6 or SubtitlePreviewLabel
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    code = """
import sys
from PySide6.QtGui import QGuiApplication, QColor
from PySide6.QtWidgets import QApplication
from app.widgets.setup_widget import SubtitlePreviewLabel

# Create QApplication
app = QApplication.instance() or QApplication(sys.argv)

# Assert QGuiApplication.platformName().lower() == "offscreen"
assert QGuiApplication.platformName().lower() == "offscreen", f"Platform is {QGuiApplication.platformName()}"

# Create SubtitlePreviewLabel
widget = SubtitlePreviewLabel("Cuộc rượt đuổi bắt đầu lúc nửa đêm.")

# Set style parameters
widget.set_style_params(
    outline_width=40.0,
    shadow_alpha=0.8,
    shadow_distance=5.0,
    shadow_enabled=True
)
widget.outline_color = QColor("#000000")

# Call show(), processEvents(), repaint(), and grab()
widget.show()
app.processEvents()
widget.repaint()

pixmap = widget.grab()

# Asserts pixmap is not null and has positive size
assert pixmap is not None, "grab() returned None"
assert not pixmap.isNull(), "Grabbed pixmap is null"
assert pixmap.width() > 0, "Pixmap width is zero or negative"
assert pixmap.height() > 0, "Pixmap height is zero or negative"

# Asserts style parameters on the widget are correct
assert widget.outline_width == 40.0
assert widget.shadow_alpha == 0.8
assert widget.shadow_distance == 5.0
assert widget.shadow_enabled is True

# Close the widget cleanly
widget.close()
app.processEvents()

sys.exit(0)
"""

    # Spawn subprocess with a 25-second timeout
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            timeout=25
        )
    except subprocess.TimeoutExpired as e:
        print("Subprocess timed out!")
        if e.stdout:
            print(f"Subprocess stdout:\n{e.stdout}")
        if e.stderr:
            print(f"Subprocess stderr:\n{e.stderr}")
        raise

    if result.returncode != 0:
        print(f"Subprocess failed with return code {result.returncode}")
        print(f"Subprocess stdout:\n{result.stdout}")
        print(f"Subprocess stderr:\n{result.stderr}")
    assert result.returncode == 0
