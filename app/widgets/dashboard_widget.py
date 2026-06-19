# app/widgets/dashboard_widget.py
from PySide6.QtCore import Qt, Signal
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

class DashboardWidget(QWidget):
    build_center_requested = Signal()
    repair_draft_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
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
        grid.setSpacing(12)

        # Add stats fields
        self.lbl_project_name = QLabel("Campaign_Beta_2024")
        self.lbl_project_name.setObjectName("stepName")
        self.lbl_project_name.setWordWrap(True)
        
        self.lbl_canvas = QLabel("9:16 Dọc")
        self.lbl_canvas.setObjectName("stepName")
        self.lbl_canvas.setWordWrap(True)
        
        self.lbl_preset = QLabel("TikTok_High_Retention")
        self.lbl_preset.setObjectName("stepName")
        self.lbl_preset.setWordWrap(True)
        
        self.lbl_fps = QLabel("60.00")
        self.lbl_fps.setObjectName("stepName")
        self.lbl_fps.setWordWrap(True)
        
        self.lbl_path = QLabel("C:/CapCut/Drafts/...")
        self.lbl_path.setObjectName("stepName")
        self.lbl_path.setWordWrap(True)
        
        self.lbl_last_compiled = QLabel("Chưa biên dịch")
        self.lbl_last_compiled.setObjectName("stepName")
        self.lbl_last_compiled.setWordWrap(True)
        
        self.lbl_voice_duration = QLabel("00:58:12")
        self.lbl_voice_duration.setObjectName("stepName")
        self.lbl_voice_duration.setWordWrap(True)
        
        self.lbl_timeline_estimate = QLabel("00:58:42")
        self.lbl_timeline_estimate.setObjectName("stepName")
        self.lbl_timeline_estimate.setWordWrap(True)

        grid.addWidget(self._create_field_label("Tên dự án:"), 0, 0)
        grid.addWidget(self.lbl_project_name, 0, 1)
        grid.addWidget(self._create_field_label("Tỉ lệ xuất:"), 0, 2)
        grid.addWidget(self.lbl_canvas, 0, 3)

        grid.addWidget(self._create_field_label("Preset đang dùng:"), 1, 0)
        grid.addWidget(self.lbl_preset, 1, 1)
        grid.addWidget(self._create_field_label("FPS mục tiêu:"), 1, 2)
        grid.addWidget(self.lbl_fps, 1, 3)

        grid.addWidget(self._create_field_label("Đường dẫn nháp:"), 2, 0)
        grid.addWidget(self.lbl_path, 2, 1)
        grid.addWidget(self._create_field_label("Biên dịch lần cuối:"), 2, 2)
        grid.addWidget(self.lbl_last_compiled, 2, 3)

        grid.addWidget(self._create_field_label("Thời lượng giọng:"), 3, 0)
        grid.addWidget(self.lbl_voice_duration, 3, 1)
        grid.addWidget(self._create_field_label("Ước lượng timeline:"), 3, 2)
        grid.addWidget(self.lbl_timeline_estimate, 3, 3)

        sum_layout.addLayout(grid)

        # Redirection buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        
        self.btn_batch_build = QPushButton("Dựng hàng loạt\nXếp hàng 50+ dự án để tạo")
        self.btn_batch_build.setObjectName("actionBtn")
        self.btn_batch_build.setCursor(Qt.PointingHandCursor)
        self.btn_batch_build.clicked.connect(self.build_center_requested.emit)
        
        self.btn_repair_draft = QPushButton("Sửa chữa draft\nChạy bác sĩ draft trên tài nguyên lỗi")
        self.btn_repair_draft.setObjectName("actionBtn")
        self.btn_repair_draft.setCursor(Qt.PointingHandCursor)
        self.btn_repair_draft.clicked.connect(self.repair_draft_requested.emit)

        # Set specific styling for action buttons
        self.btn_batch_build.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                color: #ffffff;
                padding: 12px 16px;
                text-align: left;
                font-weight: bold;
                line-height: 1.4;
            }
            QPushButton:hover {
                background-color: rgba(139, 92, 246, 0.1);
                border-color: #8b5cf6;
            }
        """)
        self.btn_repair_draft.setStyleSheet(self.btn_batch_build.styleSheet())
        
        actions_layout.addWidget(self.btn_batch_build, 1)
        actions_layout.addWidget(self.btn_repair_draft, 1)
        sum_layout.addLayout(actions_layout)

        container_layout.addWidget(summary_card)

        # 2. Resource Readiness Section
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

        # We will create 8 resource cards:
        # Giọng đọc, Phụ đề (SRT), Media nền, Nhạc nền, Bộ logo, Hiệu ứng đăng ký, Clip intro, Clip outro
        self.lbl_status_voice = QLabel()
        self.lbl_status_srt = QLabel()
        self.lbl_status_media = QLabel()
        self.lbl_status_bgm = QLabel()
        self.lbl_status_logo = QLabel()
        self.lbl_status_anim = QLabel()
        self.lbl_status_intro = QLabel()
        self.lbl_status_outro = QLabel()

        resources = [
            ("🎤  Giọng đọc", self.lbl_status_voice),
            ("📝  Phụ đề (SRT)", self.lbl_status_srt),
            ("🖼️  Media nền", self.lbl_status_media),
            ("🎵  Nhạc nền", self.lbl_status_bgm),
            ("🎬  Bộ logo", self.lbl_status_logo),
            ("✨  Hiệu ứng đăng ký", self.lbl_status_anim),
            ("🎥  Clip intro", self.lbl_status_intro),
            ("🎞️  Clip outro", self.lbl_status_outro),
        ]

        for i, (name, lbl) in enumerate(resources):
            row = i // 4
            col = i % 4
            card = QFrame()
            card.setObjectName("resourceCard")
            card.setStyleSheet("""
                QFrame#resourceCard {
                    background-color: rgba(255, 255, 255, 0.02);
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    border-radius: 8px;
                    padding: 8px 12px;
                }
                QFrame#resourceCard:hover {
                    background-color: rgba(255, 255, 255, 0.04);
                    border-color: rgba(255, 255, 255, 0.12);
                }
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(4, 4, 4, 4)
            
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet("font-size: 12px; color: #cbd5e1; font-weight: 500;")
            
            lbl.setAlignment(Qt.AlignCenter)
            self._update_badge(lbl, "KIỂM TRA", "sky")

            card_layout.addWidget(lbl_name, 1)
            card_layout.addWidget(lbl)
            readiness_grid.addWidget(card, row, col)

        readiness_layout.addLayout(readiness_grid)
        container_layout.addWidget(readiness_card)

        # 3. AI Checker Panel
        ai_card = QFrame()
        ai_card.setObjectName("configCard")
        ai_layout = QVBoxLayout(ai_card)
        ai_layout.setContentsMargins(16, 16, 16, 16)
        ai_layout.setSpacing(12)

        ai_title = QLabel("Kiểm tra AI")
        ai_title.setObjectName("cardTitle")
        ai_layout.addWidget(ai_title)

        self.ai_list = QVBoxLayout()
        self.ai_list.setSpacing(8)

        ai_layout.addLayout(self.ai_list)
        container_layout.addWidget(ai_card)

        # 4. Activity Log Console
        log_card = QFrame()
        log_card.setObjectName("configCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 16, 16, 16)
        log_layout.setSpacing(12)

        log_header_layout = QHBoxLayout()
        log_title = QLabel("Nhật ký hoạt động (Live Logs)")
        log_title.setObjectName("cardTitle")
        log_header_layout.addWidget(log_title)

        self.btn_clear_log = QPushButton("Xóa nhật ký")
        self.btn_clear_log.setCursor(Qt.PointingHandCursor)
        self.btn_clear_log.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: #cbd5e1;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.1);
                border-color: #ef4444;
                color: #ffffff;
            }
        """)
        self.btn_clear_log.clicked.connect(self.clear_logs)
        log_header_layout.addWidget(self.btn_clear_log, 0, Qt.AlignRight)
        log_layout.addLayout(log_header_layout)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumBlockCount(1000)
        self.log_console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0f172a;
                color: #e2e8f0;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 11px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 8px;
            }
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

    def add_ai_item(self, text: str, severity: str) -> None:
        row = QFrame()
        row.setObjectName("stepRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 8, 10, 8)
        row_layout.setSpacing(10)

        icon = QLabel()
        icon.setFixedSize(16, 16)
        if severity == "error":
            icon.setText("❌")
            row.setProperty("state", "error")
        elif severity == "warn" or severity == "warning":
            icon.setText("⚠️")
            row.setProperty("state", "running")
        else:
            icon.setText("✅")
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

    def update_preflight_issues(self, issues: list) -> None:
        # Clear existing items
        while self.ai_list.count():
            item = self.ai_list.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            
        for issue in issues:
            self.add_ai_item(issue.message, issue.severity)

    def append_log(self, text: str) -> None:
        self.log_console.appendPlainText(text)
        self.log_console.ensureCursorVisible()

    def clear_logs(self) -> None:
        self.log_console.clear()
