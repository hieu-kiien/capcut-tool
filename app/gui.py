from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QStackedWidget,
)

import capcut_keyframe_tool as keyframe_tool
from app.pipeline import PipelineRunner, ProjectConfig, StepResult
from app.presets import KEYFRAME_PRESETS, TRANSITION_PRESETS
from core.path_validation import validate_project_name
from app.widgets import DashboardWidget, SetupWidget, EffectsWidget, BuildWidget, HistoryWidget, MediaStudioWidget
from profiles.manager import ProfileManager
from app.controllers import (
    ProfileController,
    SettingsController,
    DoctorController,
    EffectsController,
)
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction
from datetime import datetime
from app.theme import (
    COLOR_TEAL, COLOR_CARD_BG, COLOR_CARD_BORDER, COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_DARK_ZINC, COLOR_SIDEBAR_BG, COLOR_BG_CONSOLE, COLOR_TEXT_CONSOLE,
    COLOR_TEXT_WHITE, COLOR_TEXT_LIGHT, COLOR_TEXT_BLACK
)

from app.icons import get_svg_icon
from app.workers import PipelineWorker, KeyframeWorker, SplitWorker, ScanWorker, log_signaler
from app.utils import hex_to_rgb_tuple, rgb_tuple_to_hex
from app.queue_manager import BatchQueueManager
from app.theme import get_application_stylesheet

