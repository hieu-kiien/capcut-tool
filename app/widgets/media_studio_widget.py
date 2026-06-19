import os
import time
from pathlib import Path
from PySide6.QtCore import Qt, Signal, Slot, QThread, QObject, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QFrame,
    QProgressBar,
    QPlainTextEdit,
    QDoubleSpinBox,
    QSpinBox,
    QGridLayout,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QCheckBox
)
from assets.manager import AssetManager
from app.downloader import YtDlpDownloadRunner, DownloadOptions, parse_url_list

class ImportWorker(QThread):
    progress_signal = Signal(int, int)  # current, total
    finished_signal = Signal(int)       # success_count

    def __init__(self, file_paths: list[Path], category: str = "overlay", tags: str = ""):
        super().__init__()
        self.file_paths = file_paths
        self.category = category
        self.tags = tags

    def run(self):
        success_count = 0
        total = len(self.file_paths)
        for idx, path in enumerate(self.file_paths, 1):
            if self.isInterruptionRequested():
                break
            try:
                res = AssetManager.import_single_asset(
                    file_path=path,
                    category_name=self.category,
                    tags=self.tags
                )
                if res:
                    success_count += 1
            except Exception:
                pass
            self.progress_signal.emit(idx, total)
        self.finished_signal.emit(success_count)


class DownloadThread(QThread):
    progress_signal = Signal(str)
    item_progress_signal = Signal(int, str, str, str, str)  # idx, status, msg, output_path, error
    finished_signal = Signal(object)
    error_signal = Signal(str)

    def __init__(self, options: DownloadOptions):
        super().__init__()
        self.options = options
        self.runner = YtDlpDownloadRunner()

    def run(self):
        try:
            summary = self.runner.run(
                self.options,
                progress=self.on_progress,
                item_progress=self.on_item_progress
            )
            self.finished_signal.emit(summary)
        except Exception as e:
            self.error_signal.emit(str(e))

    def on_progress(self, msg: str):
        self.progress_signal.emit(msg)

    def on_item_progress(self, idx: int, status: str, message: str, output_path: str, error: str):
        self.item_progress_signal.emit(idx, status, message, output_path, error)

    def cancel(self):
        self.runner.cancel()


class CutterWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(str)  # output_path
    error_signal = Signal(str)

    def __init__(self, source_path: Path, dest_path: Path, start_sec: float, duration_sec: float):
        super().__init__()
        self.source_path = source_path
        self.dest_path = dest_path
        self.start_sec = start_sec
        self.duration_sec = duration_sec

    def run(self):
        try:
            from core.cutter import lossless_cut_video
            output = lossless_cut_video(
                self.source_path,
                self.dest_path,
                self.start_sec,
                self.duration_sec,
                log_callback=self.on_log
            )
            self.finished_signal.emit(str(output))
        except Exception as e:
            self.error_signal.emit(str(e))

    def on_log(self, msg: str):
        self.log_signal.emit(msg)


