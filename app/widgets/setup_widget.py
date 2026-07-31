# app/widgets/setup_widget.py
import os
import struct
import subprocess
from pathlib import Path
from PySide6.QtCore import Slot, Signal, Qt, QThread, QRectF, QUrl
from PySide6.QtGui import QColor, QFontDatabase, QPixmap, QFont, QPainter, QBrush, QPen, QPainterPath
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from app.icons import get_svg_icon
from app.theme import (
    COLOR_TEAL, COLOR_CARD_BG, COLOR_CARD_BORDER, COLOR_ERROR, COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_SIDEBAR_BG,
    QCOLOR_TEAL, QCOLOR_DARK_ZINC, QCOLOR_CARD_BG, QCOLOR_CARD_BORDER,
    QCOLOR_TEXT_SECONDARY, QCOLOR_TEXT_MUTED, QCOLOR_ERROR, QCOLOR_SUCCESS,
    QCOLOR_TEXT_BLACK
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QScrollArea,
    QRadioButton,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QFileDialog,
    QColorDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGraphicsDropShadowEffect,
    QMessageBox,
)
from app.presets import KEYFRAME_PRESETS, TRANSITION_PRESETS
from profiles.subtitle import parse_srt_file, validate_subtitles
from runtime_tools import resolve_ffmpeg


class SubtitlePreviewLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.outline_width = 40.0
        self.shadow_alpha = 0.8
        self.shadow_distance = 5.0
        self.shadow_enabled = True
        self.outline_color = QCOLOR_TEXT_BLACK

    def set_style_params(self, outline_width: float, shadow_alpha: float, shadow_distance: float, shadow_enabled: bool) -> None:
        self.outline_width = outline_width
        self.shadow_alpha = shadow_alpha
        self.shadow_distance = shadow_distance
        self.shadow_enabled = shadow_enabled
        self.update()


class DropLineEdit(QLineEdit):
    """
    Custom QLineEdit that accepts Drag & Drop of files/folders from Windows Explorer.
    """
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                local_path = urls[0].toLocalFile()
                if local_path:
                    self.setText(local_path)
                    self.textChanged.emit(local_path)
                    event.acceptProposedAction()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = self.font()
        painter.setFont(font)

        rect = self.rect()
        text = self.text()

        path = QPainterPath()

        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(text)
        text_h = fm.height()

        align = self.alignment()
        if align & Qt.AlignmentFlag.AlignLeft:
            x = rect.x() + 10
        elif align & Qt.AlignmentFlag.AlignRight:
            x = rect.width() - text_w - 10
        else:
            x = (rect.width() - text_w) / 2.0

        y = (rect.height() + text_h) / 2.0 - fm.descent()

        path.addText(x, y, font, text)

        # Draw shadow
        if self.shadow_enabled:
            painter.save()
            shadow_offset = self.shadow_distance / 2.0
            painter.translate(shadow_offset, shadow_offset)

            shadow_color = QColor(0, 0, 0, int(self.shadow_alpha * 255))
            painter.setBrush(QBrush(shadow_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)
            painter.restore()

        # Draw stroke outline
        if self.outline_width > 0:
            painter.save()
            pen_w = (self.outline_width / 100.0) * 8.0
            pen = QPen(self.outline_color, pen_w, Qt.PenStyle.SolidLine)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.restore()

        # Fill text
        painter.save()
        text_color = self.palette().color(self.foregroundRole())
        painter.setBrush(QBrush(text_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
        painter.restore()


class AudioWaveformLoader(QThread):
    # Signals: amps (list), duration_str (str), metadata_str (str), error_msg (str)
    finished = Signal(list, str, str, str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.process = None

    def run(self) -> None:
        from media_probe import probe_media

        # 1. Probing the media (in the background!)
        try:
            if self.isInterruptionRequested():
                return
            asset = probe_media(self.path)
            if self.isInterruptionRequested():
                return

            if asset.error:
                self.finished.emit([], "00:00", "", f"Lỗi: {asset.error}")
                return

            dur_sec = asset.duration_us / 1_000_000.0
            m = int(dur_sec // 60)
            s = int(dur_sec % 60)
            duration_str = f"{m:02d}:{s:02d}"

            file_size_mb = os.path.getsize(self.path) / (1024 * 1024)
            file_name = os.path.basename(self.path)
            metadata_str = f"{file_name} ({file_size_mb:.2f} MB)"
        except Exception as e:
            self.finished.emit([], "00:00", "", f"Lỗi load: {str(e)}")
            return

        # 2. Extracting amplitude (in the background!)
        ffmpeg_exe = resolve_ffmpeg()
        if not ffmpeg_exe:
            self.finished.emit([], duration_str, metadata_str, "Chưa có dữ liệu waveform")
            return

        try:
            cmd = [
                ffmpeg_exe,
                "-y",
                "-i", self.path,
                "-f", "s16le",
                "-ac", "1",
                "-ar", "4000",  # 4kHz downsampling
                "-"
            ]
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags
            )

            # Read stdout in chunks to allow interruption checks
            raw_data = []
            chunk_size = 4096
            max_bytes = 5 * 1024 * 1024
            bytes_read = 0

            while bytes_read < max_bytes:
                if self.isInterruptionRequested():
                    self.process.kill()
                    return
                chunk = self.process.stdout.read(chunk_size)
                if not chunk:
                    break
                raw_data.append(chunk)
                bytes_read += len(chunk)

            self.process.wait()
            raw_bytes = b"".join(raw_data)

            if self.isInterruptionRequested():
                return

            if not raw_bytes:
                self.finished.emit([], duration_str, metadata_str, "Chưa có dữ liệu waveform")
                return

            count = len(raw_bytes) // 2
            if count == 0:
                self.finished.emit([], duration_str, metadata_str, "Chưa có dữ liệu waveform")
                return

            samples = struct.unpack(f"<{count}h", raw_bytes[:count*2])
            abs_samples = [abs(s) for s in samples]

            num_points = 200
            step = max(1, len(abs_samples) // num_points)
            amplitudes = []
            for i in range(num_points):
                if self.isInterruptionRequested():
                    return
                start = i * step
                end = min(len(abs_samples), (i + 1) * step)
                if start >= len(abs_samples):
                    amplitudes.append(0.0)
                else:
                    sub_chunk = abs_samples[start:end]
                    amplitudes.append(float(max(sub_chunk)) if sub_chunk else 0.0)

            max_val = max(amplitudes) if amplitudes else 0
            if max_val > 0:
                amplitudes = [a / max_val for a in amplitudes]

            self.finished.emit(amplitudes, duration_str, metadata_str, "")
        except Exception as e:
            print(f"Error extracting amplitude: {e}")
            self.finished.emit([], duration_str, metadata_str, "Chưa có dữ liệu waveform")

    def cancel(self):
        self.requestInterruption()
        if self.process:
            try:
                self.process.kill()
            except Exception:
                pass


class AudioWaveformWidget(QWidget):
    position_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.amplitudes = []
        self.duration_str = "00:00"
        self.metadata_str = "Không có file"
        self.playback_position = 0.0
        self.setMinimumHeight(85)
        self.setCursor(Qt.PointingHandCursor)

    def set_waveform(self, amplitudes: list, duration_str: str, metadata_str: str) -> None:
        self.amplitudes = amplitudes
        self.duration_str = duration_str
        self.metadata_str = metadata_str
        self.playback_position = 0.0
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.amplitudes:
            x = event.position().x()
            pct = x / self.width()
            pct = max(0.0, min(1.0, pct))
            self.position_changed.emit(pct)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QCOLOR_DARK_ZINC))
        painter.drawRoundedRect(0, 0, w, h, 6, 6)

        if not self.amplitudes:
            # Draw "Chưa có dữ liệu waveform" in center
            painter.setPen(QPen(QCOLOR_TEXT_SECONDARY))
            font = QFont("Inter", 10)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Chưa có dữ liệu waveform")

            # Draw metadata at bottom left
            if self.metadata_str and self.metadata_str != "Không có file":
                meta_rect = QRectF(10, h - 25, w - 20, 20)
                font_sub = QFont("Inter", 8)
                painter.setFont(font_sub)
                painter.setPen(QPen(QCOLOR_TEXT_MUTED))
                painter.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.metadata_str)
            return

        # Draw amplitude bars in Cyan-Violet Gradient
        num_bars = len(self.amplitudes)
        bar_w = w / num_bars
        gap = 1

        from PySide6.QtGui import QLinearGradient
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor("#00F2FE"))
        grad.setColorAt(1.0, QColor("#7F00FF"))

        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)

        mid_y = h / 2.0

        for i, amp in enumerate(self.amplitudes):
            # amp is [0.0, 1.0]
            bar_h = max(2.0, amp * (h - 25))  # Leave room for texts at bottom
            x = i * bar_w + gap
            y = mid_y - bar_h / 2.0 - 5
            width = max(1.0, bar_w - gap * 2)
            painter.drawRoundedRect(QRectF(x, y, width, bar_h), 1, 1)

        # Draw duration on the right
        font_lbl = QFont("Inter", 8, QFont.Weight.Bold)
        painter.setFont(font_lbl)
        dur_rect = QRectF(w - 110, h - 22, 100, 18)
        painter.setPen(QPen(QCOLOR_TEXT_MUTED))
        painter.drawText(dur_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.duration_str)

        # Draw metadata on the left
        meta_rect = QRectF(10, h - 22, w - 130, 18)
        painter.setPen(QPen(QCOLOR_TEXT_MUTED))
        painter.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.metadata_str)

        # Draw playback line
        if self.playback_position > 0:
            play_x = self.playback_position * w
            painter.setPen(QPen(QCOLOR_ERROR, 2))
            painter.drawLine(play_x, 0, play_x, h - 25)


