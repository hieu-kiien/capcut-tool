# app/widgets/history_widget.py
from pathlib import Path
from PySide6.QtCore import Slot, Qt
from PySide6.QtGui import QColor, QBrush
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
)

class HistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.project_combo.currentTextChanged.connect(self.run_diagnose)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Main splitter (Left: Task history, Right: Diagnostics + Backups)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("mainSplitter")

        # ==========================================
        # LEFT SIDE: TASK HISTORY (Lịch sử tác vụ)
        # ==========================================
        left_widget = QWidget()
        left_widget.setMinimumWidth(560)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        left_card = QFrame()
        left_card.setObjectName("queueCard")
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setContentsMargins(12, 12, 12, 12)
        left_card_layout.setSpacing(10)

        left_title = QLabel("Lịch Sử Tác Vụ (Build History)")
        left_title.setObjectName("cardTitle")
        left_card_layout.addWidget(left_title)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["Dự án", "Trạng thái", "Bắt đầu lúc", "Chi tiết / Lỗi"])
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setObjectName("historyTable")
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setShowGrid(False)
        self.history_table.setWordWrap(False)
        self.history_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.history_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.history_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.history_table.setMinimumWidth(540)
        header = self.history_table.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(82)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(38)
        self.history_table.setColumnWidth(0, 155)
        self.history_table.setColumnWidth(1, 112)
        self.history_table.setColumnWidth(2, 118)
        self.history_table.setStyleSheet(
            """
            QTableWidget#historyTable {
                background-color: #0f172a;
                alternate-background-color: #111827;
                color: #e5e7eb;
                border: 1px solid #263247;
                border-radius: 8px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
            QTableWidget#historyTable::item {
                padding: 7px 9px;
                border-bottom: 1px solid rgba(148, 163, 184, 0.12);
            }
            QTableWidget#historyTable::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QTableWidget#historyTable QHeaderView::section {
                background-color: #182235;
                color: #cbd5e1;
                border: none;
                border-right: 1px solid #263247;
                border-bottom: 1px solid #263247;
                padding: 8px 10px;
                font-weight: 700;
            }
            QTableWidget#historyTable QTableCornerButton::section {
                background-color: #182235;
                border: none;
            }
            """
        )
        
        left_card_layout.addWidget(self.history_table)
        left_layout.addWidget(left_card)
        splitter.addWidget(left_widget)

        # ==========================================
        # RIGHT SIDE: DIAGNOSTIC & BACKUPS (Scrollable)
        # ==========================================
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setObjectName("histScroll")
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        right_content = QWidget()
        right_lay = QVBoxLayout(right_content)
        right_lay.setContentsMargins(0, 0, 10, 0)
        right_lay.setSpacing(12)

        # 1. Project Selection Card
        proj_card = QFrame()
        proj_card.setObjectName("projCard")
        proj_card_lay = QVBoxLayout(proj_card)
        proj_card_lay.setContentsMargins(16, 16, 16, 16)
        proj_card_lay.setSpacing(12)
        
        proj_title = QLabel("Dự Án Nháp CapCut Mục Tiêu")
        proj_title.setObjectName("cardTitle")
        proj_card_lay.addWidget(proj_title)
        
        proj_row = QHBoxLayout()
        self.project_combo = QComboBox()
        self.project_combo.setPlaceholderText("Vui lòng nhập Draft Root để quét các dự án...")
        proj_row.addWidget(self.project_combo, 1)
        
        self.btn_refresh_projects = QPushButton("Tải Lại")
        self.btn_refresh_projects.setObjectName("btnBrowse")
        proj_row.addWidget(self.btn_refresh_projects)
        proj_card_lay.addLayout(proj_row)
        
        right_lay.addWidget(proj_card)

        # 2. Draft Doctor Card (Bác sĩ sửa lỗi)
        doctor_card = QFrame()
        doctor_card.setObjectName("configCard")
        doc_lay = QVBoxLayout(doctor_card)
        doc_lay.setContentsMargins(16, 16, 16, 16)
        doc_lay.setSpacing(10)

        doctor_title = QLabel("Bác Sĩ Sửa Lỗi (Draft Doctor)")
        doctor_title.setObjectName("cardTitle")
        doc_lay.addWidget(doctor_title)

        relink_lbl = QLabel("Thư mục tìm kiếm tài nguyên mới (Relink directory):")
        relink_lbl.setObjectName("fieldLabel")
        doc_lay.addWidget(relink_lbl)

        relink_row = QHBoxLayout()
        self.relink_media_dir = QLineEdit()
        self.relink_media_dir.setPlaceholderText("Để trống nếu dùng Thư mục video/hình nền mặc định...")
        relink_row.addWidget(self.relink_media_dir, 1)

        self.btn_browse_relink = QPushButton("Chọn...")
        self.btn_browse_relink.setObjectName("btnBrowse")
        self.btn_browse_relink.clicked.connect(self._browse_relink_dir)
        relink_row.addWidget(self.btn_browse_relink)
        doc_lay.addLayout(relink_row)

        diagnose_lbl = QLabel("Báo cáo chẩn đoán tình trạng dự án:")
        diagnose_lbl.setObjectName("fieldLabel")
        doc_lay.addWidget(diagnose_lbl)

        self.diagnose_output = QPlainTextEdit()
        self.diagnose_output.setObjectName("logTerminal")
        self.diagnose_output.setReadOnly(True)
        self.diagnose_output.setFixedHeight(180)
        doc_lay.addWidget(self.diagnose_output)

        doc_btn_row = QHBoxLayout()
        doc_btn_row.setSpacing(10)

        self.btn_diagnose = QPushButton("Chẩn Đoán Lỗi")
        self.btn_diagnose.setObjectName("btnBrowse")
        self.btn_diagnose.clicked.connect(self.run_diagnose)
        doc_btn_row.addWidget(self.btn_diagnose, 1)

        self.btn_repair_project = QPushButton("TỰ ĐỘNG SỬA LỖI DỰ ÁN (AUTO REPAIR)")
        self.btn_repair_project.setObjectName("btnRun")
        doc_btn_row.addWidget(self.btn_repair_project, 2)

        doc_lay.addLayout(doc_btn_row)
        right_lay.addWidget(doctor_card)

        # 3. Backups Card (Quản lý sao lưu & Hoàn tác)
        backup_card = QFrame()
        backup_card.setObjectName("configCard")
        back_lay = QVBoxLayout(backup_card)
        back_lay.setContentsMargins(16, 16, 16, 16)
        back_lay.setSpacing(12)
        
        back_title = QLabel("Quản Lý Sao Lưu & Hoàn Tác (Backups & Restore)")
        back_title.setObjectName("cardTitle")
        back_lay.addWidget(back_title)
        
        back_grid = QGridLayout()
        back_grid.setSpacing(10)
        
        back_grid.addWidget(self._create_field_label("Các bản sao lưu dự án"), 0, 0)
        self.backup_combo = QComboBox()
        back_grid.addWidget(self.backup_combo, 0, 1)

        back_grid.addWidget(self._create_field_label("Giữ lại backup (ngày)"), 1, 0)
        self.backup_keep_days = QDoubleSpinBox()
        self.backup_keep_days.setRange(1, 365)
        self.backup_keep_days.setValue(7)
        self.backup_keep_days.setSingleStep(1)
        self.backup_keep_days.setDecimals(0)
        back_grid.addWidget(self.backup_keep_days, 1, 1)

        back_lay.addLayout(back_grid)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_restore_backup = QPushButton("KHÔI PHỤC BẢN SAO LƯU ĐÃ CHỌN")
        self.btn_restore_backup.setObjectName("btnCancel")
        self.btn_restore_backup.setEnabled(False)
        btn_row.addWidget(self.btn_restore_backup, 2)

        self.btn_clean_backups = QPushButton("Dọn Backup Cũ")
        self.btn_clean_backups.setObjectName("btnBrowse")
        btn_row.addWidget(self.btn_clean_backups, 1)

        back_lay.addLayout(btn_row)
        right_lay.addWidget(backup_card)

        right_scroll.setWidget(right_content)
        splitter.addWidget(right_scroll)

        splitter.setSizes([620, 420])
        layout.addWidget(splitter)

    def _create_field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
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

    def refresh_history_table(self) -> None:
        self.history_table.setRowCount(0)
        from app.history import load_job_history
        from pathlib import Path
        try:
            root_dir = Path(__file__).resolve().parents[2]
            rows = load_job_history(root_dir)
            
            self.history_table.setSortingEnabled(False)
            self.history_table.setRowCount(len(rows))
            status_translation = {
                "pending": "⏳ Chờ",
                "running": "🔵 Dựng...",
                "completed": "✅ Xong",
                "success": "✅ Xong",
                "failed": "❌ Lỗi",
                "cancelled": "⚪ Hủy"
            }
            
            status_translation["error"] = status_translation.get("failed", "Error")
            status_translation.update({
                "pending": "Chờ",
                "running": "Đang dựng",
                "completed": "Xong",
                "success": "Xong",
                "failed": "Lỗi",
                "error": "Lỗi",
                "cancelled": "Hủy",
            })
            status_colors = {
                "pending": "#facc15",
                "running": "#60a5fa",
                "completed": "#34d399",
                "success": "#34d399",
                "failed": "#f87171",
                "error": "#f87171",
                "cancelled": "#cbd5e1",
            }

            for idx, job_data in enumerate(rows):
                job_type = job_data.get("job_type") or "unknown"
                status = job_data.get("status") or "unknown"
                started_at = job_data.get("started_at") or "N/A"
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
                        
                row_bg = QColor("#1f1826") if status in {"failed", "error"} or err_msg else QColor("#0f172a" if idx % 2 == 0 else "#111827")
                normal_fg = QBrush(QColor("#e5e7eb"))
                muted_fg = QBrush(QColor("#cbd5e1"))
                error_fg = QBrush(QColor("#fecaca"))

                # 1. Project
                proj_item = QTableWidgetItem(proj_name)
                proj_item.setToolTip(proj_name)
                proj_item.setForeground(normal_fg)
                self.history_table.setItem(idx, 0, proj_item)
                
                # 2. Status
                status_text = status_translation.get(status, status)
                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_item.setToolTip(status_text)
                status_item.setForeground(QBrush(QColor(status_colors.get(status, "#cbd5e1"))))
                status_font = status_item.font()
                status_font.setBold(True)
                status_item.setFont(status_font)
                self.history_table.setItem(idx, 1, status_item)
                
                # 3. Started At
                started_text = started_at
                if len(started_at) > 11 and " " in started_at:
                    started_text = started_at[11:16] + " " + started_at[8:10] + "/" + started_at[5:7]
                elif len(started_at) > 11 and "_" in started_at:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(started_at, "%Y%m%d_%H%M%S")
                        started_text = dt.strftime("%H:%M %d/%m")
                    except Exception:
                        pass
                started_item = QTableWidgetItem(started_text)
                started_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                started_item.setToolTip(started_at)
                started_item.setForeground(muted_fg)
                self.history_table.setItem(idx, 2, started_item)
                
                # 4. Details / Error
                if status == "failed" or err_msg:
                    details = err_msg
                else:
                    inputs = job_data.get("inputs", {})
                    if job_type == "download":
                        url = inputs.get("url") or ""
                        details = f"Tải media: {url}"
                    elif job_type == "apply_preset":
                        preset = inputs.get("preset_id") or ""
                        details = f"Áp dụng preset: {preset}"
                    elif job_type == "pipeline":
                        details = "Chạy pipeline dựng"
                    else:
                        details = f"Hoàn thành ({job_type})"
                        
                details_text = details.strip() if isinstance(details, str) else str(details)
                if not details_text:
                    details_text = "-"
                detail_item = QTableWidgetItem(details_text)
                detail_item.setToolTip(details_text)
                detail_item.setForeground(error_fg if status in {"failed", "error"} or err_msg else muted_fg)
                self.history_table.setItem(idx, 3, detail_item)

                for col in range(self.history_table.columnCount()):
                    item = self.history_table.item(idx, col)
                    if item:
                        item.setBackground(QBrush(row_bg))
                self.history_table.setRowHeight(idx, 38)
            self.history_table.setSortingEnabled(True)
        except Exception as e:
            print(f"Error loading history table from JSON: {e}")

    @Slot()
    def run_diagnose(self) -> None:
        proj_name = self.project_combo.currentText()
        if not proj_name:
            self.diagnose_output.setPlainText("Vui lòng chọn hoặc quét các dự án nháp để chẩn đoán.")
            return
            
        root_str = self.get_draft_root()
        if not root_str:
            self.diagnose_output.setPlainText("Chưa cấu hình thư mục lưu dự án CapCut (Draft Root).")
            return
            
        project_dir = Path(root_str) / proj_name
        if not project_dir.exists():
            self.diagnose_output.setPlainText(f"Thư mục dự án không tồn tại: {project_dir}")
            return
            
        self.diagnose_output.clear()
        self.append_diagnose_log(f"--- BẮT ĐẦU CHẨN ĐOÁN DỰ ÁN: {proj_name} ---", "system")
        
        try:
            import draft_doctor
            import media_probe
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
                
                # Report missing files specifically
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