from app.controllers.effects_controller import _PRESET_GROUP_MAP


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from core.db import Database
        Database.init_db()
        self.setWindowTitle("CapCut Long Story Studio")
        self.resize(1200, 800)

        self.thread: QThread | None = None
        self.worker: PipelineWorker | KeyframeWorker | None = None

        self._current_profile_id: str | None = None
        self._current_profile_name: str = "Mặc định"

        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None
        self._scan_threads: list[QThread] = []
        self._scan_workers: list[ScanWorker] = []
        self._scan_generation = 0
        self._last_scan_request: tuple[str, bool] | None = None
        self._scan_debounce_timer = QTimer(self)
        self._scan_debounce_timer.setSingleShot(True)
        self._scan_debounce_timer.setInterval(350)
        self._scan_debounce_timer.timeout.connect(self._start_media_scan)

        self._preflight_debounce_timer = QTimer(self)
        self._preflight_debounce_timer.setSingleShot(True)
        self._preflight_debounce_timer.setInterval(500)
        self._preflight_debounce_timer.timeout.connect(self._update_dashboard_summary)

        self.notifications_list = []

        self._build_ui()

        # Configure logging callback and setup file logging thread-safely
        import core.logger as cc_logger
        log_signaler.log_received.connect(self.dashboard_widget.append_log)

        def on_logger_log(msg: str):
            log_signaler.log_received.emit(msg)

        cc_logger.add_log_callback(on_logger_log)

        root_dir = Path(__file__).resolve().parents[1]
        cc_logger.setup_file_logging(root_dir / ".capcut_tool_jobs")
        self.settings_controller = SettingsController(self)
        self.doctor_controller = DoctorController(self)
        self.effects_controller = EffectsController(self)

        self._load_config()

        # Auto clean backups on startup based on the Retention Policy
        try:
            keep_days = int(self.history_widget.backup_keep_days.value())
            import draft_doctor
            deleted = draft_doctor.clean_all_backups_retention(keep_days)
            if deleted > 0:
                self._append_log(f"[HỆ THỐNG] Dọn dẹp tự động lúc khởi động: Đã xóa {deleted} tệp sao lưu cũ hơn {keep_days} ngày.")
        except Exception as e:
            cc_logger.logger.warning(f"Error doing startup backups cleanup: {e}")
        self.profile_controller = ProfileController(self)
        self.profile_controller._refresh_profiles_list(self._current_profile_name)

        # Connect profile UI signals
        self.profile_combo.currentIndexChanged.connect(self.profile_controller._on_profile_selection_changed)
        self.btn_save_profile.clicked.connect(self._on_build_now)  # Connect Quick Build to _on_build_now workflow
        self.action_save_profile.triggered.connect(self.profile_controller._save_current_profile)
        self.action_new_profile.triggered.connect(self.profile_controller._create_new_profile_click)
        self.action_clone_profile.triggered.connect(self.profile_controller._clone_profile_click)
        self.action_rename_profile.triggered.connect(self.profile_controller._rename_profile_click)
        self.action_delete_profile.triggered.connect(self.profile_controller._delete_profile_click)
        self.action_rollback_profile.triggered.connect(self.profile_controller._rollback_profile_click)
        self.action_export_profile.triggered.connect(self.profile_controller._export_profile_click)
        self.action_import_profile.triggered.connect(self.profile_controller._import_profile_click)

        # Connect Setup header preset action signals
        self.setup_widget.save_profile_requested.connect(lambda: self.profile_controller._save_current_profile(silent=False))
        self.setup_widget.clone_profile_requested.connect(self.profile_controller._clone_profile_click)
        self.setup_widget.export_profile_requested.connect(self.profile_controller._export_profile_click)
        self.setup_widget.import_profile_requested.connect(self.profile_controller._import_profile_click)

        # Connect media_dir change signals for ScanWorker
        self.setup_widget.media_dir.textChanged.connect(self._on_media_dir_changed)
        self.setup_widget.recursive_scan.toggled.connect(self._on_media_dir_changed)

        self._apply_style()
        self._switch_to_page("dashboard")

        # State listener to transition header status to 'Cần kiểm tra' when any configuration input is edited
        def on_input_changed():
            self.update_status_pill("needs_checking")
            self._preflight_debounce_timer.start()

        # Connect text/config changes to update dashboard stats via debounce
        self.setup_widget.draft_root.textChanged.connect(self._refresh_projects)
        self.setup_widget.draft_root.textChanged.connect(on_input_changed)
        self.setup_widget.draft_root.textChanged.connect(self._update_disk_usage)  # update disk usage label
        self.setup_widget.project_name.textChanged.connect(on_input_changed)
        self.setup_widget.voice_path.textChanged.connect(on_input_changed)
        self.setup_widget.media_dir.textChanged.connect(on_input_changed)
        self.setup_widget.bgm_path.textChanged.connect(on_input_changed)
        self.setup_widget.srt_path.textChanged.connect(on_input_changed)
        self.setup_widget.intro_combo.currentIndexChanged.connect(on_input_changed)
        self.setup_widget.outro_combo.currentIndexChanged.connect(on_input_changed)
        self.effects_widget.logo_path.textChanged.connect(on_input_changed)
        self.effects_widget.anim_path.textChanged.connect(on_input_changed)
        self.setup_widget.auto_kf_combo.currentIndexChanged.connect(on_input_changed)
        self.setup_widget.ratio_16_9.toggled.connect(on_input_changed)

        # Call initial disk usage check
        self._update_disk_usage()

        # Connect queue manager finished notifications
        BatchQueueManager.get_instance().job_finished.connect(self._on_job_finished_notification)

        def bind_change_listeners(widget: QWidget):
            for child in widget.findChildren(QWidget):
                if isinstance(child, QLineEdit):
                    child.textChanged.connect(on_input_changed)
                elif isinstance(child, (QRadioButton, QCheckBox)):
                    child.toggled.connect(on_input_changed)
                elif isinstance(child, (QDoubleSpinBox, QSpinBox)):
                    child.valueChanged.connect(on_input_changed)
                elif isinstance(child, QComboBox):
                    child.currentIndexChanged.connect(on_input_changed)

        bind_change_listeners(self.setup_widget)
        bind_change_listeners(self.effects_widget)

        self._update_dashboard_summary()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Left Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 20, 10, 20)
        sidebar_layout.setSpacing(8)

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(4, 0, 4, 0)
        logo_row.setSpacing(8)
        logo_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        logo_icon = QFrame()
        logo_icon.setObjectName("logoIcon")
        logo_icon.setFixedSize(20, 20)
        logo_row.addWidget(logo_icon)
 
        logo_label = QLabel("Vortex Studio")
        logo_label.setObjectName("appTitle")
        logo_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        logo_row.addWidget(logo_label)
        logo_row.addStretch()
        sidebar_layout.addLayout(logo_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); margin: 10px 0;")
        sidebar_layout.addWidget(sep)

        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "Bảng điều khiển", "dashboard"),
            ("project-setup", "Thiết lập dự án", "settings"),
            ("media-studio", "Xưởng media", "folder"),
            ("effects", "Hiệu ứng & Thương hiệu", "sparkles"),
            ("build-center", "Trung tâm dựng", "rocket"),
            ("history", "Lịch sử & Phục hồi", "history"),
        ]

        from app.icons import get_svg_icon
        for code, label, icon_name in nav_items:
            btn = QPushButton(f"  {label}")
            btn.setIcon(get_svg_icon(icon_name, color=COLOR_TEXT_SECONDARY, size=18))
            btn.setObjectName("navButton")
            btn.setProperty("code", code)
            btn.setProperty("icon_name", icon_name)
            btn.setProperty("active", "false")
            btn.clicked.connect(self._on_nav_clicked)
            sidebar_layout.addWidget(btn)
            self.nav_buttons[code] = btn

        # Disk usage indicator at the bottom of the sidebar
        self.disk_usage_widget = QFrame()
        self.disk_usage_widget.setObjectName("diskUsageCard")
        self.disk_usage_widget.setStyleSheet(f"""
            QFrame#diskUsageCard {{
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 8px;
                padding: 10px;
                margin-top: 10px;
            }}
        """)
        disk_layout = QVBoxLayout(self.disk_usage_widget)
        disk_layout.setContentsMargins(8, 8, 8, 8)
        disk_layout.setSpacing(4)

        disk_title = QLabel("Dung lượng ổ đĩa")
        disk_title.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px; font-weight: bold; text-transform: uppercase;")
        disk_layout.addWidget(disk_title)

        self.disk_path_label = QLabel("Draft Root: --")
        self.disk_path_label.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
        disk_layout.addWidget(self.disk_path_label)

        self.disk_bar = QProgressBar()
        self.disk_bar.setFixedHeight(6)
        self.disk_bar.setRange(0, 100)
        self.disk_bar.setValue(0)
        self.disk_bar.setTextVisible(False)
        self.disk_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_TEAL};
                border-radius: 3px;
            }}
        """)
        disk_layout.addWidget(self.disk_bar)

        self.disk_text_label = QLabel("Trống: -- / --")
        self.disk_text_label.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 500;")
        disk_layout.addWidget(self.disk_text_label)

        sidebar_layout.addWidget(self.disk_usage_widget)

        sidebar_layout.addStretch()
        main_layout.addWidget(self.sidebar)

        # 2. Right Workspace Content Area
        workspace_container = QWidget()
        workspace_layout = QVBoxLayout(workspace_container)
        workspace_layout.setContentsMargins(20, 20, 20, 20)
        workspace_layout.setSpacing(15)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 10)

        title_box = QVBoxLayout()
        title_row = QHBoxLayout()

        # Breadcrumbs
        lbl_breadcrumbs = QLabel("Dự án / ")
        lbl_breadcrumbs.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-weight: 500; font-size: 13px;")
        title_row.addWidget(lbl_breadcrumbs)

        self.header_title = QLabel("Campaign_Beta_2024")
        self.header_title.setObjectName("appTitle")
        title_row.addWidget(self.header_title)

        # Status Pill
        self.status_pill = QLabel("● SẴN SÀNG DỰNG")
        self.status_pill.setStyleSheet(f"""
            background-color: rgba(16, 185, 129, 0.15);
            color: {COLOR_SUCCESS};
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
        """)
        title_row.addWidget(self.status_pill)

        title_row.addStretch()

        # 1-Click Launch CapCut PC Action Button
        self.btn_launch_capcut = QPushButton("  Mở CapCut PC")
        self.btn_launch_capcut.setIcon(get_svg_icon("capcut", color="#ffffff", size=16))
        self.btn_launch_capcut.setToolTip("Tự động định vị và mở ứng dụng CapCut PC")
        self.btn_launch_capcut.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00F2FE, stop:1 #7F00FF);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
        """)
        self.btn_launch_capcut.clicked.connect(self._launch_capcut_direct)
        title_row.addWidget(self.btn_launch_capcut)

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setReadOnly(False)
        self.search_bar.setPlaceholderText("Tìm nhanh project, media, preset...")
        self.search_bar.setMinimumWidth(250)
        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLOR_SIDEBAR_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        title_row.addWidget(self.search_bar)

        # Profile Selector Layout in Header
        profile_layout = QHBoxLayout()
        profile_layout.setSpacing(6)

        profile_lbl = QLabel("PRESET:")
        profile_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px; font-weight: bold;")
        title_row.addWidget(profile_lbl)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(150)
        self.profile_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: transparent;
                border: none;
                padding: 3px 6px;
                color: {COLOR_TEXT_WHITE};
                font-weight: bold;
                font-size: 12px;
            }}
        """)
        title_row.addWidget(self.profile_combo)

        self.btn_save_profile = QPushButton("  Dựng nhanh")
        self.btn_save_profile.setIcon(get_svg_icon("play", color="#ffffff", size=14))
        self.btn_save_profile.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SUCCESS};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        profile_layout.addWidget(self.btn_save_profile)

        self.btn_profile_opts = QPushButton("  Tùy chọn")
        self.btn_profile_opts.setIcon(get_svg_icon("settings", color="#ffffff", size=14))
        self.btn_profile_opts.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_CARD_BORDER};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.08);
            }}
        """)

        # QMenu for options
        self.profile_menu = QMenu(self)
        self.profile_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLOR_CARD_BG};
                color: {COLOR_TEXT_WHITE};
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
            QMenu::item:selected {{
                background-color: {COLOR_CARD_BORDER};
            }}
        """)

        self.action_save_profile = QAction("Lưu cấu hình hồ sơ", self)
        self.action_new_profile = QAction("Tạo hồ sơ mới", self)
        self.action_clone_profile = QAction("Nhân bản hồ sơ", self)
        self.action_rename_profile = QAction("Đổi tên hồ sơ", self)
        self.action_delete_profile = QAction("Xóa hồ sơ", self)
        self.action_rollback_profile = QAction("Lịch sử phiên bản / Rollback", self)
        self.action_export_profile = QAction("Xuất lên mây (Export)", self)
        self.action_import_profile = QAction("Nhập từ mây (Import)", self)

        self.profile_menu.addAction(self.action_save_profile)
        self.profile_menu.addSeparator()
        self.profile_menu.addAction(self.action_new_profile)
        self.profile_menu.addAction(self.action_clone_profile)
        self.profile_menu.addAction(self.action_rename_profile)
        self.profile_menu.addAction(self.action_delete_profile)
        self.profile_menu.addSeparator()
        self.profile_menu.addAction(self.action_rollback_profile)
        self.profile_menu.addSeparator()
        self.profile_menu.addAction(self.action_export_profile)
        self.profile_menu.addAction(self.action_import_profile)

        self.btn_profile_opts.setMenu(self.profile_menu)
        profile_layout.addWidget(self.btn_profile_opts)

        # Notification Bell Button
        self.btn_notifications = QPushButton()
        self.btn_notifications.setIcon(get_svg_icon("bell", color="#ffffff", size=16))
        self.btn_notifications.setToolTip("Thông báo hệ thống")
        self.btn_notifications.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_CARD_BORDER};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.08);
            }}
        """)
        self.btn_notifications.clicked.connect(self._show_notifications_menu)
        profile_layout.addWidget(self.btn_notifications)

        title_row.addLayout(profile_layout)

        title_box.addLayout(title_row)
        subtitle = QLabel("Tự động dựng timeline từ Voice/BGM & Tùy chỉnh Keyframe / Hiệu ứng chuyển cảnh chuyên sâu")
        subtitle.setObjectName("appSubtitle")
        title_box.addWidget(subtitle)

        header_layout.addLayout(title_box)
        workspace_layout.addWidget(header)

        self.stacked_widget = QStackedWidget()

        # Instantiate widgets
        self.dashboard_widget = DashboardWidget()
        self.setup_widget = SetupWidget()
        self.media_studio_widget = MediaStudioWidget()

        self.setup_widget.media_dir.textChanged.connect(self.media_studio_widget.set_download_output_dir)
        self.media_studio_widget.set_download_output_dir(self.setup_widget.media_dir.text())

        self.effects_widget = EffectsWidget()
        self.build_widget = BuildWidget()
        self.history_widget = HistoryWidget()

        self.stacked_widget.addWidget(self.dashboard_widget)
        self.stacked_widget.addWidget(self.setup_widget)
        self.stacked_widget.addWidget(self.media_studio_widget)
        self.stacked_widget.addWidget(self.effects_widget)
        self.stacked_widget.addWidget(self.build_widget)
        self.stacked_widget.addWidget(self.history_widget)

        # Connect media studio log signal
        self.media_studio_widget.log_requested.connect(self._append_log)

        workspace_layout.addWidget(self.stacked_widget, 1)
        main_layout.addWidget(workspace_container, 1)

        # Wire Signals/Slots for modular widgets
        self.effects_widget.project_combo.currentTextChanged.connect(self._on_project_selected_sync)
        self.history_widget.project_combo.currentTextChanged.connect(self._on_project_selected_sync)
        self.effects_widget.btn_refresh_projects.clicked.connect(self._refresh_projects)
        self.history_widget.btn_refresh_projects.clicked.connect(self._refresh_projects)
        self.effects_widget.btn_apply_effect.clicked.connect(self._apply_effect_click)
        self.history_widget.btn_restore_backup.clicked.connect(self._restore_backup_click)
        self.history_widget.btn_clean_backups.clicked.connect(self._clean_backups_click)
        self.history_widget.btn_repair_project.clicked.connect(self._repair_project_click)
        self.build_widget.run_requested.connect(self._start_pipeline)
        self.build_widget.cancel_requested.connect(self._cancel_pipeline)
        self.build_widget.add_to_queue_requested.connect(self._on_add_to_queue)
        self.setup_widget.add_to_queue_requested.connect(self._on_add_to_queue)
        self.setup_widget.build_now_requested.connect(self._on_build_now)
        self.dashboard_widget.build_center_requested.connect(lambda: self._switch_to_page("build-center"))
        self.dashboard_widget.repair_draft_requested.connect(lambda: self._switch_to_page("history"))
        self.dashboard_widget.build_draft_requested.connect(self._on_build_now)

    def _download_options_from_ui(self, urls: list[str] = None, url_tools: list[str] = None) -> Any:
        return self.media_studio_widget.get_download_options(urls=urls, url_tools=url_tools)

    @property
    def download_urls_edit(self):
        return self.media_studio_widget.download_urls_edit

    @property
    def download_out_edit(self):
        return self.media_studio_widget.download_out_edit

    @property
    def download_cookies_edit(self):
        return self.media_studio_widget.download_cookies_edit

    @property
    def download_max_file_size_mb(self):
        return self.media_studio_widget.download_max_file_size_mb

    @property
    def download_stall_timeout_sec(self):
        return self.media_studio_widget.download_stall_timeout_sec

    @property
    def download_item_timeout_sec(self):
        return self.media_studio_widget.download_item_timeout_sec


    @Slot()
    def _on_media_dir_changed(self) -> None:
        path_str = self.setup_widget.media_dir.text().strip()
        if not path_str:
            self._scan_debounce_timer.stop()
            return
        path = Path(path_str)
        if not path.exists() or not path.is_dir():
            self._scan_debounce_timer.stop()
            return

        self._scan_debounce_timer.start()

    @Slot()
    def _start_media_scan(self) -> None:
        path_str = self.setup_widget.media_dir.text().strip()
        if not path_str:
            return
        path = Path(path_str)
        if not path.exists() or not path.is_dir():
            return

        recursive = self.setup_widget.recursive_scan.isChecked()
        request = (str(path), recursive)
        if request == self._last_scan_request and self._scan_threads:
            return

        self._last_scan_request = request
        self._cancel_scan_threads(wait_ms=0)
        self._scan_generation += 1
        scan_id = self._scan_generation

        self._scan_thread = QThread(self)
        self._scan_worker = ScanWorker(path, recursive=recursive, scan_id=scan_id)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_threads.append(self._scan_thread)
        self._scan_workers.append(self._scan_worker)

        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.failed.connect(lambda message, sid=scan_id: self._on_scan_failed(message, sid))

        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.failed.connect(self._scan_thread.quit)

        self._scan_worker.finished.connect(self._scan_worker.deleteLater)
        self._scan_worker.failed.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.finished.connect(
            lambda thread=self._scan_thread, worker=self._scan_worker: self._on_scan_thread_finished(thread, worker)
        )

        self._scan_thread.start()

    def _cancel_scan_threads(self, wait_ms: int = 0) -> bool:
        self._scan_debounce_timer.stop()
        for worker in list(self._scan_workers):
            try:
                worker.cancel()
            except RuntimeError:
                pass
        for thread in list(self._scan_threads):
            try:
                if thread.isRunning():
                    thread.requestInterruption()
                    thread.quit()
                    if wait_ms > 0:
                        thread.wait(wait_ms)
            except RuntimeError:
                pass
        for thread in list(self._scan_threads):
            try:
                if thread.isRunning():
                    thread.terminate()
                    thread.wait(200)
            except RuntimeError:
                continue
        return True

    def _on_scan_thread_finished(self, thread: QThread, worker: ScanWorker) -> None:
        if thread in self._scan_threads:
            self._scan_threads.remove(thread)
        if worker in self._scan_workers:
            self._scan_workers.remove(worker)
        if self._scan_thread is thread:
            self._scan_thread = self._scan_threads[-1] if self._scan_threads else None
        if self._scan_worker is worker:
            self._scan_worker = self._scan_workers[-1] if self._scan_workers else None

    @Slot(dict)
    def _on_scan_finished(self, result: dict) -> None:
        if result.get("scan_id") != self._scan_generation:
            return
        if result.get("cancelled"):
            self._append_log("[HỆ THỐNG] Đã hủy quét thư mục media.")
            return

        videos = result.get("videos", 0)
        images = result.get("images", 0)
        others = result.get("others", 0)
        total_size_mb = result.get("total_size", 0) / (1024 * 1024)

        self._append_log(
            f"[HỆ THỐNG] Quét thư mục media hoàn tất: {videos} video, {images} ảnh, {others} tệp khác. Tổng dung lượng: {total_size_mb:.2f} MB"
        )

    @Slot(str)
    def _on_scan_failed(self, message: str, scan_id: int | None = None) -> None:
        if scan_id is not None and scan_id != self._scan_generation:
            return
        self._append_log(f"[HỆ THỐNG] Quét thư mục media thất bại: {message}")

    @Slot()
    def _on_nav_clicked(self) -> None:
        btn = self.sender()
        if not btn:
            return
        code = btn.property("code")
        self._switch_to_page(code)

    def _switch_to_page(self, code: str) -> None:
        pages = {
            "dashboard": (0, "Bảng điều khiển"),
            "project-setup": (1, "Thiết lập dự án"),
            "media-studio": (2, "Xưởng media"),
            "effects": (3, "Hiệu ứng & Thương hiệu"),
            "build-center": (4, "Trung tâm dựng"),
            "history": (5, "Lịch sử & Phục hồi"),
        }

        if code not in pages:
            return

        page_idx, title = pages[code]
        self.stacked_widget.setCurrentIndex(page_idx)
        self.header_title.setText(title)

        if code == "media-studio":
            self.media_studio_widget.refresh_library()
        elif code == "project-setup":
            self.setup_widget.refresh_intro_outro_combos()

        # Update button active states
        from app.icons import get_svg_icon
        for c, btn in self.nav_buttons.items():
            is_active = (c == code)
            icon_name = btn.property("icon_name") or "folder"
            btn.setIcon(get_svg_icon(icon_name, color="#00F2FE" if is_active else COLOR_TEXT_SECONDARY, size=18))
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    @Slot(str)
    def _on_project_selected_sync(self, project_name: str) -> None:
        sender = self.sender()
        if sender == self.effects_widget.project_combo:
            self.history_widget.project_combo.blockSignals(True)
            idx = self.history_widget.project_combo.findText(project_name)
            if idx >= 0:
                self.history_widget.project_combo.setCurrentIndex(idx)
            self.history_widget.project_combo.blockSignals(False)
        elif sender == self.history_widget.project_combo:
            self.effects_widget.project_combo.blockSignals(True)
            idx = self.effects_widget.project_combo.findText(project_name)
            if idx >= 0:
                self.effects_widget.project_combo.setCurrentIndex(idx)
            self.effects_widget.project_combo.blockSignals(False)

        self._refresh_backups_for_project(project_name)

    def _update_dashboard_summary(self) -> None:
        name = self.setup_widget.project_name.text().strip()
        canvas = "16:9 Ngang" if self.setup_widget.ratio_16_9.isChecked() else "9:16 Dọc"
        preset = self.setup_widget.auto_kf_combo.currentText()
        fps = "60.00"
        path = self.setup_widget.draft_root.text().strip()

        # 1. Voice duration
        voice_dur_sec = 0.0
        voice_str = "00:00:00"
        voice = self.setup_widget.voice_path.text().strip()
        if voice and Path(voice).exists():
            try:
                from pymediainfo import MediaInfo
                info = MediaInfo.parse(voice)
                for track in info.tracks:
                    if track.track_type == 'Audio':
                        dur_ms = track.duration
                        if dur_ms:
                            voice_dur_sec = float(dur_ms) / 1000.0
                            sec = int(voice_dur_sec)
                            h = sec // 3600
                            m = (sec % 3600) // 60
                            s = sec % 60
                            voice_str = f"{h:02d}:{m:02d}:{s:02d}"
                            break
            except Exception:
                voice_str = "--:--:--"

        # 2. Timeline estimate (Voice + Intro + Outro)
        timeline_sec = voice_dur_sec

        def get_media_duration(media_path_str: str) -> float:
            if not media_path_str:
                return 0.0
            p = Path(media_path_str)
            if not p.exists() or not p.is_file():
                return 0.0
            try:
                from pymediainfo import MediaInfo
                info = MediaInfo.parse(p)
                for track in info.tracks:
                    if track.track_type in ('Audio', 'Video'):
                        dur_ms = track.duration
                        if dur_ms:
                            return float(dur_ms) / 1000.0
            except Exception:
                pass
            return 0.0

        intro_path = self.setup_widget.intro_combo.currentData() or ""
        outro_path = self.setup_widget.outro_combo.currentData() or ""
        timeline_sec += get_media_duration(intro_path)
        timeline_sec += get_media_duration(outro_path)

        sec = int(timeline_sec)
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        timeline_str = f"{h:02d}:{m:02d}:{s:02d}"

        # 3. Last compiled from SQLite
        last_compiled = "Chưa biên dịch"
        try:
            from core.db import Database
            conn = Database.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT created_at FROM history WHERE project_name = ? AND status = 'completed' ORDER BY created_at DESC LIMIT 1",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                from datetime import datetime
                try:
                    dt = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                    diff = datetime.now() - dt
                    diff_sec = diff.total_seconds()
                    if diff_sec < 60:
                        last_compiled = "Vừa xong"
                    elif diff_sec < 3600:
                        last_compiled = f"{int(diff_sec // 60)} phút trước"
                    elif diff_sec < 86400:
                        last_compiled = f"{int(diff_sec // 3600)} giờ trước"
                    else:
                        last_compiled = f"{int(diff_sec // 86400)} ngày trước"
                except Exception:
                    last_compiled = row[0]
        except Exception:
            pass

        # Update summary details
        self.dashboard_widget.update_project_summary(
            name, canvas, preset, fps, path, last_compiled, voice_str, timeline_str
        )

        # 4. Resource Readiness & AI Checker
        # We will run preflight using a dynamic config dictionary
        canvas_ratio = "16:9" if self.setup_widget.ratio_16_9.isChecked() else "9:16"
        selection_idx = self.setup_widget.selection_mode.currentIndex()
        selection_mode = {
            1: "sequential",
            2: "random",
            3: "duplicate_then_shuffle",
            4: "shuffle_duplicates_only",
        }.get(selection_idx, "shuffle_bag")
        short_video_mode = "loop" if self.setup_widget.short_video_mode.currentIndex() == 1 else "stretch"

        cfg = {
            "project_name": name,
            "draft_root": path,
            "voice_path": voice,
            "media_dir": self.setup_widget.media_dir.text().strip(),
            "bgm_path": self.setup_widget.bgm_path.text().strip(),
            "srt_path": self.setup_widget.srt_path.text().strip(),
            "intro_path": intro_path,
            "outro_path": outro_path,
            "logo_path": self.effects_widget.logo_path.text().strip(),
            "logo_position": self.effects_widget.logo_position.currentData() or "top_right",
            "logo_scale": self.effects_widget.logo_scale.value(),
            "anim_path": self.effects_widget.anim_path.text().strip(),
            "anim_position": self.effects_widget.anim_position.currentData() or "bottom_center",
            "anim_scale": self.effects_widget.anim_scale.value(),
            "anim_timing": self.effects_widget.anim_timing.currentData() or "end",
            "canvas": canvas_ratio,
            "clip_min_sec": self.setup_widget.clip_min.value(),
            "clip_max_sec": self.setup_widget.clip_max.value(),
            "selection_mode": selection_mode,
            "short_video_mode": short_video_mode,
            "recursive_scan": self.setup_widget.recursive_scan.isChecked(),
            "auto_keyframe": self.setup_widget.auto_kf_combo.currentData(),
            "auto_transition": self.setup_widget.auto_trans_combo.currentData(),
            "auto_transition_duration": self.setup_widget.auto_trans_dur.value(),
            "bg_switch_mode": self.setup_widget.bg_switch_mode.currentData() or "time",
            "bg_switch_group_size": self.setup_widget.bg_switch_group_size.value()
        }

        # Run preflight report
        from app.preflight import run_preflight
        report = run_preflight(cfg, fast_mode=True)

        # Map details to readiness
        voice_ok = bool(voice and Path(voice).exists())
        srt_lines = report.srt_lines_count
        media_count = report.media_count
        bgm_ok = bool(cfg["bgm_path"] and Path(cfg["bgm_path"]).exists())
        logo_ok = bool(cfg["logo_path"] and Path(cfg["logo_path"]).exists())
        anim_ok = bool(cfg["anim_path"] and Path(cfg["anim_path"]).exists())
        intro_ok = bool(intro_path and Path(intro_path).exists())
        outro_ok = bool(outro_path and Path(outro_path).exists())

        self.dashboard_widget.update_resource_readiness(
            voice_ok, srt_lines, media_count, bgm_ok, logo_ok, anim_ok, intro_ok, outro_ok
        )

        # Update AI Checker Panel
        self.dashboard_widget.update_preflight_issues(report.issues)

        # Update header status pill based on preflight result
        if report.can_run:
            self.update_status_pill("ready")
            self.btn_save_profile.setEnabled(True)
            self.dashboard_widget.btn_build_draft.setEnabled(True)
        else:
            self.update_status_pill("needs_checking")
            self.btn_save_profile.setEnabled(False)
            self.dashboard_widget.btn_build_draft.setEnabled(False)

    def _update_disk_usage(self) -> None:
        import shutil
        path_str = self.setup_widget.draft_root.text().strip()
        if not path_str:
            self.disk_path_label.setText("Draft Root: --")
            self.disk_text_label.setText("Trống: -- / --")
            self.disk_bar.setValue(0)
            return

        try:
            path = Path(path_str)
            resolved_path = None
            if path.exists():
                resolved_path = path
            else:
                for parent in path.parents:
                    if parent.exists():
                        resolved_path = parent
                        break

            if resolved_path:
                total, used, free = shutil.disk_usage(resolved_path)
                total_gb = total / (1024 ** 3)
                free_gb = free / (1024 ** 3)
                used_gb = used / (1024 ** 3)
                used_percent = int((used / total) * 100) if total > 0 else 0

                self.disk_path_label.setText(f"Draft Root: {path.name or path_str}")
                self.disk_text_label.setText(f"Trống: {free_gb:.1f}GB / {total_gb:.1f}GB")
                self.disk_bar.setValue(used_percent)
            else:
                self.disk_path_label.setText("Draft Root: --")
                self.disk_text_label.setText("Trống: -- / --")
                self.disk_bar.setValue(0)
        except Exception:
            self.disk_path_label.setText("Draft Root: --")
            self.disk_text_label.setText("Trống: -- / --")
            self.disk_bar.setValue(0)

    def update_status_pill(self, status: str) -> None:
        if status == "ready":
            self.status_pill.setText("● SẴN SÀNG DỰNG")
            self.status_pill.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.15);
                color: #10b981;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)
        elif status == "needs_checking":
            self.status_pill.setText("● CẦN KIỂM TRA")
            self.status_pill.setStyleSheet("""
                background-color: rgba(245, 158, 11, 0.15);
                color: #f59e0b;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)

    def show_toast(self, title: str, message: str, level: str = "info", duration_ms: int = 3500) -> None:
        """Shows a non-blocking floating Toast notification at top-right."""
        try:
            from app.widgets.toast import ToastManager
            ToastManager.get_instance().show(self, title, message, level=level, duration_ms=duration_ms)
        except Exception as e:
            print(f"Error showing toast: {e}")

    def _append_log(self, text: str) -> None:
        from core.logger import logger
        logger.info(text)
        self.build_widget.append_log(text)
        self._add_notification(text)

        # Trigger non-blocking floating Toast for key status events
        if "[THÀNH CÔNG]" in text:
            clean = text.replace("[THÀNH CÔNG]", "").strip()
            self.show_toast("Thành công", clean, level="success")
        elif "[LỖI]" in text:
            clean = text.replace("[LỖI]", "").strip()
            self.show_toast("Lỗi hệ thống", clean, level="error")
        elif "[CẢNH BÁO]" in text:
            clean = text.replace("[CẢNH BÁO]", "").strip()
            self.show_toast("Cảnh báo", clean, level="warning")

    @Slot()
    def _open_draft_folder_action(self) -> None:
        root_str = self.setup_widget.draft_root.text().strip()
        if root_str and Path(root_str).exists():
            try:
                os.startfile(root_str)
                self.show_toast("Thành công", f"Đã mở thư mục draft CapCut:\n{root_str}", level="info")
            except Exception as e:
                self.show_toast("Lỗi hệ thống", f"Không thể mở thư mục: {e}", level="error")

    def _refresh_projects(self) -> None:
        self.doctor_controller.refresh_projects()

    def _refresh_backups_for_project(self, project_name: str) -> None:
        self.doctor_controller.refresh_backups_for_project(project_name)

    def _run_keyframe_action(self, action: str, params: dict, project_name: str = None) -> None:
        self.effects_controller.run_keyframe_action(action, params, project_name)

    @Slot(dict)
    def _on_keyframe_finished(self, result: dict) -> None:
        self.effects_controller._on_keyframe_finished(result)

    @Slot(str)
    def _on_keyframe_failed(self, message: str) -> None:
        self.effects_controller._on_keyframe_failed(message)

    @Slot()
    def _on_keyframe_thread_finished(self) -> None:
        self.effects_controller._on_keyframe_thread_finished()

    def _set_keyframe_ui_enabled(self, enabled: bool) -> None:
        self.effects_controller.set_keyframe_ui_enabled(enabled)

    @Slot()
    def _apply_effect_click(self) -> None:
        self.effects_controller.apply_effect_click()

    def _build_preset_from_params(self, preset_id: str, segment: str) -> Optional[dict]:
        return self.effects_controller.build_preset_from_params(preset_id, segment)

    @Slot()
    def _restore_backup_click(self) -> None:
        self.doctor_controller.restore_backup_click()

    @Slot()
    def _clean_backups_click(self) -> None:
        self.doctor_controller.clean_backups_click()

    @Slot()
    def _repair_project_click(self) -> None:
        self.doctor_controller.repair_project_click()

    def _load_config(self) -> None:
        self.settings_controller.load_config(CONFIG_PATH)

    def _save_config(self) -> None:
        self.settings_controller.save_config(CONFIG_PATH)

    def _update_step_widget(self, code: str, status: str, message: str = "") -> None:
        self.build_widget.update_step_widget(code, status, message)

    @Slot()
    def _start_pipeline(self) -> None:
        self._on_build_now()

    def _get_config_from_ui(self) -> Optional[ProjectConfig]:
        if not self.setup_widget.project_name.text().strip():
            QMessageBox.critical(self, "Lỗi", "Tên dự án không được để trống!")
            return None
        if not self.setup_widget.draft_root.text().strip() or not Path(self.setup_widget.draft_root.text()).exists():
            QMessageBox.critical(self, "Lỗi", "Thư mục draft CapCut không hợp lệ!")
            return None
        if not self.setup_widget.voice_path.text().strip() or not Path(self.setup_widget.voice_path.text()).exists():
            QMessageBox.critical(self, "Lỗi", "Tệp giọng thoại không hợp lệ!")
            return None
        if not self.setup_widget.media_dir.text().strip() or not Path(self.setup_widget.media_dir.text()).exists():
            QMessageBox.critical(self, "Lỗi", "Thư mục video/ảnh nền không hợp lệ!")
            return None

        canvas = "9:16"
        if self.setup_widget.ratio_16_9.isChecked():
            canvas = "16:9"

        selection_idx = self.setup_widget.selection_mode.currentIndex()
        selection_mode = {
            1: "sequential",
            2: "random",
            3: "duplicate_then_shuffle",
            4: "shuffle_duplicates_only",
        }.get(selection_idx, "shuffle_bag")

        short_video_mode = "loop" if self.setup_widget.short_video_mode.currentIndex() == 1 else "stretch"

        return ProjectConfig(
            project_name=self.setup_widget.project_name.text().strip(),
            draft_root=self.setup_widget.draft_root.text().strip(),
            voice_path=self.setup_widget.voice_path.text().strip(),
            media_dir=self.setup_widget.media_dir.text().strip(),
            bgm_path=self.setup_widget.bgm_path.text().strip(),
            srt_path=self.setup_widget.srt_path.text().strip(),
            intro_path=self.setup_widget.intro_combo.currentData() or "",
            outro_path=self.setup_widget.outro_combo.currentData() or "",
            logo_path=self.effects_widget.logo_path.text().strip(),
            logo_position=self.effects_widget.logo_position.currentData() or "top_right",
            logo_scale=self.effects_widget.logo_scale.value(),
            logo_opacity=self.effects_widget.logo_opacity.value() / 100.0,
            anim_path=self.effects_widget.anim_path.text().strip(),
            anim_position=self.effects_widget.anim_position.currentData() or "bottom_center",
            anim_scale=self.effects_widget.anim_scale.value(),
            anim_timing=self.effects_widget.anim_timing.currentData() or "end",
            canvas=canvas,
            clip_min_sec=self.setup_widget.clip_min.value(),
            clip_max_sec=self.setup_widget.clip_max.value(),
            selection_mode=selection_mode,
            short_video_mode=short_video_mode,
            recursive_scan=self.setup_widget.recursive_scan.isChecked(),
            auto_keyframe=self.setup_widget.auto_kf_combo.currentData(),
            auto_transition=self.setup_widget.auto_trans_combo.currentData(),
            auto_transition_duration=self.setup_widget.auto_trans_dur.value(),
            bg_switch_mode=self.setup_widget.bg_switch_mode.currentData() or "time",
            bg_switch_group_size=self.setup_widget.bg_switch_group_size.value(),
            chroma_enabled=self.effects_widget.chroma_enabled.isChecked(),
            chroma_mode=self.effects_widget.chroma_mode.currentData() or "green",
            chroma_threshold=self.effects_widget.chroma_threshold.value(),
            chroma_shadow=self.effects_widget.chroma_shadow.value(),
            subtitle_karaoke=self.effects_widget.subtitle_karaoke.isChecked(),

            # Subtitle styling settings
            subtitle_font_size=self.setup_widget.subtitle_font_size.value(),
            subtitle_color=hex_to_rgb_tuple(self.setup_widget.subtitle_color.text()),
            subtitle_bold=self.setup_widget.subtitle_bold.isChecked(),
            subtitle_outline_width=self.setup_widget.subtitle_outline_width.value(),
            subtitle_shadow_alpha=self.setup_widget.subtitle_shadow_alpha.value() if self.setup_widget.subtitle_shadow.isChecked() else 0.0,
            subtitle_shadow_distance=self.setup_widget.subtitle_shadow_distance.value()
        )

    @Slot()
    def _on_add_to_queue(self) -> None:
        config = self._get_config_from_ui()
        if not config:
            return

        from app.preflight import run_preflight
        report = run_preflight(config)
        if not report.can_run:
            errors = [issue.message for issue in report.issues if issue.severity == "error"]
            error_msg = "\n".join([f"- {err}" for err in errors])
            QMessageBox.critical(self, "Lỗi Preflight", f"Không thể thêm vào hàng đợi do có lỗi cấu hình:\n{error_msg}")
            return

        warnings = [issue.message for issue in report.issues if issue.severity == "warning"]
        if warnings:
            warn_msg = "\n".join([f"- {w}" for w in warnings])
            reply = QMessageBox.warning(
                self, "Cảnh báo Preflight",
                f"Phát hiện một số cảnh báo:\n{warn_msg}\n\nBạn có chắc chắn muốn tiếp tục không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._save_config()
        BatchQueueManager.get_instance().add_job(config)
        self.build_widget.refresh_queue_table()
        self._switch_to_page("build-center")

    @Slot()
    def _on_build_now(self) -> None:
        config = self._get_config_from_ui()
        if not config:
            return

        from app.preflight import run_preflight
        report = run_preflight(config)
        if not report.can_run:
            errors = [issue.message for issue in report.issues if issue.severity == "error"]
            error_msg = "\n".join([f"- {err}" for err in errors])
            QMessageBox.critical(self, "Lỗi Preflight", f"Không thể chạy do có lỗi cấu hình:\n{error_msg}")
            return

        warnings = [issue.message for issue in report.issues if issue.severity == "warning"]
        if warnings:
            warn_msg = "\n".join([f"- {w}" for w in warnings])
            reply = QMessageBox.warning(
                self, "Cảnh báo Preflight",
                f"Phát hiện một số cảnh báo:\n{warn_msg}\n\nBạn có chắc chắn muốn tiếp tục không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._save_config()
        BatchQueueManager.get_instance().add_job(config)
        self.build_widget.refresh_queue_table()
        self._switch_to_page("build-center")

        BatchQueueManager.get_instance().start_queue()

    @Slot()
    def _cancel_pipeline(self) -> None:
        BatchQueueManager.get_instance().cancel_current_job()

    @Slot(object)
    def _on_step_update(self, res: StepResult) -> None:
        self._update_step_widget(res.code, res.status, res.message)

        done_count = sum(1 for w in self.build_widget.step_widgets.values() if w.property("state") == "done")
        self.build_widget.progress_bar.setValue(done_count)

    @Slot(dict)
    def _on_finished(self, result: dict) -> None:
        draft_path = result.get('draft_path', '')
        proj_name = result.get('project_name', 'CapCut Draft')
        duration_sec = result.get('duration', 0)
        
        self._append_log(f"[THÀNH CÔNG] Tạo bản nháp hoàn tất trong {duration_sec} giây!")
        self._append_log(f"[THÀNH CÔNG] Đường dẫn: {draft_path}")
        self.build_widget.progress_bar.setValue(4)
        
        from draft_doctor import find_capcut_executable
        capcut_exe = find_capcut_executable()
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Thành Công")
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setText(f"Dự án nháp CapCut '{proj_name}' đã được tạo thành công!")
        msg_box.setInformativeText(f"Vị trí: {draft_path}\n\nLựa chọn hành động:")
        
        btn_capcut = None
        if capcut_exe:
            btn_capcut = msg_box.addButton("Mở Trực Tiếp CapCut PC", QMessageBox.ButtonRole.AcceptRole)
            btn_capcut.setIcon(get_svg_icon("capcut", color="#ffffff", size=16))
        btn_open = msg_box.addButton("Mở Thư Mục Dự Án", QMessageBox.ButtonRole.ActionRole)
        btn_open.setIcon(get_svg_icon("folder", color="#ffffff", size=16))
        msg_box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        clicked = msg_box.clickedButton()
        
        if btn_capcut and clicked == btn_capcut:
            try:
                import subprocess
                subprocess.Popen([str(capcut_exe)])
                self._append_log(f"[HỆ THỐNG] Đã khởi động CapCut PC: {capcut_exe}")
            except Exception as e:
                self._append_log(f"[CẢNH BÁO] Không thể mở CapCut PC: {e}")
        elif clicked == btn_open and draft_path and os.path.exists(draft_path):
            try:
                os.startfile(draft_path)
            except Exception as e:
                self._append_log(f"[CẢNH BÁO] Không thể mở thư mục: {e}")
                
        self._refresh_projects()

    @Slot()
    def _launch_capcut_direct(self) -> None:
        from draft_doctor import find_capcut_executable
        capcut_exe = find_capcut_executable()
        if capcut_exe and capcut_exe.exists():
            try:
                import subprocess
                subprocess.Popen([str(capcut_exe)])
                self._append_log(f"[HỆ THỐNG] Đã khởi chạy CapCut PC: {capcut_exe}")
            except Exception as e:
                QMessageBox.warning(self, "Lỗi", f"Không thể khởi chạy CapCut: {e}")
        else:
            QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy CapCut.exe trên hệ thống Windows!\nVui lòng kiểm tra lại cài đặt CapCut PC.")

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._append_log(f"[LỖI] Quy trình bị lỗi: {message}")
        QMessageBox.critical(self, "Thất bại", f"Tạo bản nháp thất bại:\n{message}")

        for code in self.build_widget.step_codes:
            if self.build_widget.step_widgets[code].property("state") == "running":
                self._update_step_widget(code, "error")

    @Slot()
    def _on_thread_finished(self) -> None:
        self.build_widget.btn_run.setEnabled(True)
        self.build_widget.btn_run.setText("BẮT ĐẦU TẠO DỰ ÁN")
        self.build_widget.btn_cancel.setEnabled(False)
        self._set_form_inputs_enabled(True)
        self._set_keyframe_ui_enabled(True)
        self.thread = None
        self.worker = None

    def _set_form_inputs_enabled(self, enabled: bool) -> None:
        self.setup_widget.setEnabled(enabled)

    def _request_worker_shutdown(self) -> bool:
        """
        Requests shutdown of any active workers.
        Returns True if safe to close immediately, False if close should be ignored.
        """
        is_testing = (
            "pytest" in sys.modules
            or bool(os.environ.get("PYTEST_CURRENT_TEST"))
            or "unittest" in sys.modules
            or any("test" in arg for arg in sys.argv)
        )
        wait_ms = 50 if is_testing else 2000

        # Batch Build Queue / subprocess shutdown
        try:
            if not self.build_widget.shutdown(wait_ms=wait_ms):
                if not is_testing:
                    return False
        except Exception as e:
            print(f"Error shutting down build widget: {e}")

        # 1. Main Pipeline / Keyframe / Split / Downloader Thread
        if self.thread and self.thread.isRunning():
            if hasattr(self.worker, "cancel"):
                try:
                    self.worker.cancel()
                except Exception:
                    pass
            self.thread.requestInterruption()
            self.thread.quit()
            if not self.thread.wait(wait_ms):
                try:
                    self.thread.terminate()
                    self.thread.wait(100)
                except Exception:
                    pass

        # 2. Scan Thread
        self._cancel_scan_threads(wait_ms=wait_ms)

        # 3. Media studio import/download/cutter workers
        try:
            self.media_studio_widget.shutdown(wait_ms=wait_ms)
        except Exception:
            pass

        # 4. Setup widget waveform worker
        try:
            self.setup_widget.shutdown(wait_ms=wait_ms)
        except Exception:
            pass

        return True

    def closeEvent(self, event) -> None:
        try:
            if hasattr(self, "profile_controller"):
                self.profile_controller._save_current_profile()
        except Exception as e:
            print(f"Error saving profile on exit: {e}")

        if self._request_worker_shutdown():
            event.accept()
        else:
            event.ignore()

    def _apply_style(self) -> None:
        self.setStyleSheet(get_application_stylesheet())

    def _on_search_text_changed(self, text: str) -> None:
        text = text.strip()
        if not text or len(text) < 2:
            if hasattr(self, "_search_menu") and self._search_menu is not None:
                self._search_menu.hide()
            return

        # Initialize search menu if not exists
        if not hasattr(self, "_search_menu") or self._search_menu is None:
            self._search_menu = QMenu(self)
            self._search_menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {COLOR_DARK_ZINC};
                    color: {COLOR_TEXT_PRIMARY};
                    border: 1px solid {COLOR_CARD_BORDER};
                    border-radius: 6px;
                }}
                QMenu::item {{
                    padding: 6px 12px;
                }}
                QMenu::item:selected {{
                    background-color: {COLOR_TEAL};
                    color: {COLOR_TEXT_BLACK};
                }}
            """)
        else:
            self._search_menu.clear()

        # 1. Search Projects
        projects = []
        root_str = self.setup_widget.draft_root.text().strip()
        if root_str:
            root_path = Path(root_str)
            if root_path.exists() and root_path.is_dir():
                try:
                    for p in root_path.iterdir():
                        if p.is_dir() and not p.name.startswith('.'):
                            if (p / 'draft_content.json').exists() or (p / 'Timelines').exists():
                                if text.lower() in p.name.lower():
                                    projects.append(p.name)
                except Exception:
                    pass

        # 2. Search Media
        media_assets = []
        try:
            from assets.manager import AssetManager
            assets = AssetManager.list_assets(search_query=text)
            media_assets = [a["filename"] for a in assets][:5]  # limit to 5
        except Exception:
            pass

        # 3. Search Presets
        presets = []
        for p in KEYFRAME_PRESETS:
            if text.lower() in p["name"].lower():
                presets.append((p["name"], p["id"], "keyframe"))
        for t in TRANSITION_PRESETS:
            if text.lower() in t["label"].lower():
                presets.append((t["label"], t["name"], "transition"))

        # Build Menu Actions
        has_results = False

        if projects:
            has_results = True
            self._search_menu.addSection("DỰ ÁN")
            for proj in projects[:5]:
                act = self._search_menu.addAction(get_svg_icon("folder", color="#00F2FE", size=14), f"Dự án: {proj}")
                act.triggered.connect(lambda chk=False, p=proj: self._handle_search_project(p))

        if media_assets:
            has_results = True
            self._search_menu.addSection("THƯ VIỆN MEDIA")
            for media in media_assets:
                act = self._search_menu.addAction(get_svg_icon("video", color="#00F2FE", size=14), f"Media: {media}")
                act.triggered.connect(lambda chk=False, m=media: self._handle_search_media(m))

        if presets:
            has_results = True
            self._search_menu.addSection("PRESET & HIỆU ỨNG")
            for label, name, ptype in presets[:5]:
                act = self._search_menu.addAction(get_svg_icon("sparkles", color="#00F2FE", size=14), f"Preset: {label}")
                if ptype == "keyframe":
                    act.triggered.connect(lambda chk=False, n=name: self._handle_search_preset_keyframe(n))
                else:
                    act.triggered.connect(lambda chk=False, n=name: self._handle_search_preset_transition(n))

        if not has_results:
            self._search_menu.addAction("Không tìm thấy kết quả nào").setEnabled(False)

        # Positioning popup right below search bar
        pos = self.search_bar.mapToGlobal(self.search_bar.rect().bottomLeft())
        self._search_menu.setMinimumWidth(self.search_bar.width())
        self._search_menu.popup(pos)
        # Restore focus to search_bar so typing can continue without popup stealing focus
        self.search_bar.setFocus(Qt.FocusReason.OtherFocusReason)
        QTimer.singleShot(0, lambda: self.search_bar.setFocus(Qt.FocusReason.OtherFocusReason))

    def _handle_search_project(self, proj_name: str) -> None:
        idx1 = self.effects_widget.project_combo.findText(proj_name)
        if idx1 >= 0:
            self.effects_widget.project_combo.setCurrentIndex(idx1)
        idx2 = self.history_widget.project_combo.findText(proj_name)
        if idx2 >= 0:
            self.history_widget.project_combo.setCurrentIndex(idx2)
        self.setup_widget.project_name.setText(proj_name)
        self._switch_to_page("history")

    def _handle_search_media(self, filename: str) -> None:
        self.media_studio_widget.search_edit.setText(filename)
        self._switch_to_page("media-studio")

    def _handle_search_preset_keyframe(self, preset_id: str) -> None:
        self.effects_widget.tab_widget.setCurrentIndex(1) # Auto effects tab
        self.effects_widget.effect_type_combo.setCurrentIndex(0) # Preset zoom/pan combo index
        idx = self.effects_widget.kf_preset_combo.findData(preset_id)
        if idx >= 0:
            self.effects_widget.kf_preset_combo.setCurrentIndex(idx)
        self._switch_to_page("effects")

    def _handle_search_preset_transition(self, trans_name: str) -> None:
        self.effects_widget.tab_widget.setCurrentIndex(1) # Auto effects tab
        self.effects_widget.effect_type_combo.setCurrentIndex(2) # Transition combo index
        idx = self.effects_widget.trans_preset_combo.findData(trans_name)
        if idx >= 0:
            self.effects_widget.trans_preset_combo.setCurrentIndex(idx)
        self._switch_to_page("effects")

    def _add_notification(self, text: str) -> None:
        self.notifications_list.insert(0, text)
        self.notifications_list = self.notifications_list[:10]
        self.btn_notifications.setText(f" ({len(self.notifications_list)})")
        self.btn_notifications.setIcon(get_svg_icon("bell", color="#ffffff", size=16))
        self.btn_notifications.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
            }
        """)

    def _show_notifications_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1f2937;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QMenu::item {
                padding: 8px 16px;
            }
            QMenu::item:disabled {
                color: #94a3b8;
            }
        """)
        if not self.notifications_list:
            menu.addAction("Không có thông báo mới").setEnabled(False)
        else:
            for note in self.notifications_list:
                menu.addAction(note).setEnabled(False)
            menu.addSeparator()
            clear_act = menu.addAction("Dọn sạch thông báo")
            clear_act.triggered.connect(self._clear_notifications)

        pos = self.btn_notifications.mapToGlobal(self.btn_notifications.rect().bottomLeft())
        menu.popup(pos)

    def _clear_notifications(self) -> None:
        self.notifications_list.clear()
        self.btn_notifications.setText("")
        self.btn_notifications.setIcon(get_svg_icon("bell", color="#ffffff", size=16))
        self.btn_notifications.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)

    def _on_job_finished_notification(self, job_id: str, status: str, error_message: str) -> None:
        manager = BatchQueueManager.get_instance()
        job_name = "Tác vụ"
        for j in manager.jobs:
            if j.id == job_id:
                job_name = j.project_name
                break

        if status == "completed":
            self._append_log(f"[THÀNH CÔNG] Dự án '{job_name}' đã dựng xong thành công!")
        else:
            self._append_log(f"[LỖI] Dự án '{job_name}' gặp lỗi: {error_message or 'Bị hủy'}")