class EditAssetDialog(QDialog):
    def __init__(self, filename: str, category: str, tags: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chỉnh sửa tài nguyên")
        self.resize(400, 180)
        self._build_ui(filename, category, tags)

    def _build_ui(self, filename: str, category: str, tags: str) -> None:
        layout = QVBoxLayout(self)
        
        lbl_file = QLabel(f"Tệp: {filename}")
        lbl_file.setStyleSheet("font-weight: bold; color: #94a3b8;")
        layout.addWidget(lbl_file)
        
        form = QFormLayout()
        self.category_combo = QComboBox()
        self.category_combo.addItems(["overlay", "logo", "intro", "outro", "bgm", "transition"])
        idx = self.category_combo.findText(category)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        form.addRow("Danh mục:", self.category_combo)
        
        self.tags_edit = QLineEdit(tags)
        self.tags_edit.setPlaceholderText("Các nhãn cách nhau bằng dấu phẩy...")
        form.addRow("Nhãn (Tags):", self.tags_edit)
        
        layout.addLayout(form)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_data(self) -> tuple[str, str]:
        return self.category_combo.currentText(), self.tags_edit.text().strip()


class MediaStudioWidget(QWidget):
    log_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.import_worker = None
        self.dl_thread = None
        self.cutter_worker = None
        self._build_ui()
        self.refresh_library()

    def shutdown(self, wait_ms: int = 5000) -> bool:
        workers = [self.import_worker, self.dl_thread, self.cutter_worker]
        deadline = time.monotonic() + max(0, wait_ms) / 1000.0

        for worker in workers:
            if worker is None:
                continue
            try:
                worker.requestInterruption()
                if hasattr(worker, "cancel"):
                    worker.cancel()
            except RuntimeError:
                continue

        all_stopped = True
        for worker in workers:
            if worker is None:
                continue
            try:
                if worker.isRunning():
                    remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
                    if remaining_ms == 0 or not worker.wait(remaining_ms):
                        all_stopped = False
            except RuntimeError:
                continue
        return all_stopped

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # 1. Header (Title & Description)
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 4)
        header_layout.setSpacing(4)

        lbl_title = QLabel("Xưởng media")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
        lbl_subtitle = QLabel("Thu thập, phân tích và định hình tài nguyên hình ảnh/âm thanh trong dự án.")
        lbl_subtitle.setStyleSheet("font-size: 13px; color: #94a3b8;")
        
        header_layout.addWidget(lbl_title)
        header_layout.addWidget(lbl_subtitle)
        main_layout.addWidget(header_widget)

        # 2. Tabbed Panel
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.08);
                background-color: #111827;
                border-radius: 8px;
                padding: 4px;
            }
            QTabBar::tab {
                background: #1f2937;
                color: #9ca3af;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 16px;
                margin-right: 4px;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background: #374151;
                color: #ffffff;
            }
            QTabBar::tab:selected {
                background: #111827;
                color: #ffffff;
                border-color: rgba(255, 255, 255, 0.12);
                border-bottom: 2px solid #8b5cf6;
            }
        """)

        # Tab 1: Library & Scan Warnings
        self.library_tab = QWidget()
        self._build_library_tab()
        self.tab_widget.addTab(self.library_tab, "📂 Thư viện tài nguyên")

        # Tab 2: Downloader
        self.downloader_tab = QWidget()
        self._build_downloader_tab()
        self.tab_widget.addTab(self.downloader_tab, "📥 Tải media (Downloader)")

        # Tab 3: Video Cutter
        self.cutter_tab = QWidget()
        self._build_cutter_tab()
        self.tab_widget.addTab(self.cutter_tab, "✂️ Cắt video (FFmpeg)")

        main_layout.addWidget(self.tab_widget, 1)

    def _build_library_tab(self) -> None:
        layout = QHBoxLayout(self.library_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Left panel: Preview + Warnings
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # Media Preview Card
        preview_card = QFrame()
        preview_card.setStyleSheet("background-color: #0f172a; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05);")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(6)

        lbl_preview_title = QLabel("🎬 Xem trước media")
        lbl_preview_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; border: none;")
        preview_layout.addWidget(lbl_preview_title)

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setStyleSheet("background-color: transparent; border: none;")
        
        self.preview_grid_widget = QWidget()
        self.preview_grid_widget.setStyleSheet("background-color: transparent;")
        self.preview_grid_layout = QGridLayout(self.preview_grid_widget)
        self.preview_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_grid_layout.setSpacing(8)
        
        preview_scroll.setWidget(self.preview_grid_widget)
        preview_layout.addWidget(preview_scroll, 1)
        left_layout.addWidget(preview_card, 3)

        # Scan Warnings Card
        warnings_card = QFrame()
        warnings_card.setStyleSheet("background-color: #0f172a; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05);")
        warnings_layout = QVBoxLayout(warnings_card)
        warnings_layout.setContentsMargins(12, 12, 12, 12)
        warnings_layout.setSpacing(6)

        lbl_scan_title = QLabel("⚠️ Cảnh báo & Lỗi tệp")
        lbl_scan_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; border: none;")
        warnings_layout.addWidget(lbl_scan_title)

        self.scan_warnings_list = QListWidget()
        self.scan_warnings_list.setStyleSheet("""
            QListWidget {
                background-color: #0b0f19;
                border: 1px solid #1e293b;
                border-radius: 4px;
                padding: 4px;
            }
            QListWidget::item {
                border-bottom: 1px solid rgba(255, 255, 255, 0.02);
                padding: 4px;
                font-size: 11px;
            }
        """)
        warnings_layout.addWidget(self.scan_warnings_list, 1)
        left_layout.addWidget(warnings_card, 2)

        layout.addWidget(left_panel, 2)

        # Right panel: Table + Actions
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: #0f172a; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05);")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)

        lbl_lib_title = QLabel("📂 Danh sách tài nguyên đã nhập")
        lbl_lib_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; border: none;")
        right_layout.addWidget(lbl_lib_title)

        # Search and filter
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Tìm kiếm theo tên tệp hoặc nhãn...")
        self.search_edit.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 4px;")
        self.search_edit.textChanged.connect(self.refresh_library)
        filter_row.addWidget(self.search_edit, 3)

        self.filter_category = QComboBox()
        self.filter_category.addItem("Tất cả danh mục", "all")
        self.filter_category.addItem("Lớp phủ (overlay)", "overlay")
        self.filter_category.addItem("Logo thương hiệu (logo)", "logo")
        self.filter_category.addItem("Mở đầu (intro)", "intro")
        self.filter_category.addItem("Kết thúc (outro)", "outro")
        self.filter_category.addItem("Nhạc nền (bgm)", "bgm")
        self.filter_category.addItem("Chuyển cảnh (transition)", "transition")
        self.filter_category.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 2px;")
        self.filter_category.currentIndexChanged.connect(self.refresh_library)
        filter_row.addWidget(self.filter_category, 2)
        right_layout.addLayout(filter_row)

        # Import Buttons
        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.setSpacing(8)
        
        self.btn_import_files = QPushButton("📁 Nhập tệp")
        self.btn_import_files.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.btn_import_files.clicked.connect(self._on_import_files_click)
        action_buttons_layout.addWidget(self.btn_import_files)

        self.btn_import_dir = QPushButton("📂 Nhập thư mục")
        self.btn_import_dir.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.btn_import_dir.clicked.connect(self._on_import_dir_click)
        action_buttons_layout.addWidget(self.btn_import_dir)
        right_layout.addLayout(action_buttons_layout)

        # Import Progress Frame
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        self.progress_frame.setStyleSheet("background-color: #0b0f19; border-radius: 6px; padding: 6px; border: 1px solid #1e293b;")
        progress_layout = QHBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(6, 6, 6, 6)
        self.lbl_progress = QLabel("Đang nhập tài nguyên...")
        self.lbl_progress.setStyleSheet("font-size: 11px; color: #94a3b8; border: none;")
        progress_layout.addWidget(self.lbl_progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
                text-align: center;
                height: 12px;
                font-size: 9px;
            }
            QProgressBar::chunk {
                background-color: #8b5cf6;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.progress_bar, 1)
        right_layout.addWidget(self.progress_frame)

        # Resources Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Tên tệp", "Loại", "Danh mục", "Thời lượng", "Độ phân giải", "Nhãn (Tags)", "Hành động"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0b0f19;
                gridline-color: #1e293b;
                border: 1px solid #1e293b;
                border-radius: 4px;
                color: #e2e8f0;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #ffffff;
                padding: 6px;
                border: none;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 6px;
            }
        """)
        self.table.doubleClicked.connect(self._on_table_double_clicked)
        right_layout.addWidget(self.table, 1)

        layout.addWidget(right_panel, 3)

    def _build_downloader_tab(self) -> None:
        layout = QVBoxLayout(self.downloader_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        dl_card = QFrame()
        dl_card.setStyleSheet("background-color: #0f172a; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05);")
        dl_layout = QVBoxLayout(dl_card)
        dl_layout.setContentsMargins(16, 16, 16, 16)
        dl_layout.setSpacing(12)

        lbl_dl_title = QLabel("📥 Tải tài nguyên từ URL (YouTube, TikTok, Facebook, ...)")
        lbl_dl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; border: none;")
        dl_layout.addWidget(lbl_dl_title)

        self.download_urls_edit = QPlainTextEdit()
        self.download_urls_edit.setPlaceholderText("Nhập danh sách URL cần tải, mỗi dòng một URL.")
        self.download_urls_edit.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 6px;")
        self.download_urls_edit.setMaximumHeight(120)
        dl_layout.addWidget(self.download_urls_edit)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Output folder row
        self.download_out_edit = QLineEdit()
        self.download_out_edit.setPlaceholderText("Thư mục lưu tệp tải về...")
        self.download_out_edit.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 4px;")
        btn_browse_out = QPushButton("📂")
        btn_browse_out.setToolTip("Chọn thư mục lưu")
        btn_browse_out.setFixedSize(32, 24)
        btn_browse_out.setStyleSheet("background-color: #1e293b; color: #ffffff; border: 1px solid #334155; border-radius: 4px;")
        btn_browse_out.clicked.connect(self._on_browse_dl_out)
        out_layout = QHBoxLayout()
        out_layout.addWidget(self.download_out_edit, 1)
        out_layout.addWidget(btn_browse_out)
        form_layout.addRow("Lưu vào:", out_layout)

        # Cookies row
        self.download_cookies_edit = QLineEdit()
        self.download_cookies_edit.setPlaceholderText("Đường dẫn file cookies (không bắt buộc)...")
        self.download_cookies_edit.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 4px;")
        btn_browse_cookies = QPushButton("🔑")
        btn_browse_cookies.setToolTip("Chọn tệp cookies.txt")
        btn_browse_cookies.setFixedSize(32, 24)
        btn_browse_cookies.setStyleSheet("background-color: #1e293b; color: #ffffff; border: 1px solid #334155; border-radius: 4px;")
        btn_browse_cookies.clicked.connect(self._on_browse_dl_cookies)
        cookies_layout = QHBoxLayout()
        cookies_layout.addWidget(self.download_cookies_edit, 1)
        cookies_layout.addWidget(btn_browse_cookies)
        form_layout.addRow("Cookies:", cookies_layout)

        # Tool & Kind
        self.download_tool_combo = QComboBox()
        self.download_tool_combo.addItems(["yt-dlp", "gallery-dl"])
        self.download_tool_combo.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 2px;")
        
        self.download_kind_combo = QComboBox()
        self.download_kind_combo.addItems(["Video", "Audio"])
        self.download_kind_combo.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 2px;")
        
        tool_layout = QHBoxLayout()
        tool_layout.addWidget(self.download_tool_combo, 1)
        tool_layout.addWidget(QLabel("Loại:"), 0, Qt.AlignRight)
        tool_layout.addWidget(self.download_kind_combo, 1)
        form_layout.addRow("Công cụ:", tool_layout)
        dl_layout.addLayout(form_layout)

        # Advanced downloader config
        self.download_max_file_size_mb = QDoubleSpinBox()
        self.download_max_file_size_mb.setRange(0, 999999)
        self.download_max_file_size_mb.setValue(4096)
        self.download_max_file_size_mb.setSuffix(" MB")
        self.download_max_file_size_mb.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 2px;")

        self.download_stall_timeout_sec = QDoubleSpinBox()
        self.download_stall_timeout_sec.setRange(0, 999999)
        self.download_stall_timeout_sec.setValue(180)
        self.download_stall_timeout_sec.setSuffix(" s")
        self.download_stall_timeout_sec.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 2px;")

        self.download_item_timeout_sec = QDoubleSpinBox()
        self.download_item_timeout_sec.setRange(0, 999999)
        self.download_item_timeout_sec.setValue(7200)
        self.download_item_timeout_sec.setSuffix(" s")
        self.download_item_timeout_sec.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 2px;")

        self.download_workers_spin = QSpinBox()
        self.download_workers_spin.setRange(1, 4)
        self.download_workers_spin.setValue(2)
        self.download_workers_spin.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 2px;")

        adv_grid = QGridLayout()
        adv_grid.setVerticalSpacing(8)
        adv_grid.setHorizontalSpacing(10)
        adv_grid.addWidget(QLabel("Giới hạn size:"), 0, 0)
        adv_grid.addWidget(self.download_max_file_size_mb, 0, 1)
        adv_grid.addWidget(QLabel("Số luồng:"), 0, 2)
        adv_grid.addWidget(self.download_workers_spin, 0, 3)
        adv_grid.addWidget(QLabel("Timeout treo:"), 1, 0)
        adv_grid.addWidget(self.download_stall_timeout_sec, 1, 1)
        adv_grid.addWidget(QLabel("Timeout tệp:"), 1, 2)
        adv_grid.addWidget(self.download_item_timeout_sec, 1, 3)
        dl_layout.addLayout(adv_grid)

        # Progress Layout for Downloader
        self.dl_progress_frame = QFrame()
        self.dl_progress_frame.setVisible(False)
        self.dl_progress_frame.setStyleSheet("background-color: #0b0f19; border-radius: 6px; padding: 8px; border: 1px solid #1e293b;")
        dl_progress_layout = QVBoxLayout(self.dl_progress_frame)
        dl_progress_layout.setContentsMargins(8, 8, 8, 8)
        dl_progress_layout.setSpacing(6)
        self.lbl_dl_progress = QLabel("Bắt đầu tải...")
        self.lbl_dl_progress.setStyleSheet("font-size: 11px; color: #94a3b8; border: none;")
        self.dl_progress_bar = QProgressBar()
        self.dl_progress_bar.setRange(0, 100)
        self.dl_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
                text-align: center;
                height: 16px;
                font-size: 10px;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #8b5cf6;
                border-radius: 3px;
            }
        """)
        dl_progress_layout.addWidget(self.lbl_dl_progress)
        dl_progress_layout.addWidget(self.dl_progress_bar)
        dl_layout.addWidget(self.dl_progress_frame)

        # Action Buttons
        dl_buttons_layout = QHBoxLayout()
        self.btn_run_download = QPushButton("🚀 Tải xuống")
        self.btn_run_download.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: #ffffff;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.btn_run_download.clicked.connect(self._on_start_download)
        
        self.btn_cancel_download = QPushButton("🛑 Hủy")
        self.btn_cancel_download.setEnabled(False)
        self.btn_cancel_download.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.btn_cancel_download.clicked.connect(self._on_cancel_download)

        dl_buttons_layout.addWidget(self.btn_run_download, 1)
        dl_buttons_layout.addWidget(self.btn_cancel_download)
        dl_layout.addLayout(dl_buttons_layout)

        layout.addWidget(dl_card, 1)

    def _build_cutter_tab(self) -> None:
        layout = QVBoxLayout(self.cutter_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        cut_card = QFrame()
        cut_card.setStyleSheet("background-color: #0f172a; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05);")
        cut_layout = QVBoxLayout(cut_card)
        cut_layout.setContentsMargins(16, 16, 16, 16)
        cut_layout.setSpacing(12)

        lbl_cut_title = QLabel("✂️ Cắt video không mất chất lượng (Lossless Cut)")
        lbl_cut_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; border: none;")
        cut_layout.addWidget(lbl_cut_title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        # Source video file
        self.cutter_source_edit = QLineEdit()
        self.cutter_source_edit.setPlaceholderText("Đường dẫn tệp video nguồn cần cắt...")
        self.cutter_source_edit.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 4px;")
        btn_browse_src = QPushButton("📂")
        btn_browse_src.setToolTip("Chọn tệp video nguồn")
        btn_browse_src.setFixedSize(32, 24)
        btn_browse_src.setStyleSheet("background-color: #1e293b; color: #ffffff; border: 1px solid #334155; border-radius: 4px;")
        btn_browse_src.clicked.connect(self._on_browse_cutter_src)
        src_layout = QHBoxLayout()
        src_layout.addWidget(self.cutter_source_edit, 1)
        src_layout.addWidget(btn_browse_src)
        form.addRow("Tệp nguồn:", src_layout)

        # Time controls (Start, Duration)
        self.cutter_start_spin = QDoubleSpinBox()
        self.cutter_start_spin.setRange(0.0, 999999.0)
        self.cutter_start_spin.setValue(0.0)
        self.cutter_start_spin.setDecimals(3)
        self.cutter_start_spin.setSingleStep(1.0)
        self.cutter_start_spin.setSuffix(" s")
        self.cutter_start_spin.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 2px;")

        self.cutter_duration_spin = QDoubleSpinBox()
        self.cutter_duration_spin.setRange(0.1, 999999.0)
        self.cutter_duration_spin.setValue(10.0)
        self.cutter_duration_spin.setDecimals(3)
        self.cutter_duration_spin.setSingleStep(1.0)
        self.cutter_duration_spin.setSuffix(" s")
        self.cutter_duration_spin.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 2px;")

        time_layout = QHBoxLayout()
        time_layout.addWidget(self.cutter_start_spin, 1)
        time_layout.addWidget(QLabel("Thời lượng:"), 0, Qt.AlignRight)
        time_layout.addWidget(self.cutter_duration_spin, 1)
        form.addRow("Bắt đầu từ:", time_layout)

        # Output video file
        self.cutter_dest_edit = QLineEdit()
        self.cutter_dest_edit.setPlaceholderText("Đường dẫn lưu tệp video đã cắt...")
        self.cutter_dest_edit.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 4px;")
        btn_browse_dst = QPushButton("📂")
        btn_browse_dst.setToolTip("Chọn nơi lưu video kết quả")
        btn_browse_dst.setFixedSize(32, 24)
        btn_browse_dst.setStyleSheet("background-color: #1e293b; color: #ffffff; border: 1px solid #334155; border-radius: 4px;")
        btn_browse_dst.clicked.connect(self._on_browse_cutter_dst)
        dst_layout = QHBoxLayout()
        dst_layout.addWidget(self.cutter_dest_edit, 1)
        dst_layout.addWidget(btn_browse_dst)
        form.addRow("Lưu thành:", dst_layout)

        # Auto import settings
        self.cutter_auto_import_chk = QCheckBox("Tự động nhập vào Thư viện tài nguyên sau khi cắt thành công")
        self.cutter_auto_import_chk.setChecked(True)
        self.cutter_auto_import_chk.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        
        self.cutter_import_category = QComboBox()
        self.cutter_import_category.addItems(["overlay", "logo", "intro", "outro", "bgm", "transition"])
        self.cutter_import_category.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 2px;")
        
        self.cutter_import_tags = QLineEdit("cut")
        self.cutter_import_tags.setPlaceholderText("Các tag ngăn cách bằng dấu phẩy...")
        self.cutter_import_tags.setStyleSheet("background-color: #0b0f19; color: #ffffff; border: 1px solid #1e293b; border-radius: 4px; padding: 4px;")

        import_settings = QHBoxLayout()
        import_settings.addWidget(self.cutter_auto_import_chk, 2)
        import_settings.addWidget(QLabel("Danh mục:"), 0, Qt.AlignRight)
        import_settings.addWidget(self.cutter_import_category, 1)
        import_settings.addWidget(QLabel("Tags:"), 0, Qt.AlignRight)
        import_settings.addWidget(self.cutter_import_tags, 1)
        form.addRow("Nhập thư viện:", import_settings)

        cut_layout.addLayout(form)

        # Cutter Progress Bar (hidden initially)
        self.cutter_progress_bar = QProgressBar()
        self.cutter_progress_bar.setRange(0, 0)  # Marquee indicator during FFmpeg process
        self.cutter_progress_bar.setVisible(False)
        self.cutter_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
                height: 12px;
            }
            QProgressBar::chunk {
                background-color: #8b5cf6;
                border-radius: 3px;
            }
        """)
        cut_layout.addWidget(self.cutter_progress_bar)

        # Cutter Log Display
        self.cutter_log_text = QPlainTextEdit()
        self.cutter_log_text.setReadOnly(True)
        self.cutter_log_text.setPlaceholderText("Tiến trình và log của FFmpeg sẽ hiển thị tại đây...")
        self.cutter_log_text.setStyleSheet("""
            background-color: #0b0f19;
            color: #10b981;
            font-family: Consolas, monospace;
            font-size: 11px;
            border: 1px solid #1e293b;
            border-radius: 4px;
            padding: 6px;
        """)
        self.cutter_log_text.setMaximumHeight(100)
        cut_layout.addWidget(self.cutter_log_text)

        # Run button
        self.btn_run_cut = QPushButton("🚀 Bắt đầu cắt (Lossless Cut)")
        self.btn_run_cut.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: #ffffff;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.btn_run_cut.clicked.connect(self._on_start_cutting)
        cut_layout.addWidget(self.btn_run_cut)

        layout.addWidget(cut_card, 1)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = []
        for url in event.mimeData().urls():
            local_path = Path(url.toLocalFile())
            if local_path.exists():
                paths.append(local_path)
        
        if paths:
            self._process_import_paths(paths)

    def _on_import_files_click(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn tệp tài nguyên",
            "",
            "Media Files (*.mp4 *.mov *.png *.jpg *.jpeg *.webp *.mp3 *.wav)"
        )
        if files:
            paths = [Path(f) for f in files]
            self._process_import_paths(paths)

    def _on_import_dir_click(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa tài nguyên")
        if directory:
            path = Path(directory)
            self._process_import_paths([path])

    def _process_import_paths(self, paths: list[Path]) -> None:
        file_paths = []
        video_exts = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".heic", ".heif"}
        audio_exts = {".mp3", ".wav", ".m4a", ".flac"}
        supported_exts = video_exts | image_exts | audio_exts

        for p in paths:
            if p.is_file():
                if p.suffix.lower() in supported_exts:
                    file_paths.append(p)
            elif p.is_dir():
                for item in p.iterdir():
                    if item.is_file() and item.suffix.lower() in supported_exts:
                        file_paths.append(item)

        if not file_paths:
            QMessageBox.warning(self, "Thông báo", "Không tìm thấy tệp tin đa phương tiện được hỗ trợ.")
            return

        # Prompt for default category and tags
        from PySide6.QtWidgets import QInputDialog
        category, ok = QInputDialog.getItem(
            self,
            "Chọn danh mục mặc định",
            f"Chọn danh mục cho {len(file_paths)} tệp tài nguyên:",
            ["overlay", "logo", "intro", "outro", "bgm", "transition"],
            0,
            False
        )
        if not ok:
            return

        tags, ok = QInputDialog.getText(
            self,
            "Gán nhãn mặc định",
            "Nhập nhãn gán cho tài nguyên (cách nhau bằng dấu phẩy):"
        )
        if not ok:
            return

        # Start Async Worker
        self.progress_frame.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_progress.setText(f"Đang nhập tài nguyên: 0/{len(file_paths)}")
        self._set_ui_enabled(False)

        self.import_worker = ImportWorker(file_paths, category, tags)
        self.import_worker.progress_signal.connect(self._on_import_progress)
        self.import_worker.finished_signal.connect(self._on_import_finished)
        self.import_worker.start()

    def _on_import_progress(self, current: int, total: int) -> None:
        pct = int((current / total) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_progress.setText(f"Đang nhập tài nguyên: {current}/{total}")

    def _on_import_finished(self, success_count: int) -> None:
        self.progress_frame.setVisible(False)
        self._set_ui_enabled(True)
        self.import_worker = None
        
        self.log_requested.emit(f"[HỆ THỐNG] Đã nhập thành công {success_count} tệp tài nguyên vào thư viện.")
        QMessageBox.information(self, "Thành công", f"Đã nhập thành công {success_count} tệp tài nguyên!")
        self.refresh_library()

    def _set_ui_enabled(self, enabled: bool) -> None:
        self.search_edit.setEnabled(enabled)
        self.filter_category.setEnabled(enabled)
        self.btn_import_files.setEnabled(enabled)
        self.btn_import_dir.setEnabled(enabled)
        self.table.setEnabled(enabled)
        
        # Disable/enable downloader buttons too
        self.btn_run_download.setEnabled(enabled)
        self.download_urls_edit.setEnabled(enabled)
        self.download_out_edit.setEnabled(enabled)
        self.download_cookies_edit.setEnabled(enabled)
        self.download_tool_combo.setEnabled(enabled)
        self.download_kind_combo.setEnabled(enabled)

    def refresh_library(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        category = self.filter_category.currentData()
        search = self.search_edit.text().strip()

        assets = AssetManager.list_assets(category_name=category, search_query=search)
        self.table.setRowCount(len(assets))

        for idx, a in enumerate(assets):
            item_name = QTableWidgetItem(a["filename"])
            item_name.setData(Qt.ItemDataRole.UserRole, a["id"])
            item_name.setToolTip(a["path"])
            
            item_type = QTableWidgetItem(a["media_type"])
            item_cat = QTableWidgetItem(a["category_name"])
            
            dur_sec = a["duration_us"] / 1_000_000
            dur_str = f"{dur_sec:.2f}s" if dur_sec > 0 else "-"
            item_dur = QTableWidgetItem(dur_str)
            
            res_str = f"{a['width']}x{a['height']}" if a["width"] > 0 else "-"
            item_res = QTableWidgetItem(res_str)
            
            item_tags = QTableWidgetItem(a["tags"])
            
            self.table.setItem(idx, 0, item_name)
            self.table.setItem(idx, 1, item_type)
            self.table.setItem(idx, 2, item_cat)
            self.table.setItem(idx, 3, item_dur)
            self.table.setItem(idx, 4, item_res)
            self.table.setItem(idx, 5, item_tags)

            btn_delete = QPushButton("Xóa")
            btn_delete.setStyleSheet("background-color: #ef4444; padding: 2px; border: none; border-radius: 3px; color: #ffffff;")
            btn_delete.clicked.connect(lambda checked=False, asset_id=a["id"]: self._on_delete_click(asset_id))
            self.table.setCellWidget(idx, 6, btn_delete)

        self.table.setSortingEnabled(True)
        
        self.update_scan_warnings()
        self.refresh_preview_grid()

    def _on_delete_click(self, asset_id: str) -> None:
        asset = AssetManager.get_asset(asset_id)
        if not asset:
            return
            
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa tài nguyên '{asset['filename']}' khỏi thư viện?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        if AssetManager.delete_asset(asset_id):
            self.log_requested.emit(f"[HỆ THỐNG] Đã xóa tài nguyên '{asset['filename']}' khỏi thư viện.")
            self.refresh_library()

    def _on_table_double_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
            
        item = self.table.item(row, 0)
        asset_id = item.data(Qt.ItemDataRole.UserRole)
        asset = AssetManager.get_asset(asset_id)
        if not asset:
            return
            
        dialog = EditAssetDialog(asset["filename"], asset["category_name"], asset["tags"], self)
        if dialog.exec() == QDialog.Accepted:
            cat, tags = dialog.get_data()
            if AssetManager.update_asset_metadata(asset_id, tags=tags, category_name=cat):
                self.log_requested.emit(f"[HỆ THỐNG] Đã cập nhật tài nguyên '{asset['filename']}' thành công.")
                self.refresh_library()

    # --- DOWNLOADER ACTIONS ---
    def _on_browse_dl_out(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu media tải về")
        if directory:
            self.download_out_edit.setText(directory)

    def _on_browse_dl_cookies(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn cookies file", "", "Text files (*.txt)")
        if file_path:
            self.download_cookies_edit.setText(file_path)

    def _on_start_download(self) -> None:
        urls_text = self.download_urls_edit.toPlainText().strip()
        if not urls_text:
            QMessageBox.warning(self, "Thông báo", "Vui lòng nhập danh sách URL cần tải.")
            return
            
        output_dir = self.download_out_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "Thông báo", "Vui lòng chọn thư mục lưu.")
            return

        try:
            urls = parse_url_list(urls_text)
        except ValueError as e:
            QMessageBox.warning(self, "Lỗi URL", str(e))
            return

        tool = self.download_tool_combo.currentText()
        url_tools = [tool] * len(urls)
        kind = "audio" if self.download_kind_combo.currentText() == "Audio" else "video"

        options = DownloadOptions(
            urls=urls,
            output_dir=output_dir,
            cookies_file=self.download_cookies_edit.text().strip(),
            max_file_size_mb=int(self.download_max_file_size_mb.value()),
            stall_timeout_sec=int(self.download_stall_timeout_sec.value()),
            item_timeout_sec=int(self.download_item_timeout_sec.value()),
            workers=int(self.download_workers_spin.value()),
            download_kind=kind,
            url_tools=url_tools
        )

        self._set_ui_enabled(False)
        self.btn_run_download.setEnabled(False)
        self.btn_cancel_download.setEnabled(True)
        self.dl_progress_frame.setVisible(True)
        self.dl_progress_bar.setValue(0)
        self.lbl_dl_progress.setText("Bắt đầu tải...")
        self.log_requested.emit(f"[HỆ THỐNG] Bắt đầu tải {len(urls)} đường dẫn media...")

        self.dl_thread = DownloadThread(options)
        self.dl_thread.progress_signal.connect(self._on_dl_thread_progress)
        self.dl_thread.item_progress_signal.connect(self._on_dl_item_progress)
        self.dl_thread.finished_signal.connect(self._on_dl_thread_finished)
        self.dl_thread.error_signal.connect(self._on_dl_thread_error)
        self.dl_thread.start()

    def _on_dl_thread_progress(self, msg: str) -> None:
        self.lbl_dl_progress.setText(msg)
        self.log_requested.emit(msg)

    def _on_dl_item_progress(self, idx: int, status: str, message: str, output_path: str, error: str) -> None:
        msg = f"Tệp {idx+1}: {message}"
        if status == "completed":
            msg = f"Tệp {idx+1}: Hoàn thành!"
        elif status == "failed":
            msg = f"Tệp {idx+1}: Thất bại ({error})"
        self.lbl_dl_progress.setText(msg)

    def _on_dl_thread_finished(self, summary) -> None:
        self._set_ui_enabled(True)
        self.btn_run_download.setEnabled(True)
        self.btn_cancel_download.setEnabled(False)
        self.dl_progress_frame.setVisible(False)
        
        self.log_requested.emit(f"[HỆ THỐNG] Tải hoàn tất: Thành công {summary.succeeded}/{summary.total}")
        
        import_count = 0
        for res in summary.results:
            if res.status == "completed" and res.output_path:
                path = Path(res.output_path)
                if path.exists():
                    ext = path.suffix.lower()
                    if ext in {".mp3", ".wav", ".m4a", ".flac"}:
                        cat = "bgm"
                    elif ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                        cat = "logo"
                    else:
                        cat = "overlay"
                    
                    try:
                        res_import = AssetManager.import_single_asset(
                            file_path=path,
                            category_name=cat,
                            tags="downloaded"
                        )
                        if res_import:
                            import_count += 1
                    except Exception as e:
                        self.log_requested.emit(f"[CẢNH BÁO] Không thể tự động nhập tệp {path.name}: {e}")

        if import_count > 0:
            self.log_requested.emit(f"[HỆ THỐNG] Đã tự động nhập {import_count} tệp tải về vào thư viện.")
            self.refresh_library()
        else:
            QMessageBox.information(self, "Hoàn tất", f"Đã tải xong! Thành công: {summary.succeeded}, Thất bại: {summary.failed}")
            
        self.dl_thread = None

    def _on_dl_thread_error(self, err_msg: str) -> None:
        self._set_ui_enabled(True)
        self.btn_run_download.setEnabled(True)
        self.btn_cancel_download.setEnabled(False)
        self.dl_progress_frame.setVisible(False)
        self.log_requested.emit(f"[LỖI] Tải thất bại: {err_msg}")
        QMessageBox.critical(self, "Lỗi tải", f"Gặp lỗi khi tải: {err_msg}")
        self.dl_thread = None

    def _on_cancel_download(self) -> None:
        if self.dl_thread:
            self.dl_thread.cancel()
            self.log_requested.emit("[HỆ THỐNG] Đang yêu cầu hủy tải...")
            self.btn_cancel_download.setEnabled(False)

    # --- SCAN WARNINGS LOGIC ---
    def get_current_canvas_ratio(self) -> str:
        try:
            parent = self.parent()
            while parent:
                if hasattr(parent, "setup_widget"):
                    setup = parent.setup_widget
                    if hasattr(setup, "ratio_16_9") and setup.ratio_16_9.isChecked():
                        return "16:9"
                    return "9:16"
                parent = parent.parent()
        except Exception:
            pass
        return "9:16"

    def update_scan_warnings(self) -> None:
        self.scan_warnings_list.clear()
        
        # Get active canvas ratio
        canvas_ratio = self.get_current_canvas_ratio()
        
        # Check downloader out directory
        media_dir = self.download_out_edit.text().strip()
        if not media_dir or not os.path.exists(media_dir):
            # Fallback to scanning database assets
            try:
                assets = AssetManager.list_assets()
                for a in assets:
                    fname = a["filename"]
                    suffix = Path(fname).suffix.lower()
                    
                    if suffix in {".heic", ".heif"}:
                        item = QListWidgetItem(f"• {fname} — codec không hỗ trợ (HEIC/HEIF)")
                        item.setForeground(Qt.red)
                        self.scan_warnings_list.addItem(item)
                    elif a["width"] == 0 and a["height"] == 0 and a["media_type"] in {"video", "image"}:
                        item = QListWidgetItem(f"• {fname} — header bị hỏng hoặc lỗi định dạng")
                        item.setForeground(Qt.red)
                        self.scan_warnings_list.addItem(item)
                    else:
                        width = a.get("width", 0)
                        height = a.get("height", 0)
                        if width > 0 and height > 0:
                            is_vertical = width < height
                            if canvas_ratio == "9:16" and not is_vertical:
                                item = QListWidgetItem(f"• {fname} — sai tỉ lệ (media ngang/vuông trong canvas dọc)")
                                item.setForeground(Qt.yellow)
                                self.scan_warnings_list.addItem(item)
                            elif canvas_ratio == "16:9" and is_vertical:
                                item = QListWidgetItem(f"• {fname} — sai tỉ lệ (media dọc/vuông trong canvas ngang)")
                                item.setForeground(Qt.yellow)
                                self.scan_warnings_list.addItem(item)
            except Exception:
                pass
            return

        # Directory scanning via core.media
        try:
            from core.media import scan_media_directory
            res = scan_media_directory(media_dir, recursive=False, canvas_ratio=canvas_ratio)
            
            # Populate warnings
            for warn in res["warnings"]:
                fname = warn["filename"]
                err = warn["error"]
                severity = warn["severity"]
                item = QListWidgetItem(f"• {fname} — {err}")
                if severity == "error":
                    item.setForeground(Qt.red)
                else:
                    item.setForeground(Qt.yellow)
                self.scan_warnings_list.addItem(item)
                
            # If no warnings found
            if not res["warnings"] and not res["valid"]:
                item = QListWidgetItem("Chưa có tệp nào trong thư mục media.")
                item.setStyleSheet("color: #cbd5e1; font-style: italic;")
                self.scan_warnings_list.addItem(item)
                
        except Exception as e:
            item = QListWidgetItem(f"Lỗi phân tích: {e}")
            item.setForeground(Qt.red)
            self.scan_warnings_list.addItem(item)

    # --- MEDIA PREVIEW GRID ---
    def refresh_preview_grid(self) -> None:
        while self.preview_grid_layout.count():
            item = self.preview_grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        try:
            assets = AssetManager.list_assets()
            media_assets = [a for a in assets if a["media_type"] in {"video", "image"}]
            
            if not media_assets:
                lbl_placeholder = QLabel("Chưa có tệp hình ảnh hoặc video nền nào.")
                lbl_placeholder.setStyleSheet("color: #cbd5e1; font-style: italic; border: none;")
                lbl_placeholder.setAlignment(Qt.AlignCenter)
                self.preview_grid_layout.addWidget(lbl_placeholder, 0, 0)
                return

            cols = 3
            for idx, a in enumerate(media_assets):
                row = idx // cols
                col = idx % cols
                
                card = self._create_media_preview_card(a)
                self.preview_grid_layout.addWidget(card, row, col)
        except Exception:
            pass

    def _create_media_preview_card(self, asset: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QFrame:hover {
                border-color: #8b5cf6;
            }
        """)
        card.setFixedSize(115, 130)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        
        lbl_thumb = QLabel()
        lbl_thumb.setFixedSize(103, 62)
        lbl_thumb.setAlignment(Qt.AlignCenter)
        lbl_thumb.setStyleSheet("background-color: #0b0f19; border-radius: 4px; border: none;")
        
        is_video = asset["media_type"] == "video"
        path = asset["path"]
        
        if not is_video and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                lbl_thumb.setPixmap(pixmap.scaled(103, 62, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                lbl_thumb.setText("🖼️ Ảnh")
        else:
            lbl_thumb.setText("🎥 Video" if is_video else "📁 Tệp")
            lbl_thumb.setStyleSheet("background-color: #0b0f19; border-radius: 4px; color: #8b5cf6; font-weight: bold; border: none;")
            
        layout.addWidget(lbl_thumb)
        
        lbl_name = QLabel(asset["filename"])
        lbl_name.setStyleSheet("font-size: 10px; color: #e2e8f0; border: none;")
        lbl_name.setAlignment(Qt.AlignCenter)
        name = asset["filename"]
        if len(name) > 13:
            name = name[:10] + "..."
        lbl_name.setText(name)
        lbl_name.setToolTip(asset["filename"])
        layout.addWidget(lbl_name)
        
        btn_view = QPushButton("Xem" if not is_video else "Phát")
        btn_view.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: #ffffff;
                font-size: 10px;
                border: none;
                border-radius: 3px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
        """)
        btn_view.clicked.connect(lambda checked=False, p=path: self._on_preview_media(p))
        layout.addWidget(btn_view)
        
        return card

    def _on_preview_media(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy tệp tài nguyên.")
            return
            
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    # --- VIDEO CUTTER ACTIONS ---
    def _on_browse_cutter_src(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn tệp video nguồn",
            "",
            "Video Files (*.mp4 *.mov *.m4v *.avi *.mkv *.webm)"
        )
        if file_path:
            self.cutter_source_edit.setText(file_path)
            
            # Automatically suggest a default output path
            src_path = Path(file_path)
            suggested_dst = src_path.parent / f"cut_{src_path.name}"
            self.cutter_dest_edit.setText(str(suggested_dst))

    def _on_browse_cutter_dst(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Chọn nơi lưu video đã cắt",
            self.cutter_dest_edit.text() or "",
            "Video Files (*.mp4 *.mov *.m4v *.avi *.mkv *.webm)"
        )
        if file_path:
            self.cutter_dest_edit.setText(file_path)

    def _on_start_cutting(self) -> None:
        src_text = self.cutter_source_edit.text().strip()
        dst_text = self.cutter_dest_edit.text().strip()
        
        if not src_text or not os.path.exists(src_text):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn tệp video nguồn hợp lệ.")
            return
        if not dst_text:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn nơi lưu video kết quả.")
            return

        start_sec = self.cutter_start_spin.value()
        duration_sec = self.cutter_duration_spin.value()
        
        if duration_sec <= 0:
            QMessageBox.warning(self, "Lỗi", "Thời lượng cắt phải lớn hơn 0.")
            return

        self.btn_run_cut.setEnabled(False)
        self.cutter_progress_bar.setVisible(True)
        self.cutter_log_text.clear()
        
        self.cutter_worker = CutterWorker(Path(src_text), Path(dst_text), start_sec, duration_sec)
        self.cutter_worker.log_signal.connect(self._on_cutter_log)
        self.cutter_worker.error_signal.connect(self._on_cutter_error)
        self.cutter_worker.finished_signal.connect(self._on_cutter_finished)
        
        self.log_requested.emit(f"[HỆ THỐNG] Bắt đầu cắt lossless từ {src_text}...")
        self.cutter_worker.start()

    def _on_cutter_log(self, msg: str) -> None:
        self.cutter_log_text.appendPlainText(msg)
        self.log_requested.emit(msg)

    def _on_cutter_error(self, err_msg: str) -> None:
        self.btn_run_cut.setEnabled(True)
        self.cutter_progress_bar.setVisible(False)
        QMessageBox.critical(self, "Lỗi cắt video", f"FFmpeg báo lỗi:\n{err_msg}")
        self.cutter_worker = None

    def _on_cutter_finished(self, out_path_str: str) -> None:
        self.btn_run_cut.setEnabled(True)
        self.cutter_progress_bar.setVisible(False)
        
        out_path = Path(out_path_str)
        msg = f"[HỆ THỐNG] Cắt video hoàn tất! Tệp lưu tại: {out_path.name}"
        self.cutter_log_text.appendPlainText(msg)
        self.log_requested.emit(msg)
        
        # Auto import if checked
        if self.cutter_auto_import_chk.isChecked():
            category = self.cutter_import_category.currentText()
            tags = self.cutter_import_tags.text().strip()
            
            try:
                asset_id = AssetManager.import_single_asset(
                    file_path=out_path,
                    category_name=category,
                    tags=tags
                )
                if asset_id:
                    self.log_requested.emit(f"[HỆ THỐNG] Đã tự động nhập video cắt '{out_path.name}' vào thư viện.")
                    self.refresh_library()
            except Exception as e:
                self.log_requested.emit(f"[CẢNH BÁO] Không thể tự động nhập video cắt: {e}")
                
        QMessageBox.information(self, "Thành công", f"Đã cắt video thành công!\nTệp kết quả: {out_path.name}")
        self.cutter_worker = None
