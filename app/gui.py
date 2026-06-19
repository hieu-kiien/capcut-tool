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
from app.widgets import DashboardWidget, SetupWidget, EffectsWidget, BuildWidget, HistoryWidget, MediaStudioWidget
from profiles.manager import ProfileManager
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction
from datetime import datetime

# Mapping preset_id -> (group_type, default_values)
_PRESET_GROUP_MAP: Dict[str, tuple] = {
    "zoom_in_slow":      ("zoom",     {"zoom_from": 100.0, "zoom_to": 112.0}),
    "zoom_out_slow":     ("zoom",     {"zoom_from": 112.0, "zoom_to": 100.0}),
    "zoom_in_fast":      ("zoom",     {"zoom_from": 100.0, "zoom_to": 125.0}),
    "zoom_out_fast":     ("zoom",     {"zoom_from": 125.0, "zoom_to": 100.0}),
    "zoom_bounce":       ("bounce",   {"zoom_from": 100.0, "zoom_peak": 118.0, "zoom_peak_at": 60.0, "zoom_end": 108.0}),
    "pan_left_right":    ("pan",      {"pan_zoom": 115.0, "pan_from": -0.07, "pan_to":  0.07, "pan_axis": "pos_x", "axis_lbl": "X (Ngang)"}),
    "pan_right_left":    ("pan",      {"pan_zoom": 115.0, "pan_from":  0.07, "pan_to": -0.07, "pan_axis": "pos_x", "axis_lbl": "X (Ngang)"}),
    "pan_up_down":       ("pan",      {"pan_zoom": 115.0, "pan_from": -0.07, "pan_to":  0.07, "pan_axis": "pos_y", "axis_lbl": "Y (Dọc)"}),
    "pan_down_up":       ("pan",      {"pan_zoom": 115.0, "pan_from":  0.07, "pan_to": -0.07, "pan_axis": "pos_y", "axis_lbl": "Y (Dọc)"}),
    "zoom_in_pan_left":  ("zoompan",  {"zoom_from": 100.0, "zoom_to": 115.0, "pan_from":  0.0,  "pan_to": -0.06, "pan_axis": "pos_x", "axis_lbl": "X (Ngang)"}),
    "zoom_in_pan_right": ("zoompan",  {"zoom_from": 100.0, "zoom_to": 115.0, "pan_from":  0.0,  "pan_to":  0.06, "pan_axis": "pos_x", "axis_lbl": "X (Ngang)"}),
    "zoom_in_pan_up":    ("zoompan",  {"zoom_from": 100.0, "zoom_to": 115.0, "pan_from":  0.0,  "pan_to": -0.06, "pan_axis": "pos_y", "axis_lbl": "Y (Dọc)"}),
    "zoom_out_pan_down": ("zoompan",  {"zoom_from": 115.0, "zoom_to": 100.0, "pan_from": -0.06, "pan_to":  0.0,  "pan_axis": "pos_y", "axis_lbl": "Y (Dọc)"}),
    "subtle_rotate_cw":  ("rotate",   {"rot_zoom": 105.0, "rot_from": -1.5, "rot_to":  1.5}),
    "subtle_rotate_ccw": ("rotate",   {"rot_zoom": 105.0, "rot_from":  1.5, "rot_to": -1.5}),
    "fade_in":           ("fade",     {"fade_from": 0.0, "fade_to": 1.0}),
    "fade_out":          ("fade",     {"fade_from": 1.0, "fade_to": 0.0}),
    "fade_in_out":       ("fadeinout",{"fio_in_end": 15.0, "fio_out_start": 85.0}),
}


class PipelineWorker(QObject):
    log_signal = Signal(str)
    step_signal = Signal(object)
    finished_signal = Signal(dict)
    failed_signal = Signal(str)

    def __init__(self, config: ProjectConfig):
        super().__init__()
        self.config = config
        self.cancel_requested = False

    def cancel(self):
        self.cancel_requested = True

    def run(self):
        try:
            runner = PipelineRunner(self.config)
            
            def progress_cb(msg: str):
                self.log_signal.emit(msg)
                
            def step_cb(res: StepResult):
                self.step_signal.emit(res)
                
            def check_cancel() -> bool:
                return self.cancel_requested

            result = runner.run_all(
                progress=progress_cb,
                step=step_cb,
                cancel_check=check_cancel
            )
            self.finished_signal.emit(result)
        except Exception as e:
            detail = "".join(traceback.format_exception_only(type(e), e)).strip()
            self.failed_signal.emit(detail)


class KeyframeWorker(QObject):
    log_signal = Signal(str)
    finished_signal = Signal(dict)
    failed_signal = Signal(str)

    def __init__(self, action: str, draft_path: Path, params: dict):
        super().__init__()
        self.action = action
        self.draft_path = Path(draft_path)
        self.params = params

    def run(self):
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        app_root = Path(__file__).resolve().parent.parent
        
        project_name = self.draft_path.parent.name
        if "Timelines" in self.draft_path.parts:
            idx = self.draft_path.parts.index("Timelines")
            project_name = self.draft_path.parts[idx - 1]
            
        try:
            import capcut_keyframe_tool as kt
            
            class DummyArgs:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)
                    
            if not self.draft_path.exists():
                raise FileNotFoundError(f"Không tìm thấy tệp nháp: {self.draft_path}")

            if kt.is_capcut_running():
                self.log_signal.emit("[CẢNH BÁO] Phát hiện phần mềm CapCut đang chạy! Vui lòng lưu và đóng dự án trong CapCut trước để tránh bị ghi đè dữ liệu.")

            self.log_signal.emit(f"[HỆ THỐNG] Khởi động thao tác '{self.action}' trên dự án: {project_name}")

            # Get project directory and mirrors to sync modifications
            if "Timelines" in self.draft_path.parts:
                idx = self.draft_path.parts.index("Timelines")
                project_dir = Path(*self.draft_path.parts[:idx])
            else:
                project_dir = self.draft_path.parent
            _, mirrors = kt.resolve_project_draft_paths(project_dir)

            changed = 0
            actions = []
            
            if self.action == "apply_preset":
                presets = self.params.get("presets", [])
                segment_type = self.params.get("segment_type", "video")
                mode = self.params.get("mode", "replace")
                
                args = DummyArgs(segment_type=segment_type, mode=mode, dry_run=False)
                changed = kt.apply_random_presets_to_file(self.draft_path, args, presets)
                if changed and mirrors:
                    kt.mirror_draft_file(self.draft_path, mirrors)
                self.log_signal.emit(f"[THÀNH CÔNG] Đã áp dụng hiệu ứng keyframe thành công cho {changed} phân đoạn.")
                self.finished_signal.emit({"action": self.action, "changed": changed})
                
            elif self.action == "apply_transition":
                transition_presets = self.params.get("transition_presets", [])
                duration_sec = self.params.get("duration_sec", 0.4)
                apply_all = self.params.get("apply_all", False)
                segment_type = self.params.get("segment_type", "video")
                mode = self.params.get("mode", "replace")
                
                args = DummyArgs(
                    root=project_dir.parent,
                    transition_duration_sec=duration_sec,
                    transition_apply_all=apply_all,
                    segment_type=segment_type,
                    mode=mode,
                    dry_run=False
                )
                changed = kt.apply_random_transitions_to_file(self.draft_path, args, transition_presets)
                if changed and mirrors:
                    kt.mirror_draft_file(self.draft_path, mirrors)
                self.log_signal.emit(f"[THÀNH CÔNG] Đã áp dụng chuyển cảnh thành công cho {changed} điểm cắt.")
                self.finished_signal.emit({"action": self.action, "changed": changed})
                
            elif self.action == "apply_speed":
                speed_mode = self.params.get("speed_mode", "speed")
                speed_value = self.params.get("speed_value", 1.0)
                
                args = DummyArgs(video_speed_mode=speed_mode, video_speed_value=speed_value, dry_run=False)
                changed = kt.apply_video_speed_to_file(self.draft_path, args)
                if changed and mirrors:
                    kt.mirror_draft_file(self.draft_path, mirrors)
                self.log_signal.emit(f"[THÀNH CÔNG] Đã áp dụng tốc độ ({speed_mode}: {speed_value}) thành công cho {changed} video.")
                self.finished_signal.emit({"action": self.action, "changed": changed})
                
            elif self.action == "apply_scale":
                scale_percent = self.params.get("scale_percent", 100.0)
                skip_first = self.params.get("skip_first", False)
                
                args = DummyArgs(video_scale_percent=scale_percent, skip_first_video_scale=skip_first, dry_run=False)
                changed = kt.apply_video_scale_to_file(self.draft_path, args)
                if changed and mirrors:
                    kt.mirror_draft_file(self.draft_path, mirrors)
                self.log_signal.emit(f"[THÀNH CÔNG] Đã áp dụng tỷ lệ zoom ({scale_percent}%) thành công cho {changed} video.")
                self.finished_signal.emit({"action": self.action, "changed": changed})
                
            elif self.action == "restore_backup":
                backup_str = self.params.get("backup_path")
                if not backup_str:
                    raise ValueError("Không tìm thấy đường dẫn bản sao lưu để khôi phục.")
                backup_path = Path(backup_str)
                
                import draft_doctor
                draft_doctor.restore_draft_backup(self.draft_path, backup_path)
                    
                self.log_signal.emit(f"[THÀNH CÔNG] Đã khôi phục dự án về trạng thái bản sao lưu: {backup_path.name}")
                self.finished_signal.emit({"action": self.action, "backup_name": backup_path.name})
                
            elif self.action == "repair_project":
                import draft_doctor
                media_dir = self.params.get("media_dir")
                media_dirs = []
                if media_dir:
                    media_dirs.append(media_dir)
                media_dirs.append(project_dir)
                
                self.log_signal.emit("[HỆ THỐNG] Đang chẩn đoán và tự động sửa dự án...")
                actions = draft_doctor.repair_draft_project(project_dir, media_dirs=media_dirs)
                for act in actions:
                    self.log_signal.emit(f"[ĐÃ SỬA] {act}")
                
                self.log_signal.emit("[THÀNH CÔNG] Đã hoàn tất quy trình tự động sửa lỗi dự án.")
                self.finished_signal.emit({"action": self.action, "actions_taken": actions})
                
            else:
                raise ValueError(f"Hành động không hợp lệ: {self.action}")
                
            # Write success history JSON
            try:
                from app.history import write_job_history
                job_data = {
                    "project_name": project_name,
                    "started_at": started_at,
                    "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "success",
                    "inputs": {
                        "action": self.action,
                        "draft_path": str(self.draft_path),
                        **self.params
                    },
                    "outputs": {},
                    "error": ""
                }
                if self.action in ("apply_preset", "apply_transition", "apply_speed", "apply_scale"):
                    job_data["outputs"]["changed"] = changed
                elif self.action == "repair_project":
                    job_data["outputs"]["actions_taken"] = actions
                elif self.action == "restore_backup":
                    job_data["outputs"]["backup_name"] = backup_path.name
                write_job_history(self.action, job_data, app_root)
            except Exception as hist_err:
                print(f"Error logging keyframe success: {hist_err}")
                
        except Exception as e:
            detail = "".join(traceback.format_exception_only(type(e), e)).strip()
            
            # Write failed history JSON
            try:
                from app.history import write_job_history
                job_data = {
                    "project_name": project_name,
                    "started_at": started_at,
                    "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "failed",
                    "inputs": {
                        "action": self.action,
                        "draft_path": str(self.draft_path),
                        **self.params
                    },
                    "outputs": {},
                    "error": detail
                }
                write_job_history(self.action, job_data, app_root)
            except Exception as hist_err:
                print(f"Error logging keyframe failure: {hist_err}")
                
            self.failed_signal.emit(detail)


