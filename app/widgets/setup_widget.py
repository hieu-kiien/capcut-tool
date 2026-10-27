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
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_SIDEBAR_BG, DARK_BG, FONT_CONSOLE,
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
    QSplitter,
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

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = self.font()
        painter.setFont(font)

        rect = self.rect()
        text = self.text()
        if not text:
            return

        fm = painter.fontMetrics()
        lines = text.split("\n")
        line_height = fm.lineSpacing()
        total_text_height = len(lines) * line_height

        start_y = (rect.height() - total_text_height) / 2.0 + fm.ascent()

        path = QPainterPath()
        align = self.alignment()

        for i, line in enumerate(lines):
            line_w = fm.horizontalAdvance(line)
            if align & Qt.AlignmentFlag.AlignLeft:
                lx = rect.x() + 10.0
            elif align & Qt.AlignmentFlag.AlignRight:
                lx = rect.width() - line_w - 10.0
            else:
                lx = (rect.width() - line_w) / 2.0
            ly = start_y + i * line_height
            path.addText(lx, ly, font, line)

        # Draw shadow
        if self.shadow_enabled and self.shadow_distance > 0 and self.shadow_alpha > 0:
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


class DropLineEdit(QLineEdit):
    """
    Custom QLineEdit that accepts Drag & Drop of files/folders from Windows Explorer.
    """
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.setStyleSheet("border: 1px solid #00F2FE;")
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.setStyleSheet("")
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                local_path = urls[0].toLocalFile()
                if local_path:
                    norm_path = os.path.normpath(local_path)
                    self.setText(norm_path)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)


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
        font_lbl = QFont("JetBrains Mono", 8, QFont.Weight.Bold)
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
                background-color: {COLOR_TEAL};
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

        # ---------------------------------------------------------
        # COMMERCIAL STUDIO SINGLE-SCREEN 3-COLUMN STUDIO LAYOUT
        # QSplitter: Left 25% (Assets) | Center 50% (Canvas & Timeline) | Right 25% (Keyframes & Build)
        # ---------------------------------------------------------
        self.studio_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.studio_splitter.setObjectName("studioSplitter")
        self.splitter = self.studio_splitter

        # ==================== COLUMN 1: MATERIAL ASSETS (25%) ====================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 8, 4)
        left_layout.setSpacing(14)

        # 1. ÂM THANH CARD (Voice & BGM with Auto-Ducking)
        audio_card = QFrame()
        audio_card.setObjectName("configCard")
        audio_layout = QVBoxLayout(audio_card)
        audio_layout.setContentsMargins(14, 14, 14, 14)
        audio_layout.setSpacing(10)

        audio_title = QLabel("Tài nguyên âm thanh")
        audio_title.setObjectName("cardTitle")
        audio_layout.addWidget(audio_title)

        self.voice_path = DropLineEdit("Chọn tệp âm thanh giọng đọc chính (.mp3, .wav)...")
        audio_layout.addWidget(self._create_field_label("Giọng đọc chính (Voice Audio)"))
        audio_layout.addLayout(self._create_path_row(self.voice_path, "audio"))

        # Voice Waveform Widget
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
        self.lbl_playback_time.setStyleSheet(f"font-family: {FONT_CONSOLE}; color: #a1a1aa; font-size: 11px;")
        self.playback_controls.addWidget(self.lbl_playback_time)
        self.playback_controls.addStretch()
        audio_layout.addLayout(self.playback_controls)

        # BGM Audio Path
        self.bgm_path = DropLineEdit("Chọn nhạc nền lồng thêm (Không bắt buộc)...")
        audio_layout.addWidget(self._create_field_label("Nhạc nền (BGM Audio - Tùy chọn)"))
        audio_layout.addLayout(self._create_path_row(self.bgm_path, "audio"))

        # BGM Waveform Widget
        self.bgm_waveform_widget = AudioWaveformWidget()
        audio_layout.addWidget(self.bgm_waveform_widget)

        # Auto-Ducking 20% Rule Badge
        ducking_badge = QLabel("● Audio Auto-Ducking: BGM tự động giảm còn 20% khi có Voice")
        ducking_badge.setStyleSheet("color: #00F2FE; font-size: 10px; font-weight: 600; padding: 2px 0;")
        audio_layout.addWidget(ducking_badge)

        self.voice_path.textChanged.connect(self._on_voice_path_changed)
        self.bgm_path.textChanged.connect(self._on_bgm_path_changed)
        left_layout.addWidget(audio_card)

        # 2. MEDIA NỀN CARD
        media_card = QFrame()
        media_card.setObjectName("configCard")
        media_layout = QVBoxLayout(media_card)
        media_layout.setContentsMargins(14, 14, 14, 14)
        media_layout.setSpacing(10)

        media_title = QLabel("Kho Media nền")
        media_title.setObjectName("cardTitle")
        media_layout.addWidget(media_title)

        self.media_dir = DropLineEdit("Thư mục chứa kho video/hình ảnh nền...")
        media_layout.addWidget(self._create_field_label("Thư mục Video/Ảnh nền (Background Media)"))
        media_layout.addLayout(self._create_path_row(self.media_dir, "folder"))
        self.media_dir.textChanged.connect(self._on_media_dir_changed_sync)
        left_layout.addWidget(media_card)

        # 3. PHỤ ĐỀ (SRT) CARD
        srt_card = QFrame()
        srt_card.setObjectName("configCard")
        srt_layout = QVBoxLayout(srt_card)
        srt_layout.setContentsMargins(14, 14, 14, 14)
        srt_layout.setSpacing(10)

        srt_title = QLabel("Phụ đề (SRT)")
        srt_title.setObjectName("cardTitle")
        srt_layout.addWidget(srt_title)

        self.srt_path = DropLineEdit("Chọn tệp phụ đề (.srt - Không bắt buộc)...")
        srt_layout.addWidget(self._create_field_label("Tệp phụ đề (SRT Subtitles - Tùy chọn)"))
        srt_layout.addLayout(self._create_path_row(self.srt_path, "srt"))

        # Table of subtitles
        self.sub_table = QTableWidget()
        self.sub_table.setColumnCount(5)
        self.sub_table.setHorizontalHeaderLabels(["STT", "Thời gian", "Độ dài", "Nội dung", "Trạng thái"])
        self.sub_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.sub_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.sub_table.setMinimumHeight(150)
        self.sub_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.SelectedClicked)
        self.sub_table.itemSelectionChanged.connect(self._on_sub_table_selection_changed)
        srt_layout.addWidget(self.sub_table)

        # Subtitle timing diagnostics footer
        diag_layout = QHBoxLayout()
        diag_layout.setContentsMargins(2, 2, 2, 2)
        diag_layout.setSpacing(8)

        self.lbl_srt_diag = QLabel("Chưa tải tệp phụ đề.")
        self.lbl_srt_diag.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px; font-weight: 500;")

        self.btn_check_timing = QPushButton(" Kiểm tra")
        self.btn_check_timing.setIcon(get_svg_icon("clock", color=COLOR_TEXT_PRIMARY, size=12))
        self.btn_check_timing.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SIDEBAR_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                color: {COLOR_TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLOR_TEAL};
                color: #000000;
                border-color: {COLOR_TEAL};
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
        left_layout.addWidget(srt_card)

        # ==================== COLUMN 2: CANVAS PREVIEW & TIMELINE (50%) ====================
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(6, 4, 6, 4)
        center_layout.setSpacing(14)

        # 4. KHUNG XEM TRƯỚC VÀ ĐỊNH DẠNG CHỮ CARD
        font_card = QFrame()
        font_card.setObjectName("configCard")
        font_layout = QVBoxLayout(font_card)
        font_layout.setContentsMargins(14, 14, 14, 14)
        font_layout.setSpacing(10)

        preview_header_row = QHBoxLayout()
        font_title = QLabel("Xem trước & Kiểu chữ phụ đề")
        font_title.setObjectName("cardTitle")
        preview_header_row.addWidget(font_title)

        # Aspect ratio toggle
        ratio_box = QHBoxLayout()
        ratio_box.setSpacing(10)
        self.ratio_9_16 = QRadioButton("Dọc (9:16)")
        self.ratio_9_16.setChecked(True)
        self.ratio_16_9 = QRadioButton("Ngang (16:9)")
        ratio_box.addWidget(self.ratio_9_16)
        ratio_box.addWidget(self.ratio_16_9)
        preview_header_row.addStretch()
        preview_header_row.addLayout(ratio_box)
        font_layout.addLayout(preview_header_row)

        # Live Preview Container simulating Canvas
        preview_container = QFrame()
        preview_container.setObjectName("previewContainer")
        preview_container.setMinimumHeight(300)
        preview_container.setStyleSheet(f"""
            QFrame#previewContainer {{
                background-color: {DARK_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
            }}
        """)
        preview_vbox = QVBoxLayout(preview_container)
        preview_vbox.setContentsMargins(10, 10, 10, 10)
        preview_vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Black simulated video canvas
        self.preview_canvas = QFrame()
        self.preview_canvas.setObjectName("previewCanvas")
        self.preview_canvas.setStyleSheet("background-color: #000000; border: 1px solid rgba(255,255,255,0.15); border-radius: 4px;")

        self.canvas_layout = QVBoxLayout(self.preview_canvas)
        self.canvas_layout.setContentsMargins(10, 10, 10, 10)

        self.preview_label = SubtitlePreviewLabel("Cuộc rượt đuổi bắt đầu lúc nửa đêm.")
        self.preview_label.setWordWrap(True)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_layout.addWidget(self.preview_label)

        preview_vbox.addWidget(self.preview_canvas, 0, Qt.AlignmentFlag.AlignCenter)

        preview_tag = QLabel("XEM TRƯỚC TRỰC TIẾP (9:16 VERTICAL AUTO-WRAP)")
        preview_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_tag.setStyleSheet("color: #94a3b8; font-size: 8px; font-weight: bold; letter-spacing: 1.5px; margin-top: 6px;")
        preview_vbox.addWidget(preview_tag, 0)
        font_layout.addWidget(preview_container)

        # Styling controls grid
        style_grid = QGridLayout()
        style_grid.setSpacing(8)

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

        style_grid.addWidget(self._create_field_label("Cỡ chữ"), 0, 2)
        self.subtitle_font_size = QDoubleSpinBox()
        self.subtitle_font_size.setRange(1.0, 100.0)
        self.subtitle_font_size.setValue(6.0)
        self.subtitle_font_size.setSingleStep(0.5)
        style_grid.addWidget(self.subtitle_font_size, 0, 3)

        style_grid.addWidget(self._create_field_label("Màu sắc"), 1, 0)
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
        style_grid.addLayout(color_row, 1, 1)

        style_grid.addWidget(self._create_field_label("Căn lề"), 1, 2)
        self.subtitle_align = QComboBox()
        self.subtitle_align.addItem("Giữa dưới (Bottom Center)", "bottom_center")
        self.subtitle_align.addItem("Chính giữa (Center)", "center")
        self.subtitle_align.addItem("Giữa trên (Top Center)", "top_center")
        self.subtitle_align.addItem("Trái dưới (Bottom Left)", "bottom_left")
        self.subtitle_align.addItem("Phải dưới (Bottom Right)", "bottom_right")
        style_grid.addWidget(self.subtitle_align, 1, 3)

        style_grid.addWidget(self._create_field_label("Độ rộng viền"), 2, 0)
        self.subtitle_outline_width = QDoubleSpinBox()
        self.subtitle_outline_width.setRange(0.0, 100.0)
        self.subtitle_outline_width.setValue(40.0)
        self.subtitle_outline_width.setSingleStep(5.0)
        style_grid.addWidget(self.subtitle_outline_width, 2, 1)

        style_grid.addWidget(self._create_field_label("Bóng đổ (Alpha/Dist)"), 2, 2)
        shadow_row = QHBoxLayout()
        self.subtitle_shadow_alpha = QDoubleSpinBox()
        self.subtitle_shadow_alpha.setRange(0.0, 1.0)
        self.subtitle_shadow_alpha.setValue(0.8)
        self.subtitle_shadow_alpha.setSingleStep(0.05)
        self.subtitle_shadow_distance = QDoubleSpinBox()
        self.subtitle_shadow_distance.setRange(0.0, 50.0)
        self.subtitle_shadow_distance.setValue(5.0)
        self.subtitle_shadow_distance.setSingleStep(0.5)
        shadow_row.addWidget(self.subtitle_shadow_alpha, 1)
        shadow_row.addWidget(self.subtitle_shadow_distance, 1)
        style_grid.addLayout(shadow_row, 2, 3)

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

        self.ratio_9_16.toggled.connect(self._update_preview_canvas_size)
        self.ratio_16_9.toggled.connect(self._update_preview_canvas_size)
        self.subtitle_align.currentIndexChanged.connect(self._update_preview_canvas_size)

        center_layout.addWidget(font_card)

        # 5. CẤU TRÚC TIMELINE CARD
        timeline_card = QFrame()
        timeline_card.setObjectName("configCard")
        timeline_layout = QVBoxLayout(timeline_card)
        timeline_layout.setContentsMargins(14, 14, 14, 14)
        timeline_layout.setSpacing(8)

        timeline_title = QLabel("Cấu trúc Timeline (Intro 15% / Media 70% / Outro 15%)")
        timeline_title.setObjectName("cardTitle")
        timeline_layout.addWidget(timeline_title)

        from app.widgets.dashboard_widget import TimelineWidget
        self.timeline_widget = TimelineWidget()
        timeline_layout.addWidget(self.timeline_widget)

        center_layout.addWidget(timeline_card)

        # ==================== COLUMN 3: KEYFRAME PRESETS & BUILD (25%) ====================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 4, 4, 4)
        right_layout.setSpacing(14)

        # 6. THÔNG TIN DỰ ÁN CARD
        project_card = QFrame()
        project_card.setObjectName("configCard")
        project_layout = QVBoxLayout(project_card)
        project_layout.setContentsMargins(14, 14, 14, 14)
        project_layout.setSpacing(10)

        proj_title = QLabel("Thông tin dự án")
        proj_title.setObjectName("cardTitle")
        project_layout.addWidget(proj_title)

        self.project_name = QLineEdit("Du_An_CapCut")
        self.project_name.setPlaceholderText("Tên dự án nháp CapCut (không viết dấu)...")
        project_layout.addWidget(self._create_field_label("Tên dự án nháp"))
        project_layout.addWidget(self.project_name)

        self.draft_root = DropLineEdit("Thư mục lưu dự án nháp của CapCut...")
        project_layout.addWidget(self._create_field_label("Thư mục dự án nháp CapCut (Draft Root)"))
        project_layout.addLayout(self._create_path_row(self.draft_root, "folder"))

        self.btn_capcut_launch = QPushButton(" Mở CapCut PC")
        self.btn_capcut_launch.setIcon(get_svg_icon("capcut", color="#ffffff", size=16))
        self.btn_capcut_launch.setToolTip("Tự động tìm và mở ứng dụng CapCut PC trên Windows")
        self.btn_capcut_launch.setStyleSheet(f"background-color: {COLOR_SIDEBAR_BG}; border: 1px solid {COLOR_CARD_BORDER}; border-radius: 6px; padding: 6px 12px; font-weight: 600; color: #ffffff;")
        self.btn_capcut_launch.clicked.connect(self._launch_capcut_quick)
        project_layout.addWidget(self.btn_capcut_launch)

        right_layout.addWidget(project_card)

        # 7. PRESET KEYFRAME & CHUYỂN CẢNH CARD
        kf_card = QFrame()
        kf_card.setObjectName("configCard")
        kf_layout = QVBoxLayout(kf_card)
        kf_layout.setContentsMargins(14, 14, 14, 14)
        kf_layout.setSpacing(10)

        kf_title = QLabel("Keyframe & Hiệu ứng")
        kf_title.setObjectName("cardTitle")
        kf_layout.addWidget(kf_title)

        kf_layout.addWidget(self._create_field_label("Tự động thêm Keyframe (Auto Keyframe)"))
        self.auto_kf_combo = QComboBox()
        self.auto_kf_combo.addItem("Không áp dụng (None)", "none")
        self.auto_kf_combo.addItem("Trộn ngẫu nhiên (Random)", "random")
        for p in KEYFRAME_PRESETS:
            self.auto_kf_combo.addItem(p["name"], p["id"])
        kf_layout.addWidget(self.auto_kf_combo)

        # Keyframe offset note (0.3s)
        kf_offset_note = QLabel("● Keyframe Padding Offset: Bù 0.3s điểm đầu/cuối tránh rung giật")
        kf_offset_note.setStyleSheet("color: #a1a1aa; font-size: 10px; font-weight: 500;")
        kf_layout.addWidget(kf_offset_note)

        kf_layout.addWidget(self._create_field_label("Tự động thêm Chuyển cảnh (Auto Transition)"))
        self.auto_trans_combo = QComboBox()
        self.auto_trans_combo.addItem("Không áp dụng (None)", "none")
        self.auto_trans_combo.addItem("Trộn ngẫu nhiên (Random)", "random")
        for t in TRANSITION_PRESETS:
            self.auto_trans_combo.addItem(t["label"], t["name"])
        kf_layout.addWidget(self.auto_trans_combo)

        trans_dur_row = QHBoxLayout()
        trans_dur_row.addWidget(self._create_field_label("Thời lượng chuyển cảnh (giây)"))
        self.auto_trans_dur = QDoubleSpinBox()
        self.auto_trans_dur.setRange(0.1, 5.0)
        self.auto_trans_dur.setValue(0.4)
        self.auto_trans_dur.setSingleStep(0.05)
        trans_dur_row.addWidget(self.auto_trans_dur)
        kf_layout.addLayout(trans_dur_row)

        intro_outro_grid = QGridLayout()
        intro_outro_grid.setSpacing(8)
        intro_outro_grid.addWidget(self._create_field_label("Video mở đầu (Intro)"), 0, 0)
        self.intro_combo = QComboBox()
        self.intro_combo.currentIndexChanged.connect(self._update_timeline_structure)
        intro_outro_grid.addWidget(self.intro_combo, 0, 1)

        intro_outro_grid.addWidget(self._create_field_label("Video kết thúc (Outro)"), 1, 0)
        self.outro_combo = QComboBox()
        self.outro_combo.currentIndexChanged.connect(self._update_timeline_structure)
        intro_outro_grid.addWidget(self.outro_combo, 1, 1)
        kf_layout.addLayout(intro_outro_grid)

        # Collapsible advanced settings
        self.settings_toggle = QPushButton(" Cài đặt nâng cao & Giao diện")
        self.settings_toggle.setIcon(get_svg_icon("settings", color=COLOR_TEAL, size=14))
        self.settings_toggle.setObjectName("settingsToggle")
        self.settings_toggle.setCheckable(True)
        self.settings_toggle.setChecked(False)
        self.settings_toggle.clicked.connect(self._toggle_advanced_settings)
        kf_layout.addWidget(self.settings_toggle)

        self.settings_frame = QFrame()
        self.settings_frame.setObjectName("settingsFrame")
        settings_grid = QGridLayout(self.settings_frame)
        settings_grid.setContentsMargins(8, 8, 8, 8)
        settings_grid.setSpacing(10)

        # Slicing timers
        settings_grid.addWidget(self._create_field_label("Clip nền tối thiểu (s)"), 0, 0)
        self.clip_min = QDoubleSpinBox()
        self.clip_min.setRange(0.5, 86400.0)
        self.clip_min.setValue(5.0)
        self.clip_min.setSingleStep(0.5)
        settings_grid.addWidget(self.clip_min, 0, 1)

        settings_grid.addWidget(self._create_field_label("Clip nền tối đa (s)"), 1, 0)
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
        settings_grid.addWidget(self._create_field_label("Xử lý video ngắn"), 3, 0)
        self.short_video_mode = QComboBox()
        self.short_video_mode.addItems([
            "Kéo giãn / Đổi tốc độ (stretch)",
            "Tự động lặp lại (loop)"
        ])
        settings_grid.addWidget(self.short_video_mode, 3, 1)

        # Background Switch Mode
        settings_grid.addWidget(self._create_field_label("Quy tắc chuyển cảnh"), 4, 0)
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

        kf_layout.addWidget(self.settings_frame)
        self.settings_frame.setVisible(False)
        right_layout.addWidget(kf_card)

        # 8. HÀNH ĐỘNG DỰNG (Action Buttons Card)
        actions_card = QFrame()
        actions_card.setObjectName("configCard")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(14, 14, 14, 14)
        actions_layout.setSpacing(10)

        actions_title = QLabel("Xuất bản & Điều khiển")
        actions_title.setObjectName("cardTitle")
        actions_layout.addWidget(actions_title)

        self.btn_build_now = QPushButton(" DỰNG NGAY")
        self.btn_build_now.setIcon(get_svg_icon("play", color="#000000", size=14))
        self.btn_build_now.setObjectName("btnBuildNow")
        self.btn_build_now.clicked.connect(self.build_now_requested.emit)
        actions_layout.addWidget(self.btn_build_now)

        self.btn_add_queue = QPushButton(" THÊM VÀO HÀNG ĐỢI")
        self.btn_add_queue.setIcon(get_svg_icon("plus", color="#000000", size=14))
        self.btn_add_queue.setObjectName("btnAddQueue")
        self.btn_add_queue.clicked.connect(self.add_to_queue_requested.emit)
        actions_layout.addWidget(self.btn_add_queue)

        self.btn_quick_capcut = QPushButton("  Mở CapCut PC")
        self.btn_quick_capcut.setIcon(get_svg_icon("capcut", color="#ffffff", size=16))
        self.btn_quick_capcut.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                border-color: #00F2FE;
            }
        """)
        self.btn_quick_capcut.clicked.connect(self._launch_capcut_quick)
        actions_layout.addWidget(self.btn_quick_capcut)

        right_layout.addWidget(actions_card)
        right_layout.addStretch()

        # Wrap columns in QScrollAreas for responsiveness
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setWidget(left_widget)

        center_scroll = QScrollArea()
        center_scroll.setWidgetResizable(True)
        center_scroll.setFrameShape(QFrame.Shape.NoFrame)
        center_scroll.setWidget(center_widget)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setWidget(right_widget)

        self.studio_splitter.addWidget(left_scroll)
        self.studio_splitter.addWidget(center_scroll)
        self.studio_splitter.addWidget(right_scroll)

        self.studio_splitter.setSizes([320, 640, 320])
        self.studio_splitter.setStretchFactor(0, 1)
        self.studio_splitter.setStretchFactor(1, 2)
        self.studio_splitter.setStretchFactor(2, 1)

        layout.addWidget(self.studio_splitter, 1)

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

    @Slot()
    def _on_sub_table_selection_changed(self) -> None:
        selected_rows = self.sub_table.selectedItems()
        if selected_rows:
            row = selected_rows[0].row()
            text_item = self.sub_table.item(row, 3)
            if text_item and text_item.text():
                raw_text = text_item.text().strip()
                words = raw_text.split()
                if len(words) > 8 and "\n" not in raw_text:
                    mid = len(words) // 2
                    wrapped = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
                else:
                    wrapped = raw_text
                self.preview_label.setText(wrapped)
                self.preview_label.update()

    @Slot()
    def _launch_capcut_quick(self) -> None:
        from draft_doctor import find_capcut_executable
        capcut_exe = find_capcut_executable()
        if capcut_exe and capcut_exe.exists():
            try:
                subprocess.Popen([str(capcut_exe)])
            except Exception as e:
                QMessageBox.warning(self, "Lỗi", f"Không thể khởi chạy CapCut: {e}")
        else:
            QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy CapCut.exe trên Windows!\nVui lòng kiểm tra lại cài đặt CapCut PC.")

    @Slot()
    def _update_timeline_structure(self) -> None:
        if not hasattr(self, "timeline_widget") or self.timeline_widget is None:
            return
        intro_val = self.intro_combo.currentText() if hasattr(self, "intro_combo") else ""
        has_intro = bool(intro_val and intro_val != "Không sử dụng")
        outro_val = self.outro_combo.currentText() if hasattr(self, "outro_combo") else ""
        has_outro = bool(outro_val and outro_val != "Không sử dụng")
        media_count = 0
        media_path = self.media_dir.text().strip() if hasattr(self, "media_dir") else ""
        if media_path and Path(media_path).is_dir():
            try:
                media_count = len([p for p in Path(media_path).iterdir() if p.suffix.lower() in {'.mp4', '.mov', '.jpg', '.png', '.jpeg', '.mkv'}])
            except Exception:
                media_count = 0
        dur_str = getattr(self.waveform_widget, "duration_str", "00:00")
        self.timeline_widget.set_data(has_intro, has_outro, media_count, dur_str)

    @Slot(str)
    def _on_media_dir_changed_sync(self, text: str) -> None:
        self._update_timeline_structure()

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
                    item_status.setText("Quá ngắn & Trùng lặp")
                elif is_short:
                    item_status.setText("Quá ngắn (<0.8s)")
                else:
                    item_status.setText("Trùng lặp thời gian")
                item_status.setIcon(get_svg_icon("alert", color=COLOR_ERROR, size=14))
                item_status.setForeground(QCOLOR_ERROR)  # Red

                # Apply visual warning background highlight
                warning_bg = QColor(QCOLOR_ERROR.red(), QCOLOR_ERROR.green(), QCOLOR_ERROR.blue(), 20)
                for item in [item_idx, item_time, item_dur, item_text, item_status]:
                    item.setBackground(warning_bg) # Light warning tint
            else:
                item_status.setText("Hợp lệ")
                item_status.setIcon(get_svg_icon("check", color=COLOR_SUCCESS, size=14))
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
                        status_text = "Quá ngắn & Trùng lặp"
                    elif is_short:
                        status_text = "Quá ngắn (<0.8s)"
                    else:
                        status_text = "Trùng lặp thời gian"
                    status_item.setText(status_text)
                    status_item.setIcon(get_svg_icon("alert", color=COLOR_ERROR, size=14))
                    status_item.setForeground(QCOLOR_ERROR)
                else:
                    bg_color = QColor(Qt.GlobalColor.transparent)
                    status_text = "Hợp lệ"
                    status_item.setText(status_text)
                    status_item.setIcon(get_svg_icon("check", color=COLOR_SUCCESS, size=14))
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
            self.lbl_srt_diag.setText(f"Phát hiện: {', '.join(msg_parts)}.")
            self.lbl_srt_diag.setStyleSheet(f"color: {COLOR_ERROR}; font-size: 12px; font-weight: 500;")
        else:
            self.lbl_srt_diag.setText("Tất cả phụ đề đều hợp lệ.")
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
                "Tuyệt vời! Không phát hiện lỗi trùng lặp thời gian hoặc dòng quá ngắn."
            )
            return

        report = []
        if overlap_details:
            report.append("[CẢNH BÁO TRÙNG LẶP THỜI GIAN]:")
            report.extend(overlap_details)
            report.append("")
        if short_details:
            report.append("[CẢNH BÁO DÒNG QUÁ NGẮN (<0.8s)]:")
            report.extend(short_details)

        QMessageBox.warning(
            self,
            "Kết quả kiểm tra thời gian",
            "\n".join(report)
        )
