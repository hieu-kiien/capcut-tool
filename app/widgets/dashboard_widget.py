# app/widgets/dashboard_widget.py
from PySide6.QtCore import Qt, Signal, Slot, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QPlainTextEdit,
)
from app.icons import get_svg_icon
from app.theme import (
    COLOR_TEAL, COLOR_CARD_BG, COLOR_CARD_BORDER, COLOR_ERROR,
    COLOR_TEXT_LIGHT, COLOR_TEXT_WHITE, COLOR_TEXT_BLACK,
    COLOR_BG_CONSOLE, COLOR_TEXT_CONSOLE, COLOR_TEXT_SECONDARY,
    QCOLOR_TEAL, QCOLOR_DARK_ZINC, QCOLOR_CARD_BG, QCOLOR_CARD_BORDER,
    QCOLOR_TEXT_SECONDARY, QCOLOR_SLATE, QCOLOR_ERROR, QCOLOR_TEXT_BLACK,
    QCOLOR_TEXT_WHITE
)

class TimelineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.intro_ok = False
        self.outro_ok = False
        self.media_count = 0
        self.timeline_duration = "00:00:00"
        self.setMinimumHeight(55)

    def set_data(self, intro_ok: bool, outro_ok: bool, media_count: int, duration: str) -> None:
        self.intro_ok = intro_ok
        self.outro_ok = outro_ok
        self.media_count = media_count
        self.timeline_duration = duration
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        
        # Draw background bar container
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QCOLOR_DARK_ZINC))
        painter.drawRoundedRect(0, 0, w, h, 6, 6)

        margin_x = 4
        margin_y = 4
        spacing = 6
        draw_h = h - margin_y * 2
        draw_w = w - margin_x * 2

        # 15% width for Intro, 15% for Outro, 70% (minus spacing) for Media
        w_intro = int(draw_w * 0.15)
        w_outro = int(draw_w * 0.15)
        w_media = draw_w - w_intro - w_outro - spacing * 2

        # Draw Intro
        x_intro = margin_x
        rect_intro = QRectF(x_intro, margin_y, w_intro, draw_h)
        if self.intro_ok:
            painter.setBrush(QBrush(QCOLOR_TEAL)) # Teal
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect_intro, 4, 4)
            painter.setPen(QPen(QCOLOR_TEXT_BLACK))
            font = QFont("Inter", 9, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(rect_intro, Qt.AlignmentFlag.AlignCenter, "INTRO")
        else:
            painter.setBrush(QBrush(QCOLOR_CARD_BG)) # Dark gray
            pen = QPen(QCOLOR_CARD_BORDER)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRoundedRect(rect_intro, 4, 4)
            painter.setPen(QPen(QCOLOR_TEXT_SECONDARY))
            font = QFont("Inter", 9)
            painter.setFont(font)
            painter.drawText(rect_intro, Qt.AlignmentFlag.AlignCenter, "Intro (Trống)")

        # Draw Media
        x_media = x_intro + w_intro + spacing
        rect_media = QRectF(x_media, margin_y, w_media, draw_h)
        if self.media_count > 0:
            painter.setBrush(QBrush(QCOLOR_SLATE)) # Slate Gray
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect_media, 4, 4)
            painter.setPen(QPen(QCOLOR_TEXT_WHITE))
            font = QFont("Inter", 9, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(rect_media, Qt.AlignmentFlag.AlignCenter, f"BACKGROUND MEDIA ({self.media_count} Clips)")
        else:
            painter.setBrush(QBrush(QCOLOR_CARD_BG))
            pen = QPen(QCOLOR_ERROR)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRoundedRect(rect_media, 4, 4)
            painter.setPen(QPen(QCOLOR_ERROR))
            font = QFont("Inter", 9)
            painter.setFont(font)
            painter.drawText(rect_media, Qt.AlignmentFlag.AlignCenter, "Media Nền (Thiếu)")

        # Draw Outro
        x_outro = x_media + w_media + spacing
        rect_outro = QRectF(x_outro, margin_y, w_outro, draw_h)
        if self.outro_ok:
            painter.setBrush(QBrush(QCOLOR_TEAL))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect_outro, 4, 4)
            painter.setPen(QPen(QCOLOR_TEXT_BLACK))
            font = QFont("Inter", 9, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(rect_outro, Qt.AlignmentFlag.AlignCenter, "OUTRO")
        else:
            painter.setBrush(QBrush(QCOLOR_CARD_BG))
            pen = QPen(QCOLOR_CARD_BORDER)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRoundedRect(rect_outro, 4, 4)
            painter.setPen(QPen(QCOLOR_TEXT_SECONDARY))
            font = QFont("Inter", 9)
            painter.setFont(font)
            painter.drawText(rect_outro, Qt.AlignmentFlag.AlignCenter, "Outro (Trống)")


class DashboardWidget(QWidget):
    build_center_requested = Signal()
    repair_draft_requested = Signal()
    build_draft_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.intro_ok = False
        self.outro_ok = False
        self.media_count = 0
        self.timeline_estimate = "00:00:00"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for responsiveness
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("dashboardScroll")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(16, 16, 16, 16)
        container_layout.setSpacing(16)

        # Row 1: Project Summary & Resource Readiness (Side-by-side)
        row1_widget = QWidget()
        row1_layout = QHBoxLayout(row1_widget)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(16)

        # 1. Project Summary Section
        summary_card = QFrame()
        summary_card.setObjectName("configCard")
        sum_layout = QVBoxLayout(summary_card)
        sum_layout.setContentsMargins(16, 16, 16, 16)
        sum_layout.setSpacing(12)

        sum_title = QLabel("Tóm tắt dự án")
        sum_title.setObjectName("cardTitle")
        sum_layout.addWidget(sum_title)

        grid = QGridLayout()
        grid.setSpacing(10)

        # Add stats fields
        self.lbl_project_name = QLabel("Campaign_Beta_2024")
        self.lbl_project_name.setWordWrap(True)
        
        self.lbl_canvas = QLabel("9:16 Dọc")
        self.lbl_canvas.setWordWrap(True)
        
        self.lbl_preset = QLabel("TikTok_High_Retention")
        self.lbl_preset.setWordWrap(True)
        
        self.lbl_fps = QLabel("60.00")
        self.lbl_fps.setWordWrap(True)
        
        self.lbl_path = QLabel("C:/CapCut/Drafts/...")
        self.lbl_path.setWordWrap(True)
        
        self.lbl_last_compiled = QLabel("Chưa biên dịch")
        self.lbl_last_compiled.setWordWrap(True)
        
        self.lbl_voice_duration = QLabel("00:58:12")
        self.lbl_voice_duration.setWordWrap(True)
        
        self.lbl_timeline_estimate = QLabel("00:58:42")
        self.lbl_timeline_estimate.setWordWrap(True)

        grid.addWidget(self._create_kpi_card("Tên dự án", self.lbl_project_name), 0, 0)
        grid.addWidget(self._create_kpi_card("Tỉ lệ xuất", self.lbl_canvas), 0, 1)
        grid.addWidget(self._create_kpi_card("Preset đang dùng", self.lbl_preset), 0, 2)
        grid.addWidget(self._create_kpi_card("FPS mục tiêu", self.lbl_fps), 0, 3)

        grid.addWidget(self._create_kpi_card("Đường dẫn nháp", self.lbl_path), 1, 0)
        grid.addWidget(self._create_kpi_card("Biên dịch lần cuối", self.lbl_last_compiled), 1, 1)
        grid.addWidget(self._create_kpi_card("Thời lượng giọng", self.lbl_voice_duration), 1, 2)
        grid.addWidget(self._create_kpi_card("Ước lượng timeline", self.lbl_timeline_estimate), 1, 3)

        sum_layout.addLayout(grid)
        row1_layout.addWidget(summary_card, 1)

        # 2. Resource Readiness Section (2x4 Grid horizontal layout)
        readiness_card = QFrame()
        readiness_card.setObjectName("configCard")
        readiness_layout = QVBoxLayout(readiness_card)
        readiness_layout.setContentsMargins(16, 16, 16, 16)
        readiness_layout.setSpacing(12)

        readiness_title = QLabel("Mức sẵn sàng tài nguyên")
        readiness_title.setObjectName("cardTitle")
        readiness_layout.addWidget(readiness_title)

        readiness_grid = QGridLayout()
        readiness_grid.setSpacing(10)

        # 8 resource cards:
        self.lbl_status_voice = QLabel()
        self.lbl_status_srt = QLabel()
        self.lbl_status_media = QLabel()
        self.lbl_status_bgm = QLabel()
        self.lbl_status_logo = QLabel()
        self.lbl_status_anim = QLabel()
        self.lbl_status_intro = QLabel()
        self.lbl_status_outro = QLabel()

        resources = [
            ("mic", "Giọng đọc", self.lbl_status_voice),
            ("subtitles", "Phụ đề (SRT)", self.lbl_status_srt),
            ("image", "Media nền", self.lbl_status_media),
            ("music", "Nhạc nền", self.lbl_status_bgm),
            ("film", "Bộ logo", self.lbl_status_logo),
            ("sparkles", "Hiệu ứng đăng ký", self.lbl_status_anim),
            ("video", "Clip intro", self.lbl_status_intro),
            ("video", "Clip outro", self.lbl_status_outro),
        ]

        for i, (icon_name, name, lbl) in enumerate(resources):
            row = i // 4
            col = i % 4
            card = QFrame()
            card.setObjectName("resourceCard")
            card.setStyleSheet(f"""
                QFrame#resourceCard {{
                    background-color: rgba(255, 255, 255, 0.02);
                    border: 1px solid {COLOR_CARD_BORDER};
                    border-radius: 8px;
                    padding: 8px 12px;
                }}
                QFrame#resourceCard:hover {{
                    background-color: rgba(255, 255, 255, 0.04);
                    border-color: {COLOR_TEAL};
                }}
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(4, 4, 4, 4)
            card_layout.setSpacing(6)
            
            icon_lbl = QLabel()
            icon_lbl.setPixmap(get_svg_icon(icon_name, color=COLOR_TEAL, size=14).pixmap(14, 14))
            card_layout.addWidget(icon_lbl)
            
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_LIGHT}; font-weight: 500;")
            
            lbl.setAlignment(Qt.AlignCenter)
            self._update_badge(lbl, "KIỂM TRA", "sky")

            card_layout.addWidget(lbl_name, 1)
            card_layout.addWidget(lbl)
            readiness_grid.addWidget(card, row, col)

        readiness_layout.addLayout(readiness_grid)
        row1_layout.addWidget(readiness_card, 1)
        container_layout.addWidget(row1_widget)

        # Row 2: Timeline Section & Project Checks (Side-by-side)
        row2_widget = QWidget()
        row2_layout = QHBoxLayout(row2_widget)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(16)

        # 3. Horizontal Timeline Section
        timeline_card = QFrame()
        timeline_card.setObjectName("configCard")
        timeline_card_layout = QVBoxLayout(timeline_card)
        timeline_card_layout.setContentsMargins(16, 16, 16, 16)
        timeline_card_layout.setSpacing(12)

        timeline_title = QLabel("Cấu trúc timeline dự kiến")
        timeline_title.setObjectName("cardTitle")
        timeline_card_layout.addWidget(timeline_title)

        self.timeline_widget = TimelineWidget()
        timeline_card_layout.addWidget(self.timeline_widget)

        self.lbl_timeline_stats = QLabel("Tổng thời lượng ước tính: 00:00:00  |  Media nền: 0 tệp  |  Intro: Trống  |  Outro: Trống")
        self.lbl_timeline_stats.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_LIGHT}; font-weight: 500;")
        timeline_card_layout.addWidget(self.lbl_timeline_stats)
        row2_layout.addWidget(timeline_card, 3)

        # 4. Preflight checks warning list (Kiểm tra dự án)
        checks_card = QFrame()
        checks_card.setObjectName("configCard")
        checks_layout = QVBoxLayout(checks_card)
        checks_layout.setContentsMargins(16, 16, 16, 16)
        checks_layout.setSpacing(12)

        checks_title = QLabel("Kiểm tra dự án")
        checks_title.setObjectName("cardTitle")
        checks_layout.addWidget(checks_title)

        checks_scroll = QScrollArea()
        checks_scroll.setWidgetResizable(True)
        checks_scroll.setFrameShape(QFrame.Shape.NoFrame)
        checks_scroll.setMinimumHeight(150)
        
        checks_container = QWidget()
        self.ai_list = QVBoxLayout(checks_container)
        self.ai_list.setContentsMargins(0, 0, 0, 0)
        self.ai_list.setSpacing(8)
        self.ai_list.addStretch()

        checks_scroll.setWidget(checks_container)
        checks_layout.addWidget(checks_scroll)
        row2_layout.addWidget(checks_card, 2)
        container_layout.addWidget(row2_widget)

        # Row 3: Action Buttons (Horizontal layout)
        actions_card = QFrame()
        actions_card.setObjectName("configCard")
        actions_layout = QHBoxLayout(actions_card)
        actions_layout.setContentsMargins(16, 16, 16, 16)
        actions_layout.setSpacing(16)

        self.btn_build_draft = QPushButton("Dựng draft\nTạo dự án CapCut nháp để kiểm tra")
        self.btn_build_draft.setIcon(get_svg_icon("film", color=COLOR_TEAL, size=18))
        self.btn_build_draft.setObjectName("actionBtn")
        self.btn_build_draft.setCursor(Qt.PointingHandCursor)
        self.btn_build_draft.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 242, 254, 0.08);
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 10px;
                color: {COLOR_TEAL};
                padding: 20px 16px;
                font-size: 13px;
                font-weight: bold;
                text-align: center;
                line-height: 1.4;
            }}
            QPushButton:hover {{
                background-color: {COLOR_TEAL};
                color: {COLOR_TEXT_BLACK};
                border-color: {COLOR_TEAL};
            }}
        """)

        self.btn_batch_build = QPushButton("Dựng hàng loạt\nXếp hàng nhiều dự án để tạo tự động")
        self.btn_batch_build.setIcon(get_svg_icon("layers", color=COLOR_TEXT_WHITE, size=18))
        self.btn_batch_build.setObjectName("actionBtn")
        self.btn_batch_build.setCursor(Qt.PointingHandCursor)
        self.btn_batch_build.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 10px;
                color: {COLOR_TEXT_WHITE};
                padding: 20px 16px;
                font-size: 13px;
                font-weight: bold;
                text-align: center;
                line-height: 1.4;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.08);
                border-color: {COLOR_TEAL};
            }}
        """)
        
        self.btn_repair_draft = QPushButton("Sửa chữa draft\nChạy bác sĩ kiểm tra và sửa tài nguyên lỗi")
        self.btn_repair_draft.setIcon(get_svg_icon("stethoscope", color=COLOR_TEXT_WHITE, size=18))
        self.btn_repair_draft.setObjectName("actionBtn")
        self.btn_repair_draft.setCursor(Qt.PointingHandCursor)
        self.btn_repair_draft.setStyleSheet(self.btn_batch_build.styleSheet())

        self.btn_open_capcut = QPushButton("Mở CapCut PC\nKhởi động phần mềm CapCut PC tức thì")
        self.btn_open_capcut.setIcon(get_svg_icon("rocket", color="#00F2FE", size=18))
        self.btn_open_capcut.setObjectName("actionBtn")
        self.btn_open_capcut.setCursor(Qt.PointingHandCursor)
        self.btn_open_capcut.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 242, 254, 0.12);
                border: 1px solid #00F2FE;
                border-radius: 10px;
                color: #00F2FE;
                padding: 20px 16px;
                font-size: 13px;
                font-weight: bold;
                text-align: center;
                line-height: 1.4;
            }}
            QPushButton:hover {{
                background-color: #00F2FE;
                color: #000000;
                border-color: #00F2FE;
            }}
        """)

        self.btn_build_draft.clicked.connect(self.build_draft_requested.emit)
        self.btn_batch_build.clicked.connect(self.build_center_requested.emit)
        self.btn_repair_draft.clicked.connect(self.repair_draft_requested.emit)
        self.btn_open_capcut.clicked.connect(self._on_open_capcut_click)

        actions_layout.addWidget(self.btn_build_draft, 1)
        actions_layout.addWidget(self.btn_batch_build, 1)
        actions_layout.addWidget(self.btn_repair_draft, 1)
        actions_layout.addWidget(self.btn_open_capcut, 1)
        container_layout.addWidget(actions_card)

        # Row 4: Activity Log Console (Nhật ký sản xuất)
        log_card = QFrame()
        log_card.setObjectName("configCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 16, 16, 16)
        log_layout.setSpacing(12)

        log_header_layout = QHBoxLayout()
        log_title = QLabel("Nhật ký sản xuất (Live Logs)")
        log_title.setObjectName("cardTitle")
        log_header_layout.addWidget(log_title)

        self.btn_copy_log = QPushButton(" Sao chép log")
        self.btn_copy_log.setCursor(Qt.PointingHandCursor)
        self.btn_copy_log.setIcon(get_svg_icon("copy", color="#00F2FE", size=12))
        self.btn_copy_log.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 242, 254, 0.05);
                border: 1px solid rgba(0, 242, 254, 0.2);
                border-radius: 4px;
                color: #00F2FE;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #00F2FE;
                color: #000000;
            }}
        """)
        self.btn_copy_log.clicked.connect(self._copy_log_to_clipboard)
        log_header_layout.addWidget(self.btn_copy_log, 0, Qt.AlignRight)

        self.btn_clear_log = QPushButton("Xóa nhật ký")
        self.btn_clear_log.setCursor(Qt.PointingHandCursor)
        self.btn_clear_log.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: {COLOR_TEXT_LIGHT};
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(239, 68, 68, 0.1);
                border-color: {COLOR_ERROR};
                color: {COLOR_TEXT_WHITE};
            }}
        """)
        self.btn_clear_log.clicked.connect(self.clear_logs)
        log_header_layout.addWidget(self.btn_clear_log, 0, Qt.AlignRight)
        log_layout.addLayout(log_header_layout)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumBlockCount(1000)
        self.log_console.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLOR_BG_CONSOLE};
                color: {COLOR_TEXT_CONSOLE};
                font-family: "Consolas", "Courier New", monospace;
                font-size: 11px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        self.log_console.setMinimumHeight(150)
        log_layout.addWidget(self.log_console)

        container_layout.addWidget(log_card)

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _create_field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _create_kpi_card(self, title: str, val_lbl: QLabel) -> QFrame:
        card = QFrame()
        card.setObjectName("kpiCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        
        lbl_title = QLabel(title)
        lbl_title.setObjectName("fieldLabel")
        lbl_title.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_SECONDARY}; font-weight: bold; text-transform: uppercase;")
        
        val_lbl.setObjectName("stepName")
        val_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {COLOR_TEXT_WHITE};")
        
        lay.addWidget(lbl_title)
        lay.addWidget(val_lbl)
        return card

    def _update_badge(self, label: QLabel, text: str, style_type: str) -> None:
        label.setText(text)
        if style_type == "green":
            label.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.1);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.2);
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        elif style_type == "amber":
            label.setStyleSheet("""
                background-color: rgba(245, 158, 11, 0.1);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.2);
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        elif style_type == "red":
            label.setStyleSheet("""
                background-color: rgba(239, 68, 68, 0.1);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.2);
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        elif style_type == "sky":
            label.setStyleSheet("""
                background-color: rgba(14, 165, 233, 0.1);
                color: #38bdf8;
                border: 1px solid rgba(14, 165, 233, 0.2);
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)

    def _update_timeline(self) -> None:
        self.timeline_widget.set_data(
            self.intro_ok, self.outro_ok, self.media_count, self.timeline_estimate
        )
        intro_status = "Sẵn sàng" if self.intro_ok else "Trống"
        outro_status = "Sẵn sàng" if self.outro_ok else "Trống"
        self.lbl_timeline_stats.setText(
            f"Tổng thời lượng ước tính: {self.timeline_estimate}  |  "
            f"Media nền: {self.media_count} tệp  |  "
            f"Intro: {intro_status}  |  "
            f"Outro: {outro_status}"
        )

    def add_ai_item(self, text: str, severity: str) -> None:
        row = QFrame()
        row.setObjectName("stepRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 8, 10, 8)
        row_layout.setSpacing(10)

        icon = QLabel()
        icon.setFixedSize(16, 16)
        if severity == "error":
            icon.setPixmap(get_svg_icon("x", color=COLOR_ERROR, size=16).pixmap(16, 16))
            row.setProperty("state", "error")
        elif severity in ("warn", "warning"):
            icon.setPixmap(get_svg_icon("alert", color="#fbbf24", size=16).pixmap(16, 16))
            row.setProperty("state", "running")
        else:
            icon.setPixmap(get_svg_icon("check", color=COLOR_TEAL, size=16).pixmap(16, 16))
            row.setProperty("state", "done")

        lbl = QLabel(text)
        lbl.setObjectName("stepName")
        lbl.setWordWrap(True)

        row_layout.addWidget(icon)
        row_layout.addWidget(lbl, 1)
        self.ai_list.addWidget(row)

    def update_project_summary(self, name: str, canvas: str, preset: str, fps: str, path: str, last_compiled: str, voice_duration: str, timeline_estimate: str) -> None:
        self.lbl_project_name.setText(name)
        self.lbl_canvas.setText(canvas)
        self.lbl_preset.setText(preset)
        self.lbl_fps.setText(fps)
        self.lbl_path.setText(path)
        self.lbl_last_compiled.setText(last_compiled)
        self.lbl_voice_duration.setText(voice_duration)
        self.lbl_timeline_estimate.setText(timeline_estimate)
        
        self.timeline_estimate = timeline_estimate
        self._update_timeline()

    def update_resource_readiness(self, voice_ok: bool, srt_lines: int, media_count: int, bgm_ok: bool, logo_ok: bool, anim_ok: bool, intro_ok: bool, outro_ok: bool) -> None:
        # Giọng đọc
        if voice_ok:
            self._update_badge(self.lbl_status_voice, "SẴN SÀNG", "green")
        else:
            self._update_badge(self.lbl_status_voice, "THIẾU", "red")

        # Phụ đề (SRT)
        if srt_lines > 0:
            self._update_badge(self.lbl_status_srt, f"{srt_lines} DÒNG", "green")
        else:
            self._update_badge(self.lbl_status_srt, "TUỲ CHỌN", "amber")

        # Media nền
        if media_count > 0:
            self._update_badge(self.lbl_status_media, f"{media_count} TỆP", "green")
        else:
            self._update_badge(self.lbl_status_media, "THIẾU", "red")

        # Nhạc nền (BGM)
        if bgm_ok:
            self._update_badge(self.lbl_status_bgm, "SẴN SÀNG", "green")
        else:
            self._update_badge(self.lbl_status_bgm, "TUỲ CHỌN", "amber")

        # Bộ logo
        if logo_ok:
            self._update_badge(self.lbl_status_logo, "SẴN SÀNG", "green")
        else:
            self._update_badge(self.lbl_status_logo, "TUỲ CHỌN", "amber")

        # Hiệu ứng đăng ký
        if anim_ok:
            self._update_badge(self.lbl_status_anim, "SẴN SÀNG", "green")
        else:
            self._update_badge(self.lbl_status_anim, "TUỲ CHỌN", "amber")

        # Clip intro
        if intro_ok:
            self._update_badge(self.lbl_status_intro, "SẴN SÀNG", "green")
        else:
            self._update_badge(self.lbl_status_intro, "TUỲ CHỌN", "amber")

        # Clip outro
        if outro_ok:
            self._update_badge(self.lbl_status_outro, "SẴN SÀNG", "green")
        else:
            self._update_badge(self.lbl_status_outro, "TUỲ CHỌN", "amber")

        self.intro_ok = intro_ok
        self.outro_ok = outro_ok
        self.media_count = media_count
        self._update_timeline()

    def update_preflight_issues(self, issues: list) -> None:
        # Clear existing items
        while self.ai_list.count():
            item = self.ai_list.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            
        for issue in issues:
            self.add_ai_item(issue.message, issue.severity)
            
        self.ai_list.addStretch()

    def append_log(self, text: str) -> None:
        self.log_console.appendPlainText(text)
        self.log_console.ensureCursorVisible()

    @Slot()
    def _copy_log_to_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication
        text = self.log_console.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            try:
                from app.widgets.toast import ToastManager
                ToastManager.get_instance().show(self, "Đã sao chép", "Toàn bộ nhật ký đã được chép vào bộ nhớ tạm.", level="success")
            except Exception:
                pass

    def _on_open_capcut_click(self) -> None:
        try:
            import os
            import subprocess
            from draft_doctor import find_capcut_executable
            capcut_exe = find_capcut_executable()
            if capcut_exe and capcut_exe.exists():
                subprocess.Popen([str(capcut_exe)])
                self.append_log(f"[HỆ THỐNG] Đã khởi động CapCut PC: {capcut_exe}")
            else:
                draft_path = self.lbl_path.text().strip()
                if draft_path and os.path.exists(draft_path):
                    os.startfile(draft_path)
                    self.append_log(f"[HỆ THỐNG] Đã mở thư mục dự án CapCut: {draft_path}")
                else:
                    self.append_log("[CẢNH BÁO] Không tìm thấy CapCut.exe hoặc thư mục dự án chưa tồn tại.")
        except Exception as e:
            self.append_log(f"[LỖI] Không thể mở CapCut PC: {e}")

    def clear_logs(self) -> None:
        self.log_console.clear()