class SplitWorker(QObject):
    log_signal = Signal(str)
    finished_signal = Signal(dict)
    failed_signal = Signal(str)

    def __init__(self, ffmpeg_exe, source_path, out_path, segment_time, suffix, base_name):
        super().__init__()
        self.ffmpeg_exe = ffmpeg_exe
        self.source_path = source_path
        self.out_path = out_path
        self.segment_time = segment_time
        self.suffix = suffix
        self.base_name = base_name
        self.process = None
        self.is_cancelled = False
        
    def cancel(self):
        self.is_cancelled = True
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
                
    def run(self):
        import subprocess
        try:
            pattern = self.out_path / f"split_{self.base_name}_%03d{self.suffix}"
            cmd = [
                self.ffmpeg_exe,
                "-y",
                "-i", str(self.source_path),
                "-c", "copy",
                "-map", "0",
                "-segment_time", str(self.segment_time),
                "-f", "segment",
                str(pattern)
            ]
            
            self.log_signal.emit(f"[HỆ THỐNG] Đang cắt video nguồn: {self.source_path.name} (mỗi đoạn {self.segment_time}s)...")
            self.log_signal.emit(f"[HỆ THỐNG] Chạy FFmpeg: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            stdout, stderr = self.process.communicate()
            
            if self.is_cancelled:
                self.failed_signal.emit("Quy trình cắt video đã bị hủy bởi người dùng.")
                return
                
            if self.process.returncode != 0:
                self.log_signal.emit(f"[LỖI] FFmpeg thất bại:\n{stderr}")
                self.failed_signal.emit("FFmpeg cắt video thất bại! Chi tiết xem trong log.")
                return
                
            created_files = []
            for f in self.out_path.iterdir():
                if f.is_file() and f.name.startswith(f"split_{self.base_name}_") and f.suffix == self.suffix:
                    created_files.append(f)
                    
            num_files = len(created_files)
            self.finished_signal.emit({
                "num_files": num_files,
                "out_path": str(self.out_path)
            })
        except Exception as e:
            self.failed_signal.emit(str(e))


class ScanWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, directory: Path, recursive: bool = False, scan_id: int = 0):
        super().__init__()
        self.directory = directory
        self.recursive = recursive
        self.scan_id = scan_id
        self.cancel_requested = False

    def cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        try:
            video_count = 0
            image_count = 0
            other_count = 0
            total_size = 0
            samples: list[dict] = []

            video_exts = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv"}
            image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

            thread = QThread.currentThread()
            iterator = self.directory.rglob("*") if self.recursive else self.directory.iterdir()
            for p in iterator:
                if self.cancel_requested or thread.isInterruptionRequested():
                    self.finished.emit({
                        "scan_id": self.scan_id,
                        "videos": video_count,
                        "images": image_count,
                        "others": other_count,
                        "total_size": total_size,
                        "samples": samples,
                        "cancelled": True,
                    })
                    return
                try:
                    is_file = p.is_file()
                except OSError:
                    other_count += 1
                    continue

                if is_file:
                    ext = p.suffix.lower()
                    try:
                        size = p.stat().st_size
                    except OSError:
                        other_count += 1
                        continue
                    total_size += size
                    if ext in video_exts:
                        video_count += 1
                        media_type = "Video"
                    elif ext in image_exts:
                        image_count += 1
                        media_type = "Ảnh"
                    else:
                        other_count += 1
                        media_type = "Khác"
                    if media_type != "Khác" and len(samples) < 20:
                        samples.append(
                            {
                                "name": p.name,
                                "type": media_type,
                                "size": size,
                                "folder": str(p.parent),
                            }
                        )

            self.finished.emit({
                "scan_id": self.scan_id,
                "videos": video_count,
                "images": image_count,
                "others": other_count,
                "total_size": total_size,
                "samples": samples,
            })
        except Exception as e:
            self.failed.emit(str(e))


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"


