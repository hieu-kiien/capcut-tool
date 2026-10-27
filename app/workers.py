import os
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from app.pipeline import PipelineRunner, ProjectConfig, StepResult


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
            
            def _iter_items():
                if self.recursive:
                    for dirpath, _, filenames in os.walk(self.directory):
                        for fname in filenames:
                            full_path = os.path.join(dirpath, fname)
                            try:
                                st = os.stat(full_path)
                                yield fname, True, st.st_size, dirpath
                            except OSError:
                                yield fname, False, 0, dirpath
                else:
                    with os.scandir(self.directory) as it:
                        for entry in it:
                            try:
                                is_f = entry.is_file()
                                sz = entry.stat().st_size if is_f else 0
                                yield entry.name, is_f, sz, str(self.directory)
                            except OSError:
                                yield entry.name, False, 0, str(self.directory)

            for name, is_file, size, folder in _iter_items():
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

                if not is_file:
                    other_count += 1
                    continue

                ext = os.path.splitext(name)[1].lower()
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
                            "name": name,
                            "type": media_type,
                            "size": size,
                            "folder": folder,
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


class LogSignaler(QObject):
    log_received = Signal(str)

log_signaler = LogSignaler()
