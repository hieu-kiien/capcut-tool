# app/widgets/build_widget.py
import html as _html
from datetime import datetime as _dt
from pathlib import Path
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QPlainTextEdit,
    QFrame,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMessageBox,
)
from app.queue_manager import BatchQueueManager, BuildJob
from app.icons import get_svg_icon

class BuildWidget(QWidget):
    # Signals to sync with MainWindow pipeline actions
    run_requested = Signal()  # Request current config to be started immediately
    cancel_requested = Signal()
    add_to_queue_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = BatchQueueManager.get_instance()
        
        # Keep track of which job is currently selected in the UI
        self.selected_job_id = None
        
        self.step_widgets = {}
        self.step_labels = {}
        self.step_status_labels = {}
        self.step_codes = ["preflight", "scan_media", "plan_media", "write_draft"]
        
        self.preflight_widgets = {}
        self.preflight_value_labels = {}
        
        self._build_ui()
        self._connect_signals()
        self.refresh_queue_table()
        self._update_buttons()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Page Header
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 4)
        header_layout.setSpacing(4)

        lbl_title = QLabel("Trung tâm dựng")
        lbl_title.setObjectName("pageTitle")
        lbl_subtitle = QLabel("Theo dõi tiến trình kiểm tra preflight, chạy các bước tạo timeline và ghi dự án nháp hàng loạt.")
        lbl_subtitle.setObjectName("pageSubtitle")

        header_layout.addWidget(lbl_title)
        header_layout.addWidget(lbl_subtitle)
        layout.addWidget(header_widget)

        # Main splitter (Left: Queue list, Right: Job detail + Live Logs)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("mainSplitter")

        # ==========================================
        # LEFT SIDE: QUEUE LIST
        # ==========================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        left_card = QFrame()
        left_card.setObjectName("queueCard")
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setContentsMargins(16, 16, 16, 16)
        left_card_layout.setSpacing(10)

        left_title_row = QHBoxLayout()
        left_title = QLabel("Hàng Đợi Dựng (Build Queue)")
        left_title.setObjectName("cardTitle")
        left_title_row.addWidget(left_title)
        
        self.queue_count_lbl = QLabel("(0)")
        self.queue_count_lbl.setObjectName("queueCountBadge")
        left_title_row.addWidget(self.queue_count_lbl)
        left_title_row.addStretch()
        
        left_card_layout.addLayout(left_title_row)

        # Queue controls
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(6)

        self.btn_add_to_queue = QPushButton("  Thêm dự án")
        self.btn_add_to_queue.setIcon(get_svg_icon("plus", color="#ffffff", size=14))
        self.btn_add_to_queue.setCursor(Qt.PointingHandCursor)
        self.btn_add_to_queue.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00F2FE, stop:1 #7F00FF);
                color: #ffffff;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
        """)
        self.btn_add_to_queue.clicked.connect(lambda: self.add_to_queue_requested.emit())
        ctrl_layout.addWidget(self.btn_add_to_queue)

        self.btn_start_queue = QPushButton("  Chạy queue")
        self.btn_start_queue.setIcon(get_svg_icon("play", color="#ffffff", size=14))
        self.btn_start_queue.setObjectName("btnStartQueue")
        self.btn_start_queue.clicked.connect(self._start_queue_click)
        ctrl_layout.addWidget(self.btn_start_queue)

        self.btn_pause_queue = QPushButton("  Tạm dừng")
        self.btn_pause_queue.setIcon(get_svg_icon("pause", color="#ffffff", size=14))
        self.btn_pause_queue.setObjectName("btnPauseQueue")
        self.btn_pause_queue.clicked.connect(self._pause_queue_click)
        ctrl_layout.addWidget(self.btn_pause_queue)

        self.btn_skip_job = QPushButton("  Bỏ qua")
        self.btn_skip_job.setIcon(get_svg_icon("skip", color="#ffffff", size=14))
        self.btn_skip_job.setObjectName("btnSkipJob")
        self.btn_skip_job.clicked.connect(self._skip_job_click)
        ctrl_layout.addWidget(self.btn_skip_job)

        self.btn_clear_queue = QPushButton("  Xóa hết")
        self.btn_clear_queue.setIcon(get_svg_icon("trash", color="#ef4444", size=14))
        self.btn_clear_queue.setObjectName("btnClearQueue")
        self.btn_clear_queue.clicked.connect(self._clear_queue_click)
        ctrl_layout.addWidget(self.btn_clear_queue)

        left_card_layout.addLayout(ctrl_layout)

        # Queue table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(4)
        self.queue_table.setHorizontalHeaderLabels(["Dự án", "Trạng thái", "Tiến trình", "Thao tác"])
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.setObjectName("queueTable")
        self.queue_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.queue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.queue_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setColumnWidth(1, 95)
        self.queue_table.setColumnWidth(2, 90)
        self.queue_table.itemSelectionChanged.connect(self._on_table_selection_changed)
        
        left_card_layout.addWidget(self.queue_table)

        # Global queue progress bar
        global_progress_layout = QHBoxLayout()
        global_progress_layout.setSpacing(10)
        
        global_progress_lbl = QLabel("Tiến độ tổng:")
        global_progress_lbl.setObjectName("globalProgressLabel")
        global_progress_layout.addWidget(global_progress_lbl)
        
        self.global_progress_bar = QProgressBar()
        self.global_progress_bar.setFixedHeight(8)
        self.global_progress_bar.setRange(0, 100)
        self.global_progress_bar.setValue(0)
        self.global_progress_bar.setTextVisible(False)
        global_progress_layout.addWidget(self.global_progress_bar)
        
        self.global_progress_text = QLabel("0/0")
        self.global_progress_text.setObjectName("globalProgressText")
        global_progress_layout.addWidget(self.global_progress_text)
        
        left_card_layout.addLayout(global_progress_layout)
        left_layout.addWidget(left_card)
        splitter.addWidget(left_widget)

        # ==========================================
        # RIGHT SIDE: JOB DETAIL + LIVE LOGS
        # ==========================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Top row: Preflight Card (left) and Pipeline Card (right)
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(10)

        # 1. Preflight Card
        preflight_card = QFrame()
        preflight_card.setObjectName("executionCard")
        preflight_lay = QVBoxLayout(preflight_card)
        preflight_lay.setContentsMargins(14, 14, 14, 14)
        preflight_lay.setSpacing(6)

        preflight_title = QLabel("Kiểm Tra Trước")
        preflight_title.setObjectName("cardTitle")
        preflight_lay.addWidget(preflight_title)

        preflight_items = [
            ("ffmpeg", "FFmpeg"),
            ("voice", "Giọng đọc"),
            ("srt", "Phụ đề (SRT)"),
            ("media", "Thư viện media"),
            ("draft", "Quyền draft"),
            ("brand", "Bộ thương hiệu")
        ]

        for code, label in preflight_items:
            item_row = QFrame()
            item_row.setObjectName("stepRow")
            item_row.setProperty("state", "pending")
            row_lay = QHBoxLayout(item_row)
            row_lay.setContentsMargins(8, 4, 8, 4)
            row_lay.setSpacing(8)

            circle = QLabel()
            circle.setObjectName("stepCircle")
            circle.setFixedSize(18, 18)
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row_lay.addWidget(circle)

            name_lbl = QLabel(label)
            name_lbl.setObjectName("stepName")
            name_lbl.setStyleSheet("font-size: 11px;")
            row_lay.addWidget(name_lbl)

            row_lay.addStretch()

            val_lbl = QLabel("Đang chờ...")
            val_lbl.setObjectName("stepStatus")
            val_lbl.setStyleSheet("font-size: 11px;")
            row_lay.addWidget(val_lbl)

            preflight_lay.addWidget(item_row)
            self.preflight_widgets[code] = item_row
            self.preflight_value_labels[code] = val_lbl

        top_row_layout.addWidget(preflight_card, 1)

        # 2. Pipeline Card (Stepper)
        pipeline_card = QFrame()
        pipeline_card.setObjectName("executionCard")
        pipeline_lay = QVBoxLayout(pipeline_card)
        pipeline_lay.setContentsMargins(14, 14, 14, 14)
        pipeline_lay.setSpacing(6)

        self.active_job_title = QLabel("Tiến Trình Pipeline")
        self.active_job_title.setObjectName("cardTitle")
        pipeline_lay.addWidget(self.active_job_title)

        stepper_layout = QVBoxLayout()
        stepper_layout.setSpacing(6)

        step_labels_map = {
            "preflight": "1. Kiểm tra đầu vào",
            "scan_media": "2. Quét kho media",
            "plan_media": "3. Phân bổ video nền",
            "write_draft": "4. Tạo dự án CapCut",
        }

        for code in self.step_codes:
            step_row = QFrame()
            step_row.setObjectName("stepRow")
            step_row.setProperty("state", "pending")
            row_lay = QHBoxLayout(step_row)
            row_lay.setContentsMargins(8, 4, 8, 4)
            row_lay.setSpacing(8)

            circle = QLabel()
            circle.setObjectName("stepCircle")
            circle.setFixedSize(18, 18)
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row_lay.addWidget(circle)

            det_lay = QVBoxLayout()
            det_lay.setSpacing(1)
            name_lbl = QLabel(step_labels_map[code])
            name_lbl.setObjectName("stepName")
            name_lbl.setStyleSheet("font-size: 11px;")
            status_lbl = QLabel("Đang chờ...")
            status_lbl.setObjectName("stepStatus")
            status_lbl.setStyleSheet("font-size: 10px;")

            det_lay.addWidget(name_lbl)
            det_lay.addWidget(status_lbl)
            row_lay.addLayout(det_lay)
            row_lay.addStretch()

            stepper_layout.addWidget(step_row)
            self.step_widgets[code] = step_row
            self.step_labels[code] = name_lbl
            self.step_status_labels[code] = status_lbl

        pipeline_lay.addLayout(stepper_layout)
        top_row_layout.addWidget(pipeline_card, 1)

        right_layout.addLayout(top_row_layout)

        # Log Terminal Card
        log_card = QFrame()
        log_card.setObjectName("logCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(12, 12, 12, 12)
        log_layout.setSpacing(6)
        
        log_header = QHBoxLayout()
        self.log_title = QLabel("Nhật Ký Thực Hiện (Live Logs)")
        self.log_title.setObjectName("logTitle")
        
        self.btn_clear_log = QPushButton("Xóa log")
        self.btn_clear_log.setObjectName("btnClearLog")
        self.btn_clear_log.clicked.connect(self.clear_logs)
        
        log_header.addWidget(self.log_title)
        log_header.addStretch()
        log_header.addWidget(self.btn_clear_log)
        log_layout.addLayout(log_header)

        self.log_terminal = QPlainTextEdit()
        self.log_terminal.setObjectName("logTerminal")
        self.log_terminal.setReadOnly(True)
        log_layout.addWidget(self.log_terminal, 1)
        
        right_layout.addWidget(log_card, 1)
        splitter.addWidget(right_widget)

        # Set default splitter ratio (40% left, 60% right)
        splitter.setSizes([380, 520])
        layout.addWidget(splitter)

        # Legacy compatibility aliases for MainWindow / gui.py
        self.btn_run = self.btn_start_queue
        self.btn_cancel = self.btn_pause_queue
        self.progress_bar = self.global_progress_bar

    def _connect_signals(self) -> None:
        self.manager.job_added.connect(self._on_job_added)
        self.manager.job_started.connect(self._on_job_started)
        self.manager.job_progress.connect(self._on_job_progress)
        self.manager.job_step_changed.connect(self._on_job_step_changed)
        self.manager.step_changed.connect(self._on_step_changed)
        self.manager.job_finished.connect(self._on_job_finished)
        self.manager.job_log_appended.connect(self._on_job_log_appended)
        self.manager.queue_status_changed.connect(self._on_queue_status_changed)
        self.manager.queue_cleared.connect(self._on_queue_cleared)
        self.manager.job_removed.connect(self._on_job_removed)

    # ==========================================
    # QUEUE SLOTS
    # ==========================================
    @Slot()
    def _start_queue_click(self) -> None:
        self.manager.start_queue()

    @Slot()
    def _pause_queue_click(self) -> None:
        self.manager.pause_queue()

    @Slot()
    def _skip_job_click(self) -> None:
        self.manager.cancel_current_job()

    @Slot()
    def _clear_queue_click(self) -> None:
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            "Bạn có chắc muốn xóa tất cả các công việc đang chờ khỏi hàng đợi không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.clear_queue()

    def _update_buttons(self) -> None:
        running = self.manager.is_running
        paused = self.manager.is_paused
        
        self.btn_start_queue.setEnabled(not running or paused)
        self.btn_pause_queue.setEnabled(running and not paused)
        self.btn_skip_job.setEnabled(running and self.manager.current_job_id is not None)
        self.btn_clear_queue.setEnabled(len(self.manager.jobs) > 0)

    # ==========================================
    # MANAGER SIGNAL CALLBACKS
    # ==========================================
    @Slot(object)
    def _on_job_added(self, job: BuildJob) -> None:
        self.refresh_queue_table()
        self._update_buttons()

    @Slot(str)
    def _on_job_started(self, job_id: str) -> None:
        self.refresh_queue_table()
        self._update_buttons()
        if self.selected_job_id == job_id or self.selected_job_id is None:
            self._select_job(job_id)

    @Slot(str, int, str)
    def _on_job_progress(self, job_id: str, progress_val: int, message: str) -> None:
        # Update progress in table
        for row in range(self.queue_table.rowCount()):
            item = self.queue_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == job_id:
                progress_item = QTableWidgetItem(f"{progress_val}%")
                progress_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.queue_table.setItem(row, 2, progress_item)
                break
        
        if self.selected_job_id == job_id:
            self._update_stepper_ui(progress_val, "running", message)
            self._update_global_progress()

    @Slot(str, str, str, str)
    def _on_job_step_changed(self, job_id: str, code: str, status: str, message: str) -> None:
        if self.selected_job_id == job_id or (self.selected_job_id is None and job_id == self.manager.current_job_id):
            self.update_step_widget(code, status, message)

    @Slot(str, str, str)
    def _on_step_changed(self, code: str, status: str, message: str) -> None:
        if self.selected_job_id is None or self.selected_job_id == self.manager.current_job_id:
            self.update_step_widget(code, status, message)

    @Slot(str, str, str)
    def _on_job_finished(self, job_id: str, status: str, error_message: str) -> None:
        self.refresh_queue_table()
        self._update_buttons()
        self._update_global_progress()
        
        if self.selected_job_id == job_id:
            self._update_stepper_ui(100, status, error_message)

    @Slot(str, str)
    def _on_job_log_appended(self, job_id: str, log_line: str) -> None:
        if self.selected_job_id == job_id:
            self.append_log(log_line)

    @Slot(bool, bool)
    def _on_queue_status_changed(self, running: bool, paused: bool) -> None:
        self._update_buttons()
        self.refresh_queue_table()

    @Slot()
    def _on_queue_cleared(self) -> None:
        self.refresh_queue_table()
        self._update_buttons()
        self.clear_logs()
        self.selected_job_id = None
        self.active_job_title.setText("Tiến Trình Pipeline")
        self._update_preflight_for_job(None)
        self._update_stepper_ui(0, "pending")
        self._update_global_progress()

    @Slot(str)
    def _on_job_removed(self, job_id: str) -> None:
        self.refresh_queue_table()
        self._update_buttons()
        self._update_global_progress()
        if self.selected_job_id == job_id:
            self.selected_job_id = None
            self.clear_logs()
            self.active_job_title.setText("Tiến Trình Pipeline")
            self._update_preflight_for_job(None)
            self._update_stepper_ui(0, "pending")

    # ==========================================
    # HELPERS
    # ==========================================
    def refresh_queue_table(self) -> None:
        """Reloads and redraws all queue rows in the table."""
        self.queue_table.blockSignals(True)
        self.queue_table.setRowCount(0)
        
        status_translation = {
            "pending": "Chờ",
            "running": "Dựng...",
            "completed": "Xong",
            "failed": "Lỗi",
            "cancelled": "Hủy"
        }
        status_icons = {
            "pending": ("clock", "#94a3b8"),
            "running": ("refresh", "#00F2FE"),
            "completed": ("check", "#22c55e"),
            "failed": ("x", "#ef4444"),
            "cancelled": ("stop", "#64748b"),
        }

        self.queue_count_lbl.setText(f"({len(self.manager.jobs)})")

        for idx, job in enumerate(self.manager.jobs):
            self.queue_table.insertRow(idx)

            proj_item = QTableWidgetItem(job.project_name)
            proj_item.setData(Qt.ItemDataRole.UserRole, job.id)
            self.queue_table.setItem(idx, 0, proj_item)

            status_text = status_translation.get(job.status, job.status)
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_info = status_icons.get(job.status)
            if icon_info:
                status_item.setIcon(get_svg_icon(icon_info[0], icon_info[1], 14))
            self.queue_table.setItem(idx, 1, status_item)

            progress_item = QTableWidgetItem(f"{job.progress}%")
            progress_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.queue_table.setItem(idx, 2, progress_item)

            del_btn = QPushButton("Xóa")
            del_btn.setObjectName("btnTableDelete")
            del_btn.setFixedSize(50, 20)
            del_btn.clicked.connect(lambda checked=False, j_id=job.id: self.manager.remove_job(j_id))
            self.queue_table.setCellWidget(idx, 3, del_btn)

            if self.selected_job_id == job.id:
                self.queue_table.selectRow(idx)

        self.queue_table.blockSignals(False)
        self._update_global_progress()

    def _update_global_progress(self) -> None:
        total = len(self.manager.jobs)
        if total == 0:
            self.global_progress_bar.setValue(0)
            self.global_progress_text.setText("0/0")
            return
            
        completed = sum(1 for j in self.manager.jobs if j.status in ("completed", "failed", "cancelled"))
        val = int((completed / total) * 100)
        self.global_progress_bar.setValue(val)
        self.global_progress_text.setText(f"{completed}/{total}")

    def _on_table_selection_changed(self) -> None:
        selected_ranges = self.queue_table.selectedRanges()
        if not selected_ranges:
            return
            
        row = selected_ranges[0].topRow()
        item = self.queue_table.item(row, 0)
        if item:
            job_id = item.data(Qt.ItemDataRole.UserRole)
            self._select_job(job_id)

    def _select_job(self, job_id: str) -> None:
        job = None
        for j in self.manager.jobs:
            if j.id == job_id:
                job = j
                break
                
        if not job:
            return

        self.selected_job_id = job_id

        self.active_job_title.setText(f"Tiến Trình: {job.project_name}")
        self.log_title.setText(f"Nhật Ký: {job.project_name}")

        self._update_preflight_for_job(job)
        if hasattr(job, "step_states") and job.step_states:
            for code in self.step_codes:
                st = job.step_states.get(code, "pending")
                msg = ""
                if st == "running":
                    msg = "Đang xử lý..."
                elif st == "done":
                    msg = "Hoàn thành"
                elif st in ("error", "cancelled"):
                    msg = job.error_message or "Thất bại/Bị hủy"
                elif st == "pending":
                    msg = "Đang chờ..."
                self.update_step_widget(code, st, msg)
        else:
            self._update_stepper_ui(job.progress, job.status, job.error_message or "")

        self.log_terminal.clear()
        for line in job.logs:
            self.append_log(line)
            
        self.queue_table.blockSignals(True)
        for row in range(self.queue_table.rowCount()):
            item = self.queue_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == job_id:
                self.queue_table.selectRow(row)
                break
        self.queue_table.blockSignals(False)

    @Slot()
    def clear_logs(self) -> None:
        self.log_terminal.clear()
        if self.selected_job_id:
            for j in self.manager.jobs:
                if j.id == self.selected_job_id:
                    j.logs = ["[HỆ THỐNG] Đã xóa lịch sử log hiển thị."]
                    break
        self.append_log("[HỆ THỐNG] Đã xóa lịch sử log hiển thị.")

    def append_log(self, text: str) -> None:
        ts = _dt.now().strftime("%H:%M:%S")

        if "[LỖI]" in text or "[ERROR]" in text:
            color  = "#ff6b6b"
            prefix = "[LỖI]"
            weight = "bold"
        elif "[OK]" in text or "[THÀNH CÔNG]" in text or "[SUCCESS]" in text:
            color  = "#4ade80"
            prefix = "[OK]"
            weight = "bold"
        elif "[CẢNH BÁO]" in text or "[WARNING]" in text or "[WARN]" in text:
            color  = "#fbbf24"
            prefix = "[CẢNH BÁO]"
            weight = "bold"
        elif "[HỆ THỐNG]" in text:
            color  = "#c084fc"
            prefix = "[HỆ THỐNG]"
            weight = "normal"
        elif "[ĐANG" in text or "[INFO]" in text:
            color  = "#60a5fa"
            prefix = "[THÔNG TIN]"
            weight = "normal"
        else:
            color  = "#cbd5e1"
            prefix = "▶"
            weight = "normal"

        safe = _html.escape(text)
        html = (
            f'<div style="font-family: Consolas, monospace; font-size: 11px; '
            f'color: {color}; font-weight: {weight}; line-height: 1.5; margin-bottom: 2px;">'
            f'<span style="color: #94a3b8; font-size: 10px;">[{ts}]</span> '
            f'{prefix} {safe}</div>'
        )
        self.log_terminal.appendHtml(html)

        scrollbar = self.log_terminal.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_step_widget(self, code: str, status: str, message: str = "") -> None:
        widget = self.step_widgets.get(code)
        if not widget:
            return
            
        widget.setProperty("state", status)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        
        circle = widget.findChild(QLabel, "stepCircle")
        if circle:
            circle.setText("")
            if status == "pending":
                circle.clear()
            elif status == "running":
                circle.setPixmap(get_svg_icon("refresh", "#00F2FE", 14).pixmap(14, 14))
            elif status == "done":
                circle.setPixmap(get_svg_icon("check", "#22c55e", 14).pixmap(14, 14))
            elif status in ("error", "cancelled"):
                circle.setPixmap(get_svg_icon("x", "#ef4444", 14).pixmap(14, 14))
                
        status_lbl = self.step_status_labels.get(code)
        if status_lbl:
            if status == "pending":
                status_lbl.setText("Đang chờ...")
            elif status == "running":
                status_lbl.setText(message or "Đang xử lý...")
            elif status == "done":
                status_lbl.setText(message or "Hoàn thành")
            elif status in ("error", "cancelled"):
                status_lbl.setText(message or "Lỗi!")

    def _get_step_states(self, progress: int, status: str) -> dict:
        states = {code: "pending" for code in self.step_codes}
        
        if status == "completed":
            return {code: "done" for code in self.step_codes}
        elif status in ("cancelled", "failed"):
            err_state = "cancelled" if status == "cancelled" else "error"
            if progress < 25:
                states["preflight"] = err_state
            elif progress < 50:
                states["preflight"] = "done"
                states["scan_media"] = err_state
            elif progress < 75:
                states["preflight"] = "done"
                states["scan_media"] = "done"
                states["plan_media"] = err_state
            else:
                states["preflight"] = "done"
                states["scan_media"] = "done"
                states["plan_media"] = "done"
                states["write_draft"] = err_state
            return states
            
        if status == "pending":
            return states
            
        # status == "running"
        if progress < 25:
            states["preflight"] = "running"
        elif progress < 50:
            states["preflight"] = "done"
            states["scan_media"] = "running"
        elif progress < 75:
            states["preflight"] = "done"
            states["scan_media"] = "done"
            states["plan_media"] = "running"
        elif progress < 100:
            states["preflight"] = "done"
            states["scan_media"] = "done"
            states["plan_media"] = "done"
            states["write_draft"] = "running"
        else:
            for c in self.step_codes:
                states[c] = "done"
        return states

    def _update_stepper_ui(self, progress: int, status: str, message: str = "") -> None:
        states = self._get_step_states(progress, status)
        for code in self.step_codes:
            state = states[code]
            msg = ""
            if state == "running":
                msg = message or "Đang xử lý..."
            elif state == "done":
                msg = "Hoàn thành"
            elif state == "error":
                msg = "Thất bại/Bị hủy"
            elif state == "pending":
                msg = "Đang chờ..."
                
            self.update_step_widget(code, state, msg)

    def _update_preflight_for_job(self, job: BuildJob) -> None:
        if not job or not job.config:
            for code in ["ffmpeg", "voice", "srt", "media", "draft", "brand"]:
                self.update_preflight_widget(code, "pending", "Chờ kiểm tra...")
            return
            
        config = job.config
        
        # 1. FFmpeg
        from runtime_tools import resolve_ffmpeg, tool_first_line
        ffmpeg_bin = resolve_ffmpeg()
        if ffmpeg_bin:
            ffmpeg_ver = tool_first_line(ffmpeg_bin)
            ver = "v6.1"
            if ffmpeg_ver:
                for word in ffmpeg_ver.split():
                    if "version" in word.lower():
                        continue
                    if word.replace(".", "").replace("-", "").isalnum() or "." in word:
                        ver = word.split("-")[0]
                        if not ver.startswith("v"):
                            ver = "v" + ver
                        break
            ffmpeg_str = f"Phát hiện {ver}"
            ffmpeg_state = "done"
        else:
            ffmpeg_str = "Không tìm thấy"
            ffmpeg_state = "error"
        self.update_preflight_widget("ffmpeg", ffmpeg_state, ffmpeg_str)
        
        # 2. Giọng đọc
        import media_probe
        voice_path = Path(config.voice_path).expanduser() if config.voice_path else None
        if voice_path and voice_path.exists() and voice_path.is_file():
            ext = voice_path.suffix.upper().replace(".", "")
            voice_str = f"44.1kHz · {ext}"
            voice_state = "done"
        else:
            voice_str = "Chưa cấu hình"
            voice_state = "error"
        self.update_preflight_widget("voice", voice_state, voice_str)
        
        # 3. Phụ đề (SRT)
        srt_path = Path(config.srt_path).expanduser() if config.srt_path else None
        if srt_path and srt_path.exists() and srt_path.is_file():
            try:
                from capcut_draft_creator import parse_srt
                subtitles = parse_srt(str(srt_path))
                cnt = len(subtitles)
                
                srt_duration_sec = (subtitles[-1]["start"] + subtitles[-1]["duration"]) / 1e6 if cnt > 0 else 0
                voice_dur = 0
                if voice_path and voice_path.exists():
                    asset = media_probe.probe_media(voice_path)
                    if not asset.error:
                        voice_dur = asset.duration_us / 1e6
                
                if voice_dur > 0 and srt_duration_sec > voice_dur:
                    srt_str = "1 cảnh báo thời gian"
                    srt_state = "running"
                else:
                    srt_str = f"Hợp lệ ({cnt} dòng)"
                    srt_state = "done"
            except Exception:
                srt_str = "Lỗi parse SRT"
                srt_state = "error"
        else:
            srt_str = "Không dùng"
            srt_state = "done"
        self.update_preflight_widget("srt", srt_state, srt_str)
        
        # 4. Thư viện media
        media_dir = Path(config.media_dir).expanduser() if config.media_dir else None
        if media_dir and media_dir.exists() and media_dir.is_dir():
            extensions = media_probe.SUPPORTED_VISUAL_EXTENSIONS
            recursive_scan = config.recursive_scan
            cnt = 0
            try:
                iterator = media_dir.rglob("*") if recursive_scan else media_dir.iterdir()
                for p in iterator:
                    if p.is_file() and p.suffix.lower() in extensions:
                        cnt += 1
                media_str = f"{cnt} tài nguyên đã lập chỉ mục"
                media_state = "done" if cnt > 0 else "error"
            except Exception:
                media_str = "Lỗi quét media"
                media_state = "error"
        else:
            media_str = "Chưa cấu hình"
            media_state = "error"
        self.update_preflight_widget("media", media_state, media_str)
        
        # 5. Quyền draft
        draft_root = Path(config.draft_root).expanduser() if config.draft_root else None
        if draft_root and draft_root.exists() and draft_root.is_dir():
            try:
                import time
                test_file = draft_root / f".write_test_{int(time.time())}"
                test_file.write_text("test", encoding="utf-8")
                test_file.unlink()
                
                path_abbr = str(draft_root).replace("\\", "/")
                if len(path_abbr) > 15:
                    parts = path_abbr.split("/")
                    if len(parts) > 2:
                        path_abbr = parts[0] + "/.../" + parts[-1]
                    else:
                        path_abbr = path_abbr[:12] + "..."
                draft_perm_str = f"RW · {path_abbr}"
                draft_perm_state = "done"
            except Exception:
                draft_perm_str = "Không có quyền ghi"
                draft_perm_state = "error"
        else:
            draft_perm_str = "Không tìm thấy"
            draft_perm_state = "error"
        self.update_preflight_widget("draft", draft_perm_state, draft_perm_str)
        
        # 6. Bộ thương hiệu
        logo_path = Path(config.logo_path).expanduser() if config.logo_path else None
        if logo_path and logo_path.exists() and logo_path.is_file():
            brand_str = f"Đầy đủ ({logo_path.name})"
            brand_state = "done"
        else:
            brand_str = "Thiếu logo_white.png"
            brand_state = "running"
        self.update_preflight_widget("brand", brand_state, brand_str)

    def update_preflight_widget(self, code: str, status: str, message: str = "") -> None:
        widget = self.preflight_widgets.get(code)
        if not widget:
            return
            
        widget.setProperty("state", status)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        
        circle = widget.findChild(QLabel, "stepCircle")
        if circle:
            circle.setText("")
            if status == "pending":
                circle.clear()
            elif status == "running":
                circle.setPixmap(get_svg_icon("alert", "#eab308", 14).pixmap(14, 14))
            elif status == "done":
                circle.setPixmap(get_svg_icon("check", "#22c55e", 14).pixmap(14, 14))
            elif status in ("error", "cancelled"):
                circle.setPixmap(get_svg_icon("x", "#ef4444", 14).pixmap(14, 14))
                
        status_lbl = self.preflight_value_labels.get(code)
        if status_lbl:
            status_lbl.setText(message)

    def shutdown(self, wait_ms: int = 5000) -> bool:
        """
        Cleanly requests shutdown of active build queue jobs and worker threads.
        Returns True if safe to close, False otherwise.
        """
        try:
            from app.queue_manager import BatchQueueManager
            return BatchQueueManager.get_instance().shutdown(wait_ms=wait_ms)
        except Exception as e:
            print(f"Error during BuildWidget shutdown: {e}")
            return True