class SetupWidget(QWidget):
    add_to_queue_requested = Signal()
    build_now_requested = Signal()
    save_profile_requested = Signal()
    clone_profile_requested = Signal()
    export_profile_requested = Signal()
    import_profile_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wave_loader = None
        self._bgm_wave_loader = None
        self.current_subtitles = []

        # Audio media player
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)

        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.durationChanged.connect(self._on_player_duration_changed)

        self._build_ui()
        self.waveform_widget.position_changed.connect(self._on_waveform_seek)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Page Header
        header_widget = QWidget()
        header_main_layout = QHBoxLayout(header_widget)
        header_main_layout.setContentsMargins(0, 0, 0, 4)
        header_main_layout.setSpacing(10)

        # Title block
        title_block = QWidget()
        title_layout = QVBoxLayout(title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)

        lbl_title = QLabel("Thiết lập dự án")
        lbl_title.setObjectName("pageTitle")
        lbl_subtitle = QLabel("Cấu hình thư mục, tệp phụ đề, kiểm tra live-preview âm thanh và căn lề kiểu chữ.")
        lbl_subtitle.setObjectName("pageSubtitle")
        title_layout.addWidget(lbl_title)
        title_layout.addWidget(lbl_subtitle)
        header_main_layout.addWidget(title_block, 1)

        # Preset actions toolbar
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)

        btn_style = f"""
            QPushButton {{
                background-color: {COLOR_CARD_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                color: {COLOR_TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLOR_TEAL};
                color: #000000;
                border-color: {COLOR_TEAL};
            }}
            QPushButton:pressed {{
                background-color: #0bc0a9;
            }}
        """

        self.btn_save_preset = QPushButton("  Lưu Preset")
        self.btn_save_preset.setIcon(get_svg_icon("file", color="#f8fafc", size=14))
        self.btn_save_preset.setStyleSheet(btn_style)
        self.btn_save_preset.clicked.connect(self.save_profile_requested.emit)

        self.btn_clone_preset = QPushButton("  Nhân bản")
        self.btn_clone_preset.setIcon(get_svg_icon("copy", color="#f8fafc", size=14))
        self.btn_clone_preset.setStyleSheet(btn_style)
        self.btn_clone_preset.clicked.connect(self.clone_profile_requested.emit)

        self.btn_export_preset = QPushButton("  Xuất Preset")
        self.btn_export_preset.setIcon(get_svg_icon("download", color="#f8fafc", size=14))
        self.btn_export_preset.setStyleSheet(btn_style)
        self.btn_export_preset.clicked.connect(self.export_profile_requested.emit)

        self.btn_import_preset = QPushButton("  Nhập Preset")
        self.btn_import_preset.setIcon(get_svg_icon("plus", color="#f8fafc", size=14))
        self.btn_import_preset.setStyleSheet(btn_style)
        self.btn_import_preset.clicked.connect(self.import_profile_requested.emit)

        toolbar_layout.addWidget(self.btn_save_preset)
        toolbar_layout.addWidget(self.btn_clone_preset)
        toolbar_layout.addWidget(self.btn_export_preset)
        toolbar_layout.addWidget(self.btn_import_preset)
        header_main_layout.addWidget(toolbar_widget, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        layout.addWidget(header_widget)

        # Scroll area for responsiveness
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(16)

        # LEFT COLUMN Layout
        left_side = QVBoxLayout()
        left_side.setSpacing(15)

        # 1. THÔNG TIN DỰ ÁN CARD
        project_card = QFrame()
        project_card.setObjectName("configCard")
        project_layout = QVBoxLayout(project_card)
        project_layout.setContentsMargins(16, 16, 16, 16)
        project_layout.setSpacing(12)

        proj_title = QLabel("Thông tin dự án")
        proj_title.setObjectName("cardTitle")
        project_layout.addWidget(proj_title)

        self.project_name = QLineEdit("Du_An_CapCut")
        self.project_name.setPlaceholderText("Tên dự án nháp CapCut (không viết dấu)...")
        project_layout.addWidget(self._create_field_label("Tên dự án nháp"))
        project_layout.addWidget(self.project_name)

        self.draft_root = QLineEdit()
        self.draft_root.setPlaceholderText("Thư mục lưu dự án nháp của CapCut...")
        project_layout.addWidget(self._create_field_label("Thư mục dự án nháp CapCut (Draft Root)"))
        project_layout.addLayout(self._create_path_row(self.draft_root, "folder"))

        self.media_dir = QLineEdit()
        self.media_dir.setPlaceholderText("Thư mục chứa kho video/hình ảnh nền...")
        project_layout.addWidget(self._create_field_label("Thư mục Video/Ảnh nền (Background Media)"))
        project_layout.addLayout(self._create_path_row(self.media_dir, "folder"))

        # Aspect ratio option inside project card
        project_layout.addWidget(self._create_field_label("Tỷ lệ khung hình"))
        ratio_layout = QHBoxLayout()
        self.ratio_9_16 = QRadioButton("Dọc (9:16 Shorts/TikTok)")
        self.ratio_9_16.setChecked(True)
        self.ratio_16_9 = QRadioButton("Ngang (16:9 YouTube)")
        ratio_layout.addWidget(self.ratio_9_16)
        ratio_layout.addWidget(self.ratio_16_9)
        project_layout.addLayout(ratio_layout)

        left_side.addWidget(project_card)

        # 2. PHỤ ĐỀ (SRT) CARD
        srt_card = QFrame()
        srt_card.setObjectName("configCard")
        srt_layout = QVBoxLayout(srt_card)
        srt_layout.setContentsMargins(16, 16, 16, 16)
        srt_layout.setSpacing(12)

        srt_title = QLabel("Phụ đề (SRT)")
        srt_title.setObjectName("cardTitle")
        srt_layout.addWidget(srt_title)

        self.srt_path = QLineEdit()
        self.srt_path.setPlaceholderText("Chọn tệp phụ đề (.srt - Không bắt buộc)...")
        srt_layout.addWidget(self._create_field_label("Tệp phụ đề (SRT Subtitles - Tùy chọn)"))
        srt_layout.addLayout(self._create_path_row(self.srt_path, "srt"))

        # Table of subtitles showing timestamps and checking warnings
        self.sub_table = QTableWidget()
        self.sub_table.setColumnCount(5)
        self.sub_table.setHorizontalHeaderLabels(["STT", "Thời gian", "Độ dài", "Nội dung", "Trạng thái"])
        self.sub_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.sub_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.sub_table.setMinimumHeight(180)
        self.sub_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.SelectedClicked)
        srt_layout.addWidget(self.sub_table)

        # Subtitle timing diagnostics footer
        diag_layout = QHBoxLayout()
        diag_layout.setContentsMargins(4, 2, 4, 2)
        diag_layout.setSpacing(10)

        self.lbl_srt_diag = QLabel("Chưa tải tệp phụ đề.")
        self.lbl_srt_diag.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px; font-weight: 500;")

        self.btn_check_timing = QPushButton(" Kiểm tra thời gian")
        self.btn_check_timing.setIcon(get_svg_icon("clock", color=COLOR_TEXT_PRIMARY, size=12))
        self.btn_check_timing.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SIDEBAR_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 4px;
                padding: 4px 10px;
                color: {COLOR_TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLOR_TEAL};
                color: #000000;
                border-color: {COLOR_TEAL};
            }}
            QPushButton:pressed {{
                background-color: #0bc0a9;
            }}
        """)
        self.btn_check_timing.clicked.connect(self._on_check_timing_clicked)

        diag_layout.addWidget(self.lbl_srt_diag, 1)
        diag_layout.addWidget(self.btn_check_timing, 0)
        srt_layout.addLayout(diag_layout)

        # Save SRT button
        self.btn_save_srt = QPushButton(" LƯU PHỤ ĐỀ (SRT)")
        self.btn_save_srt.setIcon(get_svg_icon("save", color="#ffffff", size=14))
        self.btn_save_srt.setObjectName("btnSaveSrt")
        self.btn_save_srt.setEnabled(False)
        self.btn_save_srt.clicked.connect(self._on_save_srt_clicked)
        srt_layout.addWidget(self.btn_save_srt)

        self.srt_path.textChanged.connect(self._on_srt_path_changed)

        left_side.addWidget(srt_card)

        # Collapsible advanced settings
        self.settings_toggle = QPushButton(" Cài đặt nâng cao & Giao diện")
        self.settings_toggle.setIcon(get_svg_icon("settings", color=COLOR_TEAL, size=14))
        self.settings_toggle.setObjectName("settingsToggle")
        self.settings_toggle.setCheckable(True)
        self.settings_toggle.setChecked(False)
        self.settings_toggle.clicked.connect(self._toggle_advanced_settings)
        left_side.addWidget(self.settings_toggle)

        self.settings_frame = QFrame()
        self.settings_frame.setObjectName("settingsFrame")
        settings_grid = QGridLayout(self.settings_frame)
        settings_grid.setContentsMargins(10, 10, 10, 10)
        settings_grid.setSpacing(12)

        # Slicing timers
        settings_grid.addWidget(self._create_field_label("Độ dài clip nền tối thiểu (giây)"), 0, 0)
        self.clip_min = QDoubleSpinBox()
        self.clip_min.setRange(0.5, 86400.0)
        self.clip_min.setValue(5.0)
        self.clip_min.setSingleStep(0.5)
        settings_grid.addWidget(self.clip_min, 0, 1)

        settings_grid.addWidget(self._create_field_label("Độ dài clip nền tối đa (giây)"), 1, 0)
        self.clip_max = QDoubleSpinBox()
        self.clip_max.setRange(0.5, 86400.0)
        self.clip_max.setValue(9.0)
        self.clip_max.setSingleStep(0.5)
        settings_grid.addWidget(self.clip_max, 1, 1)

        # Selection Mode
        settings_grid.addWidget(self._create_field_label("Cách trộn video nền"), 2, 0)
        self.selection_mode = QComboBox()
        self.selection_mode.addItems([
            "Trộn ngẫu nhiên (shuffle_bag)",
            "Lần lượt (sequential)",
            "Ngẫu nhiên (random)",
            "Nhân bản rồi trộn toàn bộ (duplicate_then_shuffle)",
            "Nhân bản rồi trộn phần nhân bản (shuffle_duplicates_only)"
        ])
        settings_grid.addWidget(self.selection_mode, 2, 1)

        # Short video handling mode
        settings_grid.addWidget(self._create_field_label("Xử lý video ngắn hơn voice"), 3, 0)
        self.short_video_mode = QComboBox()
        self.short_video_mode.addItems([
            "Kéo giãn / Đổi tốc độ (stretch)",
            "Tự động lặp lại (loop)"
        ])
        settings_grid.addWidget(self.short_video_mode, 3, 1)

        # Background Switch Mode
        settings_grid.addWidget(self._create_field_label("Quy tắc chuyển cảnh nền"), 4, 0)
        self.bg_switch_mode = QComboBox()
        self.bg_switch_mode.addItem("Theo thời gian cố định / ngẫu nhiên", "time")
        self.bg_switch_mode.addItem("Theo từng câu phụ đề SRT", "subtitle")
        self.bg_switch_mode.addItem("Theo cụm câu phụ đề (Gom nhóm)", "subtitle_group")
        settings_grid.addWidget(self.bg_switch_mode, 4, 1)

        # Group size (Subtitle group)
        self.bg_switch_group_label = self._create_field_label("Số câu thoại mỗi cảnh")
        settings_grid.addWidget(self.bg_switch_group_label, 5, 0)
        self.bg_switch_group_size = QSpinBox()
        self.bg_switch_group_size.setRange(1, 50)
        self.bg_switch_group_size.setValue(3)
        settings_grid.addWidget(self.bg_switch_group_size, 5, 1)

        self.bg_switch_mode.currentIndexChanged.connect(self._on_bg_switch_mode_changed)

        self.recursive_scan = QCheckBox("Quét cả thư mục con (Recursive)")
        self.recursive_scan.setChecked(False)
        settings_grid.addWidget(self.recursive_scan, 6, 0, 1, 2)

        # Auto-apply settings inside draft pipeline
        settings_grid.addWidget(self._create_field_label("Tự động thêm Keyframe (Auto Keyframe)"), 7, 0)
        self.auto_kf_combo = QComboBox()
        self.auto_kf_combo.addItem("Không áp dụng (None)", "none")
        self.auto_kf_combo.addItem("Trộn ngẫu nhiên (Random)", "random")
        for p in KEYFRAME_PRESETS:
            self.auto_kf_combo.addItem(p["name"], p["id"])
        settings_grid.addWidget(self.auto_kf_combo, 7, 1)

        settings_grid.addWidget(self._create_field_label("Tự động thêm Chuyển cảnh (Auto Transition)"), 8, 0)
        self.auto_trans_combo = QComboBox()
        self.auto_trans_combo.addItem("Không áp dụng (None)", "none")
        self.auto_trans_combo.addItem("Trộn ngẫu nhiên (Random)", "random")
        for t in TRANSITION_PRESETS:
            self.auto_trans_combo.addItem(t["label"], t["name"])
        settings_grid.addWidget(self.auto_trans_combo, 8, 1)

        settings_grid.addWidget(self._create_field_label("Thời lượng chuyển cảnh tự động (giây)"), 9, 0)
        self.auto_trans_dur = QDoubleSpinBox()
        self.auto_trans_dur.setRange(0.1, 5.0)
        self.auto_trans_dur.setValue(0.4)
        self.auto_trans_dur.setSingleStep(0.05)
        settings_grid.addWidget(self.auto_trans_dur, 9, 1)

        # Intro / Outro selection from Asset Library
        settings_grid.addWidget(self._create_field_label("Video mở đầu (Intro)"), 10, 0)
        self.intro_combo = QComboBox()
        settings_grid.addWidget(self.intro_combo, 10, 1)

        settings_grid.addWidget(self._create_field_label("Video kết thúc (Outro)"), 11, 0)
        self.outro_combo = QComboBox()
        settings_grid.addWidget(self.outro_combo, 11, 1)

        left_side.addWidget(self.settings_frame)
        self.settings_frame.setVisible(False)

        # Action Buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self.btn_add_queue = QPushButton(" THÊM VÀO HÀNG ĐỢI")
        self.btn_add_queue.setIcon(get_svg_icon("plus", color="#000000", size=14))
        self.btn_add_queue.setObjectName("btnAddQueue")
        self.btn_add_queue.clicked.connect(self.add_to_queue_requested.emit)

        self.btn_build_now = QPushButton(" DỰNG NGAY")
        self.btn_build_now.setIcon(get_svg_icon("play", color="#000000", size=14))
        self.btn_build_now.setObjectName("btnBuildNow")
        self.btn_build_now.clicked.connect(self.build_now_requested.emit)

        actions_layout.addWidget(self.btn_add_queue, 1)
        actions_layout.addWidget(self.btn_build_now, 1)
        left_side.addLayout(actions_layout)

        # RIGHT COLUMN Layout
        right_side = QVBoxLayout()
        right_side.setSpacing(15)

        # 3. ÂM THANH CARD
        audio_card = QFrame()
        audio_card.setObjectName("configCard")
        audio_layout = QVBoxLayout(audio_card)
        audio_layout.setContentsMargins(16, 16, 16, 16)
        audio_layout.setSpacing(12)

        audio_title = QLabel("Âm thanh")
        audio_title.setObjectName("cardTitle")
        audio_layout.addWidget(audio_title)

        self.voice_path = QLineEdit()
        self.voice_path.setPlaceholderText("Chọn tệp âm thanh giọng đọc chính (.mp3, .wav)...")
        audio_layout.addWidget(self._create_field_label("Tệp giọng đọc chính (Voice Audio)"))
        audio_layout.addLayout(self._create_path_row(self.voice_path, "audio"))

        # Waveform Widget (Voice)
        audio_layout.addWidget(self._create_field_label("Dạng sóng giọng đọc (Voice Waveform)"))
        self.waveform_widget = AudioWaveformWidget()
        audio_layout.addWidget(self.waveform_widget)

        # Play/Pause controls
        self.playback_controls = QHBoxLayout()
        self.btn_play_voice = QPushButton(" Phát")
        self.btn_play_voice.setIcon(get_svg_icon("play", color=COLOR_TEAL, size=14))
        self.btn_play_voice.setEnabled(False)
        self.btn_play_voice.clicked.connect(self._toggle_voice_playback)
        self.playback_controls.addWidget(self.btn_play_voice)

        self.lbl_playback_time = QLabel("00:00 / 00:00")
        self.lbl_playback_time.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.playback_controls.addWidget(self.lbl_playback_time)
        self.playback_controls.addStretch()
        audio_layout.addLayout(self.playback_controls)

        self.bgm_path = QLineEdit()
        self.bgm_path.setPlaceholderText("Chọn nhạc nền lồng thêm (Không bắt buộc)...")
        audio_layout.addWidget(self._create_field_label("Tệp nhạc nền (BGM Audio - Tùy chọn)"))
        audio_layout.addLayout(self._create_path_row(self.bgm_path, "audio"))

        # Waveform Widget (BGM)
        audio_layout.addWidget(self._create_field_label("Dạng sóng nhạc nền (BGM Waveform)"))
        self.bgm_waveform_widget = AudioWaveformWidget()
        audio_layout.addWidget(self.bgm_waveform_widget)

        self.voice_path.textChanged.connect(self._on_voice_path_changed)
        self.bgm_path.textChanged.connect(self._on_bgm_path_changed)

        right_side.addWidget(audio_card)

        # 4. KIỂU CHỮ PHỤ ĐỀ CARD
        font_card = QFrame()
        font_card.setObjectName("configCard")
        font_layout = QVBoxLayout(font_card)
        font_layout.setContentsMargins(16, 16, 16, 16)
        font_layout.setSpacing(12)

        font_title = QLabel("Kiểu chữ phụ đề")
        font_title.setObjectName("cardTitle")
        font_layout.addWidget(font_title)

        # Premium Live Preview Container simulating Aspect Ratio Canvas
        preview_container = QFrame()
        preview_container.setObjectName("previewContainer")
        preview_container.setMinimumHeight(350)
        preview_container.setStyleSheet("""
            QFrame#previewContainer {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
        """)
        preview_vbox = QVBoxLayout(preview_container)
        preview_vbox.setContentsMargins(12, 12, 12, 12)
        preview_vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Black simulated video canvas
        self.preview_canvas = QFrame()
        self.preview_canvas.setObjectName("previewCanvas")
        self.preview_canvas.setStyleSheet("background-color: #000000; border: 1px solid rgba(255,255,255,0.15); border-radius: 4px;")

        # Layout inside the canvas for subtitle positioning
        self.canvas_layout = QVBoxLayout(self.preview_canvas)
        self.canvas_layout.setContentsMargins(10, 10, 10, 10)

        self.preview_label = SubtitlePreviewLabel("Cuộc rượt đuổi bắt đầu lúc nửa đêm.")
        self.preview_label.setWordWrap(True)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_layout.addWidget(self.preview_label)

        preview_vbox.addWidget(self.preview_canvas, 0, Qt.AlignmentFlag.AlignCenter)

        preview_tag = QLabel("XEM TRƯỚC TRỰC TIẾP")
        preview_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_tag.setStyleSheet("color: #94a3b8; font-size: 8px; font-weight: bold; letter-spacing: 1.5px; margin-top: 8px;")
        preview_vbox.addWidget(preview_tag, 0)
        font_layout.addWidget(preview_container)

        # Styling controls grid
        style_grid = QGridLayout()
        style_grid.setSpacing(10)

        style_grid.addWidget(self._create_field_label("Phông chữ"), 0, 0)
        self.subtitle_font = QComboBox()
        popular_fonts = ["SystemFont", "Inter", "Arial", "Times New Roman", "Segoe UI", "Calibri", "Courier New"]
        for f in popular_fonts:
            self.subtitle_font.addItem(f)
        try:
            for family in QFontDatabase.families():
                if family not in popular_fonts:
                    self.subtitle_font.addItem(family)
        except Exception:
            pass
        style_grid.addWidget(self.subtitle_font, 0, 1)

        style_grid.addWidget(self._create_field_label("Cỡ chữ"), 1, 0)
        self.subtitle_font_size = QDoubleSpinBox()
        self.subtitle_font_size.setRange(1.0, 100.0)
        self.subtitle_font_size.setValue(6.0)
        self.subtitle_font_size.setSingleStep(0.5)
        style_grid.addWidget(self.subtitle_font_size, 1, 1)

        style_grid.addWidget(self._create_field_label("Màu sắc"), 2, 0)
        color_row = QHBoxLayout()
        self.subtitle_color = QLineEdit("#FFFFFF")
        self.subtitle_color.setPlaceholderText("#FFFFFF")
        self.color_preview = QFrame()
        self.color_preview.setFixedSize(18, 18)
        self.color_preview.setStyleSheet("background-color: #FFFFFF; border: 1px solid white; border-radius: 3px;")
        self.btn_subtitle_color = QPushButton("Chọn")
        self.btn_subtitle_color.setObjectName("btnBrowse")
        self.btn_subtitle_color.clicked.connect(self._on_choose_color)
        color_row.addWidget(self.subtitle_color, 1)
        color_row.addWidget(self.color_preview, 0)
        color_row.addWidget(self.btn_subtitle_color, 0)
        style_grid.addLayout(color_row, 2, 1)

        style_grid.addWidget(self._create_field_label("Căn lề / Vị trí"), 3, 0)
        self.subtitle_align = QComboBox()
        self.subtitle_align.addItem("Giữa dưới (Bottom Center)", "bottom_center")
        self.subtitle_align.addItem("Chính giữa (Center)", "center")
        self.subtitle_align.addItem("Giữa trên (Top Center)", "top_center")
        self.subtitle_align.addItem("Trái dưới (Bottom Left)", "bottom_left")
        self.subtitle_align.addItem("Phải dưới (Bottom Right)", "bottom_right")
        style_grid.addWidget(self.subtitle_align, 3, 1)

        style_grid.addWidget(self._create_field_label("Độ rộng viền"), 4, 0)
        self.subtitle_outline_width = QDoubleSpinBox()
        self.subtitle_outline_width.setRange(0.0, 100.0)
        self.subtitle_outline_width.setValue(40.0)
        self.subtitle_outline_width.setSingleStep(5.0)
        style_grid.addWidget(self.subtitle_outline_width, 4, 1)

        style_grid.addWidget(self._create_field_label("Độ mờ bóng đổ"), 5, 0)
        self.subtitle_shadow_alpha = QDoubleSpinBox()
        self.subtitle_shadow_alpha.setRange(0.0, 1.0)
        self.subtitle_shadow_alpha.setValue(0.8)
        self.subtitle_shadow_alpha.setSingleStep(0.05)
        style_grid.addWidget(self.subtitle_shadow_alpha, 5, 1)

        style_grid.addWidget(self._create_field_label("Khoảng cách bóng"), 6, 0)
        self.subtitle_shadow_distance = QDoubleSpinBox()
        self.subtitle_shadow_distance.setRange(0.0, 50.0)
        self.subtitle_shadow_distance.setValue(5.0)
        self.subtitle_shadow_distance.setSingleStep(0.5)
        style_grid.addWidget(self.subtitle_shadow_distance, 6, 1)

        font_layout.addLayout(style_grid)

        # Style toggle buttons (Bold, Italic, Underline, Shadow)
        btn_style_layout = QHBoxLayout()
        btn_style_layout.setSpacing(6)

        self.subtitle_bold = QPushButton("Đậm")
        self.subtitle_bold.setCheckable(True)
        self.subtitle_bold.setChecked(True)
        self.subtitle_bold.setObjectName("btnStyle")

        self.subtitle_italic = QPushButton("Nghiêng")
        self.subtitle_italic.setCheckable(True)
        self.subtitle_italic.setObjectName("btnStyle")

        self.subtitle_underline = QPushButton("Gạch chân")
        self.subtitle_underline.setCheckable(True)
        self.subtitle_underline.setObjectName("btnStyle")

        self.subtitle_shadow = QPushButton("Bóng")
        self.subtitle_shadow.setCheckable(True)
        self.subtitle_shadow.setChecked(True)
        self.subtitle_shadow.setObjectName("btnStyle")

        btn_style_layout.addWidget(self.subtitle_bold)
        btn_style_layout.addWidget(self.subtitle_italic)
        btn_style_layout.addWidget(self.subtitle_underline)
        btn_style_layout.addWidget(self.subtitle_shadow)
        font_layout.addLayout(btn_style_layout)

        # Connections for live preview updates
        self.subtitle_font.currentIndexChanged.connect(self._update_subtitle_preview)
        self.subtitle_font_size.valueChanged.connect(self._update_subtitle_preview)
        self.subtitle_color.textChanged.connect(self._update_subtitle_preview)
        self.subtitle_bold.toggled.connect(self._update_subtitle_preview)
        self.subtitle_italic.toggled.connect(self._update_subtitle_preview)
        self.subtitle_underline.toggled.connect(self._update_subtitle_preview)
        self.subtitle_shadow_alpha.valueChanged.connect(self._update_subtitle_preview)
        self.subtitle_shadow_distance.valueChanged.connect(self._update_subtitle_preview)
        self.subtitle_outline_width.valueChanged.connect(self._update_subtitle_preview)
        self.subtitle_shadow.toggled.connect(self._update_subtitle_preview)

        # Connections for aspect ratio / alignment changes to update preview canvas dimensions and positioning
        self.ratio_9_16.toggled.connect(self._update_preview_canvas_size)
        self.ratio_16_9.toggled.connect(self._update_preview_canvas_size)
        self.subtitle_align.currentIndexChanged.connect(self._update_preview_canvas_size)

        right_side.addWidget(font_card)

        # Assemble the double columns layout
        container_layout.addLayout(left_side, 1)
        container_layout.addLayout(right_side, 1)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Initializations
        self._on_bg_switch_mode_changed()
        self.refresh_intro_outro_combos()
        self._update_subtitle_preview()
        self._update_preview_canvas_size()
        self._on_voice_path_changed(self.voice_path.text())
        self._on_bgm_path_changed(self.bgm_path.text())

    def _create_field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _create_path_row(self, line_edit: QLineEdit, mode: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(line_edit)
        btn = QPushButton("Chọn")
        btn.setObjectName("btnBrowse")
        btn.clicked.connect(lambda: self._browse_path(line_edit, mode))
        layout.addWidget(btn)
        return layout

    def _browse_path(self, line_edit: QLineEdit, mode: str) -> None:
        if mode == "folder":
            path = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        elif mode == "audio":
            path, _ = QFileDialog.getOpenFileName(
                self, "Chọn file âm thanh", "", "Audio Files (*.wav *.mp3 *.m4a *.flac *.ogg)"
            )
        elif mode == "srt":
            path, _ = QFileDialog.getOpenFileName(
                self, "Chọn file phụ đề", "", "Subtitle Files (*.srt)"
            )
        else:
            path = ""

        if path:
            line_edit.setText(os.path.normpath(path))

    @Slot()
    def _toggle_advanced_settings(self) -> None:
        checked = self.settings_toggle.isChecked()
        self.settings_frame.setVisible(checked)

    @Slot()
    def _on_bg_switch_mode_changed(self) -> None:
        mode = self.bg_switch_mode.currentData()
        is_group = (mode == "subtitle_group")
        self.bg_switch_group_label.setEnabled(is_group)
        self.bg_switch_group_size.setEnabled(is_group)

    @Slot()
    def _on_choose_color(self) -> None:
        current_color = QColor(self.subtitle_color.text().strip())
        color = QColorDialog.getColor(current_color, self, "Chọn màu chữ phụ đề")
        if color.isValid():
            self.subtitle_color.setText(color.name().upper())
            self._update_subtitle_preview()

    @Slot()
    def _update_subtitle_preview(self) -> None:
        font_family = self.subtitle_font.currentText()
        font_size = self.subtitle_font_size.value()
        color_hex = self.subtitle_color.text().strip()
        bold = self.subtitle_bold.isChecked()
        italic = self.subtitle_italic.isChecked()
        underline = self.subtitle_underline.isChecked()

        # Build font
        font = QFont(font_family, max(8, int(font_size * 2.2)))
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)
        self.preview_label.setFont(font)

        # Set text color (background transparent)
        self.preview_label.setStyleSheet(f"color: {color_hex}; background: transparent; border: none;")

        # Update custom label parameters
        outline_val = self.subtitle_outline_width.value()
        shadow_a = self.subtitle_shadow_alpha.value()
        shadow_d = self.subtitle_shadow_distance.value()
        shadow_on = self.subtitle_shadow.isChecked()

        self.preview_label.set_style_params(outline_val, shadow_a, shadow_d, shadow_on)

        self.color_preview.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #ffffff; border-radius: 3px;")

    @Slot()
    def _update_preview_canvas_size(self) -> None:
        is_vertical = self.ratio_9_16.isChecked()
        if is_vertical:
            self.preview_canvas.setFixedSize(162, 288) # 9:16 scaled down
        else:
            self.preview_canvas.setFixedSize(288, 162) # 16:9 scaled down

        # Re-align preview_label inside canvas layout based on selected alignment
        while self.canvas_layout.count():
            item = self.canvas_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)

        align_data = self.subtitle_align.currentData() or "bottom_center"
        self.preview_label.setParent(self.preview_canvas)

        if align_data == "bottom_center":
            self.canvas_layout.addStretch(1)
            self.canvas_layout.addWidget(self.preview_label, 0, Qt.AlignmentFlag.AlignCenter)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        elif align_data == "center":
            self.canvas_layout.addStretch(1)
            self.canvas_layout.addWidget(self.preview_label, 0, Qt.AlignmentFlag.AlignCenter)
            self.canvas_layout.addStretch(1)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        elif align_data == "top_center":
            self.canvas_layout.addWidget(self.preview_label, 0, Qt.AlignmentFlag.AlignCenter)
            self.canvas_layout.addStretch(1)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        elif align_data == "bottom_left":
            self.canvas_layout.addStretch(1)
            row = QHBoxLayout()
            row.addWidget(self.preview_label, 0, Qt.AlignmentFlag.AlignLeft)
            row.addStretch(1)
            self.canvas_layout.addLayout(row)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        elif align_data == "bottom_right":
            self.canvas_layout.addStretch(1)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(self.preview_label, 0, Qt.AlignmentFlag.AlignRight)
            self.canvas_layout.addLayout(row)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    @Slot(str)
    def _on_srt_path_changed(self, path_str: str) -> None:
        try:
            self.sub_table.cellChanged.disconnect(self._on_subtitle_cell_changed)
        except Exception:
            pass

        self.sub_table.setRowCount(0)
        path_str = path_str.strip()
        if not path_str or not os.path.exists(path_str):
            self.current_subtitles = []
            self.btn_save_srt.setEnabled(False)
            self._update_srt_diagnostics()
            return

        subtitles = parse_srt_file(path_str)
        self.current_subtitles = subtitles
        self.btn_save_srt.setEnabled(False)

        issues = validate_subtitles(subtitles, min_duration_sec=0.8)
        short_sub_indexes = {issue["index"] for issue in issues}

        overlap_indexes = set()
        for i in range(len(subtitles) - 1):
            s1 = subtitles[i]
            s2 = subtitles[i+1]
            if s1["end"] > s2["start"]:
                overlap_indexes.add(s1["index"])
                overlap_indexes.add(s2["index"])

        self.sub_table.setRowCount(len(subtitles))
        for idx, sub in enumerate(subtitles):
            # Index
            item_idx = QTableWidgetItem(str(sub["index"]))
            item_idx.setFlags(item_idx.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Time Range
            item_time = QTableWidgetItem(f"{sub['start_time_str']} -> {sub['end_time_str']}")

            # Duration
            duration_sec = sub["duration"] / 1_000_000.0
            item_dur = QTableWidgetItem(f"{duration_sec:.2f}s")
            item_dur.setFlags(item_dur.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_dur.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Text content
            item_text = QTableWidgetItem(sub["text"])

            # Status and Warnings
            is_short = sub["index"] in short_sub_indexes
            is_overlap = sub["index"] in overlap_indexes

            item_status = QTableWidgetItem()
            item_status.setFlags(item_status.flags() & ~Qt.ItemFlag.ItemIsEditable)

            if is_short or is_overlap:
                if is_short and is_overlap:
                    item_status.setText("⚠️ Quá ngắn & Trùng lặp")
                elif is_short:
                    item_status.setText("⚠️ Quá ngắn (<0.8s)")
                else:
                    item_status.setText("⚠️ Trùng lặp thời gian")
                item_status.setForeground(QCOLOR_ERROR)  # Red

                # Apply visual warning background highlight
                warning_bg = QColor(QCOLOR_ERROR.red(), QCOLOR_ERROR.green(), QCOLOR_ERROR.blue(), 20)
                for item in [item_idx, item_time, item_dur, item_text, item_status]:
                    item.setBackground(warning_bg) # Light warning tint
            else:
                item_status.setText("✅ Hợp lệ")
                item_status.setForeground(QCOLOR_SUCCESS)  # Green

            self.sub_table.setItem(idx, 0, item_idx)
            self.sub_table.setItem(idx, 1, item_time)
            self.sub_table.setItem(idx, 2, item_dur)
            self.sub_table.setItem(idx, 3, item_text)
            self.sub_table.setItem(idx, 4, item_status)

        self.sub_table.cellChanged.connect(self._on_subtitle_cell_changed)
        self._update_srt_diagnostics()

    @Slot(str)
    def _on_voice_path_changed(self, path_str: str) -> None:
        path_str = path_str.strip()
        if not path_str or not os.path.exists(path_str):
            self.waveform_widget.set_waveform([], "00:00", "Chưa chọn tệp hoặc tệp không tồn tại")
            return

        # Smart Feature 1: Auto-detect matching SRT file if SRT field is empty
        try:
            voice_path_obj = Path(path_str)
            voice_dir = voice_path_obj.parent
            voice_stem = voice_path_obj.stem
            
            curr_srt = self.srt_path.text().strip()
            if not curr_srt or not os.path.exists(curr_srt):
                matching_srt = voice_dir / f"{voice_stem}.srt"
                if matching_srt.exists():
                    self.srt_path.setText(str(matching_srt))

            # Smart Feature 2: Auto-suggest project name if empty or default
            curr_proj = self.project_name.text().strip()
            if not curr_proj or curr_proj == "Dự án mới":
                from core.path_validation import sanitize_project_name
                import datetime
                date_suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                suggested_name = sanitize_project_name(f"{voice_stem}_{date_suffix}")
                self.project_name.setText(suggested_name)
        except Exception as e:
            print(f"Error in smart auto-detect on voice change: {e}")

        self.media_player.stop()
        self.media_player.setSource(QUrl.fromLocalFile(path_str))

        if self._wave_loader and self._wave_loader.isRunning():
            try:
                self._wave_loader.finished.disconnect()
            except Exception:
                pass
            self._wave_loader.cancel()

        self.waveform_widget.set_waveform([], "00:00", "Đang phân tích tệp âm thanh...")
        self._wave_loader = AudioWaveformLoader(path_str, self)

        def on_loader_finished(amps, duration_str, metadata_str, error_msg):
            if error_msg:
                self.waveform_widget.set_waveform([], duration_str, error_msg)
            else:
                self.waveform_widget.set_waveform(amps, duration_str, metadata_str)

        self._wave_loader.finished.connect(on_loader_finished)
        self._wave_loader.start()

    @Slot(str)
    def _on_bgm_path_changed(self, path_str: str) -> None:
        path_str = path_str.strip()
        if not path_str or not os.path.exists(path_str):
            self.bgm_waveform_widget.set_waveform([], "00:00", "Chưa chọn tệp hoặc tệp không tồn tại")
            return

        if self._bgm_wave_loader and self._bgm_wave_loader.isRunning():
            try:
                self._bgm_wave_loader.finished.disconnect()
            except Exception:
                pass
            self._bgm_wave_loader.cancel()

        self.bgm_waveform_widget.set_waveform([], "00:00", "Đang phân tích tệp nhạc nền...")
        self._bgm_wave_loader = AudioWaveformLoader(path_str, self)

        def on_bgm_loader_finished(amps, duration_str, metadata_str, error_msg):
            if error_msg:
                self.bgm_waveform_widget.set_waveform([], duration_str, error_msg)
            else:
                self.bgm_waveform_widget.set_waveform(amps, duration_str, metadata_str)

        self._bgm_wave_loader.finished.connect(on_bgm_loader_finished)
        self._bgm_wave_loader.start()

    def refresh_intro_outro_combos(self) -> None:
        self.intro_combo.clear()
        self.outro_combo.clear()

        self.intro_combo.addItem("Không sử dụng (None)", "")
        self.outro_combo.addItem("Không sử dụng (None)", "")

        from core.db import Database
        try:
            conn = Database.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assets'")
            if not cursor.fetchone():
                return

            cursor.execute("SELECT path, filename FROM assets WHERE category_name = 'intro' ORDER BY filename ASC")
            for row in cursor.fetchall():
                self.intro_combo.addItem(row["filename"], row["path"])

            cursor.execute("SELECT path, filename FROM assets WHERE category_name = 'outro' ORDER BY filename ASC")
            for row in cursor.fetchall():
                self.outro_combo.addItem(row["filename"], row["path"])
        except Exception as e:
            print(f"Error loading intro/outro assets: {e}")

    def shutdown(self, wait_ms: int = 2000) -> None:
        if hasattr(self, "media_player") and self.media_player:
            try:
                self.media_player.stop()
            except Exception:
                pass
        for loader in (getattr(self, "_wave_loader", None), getattr(self, "_bgm_wave_loader", None)):
            if loader and loader.isRunning():
                try:
                    loader.finished.disconnect()
                except Exception:
                    pass
                if hasattr(loader, "cancel"):
                    try:
                        loader.cancel()
                    except Exception:
                        pass
                loader.requestInterruption()
                loader.quit()
                if not loader.wait(wait_ms):
                    try:
                        loader.terminate()
                        loader.wait(500)
                    except Exception:
                        pass

    @Slot()
    def _toggle_voice_playback(self) -> None:
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.btn_play_voice.setText(" Phát")
            self.btn_play_voice.setIcon(get_svg_icon("play", color=COLOR_TEAL, size=14))
        else:
            self.media_player.play()
            self.btn_play_voice.setText(" Tạm dừng")
            self.btn_play_voice.setIcon(get_svg_icon("pause", color=COLOR_TEAL, size=14))

    def _on_player_position_changed(self, pos_ms: int) -> None:
        dur_ms = self.media_player.duration()
        if dur_ms > 0:
            pct = pos_ms / dur_ms
            self.waveform_widget.playback_position = pct
            self.waveform_widget.update()

            cur_sec = pos_ms // 1000
            tot_sec = dur_ms // 1000
            cur_str = f"{cur_sec // 60:02d}:{cur_sec % 60:02d}"
            tot_str = f"{tot_sec // 60:02d}:{tot_sec % 60:02d}"
            self.lbl_playback_time.setText(f"{cur_str} / {tot_str}")

    def _on_player_duration_changed(self, dur_ms: int) -> None:
        cur_sec = self.media_player.position() // 1000
        tot_sec = dur_ms // 1000
        cur_str = f"{cur_sec // 60:02d}:{cur_sec % 60:02d}"
        tot_str = f"{tot_sec // 60:02d}:{tot_sec % 60:02d}"
        self.lbl_playback_time.setText(f"{cur_str} / {tot_str}")
        self.btn_play_voice.setEnabled(dur_ms > 0)

    def _on_waveform_seek(self, pct: float) -> None:
        dur_ms = self.media_player.duration()
        if dur_ms > 0:
            target_ms = int(pct * dur_ms)
            self.media_player.setPosition(target_ms)

    @Slot(int, int)
    def _on_subtitle_cell_changed(self, row: int, col: int) -> None:
        if not hasattr(self, "current_subtitles") or not self.current_subtitles:
            return

        try:
            self.sub_table.cellChanged.disconnect(self._on_subtitle_cell_changed)
        except Exception:
            pass

        try:
            sub = self.current_subtitles[row]
            item = self.sub_table.item(row, col)
            val = item.text().strip()

            if col == 1:
                parsed_successfully = False
                if " -> " in val:
                    def time_str_to_us(time_str: str) -> int:
                        time_str = time_str.replace(".", ",")
                        parts = time_str.split(",")
                        hms = parts[0].split(":")
                        h, m, s = map(int, hms)
                        ms = int(parts[1]) if len(parts) > 1 else 0
                        return (((h * 3600 + m * 60 + s) * 1000) + ms) * 1000

                    try:
                        start_str, end_str = val.split(" -> ")
                        start_us = time_str_to_us(start_str)
                        end_us = time_str_to_us(end_str)
                        if end_us > start_us:
                            sub["start"] = start_us
                            sub["end"] = end_us
                            sub["duration"] = end_us - start_us
                            sub["start_time_str"] = start_str
                            sub["end_time_str"] = end_str

                            duration_sec = sub["duration"] / 1_000_000.0
                            self.sub_table.item(row, 2).setText(f"{duration_sec:.2f}s")
                            parsed_successfully = True
                    except Exception:
                        pass

                if not parsed_successfully:
                    QMessageBox.warning(
                        self,
                        "Lỗi định dạng",
                        "Định dạng thời gian nhập vào không hợp lệ!\n"
                        "Vui lòng nhập đúng định dạng: HH:MM:SS,mmm -> HH:MM:SS,mmm\n"
                        "(Ví dụ: 00:00:01,234 -> 00:00:04,567 và thời gian kết thúc phải lớn hơn thời gian bắt đầu)."
                    )
                    item.setText(f"{sub['start_time_str']} -> {sub['end_time_str']}")
            elif col == 3:
                sub["text"] = val

            issues = validate_subtitles(self.current_subtitles, min_duration_sec=0.8)
            short_sub_indexes = {issue["index"] for issue in issues}

            overlap_indexes = set()
            for i in range(len(self.current_subtitles) - 1):
                s1 = self.current_subtitles[i]
                s2 = self.current_subtitles[i+1]
                if s1["end"] > s2["start"]:
                    overlap_indexes.add(s1["index"])
                    overlap_indexes.add(s2["index"])

            for r in range(self.sub_table.rowCount()):
                s = self.current_subtitles[r]
                status_item = self.sub_table.item(r, 4)

                is_short = s["index"] in short_sub_indexes
                is_overlap = s["index"] in overlap_indexes

                if is_short or is_overlap:
                    bg_color = QColor(QCOLOR_ERROR.red(), QCOLOR_ERROR.green(), QCOLOR_ERROR.blue(), 20)
                    if is_short and is_overlap:
                        status_text = "⚠️ Quá ngắn & Trùng lặp"
                    elif is_short:
                        status_text = "⚠️ Quá ngắn (<0.8s)"
                    else:
                        status_text = "⚠️ Trùng lặp thời gian"
                    status_item.setText(status_text)
                    status_item.setForeground(QCOLOR_ERROR)
                else:
                    bg_color = QColor(Qt.GlobalColor.transparent)
                    status_text = "✅ Hợp lệ"
                    status_item.setText(status_text)
                    status_item.setForeground(QCOLOR_SUCCESS)

                for c in range(self.sub_table.columnCount()):
                    self.sub_table.item(r, c).setBackground(bg_color)

            self.btn_save_srt.setEnabled(True)
            self._update_srt_diagnostics()
        except Exception as e:
            print(f"Error handling cell change: {e}")
        finally:
            self.sub_table.cellChanged.connect(self._on_subtitle_cell_changed)

    @Slot()
    def _on_save_srt_clicked(self) -> None:
        if not hasattr(self, "current_subtitles") or not self.current_subtitles:
            return

        srt_path_str = self.srt_path.text().strip()
        if not srt_path_str:
            return

        reply = QMessageBox.question(
            self, "Xác nhận lưu phụ đề",
            "Bạn có chắc muốn ghi đè các thay đổi vào tệp phụ đề gốc không?\n"
            "(Hệ thống sẽ tự động tạo file sao lưu .bak trước khi ghi)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        )

        if reply == QMessageBox.StandardButton.Cancel:
            return

        target_path = srt_path_str
        if reply == QMessageBox.StandardButton.No:
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Lưu tệp phụ đề mới", srt_path_str, "Subtitle Files (*.srt)"
            )
            if not save_path:
                return
            target_path = save_path

        if target_path == srt_path_str:
            try:
                import shutil
                shutil.copy2(srt_path_str, srt_path_str + ".bak")
            except Exception as e:
                print(f"Error creating backup: {e}")

        try:
            lines = []
            for sub in self.current_subtitles:
                lines.append(str(sub["index"]))
                start_fmt = sub["start_time_str"].replace(".", ",")
                end_fmt = sub["end_time_str"].replace(".", ",")
                lines.append(f"{start_fmt} --> {end_fmt}")
                lines.append(sub["text"])
                lines.append("")

            with open(target_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            QMessageBox.information(self, "Thành công", f"Đã lưu phụ đề vào:\n{target_path}")
            self.btn_save_srt.setEnabled(False)

            if target_path != srt_path_str:
                self.srt_path.setText(target_path)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu phụ đề: {e}")

    def _update_srt_diagnostics(self) -> None:
        if not hasattr(self, "current_subtitles") or not self.current_subtitles:
            self.lbl_srt_diag.setText("Chưa tải tệp phụ đề.")
            self.lbl_srt_diag.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px; font-weight: 500;")
            return

        issues = validate_subtitles(self.current_subtitles, min_duration_sec=0.8)
        num_short = len(issues)

        overlap_indexes = set()
        for i in range(len(self.current_subtitles) - 1):
            s1 = self.current_subtitles[i]
            s2 = self.current_subtitles[i+1]
            if s1["end"] > s2["start"]:
                overlap_indexes.add(s1["index"])
                overlap_indexes.add(s2["index"])
        num_overlap = len(overlap_indexes)

        if num_short > 0 or num_overlap > 0:
            msg_parts = []
            if num_overlap > 0:
                msg_parts.append(f"{num_overlap} dòng trùng lặp")
            if num_short > 0:
                msg_parts.append(f"{num_short} dòng quá ngắn")
            self.lbl_srt_diag.setText(f"⚠️ Phát hiện: {', '.join(msg_parts)}.")
            self.lbl_srt_diag.setStyleSheet(f"color: {COLOR_ERROR}; font-size: 12px; font-weight: 500;")
        else:
            self.lbl_srt_diag.setText("✅ Tất cả phụ đề đều hợp lệ.")
            self.lbl_srt_diag.setStyleSheet(f"color: {COLOR_SUCCESS}; font-size: 12px; font-weight: 500;")

    @Slot()
    def _on_check_timing_clicked(self) -> None:
        if not hasattr(self, "current_subtitles") or not self.current_subtitles:
            QMessageBox.information(self, "Kiểm tra thời gian", "Chưa có dữ liệu phụ đề để kiểm tra.")
            return

        issues = validate_subtitles(self.current_subtitles, min_duration_sec=0.8)
        overlap_indexes = set()
        overlap_details = []
        for i in range(len(self.current_subtitles) - 1):
            s1 = self.current_subtitles[i]
            s2 = self.current_subtitles[i+1]
            if s1["end"] > s2["start"]:
                overlap_indexes.add(s1["index"])
                overlap_indexes.add(s2["index"])
                overlap_details.append(
                    f"- Dòng {s1['index']} đè thời gian với Dòng {s2['index']} ({s1['end_time_str']} > {s2['start_time_str']})"
                )

        short_details = [
            f"- Dòng {issue['index']}: Thời lượng chỉ {issue['duration'] / 1_000_000.0:.2f}s (< 0.8s)"
            for issue in issues
        ]

        if not overlap_indexes and not issues:
            QMessageBox.information(
                self,
                "Kiểm tra thời gian",
                "✅ Tuyệt vời! Không phát hiện lỗi trùng lặp thời gian hoặc dòng quá ngắn."
            )
            return

        report = []
        if overlap_details:
            report.append("❌ CẢNH BÁO TRÙNG LẶP THỜI GIAN (OVERLAPS):")
            report.extend(overlap_details)
            report.append("")
        if short_details:
            report.append("⚠️ CẢNH BÁO DÒNG QUÁ NGẮN (<0.8s):")
            report.extend(short_details)

        QMessageBox.warning(
            self,
            "Kết quả kiểm tra thời gian",
            "\n".join(report)
        )
