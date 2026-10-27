# app/widgets/history_widget.py
import json
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Slot, Qt
from PySide6.QtGui import QColor, QBrush
from app.theme import (
    COLOR_TEAL, COLOR_CARD_BG, COLOR_CARD_BORDER, COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_DARK_ZINC, COLOR_SIDEBAR_BG, COLOR_BG_CONSOLE, COLOR_TEXT_CONSOLE,
    COLOR_TEXT_WHITE, COLOR_TEXT_LIGHT, COLOR_TEXT_BLACK,
    QCOLOR_TEAL, QCOLOR_DARK_ZINC, QCOLOR_CARD_BG, QCOLOR_CARD_BORDER,
    QCOLOR_TEXT_PRIMARY, QCOLOR_TEXT_SECONDARY, QCOLOR_TEXT_MUTED,
    QCOLOR_ERROR, QCOLOR_SUCCESS, QCOLOR_WARNING, QCOLOR_TEXT_LIGHT
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QComboBox,
    QDoubleSpinBox,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QSplitter,
    QPlainTextEdit,
    QLineEdit,
    QFileDialog,
    QTabWidget,
    QDialog,
    QTextBrowser,
    QMessageBox,
)
from app.widgets.setup_widget import DropLineEdit

class LogViewerDialog(QDialog):
    def __init__(self, job_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Chi tiết tác vụ: {job_data.get('project_name', 'Không rõ')}")
        self.resize(600, 500)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_DARK_ZINC};
                color: {COLOR_TEXT_PRIMARY};
            }}
            QLabel {{
                color: {COLOR_TEXT_PRIMARY};
                font-weight: bold;
            }}
            QTextBrowser {{
                background-color: {COLOR_SIDEBAR_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 6px;
                color: {COLOR_TEXT_LIGHT};
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 11px;
            }}
            QPushButton {{
                background-color: {COLOR_TEAL};
                color: {COLOR_TEXT_BLACK};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #00F2FE;
                opacity: 0.9;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Details label
        started_at = job_data.get("started_at", "N/A")
        finished_at = job_data.get("finished_at", "N/A")
        status = job_data.get("status", "unknown").upper()
        job_type = job_data.get("job_type", "unknown").upper()
        
        info_lbl = QLabel(
            f"Loại tác vụ: <span style='color:{COLOR_TEAL};'>{job_type}</span><br>"
            f"Trạng thái: <span style='color:{COLOR_TEXT_LIGHT};'>{status}</span><br>"
            f"Thời gian bắt đầu: <span style='color:{COLOR_TEXT_LIGHT};'>{started_at}</span><br>"
            f"Thời gian hoàn thành: <span style='color:{COLOR_TEXT_LIGHT};'>{finished_at}</span>"
        )
        layout.addWidget(info_lbl)
        
        # Inputs/config display
        layout.addWidget(QLabel("Cấu hình / Dữ liệu đầu vào:"))
        self.browser = QTextBrowser()
        pretty_inputs = json.dumps(job_data.get("inputs", {}), indent=2, ensure_ascii=False)
        self.browser.setPlainText(pretty_inputs)
        layout.addWidget(self.browser, 1)
        
        # Error display if failed
        err_msg = job_data.get("error") or job_data.get("error_message") or ""
        if err_msg:
            layout.addWidget(QLabel("Chi tiết lỗi:"))
            self.err_browser = QTextBrowser()
            self.err_browser.setStyleSheet(f"color: {COLOR_ERROR}; background-color: {COLOR_SIDEBAR_BG}; border: 1px solid {COLOR_CARD_BORDER};")
            self.err_browser.setPlainText(err_msg)
            self.err_browser.setFixedHeight(120)
            layout.addWidget(self.err_browser)
            
        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


class HistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_records = []
        self._build_ui()
        self.project_combo.currentTextChanged.connect(self.run_diagnose)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Tab Widget to separate Task History from Draft Doctor
        self.tabs = QTabWidget()
        self.tabs.setObjectName("historyTabs")
        
        # ==========================================
        # TAB 1: TASK HISTORY (Lịch sử tác vụ)
        # ==========================================
        tab_history = QWidget()
        tab_history_layout = QVBoxLayout(tab_history)
        tab_history_layout.setContentsMargins(16, 16, 16, 16)
        tab_history_layout.setSpacing(12)
        
        # Tab Header
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 4)
        header_layout.setSpacing(4)
        
        lbl_title = QLabel("Lịch sử tác vụ")
        lbl_title.setObjectName("pageTitle")
        lbl_subtitle = QLabel("Tra cứu trạng thái, thời gian chạy, và dữ liệu cấu hình đầu vào của các tiến trình dựng.")
        lbl_subtitle.setObjectName("pageSubtitle")
        
        header_layout.addWidget(lbl_title)
        header_layout.addWidget(lbl_subtitle)
        tab_history_layout.addWidget(header_widget)
        
        history_card = QFrame()
        history_card.setObjectName("queueCard")
        history_card_layout = QVBoxLayout(history_card)
        history_card_layout.setContentsMargins(16, 16, 16, 16)
        history_card_layout.setSpacing(10)
 
        header_row = QHBoxLayout()
        left_title = QLabel("Lịch Sử Tác Vụ (Build History)")
        left_title.setObjectName("cardTitle")
        header_row.addWidget(left_title)
        header_row.addStretch()
        
        btn_refresh_history = QPushButton("Làm Mới")
        btn_refresh_history.setObjectName("btnBrowse")
        btn_refresh_history.clicked.connect(self.refresh_history_table)
        header_row.addWidget(btn_refresh_history)
        history_card_layout.addLayout(header_row)
 
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(["Thời gian", "Tác vụ", "Dự án", "Trạng thái", "Thời lượng", "Thao tác"])
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setObjectName("historyTable")
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setShowGrid(False)
        self.history_table.setWordWrap(False)
        self.history_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        
        header = self.history_table.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(38)
        
        self.history_table.setColumnWidth(0, 110)
        self.history_table.setColumnWidth(1, 90)
        self.history_table.setColumnWidth(3, 85)
        self.history_table.setColumnWidth(4, 90)
        
        history_card_layout.addWidget(self.history_table)
        tab_history_layout.addWidget(history_card)
        self.tabs.addTab(tab_history, "Lịch Sử Tác Vụ")

        # ==========================================
        # TAB 2: DRAFT DOCTOR & BACKUPS
        # ==========================================
        tab_doctor = QWidget()
        tab_doctor_layout = QVBoxLayout(tab_doctor)
        tab_doctor_layout.setContentsMargins(16, 16, 16, 16)
        tab_doctor_layout.setSpacing(12)
        
        # Tab Header
        doc_header_widget = QWidget()
        doc_header_layout = QVBoxLayout(doc_header_widget)
        doc_header_layout.setContentsMargins(0, 0, 0, 4)
        doc_header_layout.setSpacing(4)
        
        lbl_doc_title = QLabel("Bác sĩ sửa lỗi (Draft Doctor)")
        lbl_doc_title.setObjectName("pageTitle")
        lbl_doc_subtitle = QLabel("Quản lý bản sao lưu khôi phục dự án nháp và chạy chẩn đoán, tự động relink tài nguyên lỗi.")
        lbl_doc_subtitle.setObjectName("pageSubtitle")
        
        doc_header_layout.addWidget(lbl_doc_title)
        doc_header_layout.addWidget(lbl_doc_subtitle)
        tab_doctor_layout.addWidget(doc_header_widget)
        
        doctor_splitter = QSplitter(Qt.Orientation.Horizontal)
        doctor_splitter.setObjectName("doctorSplitter")
 
        # Left side: Backup Manager
        backup_card = QFrame()
        backup_card.setObjectName("backupCard")
        back_lay = QVBoxLayout(backup_card)
        back_lay.setContentsMargins(16, 16, 16, 16)
        back_lay.setSpacing(10)
        
        back_title = QLabel("Quản Lý Sao Lưu & Hoàn Tác")
        back_title.setObjectName("cardTitle")
        back_lay.addWidget(back_title)
        
        # Hidden combobox to sync with gui.py operations
        self.backup_combo = QComboBox()
        self.backup_combo.setVisible(False)
        back_lay.addWidget(self.backup_combo)

        # Hidden restore button (triggered programmatically)
        self.btn_restore_backup = QPushButton("KHÔI PHỤC")
        self.btn_restore_backup.setVisible(False)
        back_lay.addWidget(self.btn_restore_backup)
        
        # Retention Policy Controls
        retention_row = QHBoxLayout()
        retention_row.addWidget(self._create_field_label("Giữ lại backup:"))
        
        self.backup_keep_days = QDoubleSpinBox()
        self.backup_keep_days.setRange(1, 365)
        self.backup_keep_days.setValue(7)
        self.backup_keep_days.setSingleStep(1)
        self.backup_keep_days.setDecimals(0)
        self.backup_keep_days.setFixedWidth(70)
        retention_row.addWidget(self.backup_keep_days)
        retention_row.addWidget(QLabel("ngày"))
        
        retention_row.addStretch()
        
        self.btn_clean_backups = QPushButton("Dọn dẹp")
        self.btn_clean_backups.setObjectName("btnBrowse")
        retention_row.addWidget(self.btn_clean_backups)
        
        back_lay.addLayout(retention_row)
        
        # Backup records list table
        self.backups_table = QTableWidget()
        self.backups_table.setColumnCount(3)
        self.backups_table.setHorizontalHeaderLabels(["Thời gian", "Mô tả", "Thao tác"])
        self.backups_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.backups_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.backups_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.backups_table.setObjectName("historyTable")
        self.backups_table.setAlternatingRowColors(True)
        self.backups_table.setShowGrid(False)
        self.backups_table.verticalHeader().setVisible(False)
        self.backups_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.backups_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.backups_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.backups_table.setColumnWidth(0, 110)
        
        back_lay.addWidget(self.backups_table)
        
        # Connect combobox model changes to table synchronizer
        self.backup_combo.model().rowsInserted.connect(self.sync_backups_table)
        self.backup_combo.model().rowsRemoved.connect(self.sync_backups_table)
        self.backup_combo.model().modelReset.connect(self.sync_backups_table)
        
        doctor_splitter.addWidget(backup_card)

        # Right side: Draft Doctor Diagnostics Panel
        doctor_card = QFrame()
        doctor_card.setObjectName("doctorCard")
        doc_lay = QVBoxLayout(doctor_card)
        doc_lay.setContentsMargins(16, 16, 16, 16)
        doc_lay.setSpacing(10)

        doctor_title = QLabel("Bác Sĩ Sửa Lỗi (Draft Doctor)")
        doctor_title.setObjectName("cardTitle")
        doc_lay.addWidget(doctor_title)

        # Project Selector Row
        proj_row = QHBoxLayout()
        proj_row.addWidget(self._create_field_label("Dự án mục tiêu:"))
        self.project_combo = QComboBox()
        self.project_combo.setPlaceholderText("Vui lòng nhập Draft Root để quét các dự án...")
        proj_row.addWidget(self.project_combo, 1)
        
        self.btn_refresh_projects = QPushButton("Quét lại")
        self.btn_refresh_projects.setObjectName("btnBrowse")
        proj_row.addWidget(self.btn_refresh_projects)
        doc_lay.addLayout(proj_row)

        # Relink directory input
        relink_row = QHBoxLayout()
        relink_row.addWidget(self._create_field_label("Thư mục Relink:"))
        self.relink_media_dir = DropLineEdit("Để trống nếu dùng Thư mục video/hình nền mặc định...")
        relink_row.addWidget(self.relink_media_dir, 1)

        self.btn_browse_relink = QPushButton("Chọn...")
        self.btn_browse_relink.setObjectName("btnBrowse")
        self.btn_browse_relink.clicked.connect(self._browse_relink_dir)
        relink_row.addWidget(self.btn_browse_relink)
        doc_lay.addLayout(relink_row)

        # Issues Table (warnings, errors) - Hide individual line edit buttons
        issues_lbl = QLabel("Danh sách cảnh báo phát hiện:")
        issues_lbl.setObjectName("fieldLabel")
        doc_lay.addWidget(issues_lbl)

        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(3)
        self.issues_table.setHorizontalHeaderLabels(["Mức độ", "Chi tiết lỗi", "Thao tác"])
        self.issues_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.issues_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.issues_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.issues_table.verticalHeader().setVisible(False)
        self.issues_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.issues_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.issues_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.issues_table.setColumnWidth(0, 90)
        self.issues_table.setFixedHeight(120)
        doc_lay.addWidget(self.issues_table)

        # Diagnostics detailed console logs output terminal
        diagnose_lbl = QLabel("Báo cáo chẩn đoán chi tiết:")
        diagnose_lbl.setObjectName("fieldLabel")
        doc_lay.addWidget(diagnose_lbl)

        self.diagnose_output = QPlainTextEdit()
        self.diagnose_output.setObjectName("logTerminal")
        self.diagnose_output.setReadOnly(True)
        self.diagnose_output.setFixedHeight(110)
        doc_lay.addWidget(self.diagnose_output)

        # Action Buttons Row
        doc_btn_row = QHBoxLayout()
        doc_btn_row.setSpacing(10)

        self.btn_diagnose = QPushButton("Chẩn Đoán Lỗi")
        self.btn_diagnose.setObjectName("btnBrowse")
        self.btn_diagnose.clicked.connect(self.run_diagnose)
        doc_btn_row.addWidget(self.btn_diagnose, 1)

        self.btn_export_diagnose = QPushButton("Xuất Báo Cáo")
        self.btn_export_diagnose.setObjectName("btnBrowse")
        self.btn_export_diagnose.clicked.connect(self.export_diagnose_report)
        doc_btn_row.addWidget(self.btn_export_diagnose, 1)

        self.btn_repair_project = QPushButton("TỰ ĐỘNG SỬA LỖI DỰ ÁN (AUTO REPAIR)")
        self.btn_repair_project.setObjectName("btnRun")
        doc_btn_row.addWidget(self.btn_repair_project, 2)

        doc_lay.addLayout(doc_btn_row)
        
        doctor_splitter.addWidget(doctor_card)
        tab_doctor_layout.addWidget(doctor_splitter)
        self.tabs.addTab(tab_doctor, "Bác Sĩ Sửa Lỗi (Draft Doctor)")

        layout.addWidget(self.tabs)

    def _create_field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        lbl.setStyleSheet("font-size: 11px;")
        return lbl

    @Slot()
    def _browse_relink_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục tìm kiếm tài nguyên mới")
        if dir_path:
            self.relink_media_dir.setText(dir_path)

    def get_draft_root(self) -> str:
        main_win = self.window()
        if main_win and hasattr(main_win, "setup_widget"):
            return main_win.setup_widget.draft_root.text().strip()
        return ""

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_history_table()
        self.run_diagnose()

    @Slot()
    def sync_backups_table(self) -> None:
        """Synchronizes the visible backups table with the hidden backup_combo model."""
        self.backups_table.blockSignals(True)
        self.backups_table.setRowCount(0)
        
        count = self.backup_combo.count()
        self.backups_table.setRowCount(count)
        
        for idx in range(count):
            display_text = self.backup_combo.itemText(idx)
            
            # E.g. "2026-06-21 14:14:42 · Bản sao lưu tự động" or similar
            parts = display_text.split(" · ")
            time_str = parts[0] if len(parts) > 0 else display_text
            note_str = parts[1] if len(parts) > 1 else "Bản sao lưu"
            
            time_item = QTableWidgetItem(time_str)
            time_item.setForeground(QBrush(QCOLOR_TEXT_PRIMARY))
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.backups_table.setItem(idx, 0, time_item)
            
            note_item = QTableWidgetItem(note_str)
            note_item.setForeground(QBrush(QColor(COLOR_TEXT_LIGHT)))
            self.backups_table.setItem(idx, 1, note_item)
            
            restore_btn = QPushButton("Khôi phục")
            restore_btn.setObjectName("btnBrowse")
            restore_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
            restore_btn.clicked.connect(lambda checked=False, index=idx: self._restore_backup_at(index))
            self.backups_table.setCellWidget(idx, 2, restore_btn)
            
        self.backups_table.blockSignals(False)

    def _restore_backup_at(self, index: int) -> None:
        self.backup_combo.setCurrentIndex(index)
        self.btn_restore_backup.click()

    def refresh_history_table(self) -> None:
        self.history_table.setRowCount(0)
        from app.history import load_job_history
        try:
            root_dir = Path(__file__).resolve().parents[2]
            rows = load_job_history(root_dir)
            self.history_records = rows
            
            self.history_table.setSortingEnabled(False)
            self.history_table.setRowCount(len(rows))
            
            status_translation = {
                "pending": "Chờ",
                "running": "Đang dựng",
                "completed": "Hoàn thành",
                "success": "Hoàn thành",
                "failed": "Lỗi",
                "error": "Lỗi",
                "cancelled": "Đã hủy"
            }
            
            status_colors = {
                "HOÀN THÀNH": COLOR_SUCCESS,
                "LỖI": COLOR_ERROR,
                "ĐÃ HỦY": COLOR_WARNING,
                "CHỜ": COLOR_WARNING,
                "ĐANG DỰNG": "#00F2FE",
                "OK": COLOR_SUCCESS,
                "C.B": COLOR_WARNING,
                "pending": COLOR_WARNING,
                "running": "#00F2FE"
            }

            for idx, job_data in enumerate(rows):
                job_type = job_data.get("job_type") or "unknown"
                status = job_data.get("status") or "unknown"
                started_at = job_data.get("started_at") or "N/A"
                finished_at = job_data.get("finished_at") or "N/A"
                err_msg = job_data.get("error") or job_data.get("error_message") or ""
                
                # Determine project name
                proj_name = job_data.get("project_name") or job_data.get("inputs", {}).get("project_name") or job_data.get("inputs", {}).get("draft_name")
                if not proj_name:
                    if job_type == "download":
                        proj_name = "Download"
                    elif job_type == "apply_preset":
                        proj_name = "Keyframe Preset"
                    else:
                        proj_name = f"Tác vụ {job_type.upper()}"
                
                # Use QColor constants directly or parse to avoid hardcoding
                row_bg = QColor(31, 24, 38) if status in {"failed", "error"} or err_msg else QColor(COLOR_BG_CONSOLE if idx % 2 == 0 else COLOR_CARD_BG)
                normal_fg = QBrush(QCOLOR_TEXT_PRIMARY)
                muted_fg = QBrush(QCOLOR_TEXT_LIGHT)

                # 1. Started At
                started_text = started_at
                if len(started_at) > 11 and " " in started_at:
                    started_text = started_at[11:16] + " " + started_at[8:10] + "/" + started_at[5:7]
                elif len(started_at) > 11 and "_" in started_at:
                    try:
                        dt = datetime.strptime(started_at, "%Y%m%d_%H%M%S")
                        started_text = dt.strftime("%H:%M %d/%m")
                    except Exception:
                        pass
                started_item = QTableWidgetItem(started_text)
                started_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                started_item.setToolTip(started_at)
                started_item.setForeground(muted_fg)
                self.history_table.setItem(idx, 0, started_item)
                
                # 2. Type/Tác vụ
                type_display_map = {
                    "pipeline": "Pipeline",
                    "download": "Tải media",
                    "apply_preset": "Preset Keyframe",
                    "repair_project": "Doctor Repair"
                }
                type_display = type_display_map.get(job_type, job_type.capitalize())
                type_item = QTableWidgetItem(type_display)
                type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                type_item.setForeground(muted_fg)
                self.history_table.setItem(idx, 1, type_item)
                
                # 3. Project Name
                proj_item = QTableWidgetItem(proj_name)
                proj_item.setToolTip(proj_name)
                proj_item.setForeground(normal_fg)
                self.history_table.setItem(idx, 2, proj_item)
                
                # 4. Status Badge
                badge_text = status_translation.get(status, status).upper()
                badge_item = QTableWidgetItem(badge_text)
                badge_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                badge_item.setForeground(QBrush(QColor(status_colors.get(badge_text, "#cbd5e1"))))
                font = badge_item.font()
                font.setBold(True)
                badge_item.setFont(font)
                self.history_table.setItem(idx, 3, badge_item)

                # 5. Duration
                duration_str = "--"
                if started_at != "N/A" and finished_at != "N/A":
                    try:
                        fmt = "%Y-%m-%d %H:%M:%S"
                        start_dt = datetime.strptime(started_at, fmt)
                        finish_dt = datetime.strptime(finished_at, fmt)
                        duration_sec = int((finish_dt - start_dt).total_seconds())
                        duration_str = f"{duration_sec}s"
                    except Exception:
                        pass
                duration_item = QTableWidgetItem(duration_str)
                duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                duration_item.setForeground(muted_fg)
                self.history_table.setItem(idx, 4, duration_item)
                
                # 6. Action buttons widget
                btn_widget = QWidget()
                btn_widget.setStyleSheet("background: transparent;")
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(4, 2, 4, 2)
                btn_layout.setSpacing(6)
                
                view_log_btn = QPushButton("Xem log")
                view_log_btn.setCursor(Qt.PointingHandCursor)
                view_log_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLOR_CARD_BORDER};
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        color: {COLOR_TEXT_PRIMARY};
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 11px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: rgba(255, 255, 255, 0.15);
                        color: #ffffff;
                    }}
                """)
                view_log_btn.clicked.connect(lambda checked=False, r=job_data: self._show_job_log(r))
                btn_layout.addWidget(view_log_btn)
                
                reload_btn = QPushButton("Tải lại")
                reload_btn.setCursor(Qt.PointingHandCursor)
                reload_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(0, 242, 254, 0.15);
                        border: 1px solid #00F2FE;
                        color: #00F2FE;
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 11px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #00F2FE;
                        color: #000000;
                    }
                """)
                reload_btn.clicked.connect(lambda checked=False, r=job_data: self._reload_job_config(r))
                btn_layout.addWidget(reload_btn)
                
                rerun_btn = QPushButton("Chạy lại")
                rerun_btn.setCursor(Qt.PointingHandCursor)
                rerun_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00F2FE, stop:1 #7F00FF);
                        border: none;
                        color: #ffffff;
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 11px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        opacity: 0.9;
                    }
                """)
                rerun_btn.clicked.connect(lambda checked=False, r=job_data: self._rerun_job(r))
                btn_layout.addWidget(rerun_btn)
                
                btn_layout.addStretch()
                self.history_table.setCellWidget(idx, 5, btn_widget)

                for col in range(self.history_table.columnCount()):
                    item = self.history_table.item(idx, col)
                    if item:
                        item.setBackground(QBrush(row_bg))
                self.history_table.setRowHeight(idx, 38)
                
            self.history_table.setSortingEnabled(True)
        except Exception as e:
            print(f"Error loading history table: {e}")

    def _show_job_log(self, job_data: dict) -> None:
        dialog = LogViewerDialog(job_data, self)
        dialog.exec()

    def _reload_job_config(self, job_data: dict) -> None:
        inputs = job_data.get("inputs")
        if not inputs:
            QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy thông tin cấu hình của tác vụ này.")
            return
            
        self.load_job_inputs(inputs)
        QMessageBox.information(
            self, "Đã tải cấu hình",
            f"Đã tải cấu hình của dự án '{job_data.get('project_name')}' vào tab Thiết lập."
        )
        main_win = self.window()
        if main_win and hasattr(main_win, "_switch_to_page"):
            main_win._switch_to_page("project-setup")

    def _rerun_job(self, job_data: dict) -> None:
        inputs = job_data.get("inputs")
        if not inputs:
            QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy thông tin cấu hình của tác vụ này.")
            return
            
        try:
            from app.pipeline import ProjectConfig
            from app.queue_manager import BatchQueueManager
            import inspect
            
            # Reconstruct ProjectConfig
            sig = inspect.signature(ProjectConfig)
            valid_keys = {}
            for name, param in sig.parameters.items():
                if name in inputs:
                    val = inputs[name]
                    if name == "subtitle_color" and isinstance(val, list):
                        val = tuple(val)
                    valid_keys[name] = val
            
            # Ensure required fields exist in valid_keys
            required_fields = ["project_name", "draft_root", "voice_path", "media_dir"]
            for f in required_fields:
                if f not in valid_keys:
                    valid_keys[f] = inputs.get(f, "")
                    
            config = ProjectConfig(**valid_keys)
            
            manager = BatchQueueManager.get_instance()
            job_id = manager.add_job(config)
            
            main_win = self.window()
            if main_win and hasattr(main_win, "build_widget"):
                main_win.build_widget.refresh_queue_table()
                
            QMessageBox.information(
                self, "Đã thêm vào hàng đợi dựng",
                f"Đã tải cấu hình của dự án '{job_data.get('project_name')}' và thêm vào Hàng đợi dựng thành công."
            )
            
            if main_win and hasattr(main_win, "_switch_to_page"):
                main_win._switch_to_page("build-center")
                
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể khởi chạy lại tác vụ: {e}")

    def load_job_inputs(self, inputs: dict) -> None:
        main_win = self.window()
        if not main_win:
            return
        
        # Load setup widget inputs
        if hasattr(main_win, "setup_widget"):
            sw = main_win.setup_widget
            if "project_name" in inputs and hasattr(sw, "project_name"):
                sw.project_name.setText(str(inputs["project_name"]))
            if "draft_root" in inputs and hasattr(sw, "draft_root"):
                sw.draft_root.setText(str(inputs["draft_root"]))
            if "voice_path" in inputs and hasattr(sw, "voice_path"):
                sw.voice_path.setText(str(inputs["voice_path"]))
            if "media_dir" in inputs and hasattr(sw, "media_dir"):
                sw.media_dir.setText(str(inputs["media_dir"]))
            if "bgm_path" in inputs and hasattr(sw, "bgm_path"):
                sw.bgm_path.setText(str(inputs["bgm_path"]))
            if "srt_path" in inputs and hasattr(sw, "srt_path"):
                sw.srt_path.setText(str(inputs["srt_path"]))
            if "intro_path" in inputs and hasattr(sw, "intro_combo"):
                idx = sw.intro_combo.findData(inputs["intro_path"])
                if idx >= 0:
                    sw.intro_combo.setCurrentIndex(idx)
            if "outro_path" in inputs and hasattr(sw, "outro_combo"):
                idx = sw.outro_combo.findData(inputs["outro_path"])
                if idx >= 0:
                    sw.outro_combo.setCurrentIndex(idx)
            if "canvas" in inputs:
                if str(inputs["canvas"]) == "16:9" and hasattr(sw, "ratio_16_9"):
                    sw.ratio_16_9.setChecked(True)
                elif hasattr(sw, "ratio_9_16"):
                    sw.ratio_9_16.setChecked(True)
            if "clip_min_sec" in inputs and hasattr(sw, "clip_min"):
                sw.clip_min.setValue(int(inputs["clip_min_sec"]))
            if "clip_max_sec" in inputs and hasattr(sw, "clip_max"):
                sw.clip_max.setValue(int(inputs["clip_max_sec"]))
            if "recursive_scan" in inputs and hasattr(sw, "recursive_scan"):
                sw.recursive_scan.setChecked(bool(inputs["recursive_scan"]))
        
        # Load effects widget inputs
        if hasattr(main_win, "effects_widget"):
            ew = main_win.effects_widget
            if "logo_path" in inputs:
                ew.logo_path.setText(inputs["logo_path"])
            if "logo_position" in inputs:
                idx = ew.logo_position.findData(inputs["logo_position"])
                if idx >= 0:
                    ew.logo_position.setCurrentIndex(idx)
            if "logo_scale" in inputs:
                ew.logo_scale.setValue(inputs["logo_scale"])
            if "logo_opacity" in inputs:
                ew.logo_opacity.setValue(inputs["logo_opacity"])
            if "logo_bg_mode" in inputs:
                ew.logo_bg_mode.setCurrentText(inputs["logo_bg_mode"])
            if "anim_path" in inputs:
                ew.anim_path.setText(inputs["anim_path"])
            if "anim_position" in inputs:
                idx = ew.anim_position.findData(inputs["anim_position"])
                if idx >= 0:
                    ew.anim_position.setCurrentIndex(idx)
            if "anim_scale" in inputs:
                ew.anim_scale.setValue(inputs["anim_scale"])
            if "anim_timing" in inputs:
                ew.anim_timing.setCurrentText(inputs["anim_timing"])
            if "anim_bg_mode" in inputs:
                ew.anim_bg_mode.setCurrentText(inputs["anim_bg_mode"])
            if "chroma_enabled" in inputs:
                ew.chroma_enabled.setChecked(bool(inputs["chroma_enabled"]))
            if "chroma_mode" in inputs:
                ew.chroma_mode.setCurrentText(inputs["chroma_mode"])
            if "chroma_threshold" in inputs:
                ew.chroma_threshold.setValue(inputs["chroma_threshold"])
            if "chroma_shadow" in inputs:
                ew.chroma_shadow.setValue(inputs["chroma_shadow"])
            if "subtitle_karaoke" in inputs:
                ew.subtitle_karaoke.setChecked(bool(inputs["subtitle_karaoke"]))
            if "auto_keyframe" in inputs:
                ew.auto_keyframe.setCurrentText(inputs["auto_keyframe"])
            if "auto_transition" in inputs:
                ew.auto_transition.setCurrentText(inputs["auto_transition"])
            if "auto_transition_duration" in inputs:
                ew.auto_transition_duration.setValue(inputs["auto_transition_duration"])
            if "subtitle_font_size" in inputs:
                ew.subtitle_font_size.setValue(inputs["subtitle_font_size"])
            if "subtitle_bold" in inputs:
                ew.subtitle_bold.setChecked(bool(inputs["subtitle_bold"]))
            if "subtitle_outline_width" in inputs:
                ew.subtitle_outline_width.setValue(inputs["subtitle_outline_width"])
            if "subtitle_shadow_alpha" in inputs:
                ew.subtitle_shadow_alpha.setValue(inputs["subtitle_shadow_alpha"])
            if "subtitle_shadow_distance" in inputs:
                ew.subtitle_shadow_distance.setValue(inputs["subtitle_shadow_distance"])
            if "subtitle_color" in inputs:
                color = inputs["subtitle_color"]
                if len(color) == 3:
                    ew.subtitle_color = tuple(color)
                    if hasattr(ew, "_update_color_preview"):
                        ew._update_color_preview()

    @Slot()
    def run_diagnose(self) -> None:
        proj_name = self.project_combo.currentText()
        if not proj_name:
            self.diagnose_output.setPlainText("Vui lòng chọn hoặc quét các dự án nháp để chẩn đoán.")
            self.issues_table.setRowCount(0)
            return
            
        root_str = self.get_draft_root()
        if not root_str:
            self.diagnose_output.setPlainText("Chưa cấu hình thư mục lưu dự án CapCut (Draft Root).")
            self.issues_table.setRowCount(0)
            return
            
        project_dir = Path(root_str) / proj_name
        if not project_dir.exists():
            self.diagnose_output.setPlainText(f"Thư mục dự án không tồn tại: {project_dir}")
            self.issues_table.setRowCount(0)
            return
            
        self.diagnose_output.clear()
        self.append_diagnose_log(f"--- BẮT ĐẦU CHẨN ĐOÁN DỰ ÁN: {proj_name} ---", "system")
        self.issues_table.setRowCount(0)
        
        try:
            import draft_doctor
            from capcut_keyframe_tool import resolve_project_draft_paths
            
            # 1. Check draft_meta_info.json
            meta_path = project_dir / "draft_meta_info.json"
            if meta_path.exists():
                self.append_diagnose_log("[OK] Tìm thấy file cấu hình draft_meta_info.json", "success")
            else:
                self.append_diagnose_log("[CẢNH BÁO] Thiếu file draft_meta_info.json (Sẽ được tự động tạo lại)", "warning")
                
            # 2. Resolve draft paths
            primary_draft, mirrors = resolve_project_draft_paths(project_dir)
            if primary_draft.exists():
                self.append_diagnose_log(f"[OK] Xác định tệp nháp chính: {primary_draft.name}", "success")
                
                # Check contents
                issues = draft_doctor.check_draft_json(primary_draft)
                errors = [iss for iss in issues if iss.severity == "error"]
                warnings = [iss for iss in issues if iss.severity == "warn"]
                
                # Populate issues table
                self.issues_table.setRowCount(len(issues))
                for idx, iss in enumerate(issues):
                    sev_str = "LỖI" if iss.severity == "error" else "CẢNH BÁO"
                    sev_item = QTableWidgetItem(sev_str)
                    sev_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    
                    if iss.severity == "error":
                        sev_item.setForeground(QBrush(QColor("#f87171")))
                        sev_font = sev_item.font()
                        sev_font.setBold(True)
                        sev_item.setFont(sev_font)
                    else:
                        sev_item.setForeground(QBrush(QColor("#fbbf24")))
                        sev_font = sev_item.font()
                        sev_font.setBold(True)
                        sev_item.setFont(sev_font)
                    self.issues_table.setItem(idx, 0, sev_item)
                    
                    det_item = QTableWidgetItem(iss.message)
                    det_item.setForeground(QBrush(QColor("#e4e4e7")))
                    self.issues_table.setItem(idx, 1, det_item)

                    # Remedy button
                    fix_btn = QPushButton("Sửa lỗi")
                    fix_btn.setObjectName("btnBrowse")
                    fix_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
                    fix_btn.clicked.connect(lambda checked=False, item=iss: self._fix_single_issue(item))
                    self.issues_table.setCellWidget(idx, 2, fix_btn)
                
                # Report missing files specifically in text log
                missing_files = [iss for iss in issues if iss.code == "draft_local_file_missing"]
                if missing_files:
                    self.append_diagnose_log(f"[LỖI] Phát hiện {len(missing_files)} tài nguyên bị mất liên kết (missing files):", "error")
                    for iss in missing_files:
                        self.append_diagnose_log(f"  - Tệp bị thiếu: {iss.path}", "error")
                else:
                    self.append_diagnose_log("[OK] Tất cả tài nguyên video/âm thanh đã được liên kết đúng vị trí.", "success")
                    
                other_errors = [iss for iss in errors if iss.code != "draft_local_file_missing"]
                if other_errors:
                    for iss in other_errors:
                        self.append_diagnose_log(f"[LỖI] {iss.message}", "error")
                        
                if warnings:
                    for iss in warnings:
                        self.append_diagnose_log(f"[CẢNH BÁO] {iss.message}", "warning")
                        
                # Summary
                self.append_diagnose_log("\n--- TỔNG KẾT ---", "system")
                self.append_diagnose_log(f"Tổng số lỗi: {len(errors)} | Cảnh báo: {len(warnings)}", "system")
                if errors:
                    self.append_diagnose_log("=> Dự án có lỗi liên kết! Vui lòng chọn thư mục chứa tài nguyên mới và bấm 'Tự Động Sửa Lỗi'.", "error")
                else:
                    self.append_diagnose_log("=> Dự án ở trạng thái tốt, sẵn sàng làm việc.", "success")
            else:
                self.append_diagnose_log(f"[LỖI] Không tìm thấy tệp nháp chính: {primary_draft.name}", "error")
        except Exception as e:
            self.append_diagnose_log(f"[LỖI] Lỗi chẩn đoán dự án: {e}", "error")

    def append_diagnose_log(self, text: str, category: str = "info") -> None:
        if category == "error":
            color = "#ef4444"
            weight = "bold"
        elif category == "success":
            color = "#10b981"
            weight = "normal"
        elif category == "warning":
            color = "#f59e0b"
            weight = "bold"
        elif category == "system":
            color = "#a78bfa"
            weight = "bold"
        else:
            color = "#cbd5e1"
            weight = "normal"
            
        import html
        safe_text = html.escape(text)
        html_str = f'<div style="color: {color}; font-weight: {weight}; font-family: Consolas, monospace; font-size: 11px; margin-bottom: 2px; line-height: 1.4;">{safe_text}</div>'
        self.diagnose_output.appendHtml(html_str)

    def _fix_single_issue(self, iss) -> None:
        import os
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        import json
        import time
        from capcut_keyframe_tool import resolve_project_draft_paths
        
        proj_name = self.project_combo.currentText()
        root_str = self.get_draft_root()
        if not proj_name or not root_str:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn dự án mục tiêu trước.")
            return

        project_dir = Path(root_str) / proj_name

        if iss.code == "draft_local_file_missing":
            old_path_str = iss.path
            old_path = Path(old_path_str)
            filename = old_path.name
            
            file_filter = f"Tệp tin (*{old_path.suffix})" if old_path.suffix else "Tất cả tệp tin (*.*)"
            new_file_path, _ = QFileDialog.getOpenFileName(
                self, 
                f"Chọn tệp thay thế cho '{filename}'", 
                "", 
                file_filter
            )
            
            if not new_file_path:
                return
                
            new_file_path = str(Path(new_file_path).resolve())
            
            try:
                primary_draft, mirrors = resolve_project_draft_paths(project_dir)
                all_drafts = [primary_draft] + mirrors
                
                fixed_count = 0
                for draft_path in all_drafts:
                    if not draft_path.exists():
                        continue
                        
                    data = json.loads(draft_path.read_text(encoding="utf-8"))
                    materials = data.get("materials") or {}
                    modified = False
                    
                    for key in ("videos", "audios"):
                        for item in materials.get(key) or []:
                            if item.get("path") == old_path_str:
                                item["path"] = new_file_path
                                item["category_name"] = "local"
                                modified = True
                                fixed_count += 1
                                
                    if modified:
                        data['update_time'] = int(time.time() * 1000)
                        from draft_doctor import _backup_and_write_text
                        _backup_and_write_text(draft_path, json.dumps(data, ensure_ascii=False, separators=(',', ':')), f"Sửa lỗi thủ công: Thay thế {filename}")
                
                if fixed_count > 0:
                    QMessageBox.information(
                        self, "Thành công", 
                        f"Đã cập nhật liên kết tệp '{filename}' sang vị trí mới thành công."
                    )
                    self.run_diagnose()
                else:
                    QMessageBox.warning(
                        self, "Không tìm thấy", 
                        "Không tìm thấy liên kết tệp tương ứng trong tệp nháp để cập nhật."
                    )
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể cập nhật tệp nháp: {e}")
        elif iss.code == "srt_missing":
            new_file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "Chọn tệp SRT thay thế", 
                "", 
                "Tệp phụ đề (*.srt)"
            )
            if not new_file_path:
                return
            new_file_path = str(Path(new_file_path).resolve())
            main_win = self.window()
            if main_win and hasattr(main_win, "setup_widget"):
                main_win.setup_widget.srt_path.setText(new_file_path)
                QMessageBox.information(
                    self, "Thành công", 
                    "Đã cập nhật đường dẫn tệp SRT mới vào tab Thiết lập."
                )
                self.run_diagnose()
        else:
            main_win = self.window()
            if main_win and hasattr(main_win, "_repair_project_click"):
                main_win._repair_project_click()
            else:
                QMessageBox.information(
                    self, "Thông tin", 
                    "Vui lòng sử dụng tính năng 'Tự Động Sửa Lỗi Dự Án (Auto Repair)' để xử lý cảnh báo này."
                )

    @Slot()
    def export_diagnose_report(self) -> None:
        proj_name = self.project_combo.currentText()
        if not proj_name:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn dự án mục tiêu trước.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Lưu báo cáo chẩn đoán", 
            f"Báo_cáo_chẩn_đoán_{proj_name}.txt", 
            "Tệp văn bản (*.txt)"
        )
        if not file_path:
            return
            
        try:
            report_lines = []
            report_lines.append(f"BÁO CÁO CHẨN ĐOÁN DỰ ÁN CAPCUT: {proj_name}")
            report_lines.append(f"Thời gian chẩn đoán: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("=" * 60)
            report_lines.append("")
            
            report_lines.append("DANH SÁCH CẢNH BÁO / LỖI CHI TIẾT:")
            row_count = self.issues_table.rowCount()
            if row_count == 0:
                report_lines.append("  (Không phát hiện lỗi hoặc cảnh báo nào)")
            else:
                for r in range(row_count):
                    sev = self.issues_table.item(r, 0).text()
                    det = self.issues_table.item(r, 1).text()
                    report_lines.append(f"  [{sev}] {det}")
            report_lines.append("")
            report_lines.append("=" * 60)
            report_lines.append("")
            report_lines.append("NHẬT KÝ CHẨN ĐOÁN CHI TIẾT:")
            
            plain_text = self.diagnose_output.toPlainText()
            report_lines.append(plain_text)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(report_lines))
                
            QMessageBox.information(
                self, "Thành công",
                f"Đã xuất báo cáo chẩn đoán ra tệp tin:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể xuất báo cáo: {e}")