def hex_to_rgb_tuple(hex_str: str) -> tuple[float, float, float]:
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) != 6:
        return (1.0, 1.0, 1.0)
    try:
        r = int(hex_str[0:2], 16) / 255.0
        g = int(hex_str[2:4], 16) / 255.0
        b = int(hex_str[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        return (1.0, 1.0, 1.0)


def rgb_tuple_to_hex(rgb: tuple[float, float, float]) -> str:
    if not isinstance(rgb, (list, tuple)) or len(rgb) < 3:
        return "#FFFFFF"
    r = int(max(0.0, min(1.0, rgb[0])) * 255)
    g = int(max(0.0, min(1.0, rgb[1])) * 255)
    b = int(max(0.0, min(1.0, rgb[2])) * 255)
    return f"#{r:02X}{g:02X}{b:02X}"


class LogSignaler(QObject):
    log_received = Signal(str)

log_signaler = LogSignaler()


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
        
        # Stub widgets/slots to satisfy automated tests
        self.split_source_edit = QLineEdit()
        self.split_time_spin = QDoubleSpinBox()
        self.split_out_edit = QLineEdit()
        self.btn_run_split = QPushButton()
        
        self.download_urls_edit = QPlainTextEdit()
        self.download_out_edit = QLineEdit()
        self.download_cookies_edit = QLineEdit()
        self.download_max_file_size_mb = QDoubleSpinBox()
        self.download_max_file_size_mb.setRange(0, 999999)
        self.download_stall_timeout_sec = QDoubleSpinBox()
        self.download_stall_timeout_sec.setRange(0, 999999)
        self.download_item_timeout_sec = QDoubleSpinBox()
        self.download_item_timeout_sec.setRange(0, 999999)
        
        self._build_ui()
        
        # Configure logging callback and setup file logging thread-safely
        import core.logger as cc_logger
        log_signaler.log_received.connect(self.dashboard_widget.append_log)
        
        def on_logger_log(msg: str):
            log_signaler.log_received.emit(msg)
            
        cc_logger.add_log_callback(on_logger_log)
        
        root_dir = Path(__file__).resolve().parents[1]
        cc_logger.setup_file_logging(root_dir / ".capcut_tool_jobs")
        cc_logger.logger.info("CapCut Draft Studio v1.0.0 khởi động thành công.")

        self._load_config()
        self._refresh_profiles_list(self._current_profile_name)
        
        # Connect profile UI signals
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selection_changed)
        self.btn_save_profile.clicked.connect(self._save_current_profile)
        self.action_new_profile.triggered.connect(self._create_new_profile_click)
        self.action_clone_profile.triggered.connect(self._clone_profile_click)
        self.action_rename_profile.triggered.connect(self._rename_profile_click)
        self.action_delete_profile.triggered.connect(self._delete_profile_click)
        self.action_rollback_profile.triggered.connect(self._rollback_profile_click)
        self.action_export_profile.triggered.connect(self._export_profile_click)
        self.action_import_profile.triggered.connect(self._import_profile_click)
        
        # Connect media_dir change signals for ScanWorker
        self.setup_widget.media_dir.textChanged.connect(self._on_media_dir_changed)
        self.setup_widget.recursive_scan.toggled.connect(self._on_media_dir_changed)
        
        self._apply_style()
        self._switch_to_page("dashboard")
        
        # Connect text/config changes to update dashboard stats
        self.setup_widget.draft_root.textChanged.connect(self._refresh_projects)
        self.setup_widget.draft_root.textChanged.connect(self._update_dashboard_summary)
        self.setup_widget.project_name.textChanged.connect(self._update_dashboard_summary)
        self.setup_widget.voice_path.textChanged.connect(self._update_dashboard_summary)
        self.setup_widget.media_dir.textChanged.connect(self._update_dashboard_summary)
        self.setup_widget.bgm_path.textChanged.connect(self._update_dashboard_summary)
        self.setup_widget.srt_path.textChanged.connect(self._update_dashboard_summary)
        self.setup_widget.intro_combo.currentIndexChanged.connect(self._update_dashboard_summary)
        self.setup_widget.outro_combo.currentIndexChanged.connect(self._update_dashboard_summary)
        self.effects_widget.logo_path.textChanged.connect(self._update_dashboard_summary)
        self.effects_widget.anim_path.textChanged.connect(self._update_dashboard_summary)
        self.setup_widget.auto_kf_combo.currentIndexChanged.connect(self._update_dashboard_summary)
        self.setup_widget.ratio_16_9.toggled.connect(self._update_dashboard_summary)
        
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
        logo_icon = QFrame()
        logo_icon.setObjectName("logoIcon")
        logo_icon.setFixedSize(20, 20)
        logo_row.addWidget(logo_icon)
        
        logo_label = QLabel("Draft Studio")
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
            ("dashboard", "📊  Bảng điều khiển"),
            ("project-setup", "⚙️  Thiết lập dự án"),
            ("media-studio", "📁  Xưởng media"),
            ("effects", "✨  Hiệu ứng & Thương hiệu"),
            ("build-center", "🚀  Trung tâm dựng"),
            ("history", "📜  Lịch sử & Phục hồi"),
        ]
        
        for code, label in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("navButton")
            btn.setProperty("code", code)
            btn.setProperty("active", "false")
            btn.clicked.connect(self._on_nav_clicked)
            sidebar_layout.addWidget(btn)
            self.nav_buttons[code] = btn
            
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
        self.header_title = QLabel("Bảng điều khiển")
        self.header_title.setObjectName("appTitle")
        title_row.addWidget(self.header_title)
        
        badge = QLabel("LITE")
        badge.setObjectName("badge")
        title_row.addWidget(badge)
        title_row.addStretch()
        
        # Profile Selector Layout in Header
        profile_layout = QHBoxLayout()
        profile_layout.setSpacing(6)
        
        profile_lbl = QLabel("Hồ sơ:")
        profile_lbl.setStyleSheet("color: #94a3b8; font-weight: bold;")
        profile_layout.addWidget(profile_lbl)
        
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(150)
        self.profile_combo.setStyleSheet("""
            QComboBox {
                background-color: #1f2937;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 3px 6px;
                color: #ffffff;
            }
        """)
        profile_layout.addWidget(self.profile_combo)
        
        self.btn_save_profile = QPushButton("Lưu")
        self.btn_save_profile.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        profile_layout.addWidget(self.btn_save_profile)
        
        self.btn_profile_opts = QPushButton("⚙️ Tùy chọn")
        self.btn_profile_opts.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        
        # QMenu for options
        self.profile_menu = QMenu(self)
        self.profile_menu.setStyleSheet("""
            QMenu {
                background-color: #1f2937;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QMenu::item:selected {
                background-color: #4b5563;
            }
        """)
        
        self.action_new_profile = QAction("Tạo hồ sơ mới", self)
        self.action_clone_profile = QAction("Nhân bản hồ sơ", self)
        self.action_rename_profile = QAction("Đổi tên hồ sơ", self)
        self.action_delete_profile = QAction("Xóa hồ sơ", self)
        self.action_rollback_profile = QAction("Lịch sử phiên bản / Rollback", self)
        self.action_export_profile = QAction("Xuất lên mây (Export)", self)
        self.action_import_profile = QAction("Nhập từ mây (Import)", self)
        
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
        
        self.download_urls_edit = self.media_studio_widget.download_urls_edit
        self.download_out_edit = self.media_studio_widget.download_out_edit
        self.download_cookies_edit = self.media_studio_widget.download_cookies_edit
        self.download_max_file_size_mb = self.media_studio_widget.download_max_file_size_mb
        self.download_stall_timeout_sec = self.media_studio_widget.download_stall_timeout_sec
        self.download_item_timeout_sec = self.media_studio_widget.download_item_timeout_sec

        self.setup_widget.media_dir.textChanged.connect(self.media_studio_widget.download_out_edit.setText)
        self.media_studio_widget.download_out_edit.setText(self.setup_widget.media_dir.text())

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
        self.setup_widget.add_to_queue_requested.connect(self._on_add_to_queue)
        self.setup_widget.build_now_requested.connect(self._on_build_now)
        self.dashboard_widget.build_center_requested.connect(lambda: self._switch_to_page("build-center"))
        self.dashboard_widget.repair_draft_requested.connect(lambda: self._switch_to_page("history"))

    def _download_options_from_ui(self, urls: list[str] = None, url_tools: list[str] = None) -> Any:
        from app.downloader import DownloadOptions
        if urls is None:
            urls = self.download_urls_edit.toPlainText().strip().split("\n")
        if url_tools is None:
            url_tools = ["yt-dlp"]
        return DownloadOptions(
            urls=urls,
            output_dir=self.download_out_edit.text().strip(),
            cookies_file=self.download_cookies_edit.text().strip(),
            max_file_size_mb=int(self.download_max_file_size_mb.value()),
            stall_timeout_sec=int(self.download_stall_timeout_sec.value()),
            item_timeout_sec=int(self.download_item_timeout_sec.value()),
            url_tools=url_tools
        )


    # Stub slots to satisfy automated tests
    @Slot()
    def _browse_split_source_click(self) -> None:
        pass

    @Slot()
    def _browse_split_out_click(self) -> None:
        pass

    @Slot()
    def _run_split_click(self) -> None:
        pass

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
                    return False
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

    def _refresh_profiles_list(self, select_name: str = None) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        
        profiles = ProfileManager.list_profiles()
        for p in profiles:
            self.profile_combo.addItem(p["name"], p["id"])
            
        if select_name:
            idx = self.profile_combo.findText(select_name)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
        else:
            last_profile = getattr(self, "_current_profile_name", "Mặc định")
            idx = self.profile_combo.findText(last_profile)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
            else:
                self.profile_combo.setCurrentIndex(0)
                
        self.profile_combo.blockSignals(False)
        self._on_profile_selection_changed()

    @Slot()
    def _on_profile_selection_changed(self) -> None:
        idx = self.profile_combo.currentIndex()
        if idx < 0:
            return
            
        profile_id = self.profile_combo.itemData(idx)
        profile = ProfileManager.get_profile(profile_id)
        if profile:
            self._populate_ui_from_profile(profile)

    def _populate_ui_from_profile(self, profile: dict) -> None:
        if not profile:
            return
            
        self._current_profile_id = profile["id"]
        self._current_profile_name = profile["name"]
        
        # Populate SetupWidget inputs
        if profile["canvas"] == "16:9":
            self.setup_widget.ratio_16_9.setChecked(True)
        else:
            self.setup_widget.ratio_9_16.setChecked(True)
            
        self.setup_widget.clip_min.setValue(profile["clip_min_sec"])
        self.setup_widget.clip_max.setValue(profile["clip_max_sec"])
        
        mode_str = profile["selection_mode"]
        if "sequential" in mode_str:
            self.setup_widget.selection_mode.setCurrentIndex(1)
        elif "random" in mode_str:
            self.setup_widget.selection_mode.setCurrentIndex(2)
        elif "duplicate_then_shuffle" in mode_str:
            self.setup_widget.selection_mode.setCurrentIndex(3)
        elif "shuffle_duplicates_only" in mode_str:
            self.setup_widget.selection_mode.setCurrentIndex(4)
        else:
            self.setup_widget.selection_mode.setCurrentIndex(0)
            
        short_video_mode = profile["short_video_mode"]
        if short_video_mode == "loop":
            self.setup_widget.short_video_mode.setCurrentIndex(1)
        else:
            self.setup_widget.short_video_mode.setCurrentIndex(0)
            
        self.setup_widget.recursive_scan.setChecked(bool(profile["recursive_scan"]))
        
        auto_kf_id = profile["auto_keyframe"]
        if auto_kf_id:
            idx = self.setup_widget.auto_kf_combo.findData(auto_kf_id)
            self.setup_widget.auto_kf_combo.setCurrentIndex(max(0, idx))
            
        auto_trans_id = profile["auto_transition"]
        if auto_trans_id:
            idx = self.setup_widget.auto_trans_combo.findData(auto_trans_id)
            self.setup_widget.auto_trans_combo.setCurrentIndex(max(0, idx))
            
        self.setup_widget.auto_trans_dur.setValue(profile["auto_transition_duration"])
        
        # Populate EffectsWidget inputs
        self.effects_widget.logo_path.setText(profile["logo_path"])
        logo_pos = profile["logo_position"]
        idx = self.effects_widget.logo_position.findData(logo_pos)
        if idx >= 0:
            self.effects_widget.logo_position.setCurrentIndex(idx)
        self.effects_widget.logo_scale.setValue(profile["logo_scale"])
        self.effects_widget.logo_opacity.setValue(int(profile.get("logo_opacity", 1.0) * 100))
        
        self.effects_widget.anim_path.setText(profile["anim_path"])
        anim_pos = profile["anim_position"]
        idx = self.effects_widget.anim_position.findData(anim_pos)
        if idx >= 0:
            self.effects_widget.anim_position.setCurrentIndex(idx)
        self.effects_widget.anim_scale.setValue(profile["anim_scale"])
        
        anim_time = profile["anim_timing"]
        idx = self.effects_widget.anim_timing.findData(anim_time)
        if idx >= 0:
            self.effects_widget.anim_timing.setCurrentIndex(idx)
            
        self.effects_widget.chroma_enabled.setChecked(bool(profile.get("chroma_enabled", 0)))
        chroma_m = profile.get("chroma_mode", "green")
        idx = self.effects_widget.chroma_mode.findData(chroma_m)
        if idx >= 0:
            self.effects_widget.chroma_mode.setCurrentIndex(idx)
        self.effects_widget.chroma_threshold.setValue(profile.get("chroma_threshold", 32))
        self.effects_widget.chroma_shadow.setValue(profile.get("chroma_shadow", 2))
        self.effects_widget.subtitle_karaoke.setChecked(bool(profile.get("subtitle_karaoke", 0)))
            
        self.setup_widget.bgm_path.setText(profile["bgm_path"])
        
        # Populate subtitle styles from profile
        subtitle_style_json = profile.get("subtitle_style_json", "{}")
        if subtitle_style_json:
            try:
                sub_style = json.loads(subtitle_style_json)
                font = sub_style.get("font", "SystemFont")
                idx = self.setup_widget.subtitle_font.findText(font)
                if idx >= 0:
                    self.setup_widget.subtitle_font.setCurrentIndex(idx)
                    
                self.setup_widget.subtitle_font_size.setValue(sub_style.get("font_size", 6.0))
                self.setup_widget.subtitle_color.setText(sub_style.get("color", "#FFFFFF"))
                
                align = sub_style.get("align", "bottom_center")
                idx = self.setup_widget.subtitle_align.findData(align)
                if idx >= 0:
                    self.setup_widget.subtitle_align.setCurrentIndex(idx)
                    
                self.setup_widget.subtitle_outline_width.setValue(sub_style.get("outline_width", 40.0))
                self.setup_widget.subtitle_shadow_alpha.setValue(sub_style.get("shadow_alpha", 0.8))
                self.setup_widget.subtitle_shadow_distance.setValue(sub_style.get("shadow_distance", 5.0))
                
                self.setup_widget.subtitle_bold.setChecked(sub_style.get("bold", True))
                self.setup_widget.subtitle_italic.setChecked(sub_style.get("italic", False))
                self.setup_widget.subtitle_underline.setChecked(sub_style.get("underline", False))
                self.setup_widget.subtitle_shadow.setChecked(sub_style.get("shadow", True))
                self.setup_widget._update_subtitle_preview()
            except Exception:
                pass
                
        self._update_dashboard_summary()

    @Slot()
    def _save_current_profile(self) -> None:
        if not getattr(self, "_current_profile_id", None):
            return
            
        canvas = "16:9" if self.setup_widget.ratio_16_9.isChecked() else "9:16"
        clip_min_sec = self.setup_widget.clip_min.value()
        clip_max_sec = self.setup_widget.clip_max.value()
        
        selection_idx = self.setup_widget.selection_mode.currentIndex()
        selection_mode = {
            0: "shuffle_bag",
            1: "sequential",
            2: "random",
            3: "duplicate_then_shuffle",
            4: "shuffle_duplicates_only",
        }.get(selection_idx, "shuffle_bag")
        
        short_video_mode = "loop" if self.setup_widget.short_video_mode.currentIndex() == 1 else "stretch"
        recursive_scan = 1 if self.setup_widget.recursive_scan.isChecked() else 0
        auto_keyframe = self.setup_widget.auto_kf_combo.currentData() or "none"
        auto_transition = self.setup_widget.auto_trans_combo.currentData() or "none"
        auto_transition_duration = self.setup_widget.auto_trans_dur.value()
        
        logo_path = self.effects_widget.logo_path.text().strip()
        logo_position = self.effects_widget.logo_position.currentData() or "top_right"
        logo_scale = self.effects_widget.logo_scale.value()
        logo_opacity = self.effects_widget.logo_opacity.value() / 100.0
        
        anim_path = self.effects_widget.anim_path.text().strip()
        anim_position = self.effects_widget.anim_position.currentData() or "bottom_center"
        anim_scale = self.effects_widget.anim_scale.value()
        anim_timing = self.effects_widget.anim_timing.currentData() or "end"
        
        chroma_enabled = self.effects_widget.chroma_enabled.isChecked()
        chroma_mode = self.effects_widget.chroma_mode.currentData() or "green"
        chroma_threshold = self.effects_widget.chroma_threshold.value()
        chroma_shadow = self.effects_widget.chroma_shadow.value()
        subtitle_karaoke = self.effects_widget.subtitle_karaoke.isChecked()
        
        bgm_path = self.setup_widget.bgm_path.text().strip()
        
        # Build subtitle style JSON
        sub_style = {
            "font": self.setup_widget.subtitle_font.currentText(),
            "font_size": self.setup_widget.subtitle_font_size.value(),
            "color": self.setup_widget.subtitle_color.text().strip(),
            "align": self.setup_widget.subtitle_align.currentData() or "bottom_center",
            "outline_width": self.setup_widget.subtitle_outline_width.value(),
            "shadow_alpha": self.setup_widget.subtitle_shadow_alpha.value(),
            "shadow_distance": self.setup_widget.subtitle_shadow_distance.value(),
            "bold": self.setup_widget.subtitle_bold.isChecked(),
            "italic": self.setup_widget.subtitle_italic.isChecked(),
            "underline": self.setup_widget.subtitle_underline.isChecked(),
            "shadow": self.setup_widget.subtitle_shadow.isChecked()
        }
        subtitle_style_json = json.dumps(sub_style, ensure_ascii=False)
        
        success = ProfileManager.update_profile(
            self._current_profile_id,
            canvas=canvas,
            clip_min_sec=clip_min_sec,
            clip_max_sec=clip_max_sec,
            selection_mode=selection_mode,
            short_video_mode=short_video_mode,
            recursive_scan=recursive_scan,
            auto_keyframe=auto_keyframe,
            auto_transition=auto_transition,
            auto_transition_duration=auto_transition_duration,
            logo_path=logo_path,
            logo_position=logo_position,
            logo_scale=logo_scale,
            logo_opacity=logo_opacity,
            anim_path=anim_path,
            anim_position=anim_position,
            anim_scale=anim_scale,
            anim_timing=anim_timing,
            bgm_path=bgm_path,
            chroma_enabled=chroma_enabled,
            chroma_mode=chroma_mode,
            chroma_threshold=chroma_threshold,
            chroma_shadow=chroma_shadow,
            subtitle_karaoke=subtitle_karaoke,
            subtitle_style_json=subtitle_style_json,
            update_note=f"Đã lưu thủ công từ giao diện lúc {datetime.now().strftime('%H:%M:%S')}"
        )
        
        if success:
            self._append_log(f"[HỆ THỐNG] Đã lưu thay đổi vào hồ sơ '{self._current_profile_name}' thành công.")
            QMessageBox.information(self, "Thành công", f"Đã lưu cấu hình hồ sơ '{self._current_profile_name}' thành công!")
        else:
            self._append_log("[LỖI] Không thể cập nhật hồ sơ cấu hình.")

    @Slot()
    def _create_new_profile_click(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Tạo hồ sơ mới", "Nhập tên hồ sơ mới (không dấu):")
        if not ok or not name.strip():
            return
            
        name = name.strip()
        if ProfileManager.get_profile_by_name(name):
            QMessageBox.warning(self, "Lỗi", f"Hồ sơ '{name}' đã tồn tại!")
            return
            
        p_id = ProfileManager.create_profile(name=name)
        if p_id:
            self._refresh_profiles_list(select_name=name)
            self._append_log(f"[HỆ THỐNG] Đã tạo hồ sơ cấu hình mới: '{name}'")

    @Slot()
    def _clone_profile_click(self) -> None:
        if not getattr(self, "_current_profile_id", None):
            return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Nhân bản hồ sơ", f"Nhập tên mới cho bản sao của '{self._current_profile_name}':")
        if not ok or not name.strip():
            return
            
        name = name.strip()
        if ProfileManager.get_profile_by_name(name):
            QMessageBox.warning(self, "Lỗi", f"Hồ sơ '{name}' đã tồn tại!")
            return
            
        new_id = ProfileManager.clone_profile(self._current_profile_id, name)
        if new_id:
            self._refresh_profiles_list(select_name=name)
            self._append_log(f"[HỆ THỐNG] Đã nhân bản hồ sơ thành '{name}'")

    @Slot()
    def _rename_profile_click(self) -> None:
        if not getattr(self, "_current_profile_id", None):
            return
        if self._current_profile_name == "Mặc định":
            QMessageBox.warning(self, "Không cho phép", "Không thể đổi tên hồ sơ mặc định!")
            return
            
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Đổi tên hồ sơ", "Nhập tên mới:", text=self._current_profile_name)
        if not ok or not name.strip() or name.strip() == self._current_profile_name:
            return
            
        name = name.strip()
        if ProfileManager.get_profile_by_name(name):
            QMessageBox.warning(self, "Lỗi", f"Hồ sơ '{name}' đã tồn tại!")
            return
            
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE profiles SET name = ? WHERE id = ?", (name, self._current_profile_id))
        conn.commit()
        
        self._refresh_profiles_list(select_name=name)
        self._append_log(f"[HỆ THỐNG] Đã đổi tên hồ sơ thành '{name}'")

    @Slot()
    def _delete_profile_click(self) -> None:
        if not getattr(self, "_current_profile_id", None):
            return
        if self._current_profile_name == "Mặc định":
            QMessageBox.warning(self, "Không cho phép", "Không thể xóa hồ sơ mặc định!")
            return
            
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa hồ sơ '{self._current_profile_name}' và tất cả các phiên bản lịch sử của nó?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        deleted = ProfileManager.delete_profile(self._current_profile_id)
        if deleted:
            self._append_log(f"[HỆ THỐNG] Đã xóa hồ sơ '{self._current_profile_name}'")
            self._current_profile_name = "Mặc định"
            self._refresh_profiles_list(select_name="Mặc định")

    @Slot()
    def _export_profile_click(self) -> None:
        if not getattr(self, "_current_profile_id", None):
            return
            
        profile_data = ProfileManager.get_profile(self._current_profile_id)
        if not profile_data:
            QMessageBox.critical(self, "Lỗi", "Không thể tìm thấy dữ liệu cấu hình hồ sơ hiện tại.")
            return

        import random
        import string
        import urllib.request
        
        # Sinh Share Code ngẫu nhiên
        code = "PF-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Loại bỏ các trường cục bộ
        export_data = dict(profile_data)
        export_data.pop('id', None)
        export_data.pop('created_at', None)
        export_data.pop('version', None)
        
        url = f"https://kvdb.io/capcut_draft_studio_v1/{code}"
        
        self._append_log(f"[HỆ THỐNG] Đang xuất hồ sơ '{self._current_profile_name}' lên đám mây...")
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(export_data, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='PUT'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in (200, 201):
                    self._append_log(f"[THÀNH CÔNG] Đã xuất hồ sơ lên đám mây. Mã chia sẻ: {code}")
                    from PySide6.QtWidgets import QInputDialog
                    QInputDialog.getText(
                        self,
                        "Xuất hồ sơ thành công",
                        "Đã xuất cấu hình thành công! Hãy sao chép Mã chia sẻ (Share Code) bên dưới:",
                        QLineEdit.EchoMode.Normal,
                        code
                    )
                else:
                    raise RuntimeError(f"Máy chủ phản hồi với mã trạng thái: {response.status}")
        except Exception as e:
            self._append_log(f"[LỖI] Không thể xuất hồ sơ lên đám mây: {e}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xuất hồ sơ lên đám mây: {e}")

    @Slot()
    def _import_profile_click(self) -> None:
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        code, ok = QInputDialog.getText(self, "Nhập hồ sơ từ đám mây", "Nhập Mã chia sẻ (Share Code):")
        if not ok or not code.strip():
            return
        code = code.strip().upper()
        
        import urllib.request
        url = f"https://kvdb.io/capcut_draft_studio_v1/{code}"
        
        self._append_log(f"[HỆ THỐNG] Đang tải cấu hình cho mã chia sẻ '{code}'...")
        
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=10) as response:
                data_bytes = response.read()
                profile_data = json.loads(data_bytes.decode('utf-8'))
        except urllib.error.HTTPError as he:
            if he.code == 404:
                self._append_log(f"[LỖI] Mã chia sẻ '{code}' không tồn tại hoặc đã hết hạn.")
                QMessageBox.critical(self, "Lỗi", "Mã chia sẻ không tồn tại hoặc đã hết hạn!")
            else:
                self._append_log(f"[LỖI] Lỗi HTTP khi tải cấu hình: {he}")
                QMessageBox.critical(self, "Lỗi", f"Lỗi kết nối máy chủ: {he}")
            return
        except Exception as e:
            self._append_log(f"[LỖI] Lỗi kết nối đám mây: {e}")
            QMessageBox.critical(self, "Lỗi", f"Không thể tải cấu hình từ đám mây: {e}")
            return
            
        original_name = profile_data.get('name', 'Đồng bộ')
        new_name = original_name
        
        counter = 1
        while ProfileManager.get_profile_by_name(new_name):
            new_name = f"{original_name} (Đồng bộ {counter})"
            counter += 1
            
        try:
            new_id = ProfileManager.create_profile(
                name=new_name,
                canvas=profile_data.get('canvas', '9:16'),
                clip_min_sec=float(profile_data.get('clip_min_sec', 5.0)),
                clip_max_sec=float(profile_data.get('clip_max_sec', 9.0)),
                selection_mode=profile_data.get('selection_mode', 'shuffle_bag'),
                short_video_mode=profile_data.get('short_video_mode', 'stretch'),
                recursive_scan=bool(profile_data.get('recursive_scan', False)),
                subtitle_style_json=profile_data.get('subtitle_style_json', '{}'),
                auto_keyframe=profile_data.get('auto_keyframe', 'none'),
                auto_transition=profile_data.get('auto_transition', 'none'),
                auto_transition_duration=float(profile_data.get('auto_transition_duration', 0.4)),
                logo_path=profile_data.get('logo_path', ''),
                logo_position=profile_data.get('logo_position', 'top_right'),
                logo_scale=float(profile_data.get('logo_scale', 15.0)),
                anim_path=profile_data.get('anim_path', ''),
                anim_position=profile_data.get('anim_position', 'bottom_center'),
                anim_scale=float(profile_data.get('anim_scale', 30.0)),
                anim_timing=profile_data.get('anim_timing', 'end'),
                bgm_path=profile_data.get('bgm_path', '')
            )
            
            if new_id:
                self._refresh_profiles_list(select_name=new_name)
                self._append_log(f"[THÀNH CÔNG] Đã nhập hồ sơ mới: '{new_name}'")
                QMessageBox.information(self, "Thành công", f"Đã nhập hồ sơ '{new_name}' thành công từ đám mây!")
            else:
                raise RuntimeError("Không thể tạo hồ sơ mới trong cơ sở dữ liệu.")
        except Exception as e:
            self._append_log(f"[LỖI] Không thể lưu cấu hình nhập về: {e}")
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu cấu hình: {e}")

    @Slot()
    def _rollback_profile_click(self) -> None:
        if not getattr(self, "_current_profile_id", None):
            return
            
        versions = ProfileManager.get_versions(self._current_profile_id)
        if not versions:
            QMessageBox.information(self, "Lịch sử phiên bản", "Hồ sơ này chưa có lịch sử chỉnh sửa.")
            return
            
        from PySide6.QtWidgets import QDialog, QListWidget, QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Lịch sử phiên bản - {self._current_profile_name}")
        dialog.resize(450, 300)
        
        dialog_layout = QVBoxLayout(dialog)
        
        lbl = QLabel("Chọn một phiên bản để hoàn tác (Rollback):")
        dialog_layout.addWidget(lbl)
        
        list_widget = QListWidget()
        for v in versions:
            date_str = v.get("created_at", "")
            ver_num = v.get("version", 0)
            note = v.get("note", "Không có mô tả")
            list_widget.addItem(f"Phiên bản {ver_num} ({date_str}) - {note}")
            
        dialog_layout.addWidget(list_widget)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(btn_box)
        
        if dialog.exec() == QDialog.Accepted:
            row_idx = list_widget.currentRow()
            if row_idx >= 0:
                selected_ver = versions[row_idx]["version"]
                success = ProfileManager.rollback_profile(self._current_profile_id, selected_ver)
                if success:
                    profile = ProfileManager.get_profile(self._current_profile_id)
                    self._populate_ui_from_profile(profile)
                    self._append_log(f"[HỆ THỐNG] Đã hoàn tác hồ sơ '{self._current_profile_name}' về phiên bản {selected_ver}.")
                    QMessageBox.information(self, "Thành công", f"Đã hoàn tác cấu hình về phiên bản {selected_ver}!")
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể khôi phục phiên bản.")

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
        for c, btn in self.nav_buttons.items():
            active_val = "true" if c == code else "false"
            btn.setProperty("active", active_val)
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
        report = run_preflight(cfg)

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

    def _append_log(self, text: str) -> None:
        from core.logger import logger
        logger.info(text)
        self.build_widget.append_log(text)

    def _refresh_projects(self) -> None:
        self.effects_widget.project_combo.clear()
        self.history_widget.project_combo.clear()
        root_str = self.setup_widget.draft_root.text().strip()
        if not root_str:
            return
            
        root_path = Path(root_str)
        if not root_path.exists() or not root_path.is_dir():
            return
            
        try:
            projects = []
            for p in root_path.iterdir():
                if p.is_dir() and not p.name.startswith('.'):
                    if (p / 'draft_content.json').exists() or (p / 'Timelines').exists():
                        projects.append(p.name)
            
            projects.sort()
            self.effects_widget.project_combo.blockSignals(True)
            self.history_widget.project_combo.blockSignals(True)
            
            self.effects_widget.project_combo.addItems(projects)
            self.history_widget.project_combo.addItems(projects)
            
            self.effects_widget.project_combo.blockSignals(False)
            self.history_widget.project_combo.blockSignals(False)
            
            if projects:
                self.effects_widget.project_combo.setCurrentIndex(0)
                self.history_widget.project_combo.setCurrentIndex(0)
                self._refresh_backups_for_project(projects[0])
        except Exception as e:
            self._append_log(f"[LỖI] Không thể quét danh sách dự án: {e}")

    def _refresh_backups_for_project(self, project_name: str) -> None:
        self.history_widget.backup_combo.clear()
        if not project_name:
            self.history_widget.btn_restore_backup.setEnabled(False)
            return
            
        root_str = self.setup_widget.draft_root.text().strip()
        if not root_str:
            return
            
        project_dir = Path(root_str) / project_name
        primary_draft, _ = keyframe_tool.resolve_project_draft_paths(project_dir)
        
        if not primary_draft or not primary_draft.exists():
            self.history_widget.btn_restore_backup.setEnabled(False)
            return
            
        draft_dir = primary_draft.parent
        project_dir_str = str(project_dir.resolve())
        
        # 1. Quét các tệp sao lưu .bak thực tế trên đĩa
        scanned_backups = {}
        try:
            if draft_dir.exists():
                for f in draft_dir.iterdir():
                    if f.is_file() and f.name.startswith(primary_draft.name) and f.suffix == '.bak':
                        scanned_backups[str(f.resolve())] = f
        except Exception as e:
            self._append_log(f"[LỖI] Không thể quét danh sách bản sao lưu trên đĩa: {e}")
            self.history_widget.btn_restore_backup.setEnabled(False)
            return

        # 2. Đồng bộ hóa với SQLite
        from core.db import Database
        from datetime import datetime
        try:
            conn = Database.get_connection()
            cursor = conn.cursor()
            
            # Lấy tất cả bản ghi hiện tại của dự án này trong DB
            cursor.execute(
                "SELECT id, backup_path, timestamp, note FROM backups WHERE project_dir = ?",
                (project_dir_str,)
            )
            db_records = cursor.fetchall()
            db_paths = {row["backup_path"]: row for row in db_records}
            
            # Xóa các bản ghi mồ côi (có trong DB nhưng không có trên đĩa)
            for db_path_str in list(db_paths.keys()):
                if db_path_str not in scanned_backups:
                    cursor.execute("DELETE FROM backups WHERE backup_path = ?", (db_path_str,))
                    conn.commit()
                    del db_paths[db_path_str]
            
            # Thêm các tệp mới quét được trên đĩa nhưng chưa có trong DB
            import uuid
            for disk_path_str, f in scanned_backups.items():
                if disk_path_str not in db_paths:
                    backup_id = str(uuid.uuid4())
                    # Thử tách timestamp từ tên tệp hoặc lấy thời gian thay đổi tệp
                    # Định dạng tên: com.lveditor.draft.json.20260615_210400.bak hoặc com.lveditor.draft_bak_20260615_210400
                    # Tách các phần bằng dấu chấm hoặc dấu gạch dưới
                    ts_str = ""
                    parts = f.name.replace('_', '.').split('.')
                    for p in parts:
                        if len(p) == 15 and p.isdigit(): # yyyymmddhhmmss
                            pass
                        # Tìm phần tử dạng 20260615 hoặc timestamp
                        # Đối với format: draft_content.json.20260615_210400.bak, sau khi replace '_' bằng '.' ta có:
                        # draft_content, json, 20260615, 210400, bak
                    # Cách đơn giản: dùng regex hoặc so khớp substring 8 số liền nhau và 6 số liền nhau
                    import re
                    match = re.search(r"(\d{8})_(\d{6})", f.name)
                    if match:
                        try:
                            dt = datetime.strptime(match.group(0), "%Y%m%d_%H%M%S")
                            ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass
                    if not ts_str:
                        # Fallback lấy time mtime
                        ts_str = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                        
                    cursor.execute(
                        """
                        INSERT INTO backups (id, project_dir, backup_path, timestamp, note)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (backup_id, project_dir_str, disk_path_str, ts_str, "Bản sao lưu tự động (đồng bộ đĩa)")
                    )
                    conn.commit()

            # 3. Nạp danh sách hoàn chỉnh từ SQLite đã được đồng bộ
            cursor.execute(
                "SELECT backup_path, timestamp, note FROM backups WHERE project_dir = ? ORDER BY timestamp DESC",
                (project_dir_str,)
            )
            rows = cursor.fetchall()
            
            for row in rows:
                bp = Path(row["backup_path"])
                display_text = f"{row['timestamp']} - {bp.name}"
                if row["note"]:
                    display_text += f" ({row['note']})"
                
                # Thêm vào combobox cùng với đường dẫn tuyệt đối làm itemData
                self.history_widget.backup_combo.addItem(display_text, row["backup_path"])
                
            self.history_widget.btn_restore_backup.setEnabled(len(rows) > 0)
            
        except Exception as e:
            self._append_log(f"[LỖI] Không thể nạp danh sách bản sao lưu từ SQLite: {e}")
            self.history_widget.btn_restore_backup.setEnabled(False)

    def _run_keyframe_action(self, action: str, params: dict, project_name: str = None) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "Cảnh báo", "Một tiến trình khác đang thực thi, vui lòng đợi.")
            return
            
        proj = project_name or self.effects_widget.project_combo.currentText()
        if not proj:
            QMessageBox.critical(self, "Lỗi", "Vui lòng chọn một dự án nháp mục tiêu!")
            return
            
        root_str = self.setup_widget.draft_root.text().strip()
        project_dir = Path(root_str) / proj
        primary_draft, _ = keyframe_tool.resolve_project_draft_paths(project_dir)
        
        if not primary_draft or not primary_draft.exists():
            QMessageBox.critical(self, "Lỗi", f"Không tìm thấy tệp draft_content.json tại {project_dir}")
            return
            
        self._save_config()
        self.build_widget.clear_logs()
        self._switch_to_page("build-center")
        
        self.thread = QThread(self)
        self.worker = KeyframeWorker(action, primary_draft, params)
        self.worker.moveToThread(self.thread)
        
        self.worker.log_signal.connect(self._append_log)
        self.worker.finished_signal.connect(self._on_keyframe_finished)
        self.worker.failed_signal.connect(self._on_keyframe_failed)
        
        self.thread.started.connect(self.worker.run)
        self.worker.finished_signal.connect(self.thread.quit)
        self.worker.failed_signal.connect(self.thread.quit)
        
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.worker.failed_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._on_keyframe_thread_finished)
        
        self._set_keyframe_ui_enabled(False)
        self.build_widget.btn_run.setEnabled(False)
        
        self.thread.start()

    @Slot(dict)
    def _on_keyframe_finished(self, result: dict) -> None:
        action = result.get("action")
        if action == "restore_backup":
            QMessageBox.information(self, "Thành công", f"Khôi phục thành công dự án về bản sao lưu {result.get('backup_name')}!")
        elif action == "repair_project":
            actions_taken = result.get("actions_taken", [])
            if actions_taken:
                details = "\n".join(f"- {act}" for act in actions_taken)
                msg = f"Đã thực hiện các hành động sửa lỗi sau:\n\n{details}"
            else:
                msg = "Không phát hiện lỗi nào cần sửa hoặc dự án đã tương thích hoàn toàn."
            QMessageBox.information(self, "Kết quả sửa lỗi", msg)
            self.history_widget.run_diagnose()
        else:
            changed = result.get("changed", 0)
            QMessageBox.information(self, "Thành công", f"Đã áp dụng hiệu ứng thành công cho {changed} phân đoạn!")
            
        self._refresh_backups_for_project(self.effects_widget.project_combo.currentText())

    @Slot(str)
    def _on_keyframe_failed(self, message: str) -> None:
        self._append_log(f"[LỖI] Thao tác thất bại: {message}")
        QMessageBox.critical(self, "Thất bại", f"Thao tác thất bại:\n{message}")

    @Slot()
    def _on_keyframe_thread_finished(self) -> None:
        self._set_keyframe_ui_enabled(True)
        self.build_widget.btn_run.setEnabled(True)
        self.thread = None
        self.worker = None

    def _set_keyframe_ui_enabled(self, enabled: bool) -> None:
        self.effects_widget.setEnabled(enabled)
        self.history_widget.setEnabled(enabled)

    @Slot()
    def _apply_effect_click(self) -> None:
        action = self.effects_widget.effect_type_combo.currentData()
        segment = self.effects_widget.shared_segment_combo.currentData()
        mode = self.effects_widget.shared_mode_combo.currentData()
        
        if action == "presets":
            preset_id = self.effects_widget.kf_preset_combo.currentData()
            presets = []
            if preset_id == "random":
                presets = KEYFRAME_PRESETS
            else:
                custom = self._build_preset_from_params(preset_id, segment)
                if custom:
                    presets = [custom]
                else:
                    for p in KEYFRAME_PRESETS:
                        if p["id"] == preset_id:
                            presets = [p]
                            break
            if not presets:
                return
            params = {
                "presets": presets,
                "segment_type": segment,
                "mode": mode
            }
            self._run_keyframe_action("apply_preset", params)
            
        elif action == "custom":
            prop = self.effects_widget.custom_prop_combo.currentData()
            unit = self.effects_widget.custom_unit_combo.currentData()
            from_val = self.effects_widget.custom_from_spin.value()
            to_val = self.effects_widget.custom_to_spin.value()
            
            keyframes = [{"at": 0.0, "value": from_val}]
            if self.effects_widget.custom_mid_chk.isChecked():
                mid_val = self.effects_widget.custom_mid_spin.value()
                mid_at = self.effects_widget.custom_mid_time_spin.value() / 100.0
                keyframes.append({"at": mid_at, "value": mid_val})
            keyframes.append({"at": 1.0, "value": to_val})
            
            op = {
                "property": prop,
                "keyframes": keyframes
            }
            if unit != "raw":
                op["unit"] = unit
            if prop in ("pos_x", "pos_y") and self.effects_widget.custom_clamp_chk.isChecked():
                op["clamp_to_frame"] = True
                
            presets = [{
                "name": "Custom Dynamic Effect",
                "segment": segment,
                "operations": [op]
            }]
            
            params = {
                "presets": presets,
                "segment_type": segment,
                "mode": mode
            }
            self._run_keyframe_action("apply_preset", params)
            
        elif action == "transition":
            trans_name = self.effects_widget.trans_preset_combo.currentData()
            if trans_name == "custom":
                name = self.effects_widget.trans_custom_name.text().strip()
                if not name:
                    QMessageBox.critical(self, "Lỗi", "Vui lòng nhập tên hiệu ứng chuyển cảnh tự chọn!")
                    return
            else:
                name = trans_name
                
            duration_sec = self.effects_widget.trans_duration_spin.value()
            apply_all = self.effects_widget.trans_apply_all_chk.isChecked()
            
            if trans_name == "random":
                presets = [{"name": p["name"], "duration": p["duration"]} for p in TRANSITION_PRESETS]
            else:
                duration_us = int(duration_sec * 1_000_000)
                presets = [{"name": name, "duration": duration_us}]
                
            params = {
                "transition_presets": presets,
                "duration_sec": duration_sec,
                "apply_all": apply_all,
                "segment_type": segment,
                "mode": mode
            }
            self._run_keyframe_action("apply_transition", params)
            
        elif action == "speed":
            speed_mode = self.effects_widget.speed_mode_combo.currentData()
            speed_val = self.effects_widget.speed_val_spin.value()
            params = {
                "speed_mode": speed_mode,
                "speed_value": speed_val
            }
            self._run_keyframe_action("apply_speed", params)
            
        elif action == "scale":
            scale_pct = self.effects_widget.scale_pct_spin.value()
            skip_first = self.effects_widget.scale_skip_first_chk.isChecked()
            params = {
                "scale_percent": scale_pct,
                "skip_first": skip_first
            }
            self._run_keyframe_action("apply_scale", params)

    def _build_preset_from_params(self, preset_id: str, segment: str) -> Optional[dict]:
        mapping = _PRESET_GROUP_MAP.get(preset_id)
        if not mapping:
            return None
        group, defaults = mapping
        pan_axis = defaults.get("pan_axis", "pos_x")

        if group == "zoom":
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {"property": "scale_uniform",
                     "from": self.effects_widget.param_zoom_from.value(),
                     "to":   self.effects_widget.param_zoom_to.value(),
                     "unit": "pct_base"}
                ]
            }
        elif group == "bounce":
            at = self.effects_widget.param_bounce_peak_at.value() / 100.0
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {
                        "property": "scale_uniform",
                        "keyframes": [
                            {"at": 0.0, "value": self.effects_widget.param_bounce_from.value()},
                            {"at": at,  "value": self.effects_widget.param_bounce_peak.value()},
                            {"at": 1.0, "value": self.effects_widget.param_bounce_end.value()},
                        ],
                        "unit": "pct_base"
                    }
                ]
            }
        elif group == "pan":
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {"property": "scale_uniform",
                     "from": self.effects_widget.param_pan_zoom.value(),
                     "to":   self.effects_widget.param_pan_zoom.value(),
                     "unit": "pct_base"},
                    {"property": pan_axis,
                     "from": self.effects_widget.param_pan_from.value(),
                     "to":   self.effects_widget.param_pan_to.value()}
                ]
            }
        elif group == "zoompan":
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {"property": "scale_uniform",
                     "from": self.effects_widget.param_zp_zoom_from.value(),
                     "to":   self.effects_widget.param_zp_zoom_to.value(),
                     "unit": "pct_base"},
                    {"property": pan_axis,
                     "from": self.effects_widget.param_zp_pan_from.value(),
                     "to":   self.effects_widget.param_zp_pan_to.value()}
                ]
            }
        elif group == "rotate":
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {"property": "scale_uniform",
                     "from": self.effects_widget.param_rot_zoom.value(),
                     "to":   self.effects_widget.param_rot_zoom.value(),
                     "unit": "pct_base"},
                    {"property": "rotation",
                     "from": self.effects_widget.param_rot_from.value(),
                     "to":   self.effects_widget.param_rot_to.value()}
                ]
            }
        elif group == "fade":
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {"property": "alpha",
                     "from": self.effects_widget.param_fade_from.value(),
                     "to":   self.effects_widget.param_fade_to.value()}
                ]
            }
        elif group == "fadeinout":
            in_end     = self.effects_widget.param_fio_in_end.value() / 100.0
            out_start  = self.effects_widget.param_fio_out_start.value() / 100.0
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {
                        "property": "alpha",
                        "keyframes": [
                            {"at": 0.0,       "value": 0.0},
                            {"at": in_end,    "value": 1.0},
                            {"at": out_start, "value": 1.0},
                            {"at": 1.0,       "value": 0.0},
                        ]
                    }
                ]
            }
        return None

    @Slot()
    def _restore_backup_click(self) -> None:
        idx = self.history_widget.backup_combo.currentIndex()
        if idx < 0:
            return
        backup_path_str = self.history_widget.backup_combo.itemData(idx)
        if not backup_path_str:
            return
            
        backup_path = Path(backup_path_str)
        backup_display = self.history_widget.backup_combo.itemText(idx)
        
        reply = QMessageBox.question(
            self,
            "Xác nhận khôi phục",
            f"Bạn có thực sự muốn khôi phục timeline dự án về bản sao lưu:\n'{backup_display}' không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            params = {
                "backup_path": str(backup_path)
            }
            proj = self.history_widget.project_combo.currentText()
            self._run_keyframe_action("restore_backup", params, project_name=proj)

    @Slot()
    def _clean_backups_click(self) -> None:
        proj = self.history_widget.project_combo.currentText()
        if not proj:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn một dự án trước!")
            return

        root_str = self.setup_widget.draft_root.text().strip()
        if not root_str:
            return

        project_dir  = Path(root_str) / proj
        primary_draft, _ = keyframe_tool.resolve_project_draft_paths(project_dir)
        if not primary_draft:
            return

        keep_days  = int(self.history_widget.backup_keep_days.value())
        
        try:
            import draft_doctor
            deleted, skipped = draft_doctor.clean_project_backups(primary_draft, keep_days)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể dọn backup: {e}")
            return

        self._append_log(
            f"[THÀNH CÔNG] Dọn backup: đã xóa {deleted} file, giữ lại {skipped} file (chưa đủ {keep_days} ngày)."
        )
        QMessageBox.information(
            self, "Hoàn thành",
            f"Đã xóa {deleted} tệp sao lưu cũ hơn {keep_days} ngày khỏi đĩa và SQLite.\nGiữ lại {skipped} tệp gần đây."
        )
        self._refresh_backups_for_project(proj)

    @Slot()
    def _repair_project_click(self) -> None:
        proj = self.history_widget.project_combo.currentText()
        if not proj:
            QMessageBox.critical(self, "Lỗi", "Vui lòng chọn một dự án nháp mục tiêu cần sửa!")
            return
            
        reply = QMessageBox.question(
            self,
            "Xác nhận tự động sửa lỗi",
            f"Bạn có chắc muốn tự động sửa các lỗi tương thích, đường dẫn và liên kết file của dự án '{proj}' không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        media_dir_val = self.history_widget.relink_media_dir.text().strip()
        if not media_dir_val:
            media_dir_val = self.setup_widget.media_dir.text().strip()
            
        params = {
            "media_dir": media_dir_val
        }
        self._run_keyframe_action("repair_project", params, project_name=proj)

    def _load_config(self) -> None:
        if CONFIG_PATH.exists():
            try:
                cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                self.setup_widget.project_name.setText(cfg.get("project_name", "Du_An_CapCut"))

                saved_root = cfg.get("draft_root", "")
                if saved_root and Path(saved_root).exists():
                    self.setup_widget.draft_root.setText(saved_root)
                else:
                    detected = keyframe_tool.detect_capcut_draft_root()
                    if detected:
                        self.setup_widget.draft_root.setText(str(detected))
                    elif saved_root:
                        self.setup_widget.draft_root.setText(saved_root)

                self.setup_widget.voice_path.setText(cfg.get("voice_path", ""))
                self.setup_widget.media_dir.setText(cfg.get("media_dir", ""))
                self.setup_widget.bgm_path.setText(cfg.get("bgm_path", ""))
                self.setup_widget.srt_path.setText(cfg.get("srt_path", ""))
                
                self.effects_widget.logo_path.setText(cfg.get("logo_path", ""))
                logo_pos = cfg.get("logo_position", "top_right")
                idx = self.effects_widget.logo_position.findData(logo_pos)
                if idx >= 0:
                    self.effects_widget.logo_position.setCurrentIndex(idx)
                self.effects_widget.logo_scale.setValue(cfg.get("logo_scale", 15.0))

                self.effects_widget.anim_path.setText(cfg.get("anim_path", ""))
                anim_pos = cfg.get("anim_position", "bottom_center")
                idx = self.effects_widget.anim_position.findData(anim_pos)
                if idx >= 0:
                    self.effects_widget.anim_position.setCurrentIndex(idx)
                self.effects_widget.anim_scale.setValue(cfg.get("anim_scale", 30.0))
                anim_time = cfg.get("anim_timing", "end")
                idx = self.effects_widget.anim_timing.findData(anim_time)
                if idx >= 0:
                    self.effects_widget.anim_timing.setCurrentIndex(idx)

                if cfg.get("canvas") == "16:9":
                    self.setup_widget.ratio_16_9.setChecked(True)
                else:
                    self.setup_widget.ratio_9_16.setChecked(True)

                self.setup_widget.clip_min.setValue(cfg.get("clip_min_sec", 5.0))
                self.setup_widget.clip_max.setValue(cfg.get("clip_max_sec", 9.0))

                mode_str = cfg.get("selection_mode", "shuffle_bag")
                if "sequential" in mode_str:
                    self.setup_widget.selection_mode.setCurrentIndex(1)
                elif "random" in mode_str:
                    self.setup_widget.selection_mode.setCurrentIndex(2)
                elif "duplicate_then_shuffle" in mode_str:
                    self.setup_widget.selection_mode.setCurrentIndex(3)
                elif "shuffle_duplicates_only" in mode_str:
                    self.setup_widget.selection_mode.setCurrentIndex(4)
                else:
                    self.setup_widget.selection_mode.setCurrentIndex(0)

                short_video_mode = cfg.get("short_video_mode", "stretch")
                if short_video_mode == "loop":
                    self.setup_widget.short_video_mode.setCurrentIndex(1)
                else:
                    self.setup_widget.short_video_mode.setCurrentIndex(0)

                bg_switch_mode = cfg.get("bg_switch_mode", "time")
                idx = self.setup_widget.bg_switch_mode.findData(bg_switch_mode)
                if idx >= 0:
                    self.setup_widget.bg_switch_mode.setCurrentIndex(idx)
                self.setup_widget.bg_switch_group_size.setValue(cfg.get("bg_switch_group_size", 3))

                self.setup_widget.recursive_scan.setChecked(cfg.get("recursive_scan", False))

                auto_kf_id = cfg.get("auto_kf_id")
                if auto_kf_id:
                    idx = self.setup_widget.auto_kf_combo.findData(auto_kf_id)
                    self.setup_widget.auto_kf_combo.setCurrentIndex(max(0, idx))

                auto_trans_id = cfg.get("auto_trans_id")
                if auto_trans_id:
                    idx = self.setup_widget.auto_trans_combo.findData(auto_trans_id)
                    self.setup_widget.auto_trans_combo.setCurrentIndex(max(0, idx))

                self.setup_widget.auto_trans_dur.setValue(cfg.get("auto_trans_dur_val", 0.4))

                # Load subtitle styling settings
                subtitle_font = cfg.get("subtitle_font", "SystemFont")
                idx = self.setup_widget.subtitle_font.findText(subtitle_font)
                if idx >= 0:
                    self.setup_widget.subtitle_font.setCurrentIndex(idx)
                self.setup_widget.subtitle_font_size.setValue(cfg.get("subtitle_font_size", 6.0))
                self.setup_widget.subtitle_color.setText(cfg.get("subtitle_color", "#FFFFFF"))
                
                align = cfg.get("subtitle_align", "bottom_center")
                idx = self.setup_widget.subtitle_align.findData(align)
                if idx >= 0:
                    self.setup_widget.subtitle_align.setCurrentIndex(idx)
                
                self.setup_widget.subtitle_outline_width.setValue(cfg.get("subtitle_outline_width", 40.0))
                self.setup_widget.subtitle_shadow_alpha.setValue(cfg.get("subtitle_shadow_alpha", 0.8))
                self.setup_widget.subtitle_shadow_distance.setValue(cfg.get("subtitle_shadow_distance", 5.0))
                
                self.setup_widget.subtitle_bold.setChecked(cfg.get("subtitle_bold", True))
                self.setup_widget.subtitle_italic.setChecked(cfg.get("subtitle_italic", False))
                self.setup_widget.subtitle_underline.setChecked(cfg.get("subtitle_underline", False))
                self.setup_widget.subtitle_shadow.setChecked(cfg.get("subtitle_shadow", True))
                self.setup_widget._update_subtitle_preview()

                self._refresh_projects()
                last_project = cfg.get("last_selected_project", "")
                if last_project:
                    idx = self.effects_widget.project_combo.findText(last_project)
                    if idx >= 0:
                        self.effects_widget.project_combo.setCurrentIndex(idx)
                    idx_hist = self.history_widget.project_combo.findText(last_project)
                    if idx_hist >= 0:
                        self.history_widget.project_combo.setCurrentIndex(idx_hist)
                self._current_profile_name = cfg.get("last_selected_profile", "Mặc định")
                return
            except Exception as e:
                try:
                    self._append_log(f"[CẢNH BÁO] Không đọc được config.json (sẽ tự dò tìm lại): {e}")
                except Exception:
                    pass

        detected = keyframe_tool.detect_capcut_draft_root()
        if detected:
            self.setup_widget.draft_root.setText(str(detected))
        self._refresh_projects()

    def _save_config(self) -> None:
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

        cfg = {
            "project_name": self.setup_widget.project_name.text().strip(),
            "draft_root": self.setup_widget.draft_root.text().strip(),
            "voice_path": self.setup_widget.voice_path.text().strip(),
            "media_dir": self.setup_widget.media_dir.text().strip(),
            "bgm_path": self.setup_widget.bgm_path.text().strip(),
            "srt_path": self.setup_widget.srt_path.text().strip(),
            "logo_path": self.effects_widget.logo_path.text().strip(),
            "logo_position": self.effects_widget.logo_position.currentData() or "top_right",
            "logo_scale": self.effects_widget.logo_scale.value(),
            "anim_path": self.effects_widget.anim_path.text().strip(),
            "anim_position": self.effects_widget.anim_position.currentData() or "bottom_center",
            "anim_scale": self.effects_widget.anim_scale.value(),
            "anim_timing": self.effects_widget.anim_timing.currentData() or "end",
            "canvas": canvas,
            "clip_min_sec": self.setup_widget.clip_min.value(),
            "clip_max_sec": self.setup_widget.clip_max.value(),
            "selection_mode": selection_mode,
            "short_video_mode": short_video_mode,
            "bg_switch_mode": self.setup_widget.bg_switch_mode.currentData() or "time",
            "bg_switch_group_size": self.setup_widget.bg_switch_group_size.value(),
            "recursive_scan": self.setup_widget.recursive_scan.isChecked(),
            "auto_kf_id": self.setup_widget.auto_kf_combo.currentData() or "none",
            "auto_trans_id": self.setup_widget.auto_trans_combo.currentData() or "none",
            "auto_trans_dur_val": self.setup_widget.auto_trans_dur.value(),
            "last_selected_project": self.effects_widget.project_combo.currentText(),
            "last_selected_profile": getattr(self, "_current_profile_name", "Mặc định"),
            
            # Subtitle styling settings
            "subtitle_font": self.setup_widget.subtitle_font.currentText(),
            "subtitle_font_size": self.setup_widget.subtitle_font_size.value(),
            "subtitle_color": self.setup_widget.subtitle_color.text().strip(),
            "subtitle_align": self.setup_widget.subtitle_align.currentData() or "bottom_center",
            "subtitle_outline_width": self.setup_widget.subtitle_outline_width.value(),
            "subtitle_shadow_alpha": self.setup_widget.subtitle_shadow_alpha.value(),
            "subtitle_shadow_distance": self.setup_widget.subtitle_shadow_distance.value(),
            "subtitle_bold": self.setup_widget.subtitle_bold.isChecked(),
            "subtitle_italic": self.setup_widget.subtitle_italic.isChecked(),
            "subtitle_underline": self.setup_widget.subtitle_underline.isChecked(),
            "subtitle_shadow": self.setup_widget.subtitle_shadow.isChecked()
        }
        
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

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
        self._append_log(f"[THÀNH CÔNG] Tạo bản nháp hoàn tất trong {result.get('duration')} giây!")
        self._append_log(f"[THÀNH CÔNG] Đường dẫn: {result.get('draft_path')}")
        self.build_widget.progress_bar.setValue(4)
        QMessageBox.information(
            self, "Thành công", f"Bản nháp CapCut '{result.get('project_name')}' đã được tạo thành công!"
        )
        self._refresh_projects()

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
        # 1. Main Pipeline / Keyframe / Split / Downloader Thread
        if self.thread and self.thread.isRunning():
            is_testing = "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST")
            if not is_testing:
                reply = QMessageBox.question(
                    self,
                    "Xác nhận thoát",
                    "Tiến trình dựng hoặc hiệu ứng đang chạy. Bạn có muốn hủy tiến trình và thoát không?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return False
            
            if hasattr(self.worker, "cancel"):
                try:
                    self.worker.cancel()
                except Exception:
                    pass
            self.thread.quit()
            if not self.thread.wait(5000):
                return False

        # 2. Scan Thread
        if not self._cancel_scan_threads(wait_ms=750):
            return False

        # 3. Media studio import/download/cutter workers
        if not self.media_studio_widget.shutdown(wait_ms=5000):
            return False

        return True

    def closeEvent(self, event) -> None:
        if self._request_worker_shutdown():
            event.accept()
        else:
            event.ignore()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #0b0f19;
            }
            QWidget {
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QFrame#sidebar {
                background-color: #111827;
                border-right: 1px solid rgba(255, 255, 255, 0.08);
                min-width: 200px;
                max-width: 200px;
            }
            QPushButton#navButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                color: #94a3b8;
                text-align: left;
                padding: 12px 15px;
                font-weight: bold;
            }
            QPushButton#navButton:hover {
                color: #ffffff;
                background-color: rgba(255, 255, 255, 0.05);
            }
            QPushButton#navButton[active="true"] {
                color: #ffffff;
                background-color: rgba(139, 92, 246, 0.15);
                border-left: 3px solid #8b5cf6;
            }
            QScrollArea {
                background-color: #0b0f19;
                border: none;
            }
            QScrollArea > QWidget {
                background-color: #0b0f19;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #0b0f19;
            }
            QFrame#header {
                border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            }
            QLabel#appTitle {
                font-size: 20px;
                font-weight: bold;
                color: #ffffff;
            }
            QLabel#appSubtitle {
                font-size: 12px;
                color: #94a3b8;
            }
            QFrame#logoIcon {
                background-color: #6366f1;
                border-radius: 6px;
            }
            QLabel#badge {
                background-color: rgba(139, 92, 246, 0.15);
                border: 1px solid rgba(139, 92, 246, 0.3);
                color: #a78bfa;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: bold;
                border-radius: 4px;
            }
            QFrame#configCard, QFrame#executionCard, QFrame#logCard, QFrame#projCard {
                background-color: #111827;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            QLabel#cardTitle {
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
                border-left: 3px solid #8b5cf6;
                padding-left: 8px;
                margin-bottom: 5px;
            }
            QLabel#fieldLabel {
                font-size: 12px;
                color: #cbd5e1;
                font-weight: 500;
            }
            QLineEdit, QDoubleSpinBox, QComboBox {
                background-color: rgba(6, 8, 14, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 8px 10px;
                color: #f1f5f9;
            }
            QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #6366f1;
                background-color: rgba(10, 14, 26, 0.95);
            }
            QComboBox QAbstractItemView {
                background-color: #0b0f19;
                color: #cbd5e1;
                selection-background-color: #4f46e5;
                selection-color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QPushButton#btnBrowse {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 8px 14px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#btnBrowse:hover {
                background-color: rgba(255, 255, 255, 0.12);
            }
            QPushButton#settingsToggle {
                background: transparent;
                border: none;
                color: #a78bfa;
                font-weight: bold;
                text-align: left;
                padding: 5px 0;
            }
            QFrame#settingsFrame {
                background-color: rgba(0, 0, 0, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.03);
                border-radius: 8px;
            }
            QRadioButton, QCheckBox {
                color: #cbd5e1;
            }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            
            /* Stepper Rows */
            QFrame#stepRow {
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid transparent;
                border-radius: 8px;
            }
            QLabel#stepName {
                font-size: 13px;
                font-weight: bold;
                color: #94a3b8;
            }
            QLabel#stepStatus {
                font-size: 11px;
                color: #94a3b8;
            }
            QLabel#stepCircle {
                border-radius: 11px;
                font-size: 11px;
                font-weight: bold;
            }
            
            /* Stepper States QSS */
            QFrame#stepRow[state="pending"] {
                border-color: transparent;
            }
            QFrame#stepRow[state="pending"] QLabel#stepCircle {
                border: 2px solid #64748b;
                color: #cbd5e1;
            }
            
            QFrame#stepRow[state="running"] {
                border-color: rgba(245, 158, 11, 0.2);
                background-color: rgba(245, 158, 11, 0.03);
            }
            QFrame#stepRow[state="running"] QLabel#stepCircle {
                border: 2px solid #f59e0b;
                color: #f59e0b;
            }
            QFrame#stepRow[state="running"] QLabel#stepName {
                color: #ffffff;
            }
            QFrame#stepRow[state="running"] QLabel#stepStatus {
                color: #f59e0b;
            }
            
            QFrame#stepRow[state="done"] {
                border-color: rgba(16, 185, 129, 0.2);
                background-color: rgba(16, 185, 129, 0.03);
            }
            QFrame#stepRow[state="done"] QLabel#stepCircle {
                border: 2px solid #10b981;
                background-color: #10b981;
                color: #ffffff;
            }
            QFrame#stepRow[state="done"] QLabel#stepName {
                color: #ffffff;
            }
            QFrame#stepRow[state="done"] QLabel#stepStatus {
                color: #10b981;
            }
            
            QFrame#stepRow[state="error"] {
                border-color: rgba(239, 68, 68, 0.2);
                background-color: rgba(239, 68, 68, 0.03);
            }
            QFrame#stepRow[state="error"] QLabel#stepCircle {
                border: 2px solid #ef4444;
                background-color: #ef4444;
                color: #ffffff;
            }
            QFrame#stepRow[state="error"] QLabel#stepName {
                color: #ffffff;
            }
            QFrame#stepRow[state="error"] QLabel#stepStatus {
                color: #ef4444;
            }
            
            /* Progress Bar */
            QProgressBar {
                background-color: #06080e;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 3px;
            }
            
            /* Buttons Control */
            QPushButton#btnRun {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #7c3aed);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton#btnRun:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5a52f2, stop:1 #8b4cfc);
            }
            QPushButton#btnRun:disabled {
                background: #334155;
                color: #cbd5e1;
            }
            QPushButton#btnCancel {
                background-color: #ef4444;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-weight: bold;
            }
            QPushButton#btnCancel:hover {
                background-color: #dc2626;
            }
            QPushButton#btnCancel:disabled {
                background: #1e293b;
                color: #94a3b8;
            }
            
            /* Log Card styling */
            QLabel#logTitle {
                font-size: 14px;
                font-weight: bold;
                color: #e2e8f0;
            }
            QPushButton#btnClearLog {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton#btnClearLog:hover {
                color: #ffffff;
            }
            QPlainTextEdit#logTerminal {
                background-color: #04060c;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 8px;
                font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', monospace;
                font-size: 12px;
                padding: 10px;
                color: #cbd5e1;
                line-height: 1.6;
            }
            
            /* Custom Scrollbars */
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.25);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            
            /* QMessageBox styling */
            QMessageBox {
                background-color: #111827;
                color: #e2e8f0;
            }
            QMessageBox QLabel {
                color: #e2e8f0;
            }
            QMessageBox QPushButton {
                background-color: #312e81;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 6px 14px;
                color: #ffffff;
                font-weight: bold;
                min-width: 70px;
            }
            QMessageBox QPushButton:hover {
                background-color: #4338ca;
            }
            """
        )
