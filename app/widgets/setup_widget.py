# app/widgets/setup_widget.py
import os
from pathlib import Path
from PySide6.QtCore import Slot, Signal, Qt
from PySide6.QtGui import QColor, QFontDatabase, QPixmap, QFont
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
)
from app.presets import KEYFRAME_PRESETS, TRANSITION_PRESETS
from profiles.subtitle import parse_srt_file, validate_subtitles

class SetupWidget(QWidget):
    add_to_queue_requested = Signal()
    build_now_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setObjectName("leftScroll")
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(15)

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

        left_layout.addWidget(project_card)

        # 2. ÂM THANH CARD
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

        self.bgm_path = QLineEdit()
        self.bgm_path.setPlaceholderText("Chọn nhạc nền lồng thêm (Không bắt buộc)...")
        audio_layout.addWidget(self._create_field_label("Tệp nhạc nền (BGM Audio - Tùy chọn)"))
        audio_layout.addLayout(self._create_path_row(self.bgm_path, "audio"))

        left_layout.addWidget(audio_card)

        # 3. PHỤ ĐỀ (SRT) CARD
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
        self.sub_table.setMinimumHeight(150)
        self.sub_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sub_table.setStyleSheet("""
            QTableWidget {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                gridline-color: rgba(255, 255, 255, 0.04);
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 6px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }
            QTableWidget::item {
                padding: 4px;
            }
        """)
        srt_layout.addWidget(self.sub_table)
        
        # Connect textChanged signal to parse and validate subtitle file
        self.srt_path.textChanged.connect(self._on_srt_path_changed)

        left_layout.addWidget(srt_card)

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
                background-color: #0b0f19;
                border: 1px solid rgba(255, 255, 255, 0.08);
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
        
        self.preview_label = QLabel("Cuộc rượt đuổi bắt đầu lúc nửa đêm.")
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
            db = QFontDatabase()
            for family in db.families():
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
        
        btn_style_sheet = """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.03);
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
                color: #f1f5f9;
            }
            QPushButton:checked {
                background-color: rgba(139, 92, 246, 0.15);
                color: #a78bfa;
                border: 1px solid rgba(139, 92, 246, 0.35);
            }
        """

        self.subtitle_bold = QPushButton("Đậm")
        self.subtitle_bold.setCheckable(True)
        self.subtitle_bold.setChecked(True)
        self.subtitle_bold.setStyleSheet(btn_style_sheet)
        
        self.subtitle_italic = QPushButton("Nghiêng")
        self.subtitle_italic.setCheckable(True)
        self.subtitle_italic.setStyleSheet(btn_style_sheet)
        
        self.subtitle_underline = QPushButton("Gạch chân")
        self.subtitle_underline.setCheckable(True)
        self.subtitle_underline.setStyleSheet(btn_style_sheet)
        
        self.subtitle_shadow = QPushButton("Bóng")
        self.subtitle_shadow.setCheckable(True)
        self.subtitle_shadow.setChecked(True)
        self.subtitle_shadow.setStyleSheet(btn_style_sheet)

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

        left_layout.addWidget(font_card)

        # 5. COLLAPSIBLE ADVANCED SETTINGS SECTION
        self.settings_toggle = QPushButton("▼  Cài đặt nâng cao & Giao diện")
        self.settings_toggle.setObjectName("settingsToggle")
        self.settings_toggle.setCheckable(True)
        self.settings_toggle.setChecked(True)
        self.settings_toggle.clicked.connect(self._toggle_advanced_settings)
        left_layout.addWidget(self.settings_toggle)

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

        left_layout.addWidget(self.settings_frame)

        # Action Buttons for Queue Management
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)
        
        self.btn_add_queue = QPushButton("➕ Thêm vào hàng đợi")
        self.btn_add_queue.setObjectName("btnAddQueue")
        self.btn_add_queue.clicked.connect(self.add_to_queue_requested.emit)
        
        self.btn_build_now = QPushButton("⚡ Dựng dự án ngay")
        self.btn_build_now.setObjectName("btnBuildNow")
        self.btn_build_now.clicked.connect(self.build_now_requested.emit)
        
        actions_layout.addWidget(self.btn_add_queue, 1)
        actions_layout.addWidget(self.btn_build_now, 1)
        left_layout.addLayout(actions_layout)

        left_scroll.setWidget(left_content)
        layout.addWidget(left_scroll)

        # Initializations
        self._on_bg_switch_mode_changed()
        self.refresh_intro_outro_combos()
        self._update_subtitle_preview()
        self._update_preview_canvas_size()

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
        if checked:
            self.settings_toggle.setText("▼  Cài đặt nâng cao & Giao diện")
        else:
            self.settings_toggle.setText("▶  Cài đặt nâng cao & Giao diện")

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
        
        # Build preview stylesheet
        style = f"font-family: '{font_family}'; font-size: {max(8, int(font_size * 2.2))}px; color: {color_hex};"
        if bold:
            style += " font-weight: bold;"
        else:
            style += " font-weight: normal;"
        if italic:
            style += " font-style: italic;"
        else:
            style += " font-style: normal;"
        if underline:
            style += " text-decoration: underline;"

        self.preview_label.setStyleSheet(style)
        
        # Real-time Drop shadow using QGraphicsDropShadowEffect
        if self.subtitle_shadow.isChecked():
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(8)
            effect.setOffset(self.subtitle_shadow_distance.value() / 3.0)
            alpha = int(self.subtitle_shadow_alpha.value() * 255)
            effect.setColor(QColor(0, 0, 0, alpha))
            self.preview_label.setGraphicsEffect(effect)
        else:
            self.preview_label.setGraphicsEffect(None)
        
        # Update color preview swatch
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
        self.sub_table.setRowCount(0)
        path_str = path_str.strip()
        if not path_str or not os.path.exists(path_str):
            return
            
        subtitles = parse_srt_file(path_str)
        issues = validate_subtitles(subtitles, min_duration_sec=0.8)
        
        # Build set of issue subtitle indices
        short_sub_indexes = {issue["index"] for issue in issues}
        
        self.sub_table.setRowCount(len(subtitles))
        for idx, sub in enumerate(subtitles):
            # Index
            item_idx = QTableWidgetItem(str(sub["index"]))
            item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Time Range
            item_time = QTableWidgetItem(f"{sub['start_time_str']} -> {sub['end_time_str']}")
            
            # Duration
            duration_sec = sub["duration"] / 1_000_000.0
            item_dur = QTableWidgetItem(f"{duration_sec:.2f}s")
            item_dur.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Text content
            item_text = QTableWidgetItem(sub["text"])
            
            # Status and Warnings
            if sub["index"] in short_sub_indexes:
                item_status = QTableWidgetItem("⚠️ Quá ngắn (<0.8s)")
                item_status.setForeground(QColor("#ef4444"))  # Red
                
                # Apply visual warning background highlight
                for item in [item_idx, item_time, item_dur, item_text, item_status]:
                    item.setBackground(QColor(239, 68, 68, 20)) # Light warning tint
            else:
                item_status = QTableWidgetItem("✅ Hợp lệ")
                item_status.setForeground(QColor("#10b981"))  # Green
                
            self.sub_table.setItem(idx, 0, item_idx)
            self.sub_table.setItem(idx, 1, item_time)
            self.sub_table.setItem(idx, 2, item_dur)
            self.sub_table.setItem(idx, 3, item_text)
            self.sub_table.setItem(idx, 4, item_status)

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
