import os
import sys
import subprocess
import pytest

def test_studio_splitter_and_components():
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    code = """
import sys
import os
from PySide6.QtWidgets import QApplication, QSplitter
from PySide6.QtCore import Qt, QUrl, QMimeData, QPointF
from PySide6.QtGui import QDropEvent
from app.widgets.setup_widget import SetupWidget, DropLineEdit, SubtitlePreviewLabel
from app.widgets.effects_widget import EffectsWidget
from app.widgets.history_widget import HistoryWidget
from app.widgets.media_studio_widget import MediaStudioWidget

app = QApplication.instance() or QApplication(sys.argv)

# 1. SetupWidget & 3-Column Splitter
setup = SetupWidget()
assert hasattr(setup, "studio_splitter"), "studio_splitter missing on SetupWidget"
assert isinstance(setup.studio_splitter, QSplitter), "studio_splitter is not a QSplitter"
assert setup.studio_splitter.count() == 3, f"studio_splitter count is {setup.studio_splitter.count()}, expected 3"

# Verify 5 file inputs in Left panel are DropLineEdit
for attr in ["draft_root", "media_dir", "srt_path", "voice_path", "bgm_path"]:
    w = getattr(setup, attr, None)
    assert isinstance(w, DropLineEdit), f"{attr} is not an instance of DropLineEdit"

# Verify Center panel has SubtitlePreviewLabel & TimelineWidget
assert isinstance(setup.preview_label, SubtitlePreviewLabel), "preview_label is not SubtitlePreviewLabel"
assert hasattr(setup, "timeline_widget"), "timeline_widget missing from SetupWidget"
assert setup.timeline_widget is not None, "timeline_widget is None"

# Verify CapCut direct launch button
assert hasattr(setup, "btn_capcut_launch"), "btn_capcut_launch missing"
assert setup.btn_capcut_launch is not None

# 2. Test DropLineEdit drag-and-drop & path normalization
drop_edit = DropLineEdit()
assert "paintEvent" not in DropLineEdit.__dict__, "DropLineEdit must NOT override paintEvent"

# Simulate drop event with file url
sample_path = os.path.normpath(r"C:/test/path/sample.mp4")
mime = QMimeData()
mime.setUrls([QUrl.fromLocalFile(sample_path)])
event = QDropEvent(
    QPointF(10.0, 10.0),
    Qt.DropAction.CopyAction,
    mime,
    Qt.MouseButton.LeftButton,
    Qt.KeyboardModifier.NoModifier
)
drop_edit.dropEvent(event)
assert drop_edit.text() == sample_path, f"Expected {sample_path}, got {drop_edit.text()}"

# 3. Test SubtitlePreviewLabel multi-line rendering
multiline_label = SubtitlePreviewLabel("Dòng đầu tiên của câu phụ đề\\nDòng thứ hai tiếp theo")
multiline_label.resize(400, 200)
multiline_label.show()
app.processEvents()
multiline_label.repaint()
pix = multiline_label.grab()
assert not pix.isNull(), "Grabbed pixmap for multiline subtitle is null"
assert pix.width() > 0 and pix.height() > 0

# 4. Verify DropLineEdit deployment across other widgets
effects = EffectsWidget()
assert isinstance(effects.logo_path, DropLineEdit), "effects.logo_path is not DropLineEdit"
assert isinstance(effects.anim_path, DropLineEdit), "effects.anim_path is not DropLineEdit"

history = HistoryWidget()
assert isinstance(history.relink_media_dir, DropLineEdit), "history.relink_media_dir is not DropLineEdit"

media_studio = MediaStudioWidget()
assert isinstance(media_studio.download_out_edit, DropLineEdit), "media_studio.download_out_edit is not DropLineEdit"
assert isinstance(media_studio.download_cookies_edit, DropLineEdit), "media_studio.download_cookies_edit is not DropLineEdit"
assert isinstance(media_studio.cutter_source_edit, DropLineEdit), "media_studio.cutter_source_edit is not DropLineEdit"
assert isinstance(media_studio.cutter_dest_edit, DropLineEdit), "media_studio.cutter_dest_edit is not DropLineEdit"

print("ALL LAYOUT AND DROP CHECKS PASSED")
sys.exit(0)
"""
    res = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=35)
    assert res.returncode == 0, f"Error in test_studio_splitter_and_components: {res.stderr}\\n{res.stdout}"
