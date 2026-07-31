# app/widgets/effects_widget.py
import os
import random
import uuid
from pathlib import Path
from PySide6.QtCore import Slot, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QScrollArea,
    QFileDialog,
)
from app.icons import get_svg_icon
from app.presets import KEYFRAME_PRESETS, TRANSITION_PRESETS, load_all_presets, add_custom_preset, delete_custom_preset

class EffectsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Page Header
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 4)
        header_layout.setSpacing(4)

        lbl_title = QLabel("Hiệu ứng & Thương hiệu")
        lbl_title.setObjectName("pageTitle")
        lbl_subtitle = QLabel("Chèn logo thương hiệu, thêm video hiệu ứng tương tác và tuỳ chỉnh thuộc tính chuyển động (keyframes/transitions).")
        lbl_subtitle.setObjectName("pageSubtitle")

        header_layout.addWidget(lbl_title)
        header_layout.addWidget(lbl_subtitle)
        layout.addWidget(header_widget)

        kf_scroll = QScrollArea()
        kf_scroll.setWidgetResizable(True)
        kf_scroll.setObjectName("kfScroll")
        kf_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        kf_content = QWidget()
        kf_layout = QVBoxLayout(kf_content)
        kf_layout.setContentsMargins(0, 0, 0, 0)
        kf_layout.setSpacing(15)

        # 1. LOGO CARD
        logo_card = QFrame()
        logo_card.setObjectName("configCard")
        logo_layout = QVBoxLayout(logo_card)
        logo_layout.setContentsMargins(16, 16, 16, 16)
        logo_layout.setSpacing(12)

        logo_title = QLabel("Logo")
        logo_title.setObjectName("cardTitle")
        logo_layout.addWidget(logo_title)

        # Logo Visual Preview
        self.logo_preview_container = QFrame()
        self.logo_preview_container.setObjectName("previewContainer")
        self.logo_preview_container.setMinimumHeight(80)
        self.logo_preview_container.setStyleSheet("""
            QFrame#previewContainer {
                background-color: #0c0f17;
                border: 1px dashed rgba(255, 255, 255, 0.08);
                border-radius: 6px;
            }
        """)
        logo_preview_vbox = QVBoxLayout(self.logo_preview_container)
        self.logo_preview_label = QLabel("Chưa chọn tệp Logo")
        self.logo_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_preview_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        logo_preview_vbox.addWidget(self.logo_preview_label)
        logo_layout.addWidget(self.logo_preview_container)

        self.logo_path = QLineEdit()
        self.logo_path.setPlaceholderText("Chọn hình ảnh logo (.png, .jpg)...")
        self.logo_path.textChanged.connect(self._update_logo_preview)
        logo_layout.addWidget(self._create_field_label("Tệp hình ảnh Logo (Logo - Tùy chọn)"))
        logo_layout.addLayout(self._create_path_row(self.logo_path, "image"))

        logo_grid = QGridLayout()
        logo_grid.setSpacing(10)
        
        logo_grid.addWidget(self._create_field_label("Vị trí Logo"), 0, 0)
        self.logo_position = QComboBox()
        self.logo_position.addItem("Trên-Phải (top_right)", "top_right")
        self.logo_position.addItem("Trên-Trái (top_left)", "top_left")
        self.logo_position.addItem("Dưới-Phải (bottom_right)", "bottom_right")
        self.logo_position.addItem("Dưới-Trái (bottom_left)", "bottom_left")
        logo_grid.addWidget(self.logo_position, 0, 1)

        logo_grid.addWidget(self._create_field_label("Tỷ lệ thu phóng Logo (%)"), 1, 0)
        self.logo_scale = QDoubleSpinBox()
        self.logo_scale.setRange(1.0, 100.0)
        self.logo_scale.setValue(15.0)
        self.logo_scale.setSingleStep(1.0)
        self.logo_scale.setDecimals(0)
        logo_grid.addWidget(self.logo_scale, 1, 1)

        logo_grid.addWidget(self._create_field_label("Độ mờ đục Logo (%)"), 2, 0)
        self.logo_opacity = QSpinBox()
        self.logo_opacity.setRange(0, 100)
        self.logo_opacity.setValue(100)
        self.logo_opacity.setSingleStep(5)
        logo_grid.addWidget(self.logo_opacity, 2, 1)
        
        logo_layout.addLayout(logo_grid)
        kf_layout.addWidget(logo_card)

        # 2. HIỆU ỨNG ĐĂNG KÝ CARD
        anim_card = QFrame()
        anim_card.setObjectName("configCard")
        anim_layout = QVBoxLayout(anim_card)
        anim_layout.setContentsMargins(16, 16, 16, 16)
        anim_layout.setSpacing(12)

        anim_title = QLabel("Hiệu ứng đăng ký")
        anim_title.setObjectName("cardTitle")
        anim_layout.addWidget(anim_title)

        # Anim Visual Preview
        self.anim_preview_container = QFrame()
        self.anim_preview_container.setObjectName("previewContainer")
        self.anim_preview_container.setMinimumHeight(80)
        self.anim_preview_container.setStyleSheet("""
            QFrame#previewContainer {
                background-color: #0c0f17;
                border: 1px dashed rgba(255, 255, 255, 0.08);
                border-radius: 6px;
            }
        """)
        anim_preview_vbox = QVBoxLayout(self.anim_preview_container)
        self.anim_preview_label = QLabel("Chưa chọn tệp video đăng ký")
        self.anim_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.anim_preview_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        anim_preview_vbox.addWidget(self.anim_preview_label)
        anim_layout.addWidget(self.anim_preview_container)

        self.anim_path = QLineEdit()
        self.anim_path.setPlaceholderText("Chọn video hoạt ảnh Subscribe/Like (.mp4, .mov)...")
        self.anim_path.textChanged.connect(self._update_anim_preview)
        anim_layout.addWidget(self._create_field_label("Tệp hoạt ảnh Subscribe/Like (Tùy chọn)"))
        anim_layout.addLayout(self._create_path_row(self.anim_path, "video"))

        anim_grid = QGridLayout()
        anim_grid.setSpacing(10)
        
        anim_grid.addWidget(self._create_field_label("Vị trí Hoạt ảnh"), 0, 0)
        self.anim_position = QComboBox()
        self.anim_position.addItem("Dưới-Giữa (bottom_center)", "bottom_center")
        self.anim_position.addItem("Chính giữa (center)", "center")
        self.anim_position.addItem("Dưới-Trái (bottom_left)", "bottom_left")
        self.anim_position.addItem("Dưới-Phải (bottom_right)", "bottom_right")
        anim_grid.addWidget(self.anim_position, 0, 1)

        anim_grid.addWidget(self._create_field_label("Tỷ lệ thu phóng Anim (%)"), 1, 0)
        self.anim_scale = QDoubleSpinBox()
        self.anim_scale.setRange(1.0, 100.0)
        self.anim_scale.setValue(30.0)
        self.anim_scale.setSingleStep(1.0)
        self.anim_scale.setDecimals(0)
        anim_grid.addWidget(self.anim_scale, 1, 1)

        anim_grid.addWidget(self._create_field_label("Thời điểm xuất hiện"), 2, 0)
        self.anim_timing = QComboBox()
        self.anim_timing.addItem("Cuối video (end)", "end")
        self.anim_timing.addItem("Đầu video (start)", "start")
        self.anim_timing.addItem("Giữa video (middle)", "middle")
        self.anim_timing.addItem("Lặp lại mỗi 60s (repeat_60s)", "repeat_60s")
        anim_grid.addWidget(self.anim_timing, 2, 1)

        anim_layout.addLayout(anim_grid)
        kf_layout.addWidget(anim_card)

        # 3. CHROMA KEY CARD (Xóa phông nền)
        chroma_card = QFrame()
        chroma_card.setObjectName("configCard")
        chroma_layout = QVBoxLayout(chroma_card)
        chroma_layout.setContentsMargins(16, 16, 16, 16)
        chroma_layout.setSpacing(12)

        chroma_title = QLabel("Chroma Key")
        chroma_title.setObjectName("cardTitle")
        chroma_layout.addWidget(chroma_title)

        # Chroma Visual Backdrop simulation
        chroma_preview_container = QFrame()
        chroma_preview_container.setMinimumHeight(80)
        chroma_preview_container.setStyleSheet("""
            QFrame {
                background: conic-gradient(at top right, #00ff00, #222222, #00ff00);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
            }
        """)
        chroma_preview_vbox = QVBoxLayout(chroma_preview_container)
        chroma_preview_label = QLabel("Xóa nền xanh lá tự động")
        chroma_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chroma_preview_label.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold; text-shadow: 0px 1px 3px rgba(0,0,0,0.8);")
        chroma_preview_vbox.addWidget(chroma_preview_label)
        chroma_layout.addWidget(chroma_preview_container)

        self.chroma_enabled = QCheckBox("Kích hoạt xóa nền xanh (Chroma Key)")
        self.chroma_enabled.setChecked(False)
        chroma_layout.addWidget(self.chroma_enabled)

        chroma_grid = QGridLayout()
        chroma_grid.setSpacing(10)

        chroma_grid.addWidget(self._create_field_label("Lựa chọn màu xóa nền"), 0, 0)
        self.chroma_mode = QComboBox()
        self.chroma_mode.addItem("Xanh lá (Green Screen)", "green")
        self.chroma_mode.addItem("Xanh dương (Blue Screen)", "blue")
        self.chroma_mode.addItem("Nền đen (Black Screen)", "black")
        self.chroma_mode.addItem("Nền trắng (White Screen)", "white")
        chroma_grid.addWidget(self.chroma_mode, 0, 1)

        chroma_grid.addWidget(self._create_field_label("Độ nhạy Chroma (Ngưỡng)"), 1, 0)
        self.chroma_threshold = QSpinBox()
        self.chroma_threshold.setRange(1, 100)
        self.chroma_threshold.setValue(32)
        chroma_grid.addWidget(self.chroma_threshold, 1, 1)

        chroma_grid.addWidget(self._create_field_label("Làm mềm viền (px)"), 2, 0)
        self.chroma_shadow = QSpinBox()
        self.chroma_shadow.setRange(0, 100)
        self.chroma_shadow.setValue(2)
        chroma_grid.addWidget(self.chroma_shadow, 2, 1)

        chroma_layout.addLayout(chroma_grid)
        kf_layout.addWidget(chroma_card)

        # 3.5. HIỆU ỨNG PHỤ ĐỀ / KARAOKE CARD
        sub_card = QFrame()
        sub_card.setObjectName("configCard")
        sub_layout = QVBoxLayout(sub_card)
        sub_layout.setContentsMargins(16, 16, 16, 16)
        sub_layout.setSpacing(12)

        sub_title = QLabel("Hiệu ứng phụ đề")
        sub_title.setObjectName("cardTitle")
        sub_layout.addWidget(sub_title)

        self.subtitle_karaoke = QCheckBox("Kích hoạt chạy chữ karaoke theo tiếng (Karaoke Subtitles)")
        self.subtitle_karaoke.setChecked(False)
        sub_layout.addWidget(self.subtitle_karaoke)

        sub_hint = QLabel("Tự động áp dụng hiệu ứng đổi màu chữ chạy theo giọng nói cho phụ đề SRT.")
        sub_hint.setObjectName("appSubtitle")
        sub_layout.addWidget(sub_hint)

        kf_layout.addWidget(sub_card)

        # 4. CHUYỂN ĐỘNG & CHUYỂN CẢNH CARD
        editor_card = QFrame()
        editor_card.setObjectName("configCard")
        editor_lay = QVBoxLayout(editor_card)
        editor_lay.setContentsMargins(16, 16, 16, 16)
        editor_lay.setSpacing(14)
        
        editor_title = QLabel("Chuyển động & Chuyển cảnh")
        editor_title.setObjectName("cardTitle")
        editor_lay.addWidget(editor_title)

        # Target Project Selection Sub-panel
        target_proj_frame = QFrame()
        target_proj_frame.setObjectName("settingsFrame")
        target_proj_lay = QVBoxLayout(target_proj_frame)
        target_proj_lay.setContentsMargins(10, 8, 10, 8)
        target_proj_lay.setSpacing(8)
        
        target_proj_lay.addWidget(self._create_field_label("Dự Án Nháp CapCut Mục Tiêu"))
        proj_row = QHBoxLayout()
        self.project_combo = QComboBox()
        self.project_combo.setPlaceholderText("Vui lòng nhập Draft Root để quét các dự án...")
        proj_row.addWidget(self.project_combo, 1)
        
        self.btn_refresh_projects = QPushButton("Tải Lại")
        self.btn_refresh_projects.setObjectName("btnBrowse")
        proj_row.addWidget(self.btn_refresh_projects)
        target_proj_lay.addLayout(proj_row)
        
        editor_lay.addWidget(target_proj_frame)
        
        # Action selector
        form_lay = QFormLayout()
        form_lay.setSpacing(12)
        
        self.effect_type_combo = QComboBox()
        self.effect_type_combo.addItem("Preset Zoom/Pan có sẵn", "presets")
        self.effect_type_combo.addItem("Keyframe tự chọn (Hỗ trợ 3 điểm mốc)", "custom")
        self.effect_type_combo.addItem("Hiệu ứng chuyển cảnh (Transitions)", "transition")
        self.effect_type_combo.addItem("Thay đổi tốc độ (Speed)", "speed")
        self.effect_type_combo.addItem("Thay đổi tỷ lệ Zoom (Scale)", "scale")
        self.effect_type_combo.currentIndexChanged.connect(self._on_effect_type_changed)
        
        form_lay.addRow(self._create_field_label("Chọn loại thao tác:"), self.effect_type_combo)
        editor_lay.addLayout(form_lay)
        
        # Sub-panels for individual options
        self.pane_presets = QFrame()
        presets_outer = QVBoxLayout(self.pane_presets)
        presets_outer.setContentsMargins(0, 0, 0, 0)
        presets_outer.setSpacing(10)

        self.kf_preset_combo = QComboBox()
        self.kf_preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        
        self.btn_delete_preset = QPushButton(" Xóa")
        self.btn_delete_preset.setIcon(get_svg_icon("trash", color="#ef4444", size=14))
        self.btn_delete_preset.setObjectName("btnBrowse")
        self.btn_delete_preset.clicked.connect(self._on_delete_preset_clicked)
        self.btn_delete_preset.setEnabled(False)
        
        preset_sel_lay = QHBoxLayout()
        preset_sel_lay.setSpacing(8)
        preset_sel_lay.addWidget(self.kf_preset_combo, 1)
        preset_sel_lay.addWidget(self.btn_delete_preset)
        
        preset_sel_row = QFormLayout()
        preset_sel_row.setSpacing(8)
        preset_sel_row.addRow(self._create_field_label("Chọn Preset:"), preset_sel_lay)
        presets_outer.addLayout(preset_sel_row)
        
        self.refresh_presets_combo()

        def _spin(lo, hi, val, step=1.0, dec=1, suffix=""):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            s.setSingleStep(step)
            s.setDecimals(dec)
            if suffix:
                s.setSuffix(suffix)
            return s

        def _param_frame():
            f = QFrame()
            f.setObjectName("settingsFrame")
            lay = QFormLayout(f)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(8)
            return f, lay

        # ── Nhóm A: Zoom đơn giản ──────────────────────────────────────────
        self._pg_zoom, pg_zoom = _param_frame()
        self.param_zoom_from = _spin(50, 300, 100, 1, 1, " %")
        self.param_zoom_to   = _spin(50, 300, 112, 1, 1, " %")
        pg_zoom.addRow(self._create_field_label("Zoom từ (%): "), self.param_zoom_from)
        pg_zoom.addRow(self._create_field_label("Zoom đến (%): "), self.param_zoom_to)
        presets_outer.addWidget(self._pg_zoom)

        # ── Nhóm B: Zoom Bounce ─────────────────────────────────────────────
        self._pg_bounce, pg_bounce = _param_frame()
        self.param_bounce_from    = _spin(50, 300, 100, 1, 1, " %")
        self.param_bounce_peak    = _spin(50, 400, 118, 1, 1, " %")
        self.param_bounce_peak_at = _spin(10,  90,  60, 5, 0, " %")
        self.param_bounce_end     = _spin(50, 300, 108, 1, 1, " %")
        pg_bounce.addRow(self._create_field_label("Zoom ban đầu (%): "),      self.param_bounce_from)
        pg_bounce.addRow(self._create_field_label("Zoom đỉnh (%): "),          self.param_bounce_peak)
        pg_bounce.addRow(self._create_field_label("Thời điểm đỉnh (% clip): "),self.param_bounce_peak_at)
        pg_bounce.addRow(self._create_field_label("Zoom cuối (%): "),           self.param_bounce_end)
        presets_outer.addWidget(self._pg_bounce)

        # ── Nhóm C: Pan chỉ dọc/ngang ──────────────────────────────────────
        self._pg_pan, pg_pan = _param_frame()
        self.param_pan_zoom = _spin(100, 300, 115, 1, 1, " %")
        self.param_pan_from = _spin(-0.5, 0.5, -0.07, 0.01, 3)
        self.param_pan_to   = _spin(-0.5, 0.5,  0.07, 0.01, 3)
        pg_pan.addRow(self._create_field_label("Zoom nền (%): "), self.param_pan_zoom)
        self._lbl_pan_from = self._create_field_label("Vị trí đầu: ")
        self._lbl_pan_to   = self._create_field_label("Vị trí cuối: ")
        pg_pan.addRow(self._lbl_pan_from, self.param_pan_from)
        pg_pan.addRow(self._lbl_pan_to,   self.param_pan_to)
        _pan_hint = QLabel("Tọa độ: -0.5 ← trái/trên | 0 = giữa | 0.5 = phải/dưới")
        _pan_hint.setObjectName("appSubtitle")
        pg_pan.addRow(_pan_hint)
        presets_outer.addWidget(self._pg_pan)

        # ── Nhóm D: Zoom + Pan ──────────────────────────────────────────────
        self._pg_zoompan, pg_zp = _param_frame()
        self.param_zp_zoom_from = _spin(50, 300, 100, 1, 1, " %")
        self.param_zp_zoom_to   = _spin(50, 300, 115, 1, 1, " %")
        self.param_zp_pan_from  = _spin(-0.5, 0.5,  0.0,  0.01, 3)
        self.param_zp_pan_to    = _spin(-0.5, 0.5, -0.06, 0.01, 3)
        pg_zp.addRow(self._create_field_label("Zoom từ (%): "),   self.param_zp_zoom_from)
        pg_zp.addRow(self._create_field_label("Zoom đến (%): "),  self.param_zp_zoom_to)
        self._lbl_zp_from = self._create_field_label("Pan từ (vị trí đầu): ")
        self._lbl_zp_to   = self._create_field_label("Pan đến (vị trí cuối): ")
        pg_zp.addRow(self._lbl_zp_from, self.param_zp_pan_from)
        pg_zp.addRow(self._lbl_zp_to,   self.param_zp_pan_to)
        _zp_hint = QLabel("Pan: -0.5 ← trái/trên | 0 = giữa | 0.5 = phải/dưới")
        _zp_hint.setObjectName("appSubtitle")
        pg_zp.addRow(_zp_hint)
        presets_outer.addWidget(self._pg_zoompan)

        # ── Nhóm E: Zoom + Xoay ─────────────────────────────────────────────
        self._pg_rotate, pg_rot = _param_frame()
        self.param_rot_zoom = _spin(100, 300, 105, 1, 1, " %")
        self.param_rot_from = _spin(-360, 360, -1.5, 0.5, 1, " °")
        self.param_rot_to   = _spin(-360, 360,  1.5, 0.5, 1, " °")
        pg_rot.addRow(self._create_field_label("Zoom nền (%): "),      self.param_rot_zoom)
        pg_rot.addRow(self._create_field_label("Góc xoay đầu (°): "), self.param_rot_from)
        pg_rot.addRow(self._create_field_label("Góc xoay cuối (°): "),self.param_rot_to)
        presets_outer.addWidget(self._pg_rotate)

        # ── Nhóm F: Fade đơn giản ───────────────────────────────────────────
        self._pg_fade, pg_fade = _param_frame()
        self.param_fade_from = _spin(0, 1, 0.0, 0.05, 2)
        self.param_fade_to   = _spin(0, 1, 1.0, 0.05, 2)
        pg_fade.addRow(self._create_field_label("Alpha đầu (0=ẩn, 1=hiện): "), self.param_fade_from)
        pg_fade.addRow(self._create_field_label("Alpha cuối (0=ẩn, 1=hiện): "),self.param_fade_to)
        presets_outer.addWidget(self._pg_fade)

        # ── Nhóm G: Fade In-Out ─────────────────────────────────────────────
        self._pg_fadeinout, pg_fio = _param_frame()
        self.param_fio_in_end    = _spin(1, 49, 15, 5, 0, " %")
        self.param_fio_out_start = _spin(51, 99, 85, 5, 0, " %")
        pg_fio.addRow(self._create_field_label("Kết thúc Fade In (% clip): "),  self.param_fio_in_end)
        pg_fio.addRow(self._create_field_label("Bắt đầu Fade Out (% clip): "), self.param_fio_out_start)
        presets_outer.addWidget(self._pg_fadeinout)

        editor_lay.addWidget(self.pane_presets)
        
        # Custom Keyframe Editor (Unit, From, To, Mid value/position)
        self.pane_custom = QFrame()
        custom_form = QFormLayout(self.pane_custom)
        custom_form.setContentsMargins(0, 0, 0, 0)
        custom_form.setSpacing(10)
        
        self.custom_prop_combo = QComboBox()
        self.custom_prop_combo.addItem("Phóng to đồng đều (Scale Uniform)", "scale_uniform")
        self.custom_prop_combo.addItem("Thu phóng trục X (Scale X)", "scale_x")
        self.custom_prop_combo.addItem("Thu phóng trục Y (Scale Y)", "scale_y")
        self.custom_prop_combo.addItem("Xoay góc (Rotation)", "rotation")
        self.custom_prop_combo.addItem("Vị trí trục X (Position X)", "pos_x")
        self.custom_prop_combo.addItem("Vị trí trục Y (Position Y)", "pos_y")
        self.custom_prop_combo.addItem("Độ mờ đục / Alpha (Alpha)", "alpha")
        self.custom_prop_combo.currentIndexChanged.connect(self._on_custom_prop_changed)
        custom_form.addRow(self._create_field_label("Chọn Thuộc Tính:"), self.custom_prop_combo)
        
        self.custom_unit_combo = QComboBox()
        self.custom_unit_combo.addItem("Mặc định / Tỷ lệ (Raw / Coordinates)", "raw")
        self.custom_unit_combo.addItem("Phần trăm so với kích thước gốc (pct_base)", "pct_base")
        self.custom_unit_combo.addItem("Điểm ảnh Pixel (px)", "px")
        custom_form.addRow(self._create_field_label("Đơn vị (Unit):"), self.custom_unit_combo)
        
        self.custom_from_spin = QDoubleSpinBox()
        custom_form.addRow(self._create_field_label("Giá trị đầu (From Value):"), self.custom_from_spin)
        
        # Middle keyframe check and controls
        self.custom_mid_chk = QCheckBox("Thêm điểm mốc ở giữa (Middle Keyframe)")
        self.custom_mid_chk.setChecked(False)
        self.custom_mid_chk.toggled.connect(self._toggle_mid_keyframe_visibility)
        custom_form.addRow(self.custom_mid_chk)
        
        self.custom_mid_val_label = self._create_field_label("Giá trị giữa (Mid Value):")
        self.custom_mid_spin = QDoubleSpinBox()
        custom_form.addRow(self.custom_mid_val_label, self.custom_mid_spin)
        
        self.custom_mid_time_label = self._create_field_label("Vị trí mốc ở giữa (%):")
        self.custom_mid_time_spin = QDoubleSpinBox()
        self.custom_mid_time_spin.setRange(1.0, 99.0)
        self.custom_mid_time_spin.setValue(50.0)
        self.custom_mid_time_spin.setSingleStep(1.0)
        custom_form.addRow(self.custom_mid_time_label, self.custom_mid_time_spin)
        
        # Position coordinate auto clamping
        self.custom_clamp_chk = QCheckBox("Tự động căn lề khung hình (Clamp to Frame)")
        self.custom_clamp_chk.setChecked(True)
        custom_form.addRow(self.custom_clamp_chk)
        
        self.custom_to_spin = QDoubleSpinBox()
        custom_form.addRow(self._create_field_label("Giá trị cuối (To Value):"), self.custom_to_spin)
        
        self.custom_desc_lbl = QLabel()
        self.custom_desc_lbl.setObjectName("appSubtitle")
        custom_form.addRow(self.custom_desc_lbl)
        
        self.btn_save_custom = QPushButton(" Lưu thành Preset")
        self.btn_save_custom.setIcon(get_svg_icon("save", color="#00F2FE", size=14))
        self.btn_save_custom.setObjectName("btnBrowse")
        self.btn_save_custom.clicked.connect(self._on_save_custom_preset_clicked)
        custom_form.addRow("", self.btn_save_custom)
        
        editor_lay.addWidget(self.pane_custom)
        
        # Initial mid-keyframe controls hide
        self._toggle_mid_keyframe_visibility(False)
        
        # Transitions panel
        self.pane_trans = QFrame()
        trans_form = QFormLayout(self.pane_trans)
        trans_form.setContentsMargins(0, 0, 0, 0)
        trans_form.setSpacing(10)
        
        self.trans_preset_combo = QComboBox()
        self.trans_preset_combo.addItem("Trộn ngẫu nhiên (Random)", "random")
        for t in TRANSITION_PRESETS:
            self.trans_preset_combo.addItem(t["label"], t["name"])
        self.trans_preset_combo.addItem("Tự nhập tên riêng...", "custom")
        self.trans_preset_combo.currentIndexChanged.connect(self._on_trans_preset_changed)
        trans_form.addRow(self._create_field_label("Kiểu chuyển cảnh:"), self.trans_preset_combo)
        
        self.trans_custom_name = QLineEdit()
        self.trans_custom_name.setPlaceholderText("Ví dụ: Mix, Central Fade, Checker Fade...")
        self.trans_custom_name.setEnabled(False)
        trans_form.addRow(self._create_field_label("Tên chuyển cảnh (Tự nhập):"), self.trans_custom_name)
        
        self.trans_duration_spin = QDoubleSpinBox()
        self.trans_duration_spin.setRange(0.1, 5.0)
        self.trans_duration_spin.setValue(0.4)
        self.trans_duration_spin.setSingleStep(0.05)
        trans_form.addRow(self._create_field_label("Thời lượng hiệu ứng (giây):"), self.trans_duration_spin)
        
        self.trans_apply_all_chk = QCheckBox("Áp dụng cho tất cả điểm cắt (không lọc loại)")
        self.trans_apply_all_chk.setChecked(False)
        trans_form.addRow(self.trans_apply_all_chk)
        editor_lay.addWidget(self.pane_trans)
        
        # Speed panel
        self.pane_speed = QFrame()
        speed_form = QFormLayout(self.pane_speed)
        speed_form.setContentsMargins(0, 0, 0, 0)
        speed_form.setSpacing(10)
        self.speed_mode_combo = QComboBox()
        self.speed_mode_combo.addItem("Nhân tốc độ (ví dụ: 1.5 = nhanh gấp rưỡi)", "speed")
        self.speed_mode_combo.addItem("Đặt thời lượng cố định (giây)", "duration")
        speed_form.addRow(self._create_field_label("Chế độ tốc độ:"), self.speed_mode_combo)
        
        self.speed_val_spin = QDoubleSpinBox()
        self.speed_val_spin.setRange(0.01, 100.0)
        self.speed_val_spin.setValue(1.0)
        self.speed_val_spin.setSingleStep(0.1)
        speed_form.addRow(self._create_field_label("Giá trị tốc độ / thời lượng:"), self.speed_val_spin)
        editor_lay.addWidget(self.pane_speed)
        
        # Scale panel
        self.pane_scale = QFrame()
        scale_form = QFormLayout(self.pane_scale)
        scale_form.setContentsMargins(0, 0, 0, 0)
        scale_form.setSpacing(10)
        self.scale_pct_spin = QDoubleSpinBox()
        self.scale_pct_spin.setRange(10.0, 1000.0)
        self.scale_pct_spin.setValue(100.0)
        self.scale_pct_spin.setSingleStep(5.0)
        scale_form.addRow(self._create_field_label("Tỷ lệ Zoom thu phóng (%):"), self.scale_pct_spin)
        
        self.scale_skip_first_chk = QCheckBox("Bỏ qua clip đầu tiên (skip first)")
        self.scale_skip_first_chk.setChecked(False)
        scale_form.addRow(self.scale_skip_first_chk)
        editor_lay.addWidget(self.pane_scale)

        # Separator line
        self.editor_sep = QFrame()
        self.editor_sep.setFrameShape(QFrame.Shape.HLine)
        self.editor_sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.05);")
        editor_lay.addWidget(self.editor_sep)
        
        # Shared controls at the bottom of the card
        self.shared_controls_form = QFormLayout()
        self.shared_controls_form.setSpacing(10)
        
        self.shared_segment_combo = QComboBox()
        self.shared_segment_combo.addItem("Chỉ Video (video)", "video")
        self.shared_segment_combo.addItem("Chỉ Hình ảnh (image)", "image")
        self.shared_segment_combo.addItem("Cả hai (media)", "media")
        self.shared_segment_combo.addItem("Tất cả (all)", "all")
        self.shared_controls_form.addRow(self._create_field_label("Phân đoạn áp dụng:"), self.shared_segment_combo)
        
        self.shared_mode_combo = QComboBox()
        self.shared_mode_combo.addItem("Ghi đè thuộc tính cũ (replace)", "replace")
        self.shared_mode_combo.addItem("Thêm tiếp thuộc tính mới (append)", "append")
        self.shared_controls_form.addRow(self._create_field_label("Chế độ lưu:"), self.shared_mode_combo)
        
        editor_lay.addLayout(self.shared_controls_form)

        # Trigger default sub-panel visibility
        self._on_effect_type_changed(0)
        self._on_custom_prop_changed(0)
        self._on_preset_selected(0)
        
        self.btn_apply_effect = QPushButton("ÁP DỤNG HIỆU ỨNG CHO DỰ ÁN")
        self.btn_apply_effect.setObjectName("btnRun")
        editor_lay.addWidget(self.btn_apply_effect)
        
        kf_layout.addWidget(editor_card)
        kf_scroll.setWidget(kf_content)
        layout.addWidget(kf_scroll)

        # Trigger initial previews
        self._update_logo_preview()
        self._update_anim_preview()

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
        if mode == "image":
            path, _ = QFileDialog.getOpenFileName(
                self, "Chọn tệp hình ảnh logo", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
            )
        elif mode == "video":
            path, _ = QFileDialog.getOpenFileName(
                self, "Chọn tệp hoạt ảnh", "", "Video Files (*.mp4 *.mov *.avi *.mkv)"
            )
        else:
            path = ""
            
        if path:
            line_edit.setText(os.path.normpath(path))

    @Slot()
    def _update_logo_preview(self) -> None:
        path = self.logo_path.text().strip()
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.logo_preview_label.setPixmap(pixmap.scaled(
                    150, 70,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                return
            else:
                self.logo_preview_label.setText(os.path.basename(path))
                return
        self.logo_preview_label.setText("Chưa chọn tệp Logo")

    @Slot()
    def _update_anim_preview(self) -> None:
        path = self.anim_path.text().strip()
        if path:
            self.anim_preview_label.setText(f"{os.path.basename(path)}")
        else:
            self.anim_preview_label.setText("Chưa chọn tệp video hoạt ảnh")

    @Slot(int)
    def _on_effect_type_changed(self, index: int = 0) -> None:
        action = self.effect_type_combo.currentData()
        self.pane_presets.setVisible(action == "presets")
        self.pane_custom.setVisible(action == "custom")
        self.pane_trans.setVisible(action == "transition")
        self.pane_speed.setVisible(action == "speed")
        self.pane_scale.setVisible(action == "scale")

        if action == "presets":
            self._on_preset_selected()

        show_shared = action in ("presets", "custom", "transition")
        self.shared_segment_combo.setVisible(show_shared)
        self.shared_mode_combo.setVisible(show_shared)

        self.shared_controls_form.itemAt(0, QFormLayout.ItemRole.LabelRole).widget().setVisible(show_shared)
        self.shared_controls_form.itemAt(1, QFormLayout.ItemRole.LabelRole).widget().setVisible(show_shared)
        self.editor_sep.setVisible(show_shared)

    @Slot(int)
    def _on_custom_prop_changed(self, index: int) -> None:
        prop = self.custom_prop_combo.currentData()
        is_pos = prop in ("pos_x", "pos_y")
        self.custom_clamp_chk.setVisible(is_pos)
        
        if prop in ("scale_uniform", "scale_x", "scale_y"):
            self.custom_from_spin.setRange(0.0, 10.0)
            self.custom_from_spin.setValue(1.0)
            self.custom_from_spin.setSingleStep(0.05)
            self.custom_to_spin.setRange(0.0, 10.0)
            self.custom_to_spin.setValue(1.15)
            self.custom_to_spin.setSingleStep(0.05)
            
            self.custom_mid_spin.setRange(0.0, 10.0)
            self.custom_mid_spin.setValue(1.08)
            self.custom_mid_spin.setSingleStep(0.05)
            self.custom_desc_lbl.setText("Tỷ lệ thu phóng (ví dụ: 1.0 = 100%, 1.15 = 115%)")
        elif prop == "rotation":
            self.custom_from_spin.setRange(-360.0, 360.0)
            self.custom_from_spin.setValue(0.0)
            self.custom_from_spin.setSingleStep(1.0)
            self.custom_to_spin.setRange(-360.0, 360.0)
            self.custom_to_spin.setValue(2.0)
            self.custom_to_spin.setSingleStep(1.0)
            
            self.custom_mid_spin.setRange(-360.0, 360.0)
            self.custom_mid_spin.setValue(1.0)
            self.custom_mid_spin.setSingleStep(0.5)
            self.custom_desc_lbl.setText("Góc xoay theo độ (ví dụ: 0.0 -> 2.0 độ)")
        elif is_pos:
            self.custom_from_spin.setRange(-5000.0, 5000.0)
            self.custom_from_spin.setValue(0.0)
            self.custom_from_spin.setSingleStep(0.01)
            self.custom_to_spin.setRange(-5000.0, 5000.0)
            self.custom_to_spin.setValue(0.05)
            self.custom_to_spin.setSingleStep(0.01)
            
            self.custom_mid_spin.setRange(-5000.0, 5000.0)
            self.custom_mid_spin.setValue(0.02)
            self.custom_mid_spin.setSingleStep(0.01)
            self.custom_desc_lbl.setText("Tọa độ dịch chuyển (Raw: -0.5 đến 0.5, px: Pixel dịch chuyển)")
        elif prop == "alpha":
            self.custom_from_spin.setRange(0.0, 1.0)
            self.custom_from_spin.setValue(1.0)
            self.custom_from_spin.setSingleStep(0.05)
            self.custom_to_spin.setRange(0.0, 1.0)
            self.custom_to_spin.setValue(0.0)
            self.custom_to_spin.setSingleStep(0.05)
            
            self.custom_mid_spin.setRange(0.0, 1.0)
            self.custom_mid_spin.setValue(0.5)
            self.custom_mid_spin.setSingleStep(0.05)
            self.custom_desc_lbl.setText("Độ trong suốt Alpha (ví dụ: 1.0 = hiện rõ, 0.0 = ẩn)")

    @Slot(bool)
    def _toggle_mid_keyframe_visibility(self, visible: bool) -> None:
        self.custom_mid_val_label.setVisible(visible)
        self.custom_mid_spin.setVisible(visible)
        self.custom_mid_time_label.setVisible(visible)
        self.custom_mid_time_spin.setVisible(visible)

    @Slot(int)
    def _on_trans_preset_changed(self, index: int) -> None:
        is_custom = self.trans_preset_combo.currentData() == "custom"
        self.trans_custom_name.setEnabled(is_custom)
        if not is_custom:
            self.trans_custom_name.clear()

    @Slot(int)
    def _on_preset_selected(self, index: int = 0) -> None:
        preset_id = self.kf_preset_combo.currentData()
        
        # Cập nhật trạng thái nút xóa preset tự chế
        is_custom = bool(preset_id and preset_id.startswith("custom_"))
        if hasattr(self, "btn_delete_preset"):
            self.btn_delete_preset.setEnabled(is_custom)
            
        if not preset_id:
            return

        param_pages = [
            getattr(self, "_pg_zoom", None),
            getattr(self, "_pg_bounce", None),
            getattr(self, "_pg_pan", None),
            getattr(self, "_pg_zoompan", None),
            getattr(self, "_pg_rotate", None),
            getattr(self, "_pg_fade", None),
            getattr(self, "_pg_fadeinout", None),
        ]
        if any(page is None for page in param_pages):
            return
            
        # Hide all first
        for page in param_pages:
            page.hide()

        if preset_id == "random":
            return

        # Check if it is a custom preset
        if preset_id.startswith("custom_"):
            # custom presets don't map to predefined group shapes, keep them hidden
            return

        from app.gui import _PRESET_GROUP_MAP
        group_type, defaults = _PRESET_GROUP_MAP.get(preset_id, (None, {}))
        if group_type == "zoom":
            self.param_zoom_from.setValue(defaults["zoom_from"])
            self.param_zoom_to.setValue(defaults["zoom_to"])
            self._pg_zoom.show()
        elif group_type == "bounce":
            self.param_bounce_from.setValue(defaults["zoom_from"])
            self.param_bounce_peak.setValue(defaults["zoom_peak"])
            self.param_bounce_peak_at.setValue(defaults["zoom_peak_at"])
            self.param_bounce_end.setValue(defaults["zoom_end"])
            self._pg_bounce.show()
        elif group_type == "pan":
            self.param_pan_zoom.setValue(defaults["pan_zoom"])
            self.param_pan_from.setValue(defaults["pan_from"])
            self.param_pan_to.setValue(defaults["pan_to"])
            self._lbl_pan_from.setText(f"Dịch chuyển từ (mốc 0%): {defaults['axis_lbl']}")
            self._lbl_pan_to.setText(f"Dịch chuyển đến (mốc 100%): {defaults['axis_lbl']}")
            self._pg_pan.show()
        elif group_type == "zoompan":
            self.param_zp_zoom_from.setValue(defaults["zoom_from"])
            self.param_zp_zoom_to.setValue(defaults["zoom_to"])
            self.param_zp_pan_from.setValue(defaults["pan_from"])
            self.param_zp_pan_to.setValue(defaults["pan_to"])
            self._lbl_zp_from.setText(f"Pan từ (mốc 0%): {defaults['axis_lbl']}")
            self._lbl_zp_to.setText(f"Pan đến (mốc 100%): {defaults['axis_lbl']}")
            self._pg_zoompan.show()
        elif group_type == "rotate":
            self.param_rot_zoom.setValue(defaults["rot_zoom"])
            self.param_rot_from.setValue(defaults["rot_from"])
            self.param_rot_to.setValue(defaults["rot_to"])
            self._pg_rotate.show()
        elif group_type == "fade":
            self.param_fade_from.setValue(defaults["fade_from"])
            self.param_fade_to.setValue(defaults["fade_to"])
            self._pg_fade.show()
        elif group_type == "fadeinout":
            self.param_fio_in_end.setValue(defaults["fio_in_end"])
            self.param_fio_out_start.setValue(defaults["fio_out_start"])
            self._pg_fadeinout.show()

    def refresh_presets_combo(self) -> None:
        current_id = self.kf_preset_combo.currentData()
        self.kf_preset_combo.clear()
        self.kf_preset_combo.addItem("Ngẫu nhiên (Random Zoom/Pan)", "random")
        
        all_presets = load_all_presets()
        for p in all_presets:
            self.kf_preset_combo.addItem(p["name"], p["id"])
            
        if current_id:
            idx = self.kf_preset_combo.findData(current_id)
            if idx >= 0:
                self.kf_preset_combo.setCurrentIndex(idx)

    @Slot()
    def _on_delete_preset_clicked(self) -> None:
        preset_id = self.kf_preset_combo.currentData()
        preset_name = self.kf_preset_combo.currentText()
        if not preset_id or not preset_id.startswith("custom_"):
            return
            
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa preset '{preset_name}' không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if delete_custom_preset(preset_id):
                QMessageBox.information(self, "Thành công", "Đã xóa preset thành công.")
                self.refresh_presets_combo()
            else:
                QMessageBox.critical(self, "Lỗi", "Không thể xóa preset khỏi cơ sở dữ liệu.")

    @Slot()
    def _on_save_custom_preset_clicked(self) -> None:
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        name, ok = QInputDialog.getText(self, "Lưu Preset Tự Chế", "Nhập tên preset mới:")
        if not ok or not name.strip():
            return
        name = name.strip()
        
        prop = self.custom_prop_combo.currentData()
        unit = self.custom_unit_combo.currentData()
        from_val = self.custom_from_spin.value()
        to_val = self.custom_to_spin.value()
        clamp = self.custom_clamp_chk.isChecked()
        
        op = {
            "property": prop,
            "unit": unit,
            "clamp_to_frame": clamp
        }
        
        if self.custom_mid_chk.isChecked():
            mid_val = self.custom_mid_spin.value()
            mid_time = self.custom_mid_time_spin.value() / 100.0
            op["keyframes"] = [
                {"at": 0.0, "value": from_val},
                {"at": mid_time, "value": mid_val},
                {"at": 1.0, "value": to_val}
            ]
        else:
            op["from"] = from_val
            op["to"] = to_val
            
        operations = [op]
        segment_type = self.shared_segment_combo.currentData() or "media"
        
        preset_id = add_custom_preset(name, segment_type, operations)
        if preset_id:
            QMessageBox.information(self, "Thành công", f"Đã lưu preset '{name}' thành công.")
            self.refresh_presets_combo()
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể lưu preset. Tên preset có thể đã tồn tại.")
