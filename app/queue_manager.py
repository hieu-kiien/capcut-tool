import json
import uuid
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, Signal, Slot, QThread, QRunnable, QThreadPool, QMutex, QMutexLocker, QRecursiveMutex, Qt

from core.db import Database
from core.logger import logger
from app.pipeline import PipelineRunner, ProjectConfig, StepResult

class BuildJob:
    def __init__(
        self,
        job_id: str,
        project_name: str,
        config: ProjectConfig,
        status: str = "pending",
        progress: int = 0,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        self.id = job_id
        self.project_name = project_name
        self.config = config
        self.status = status
        self.progress = progress
        self.started_at = started_at
        self.finished_at = finished_at
        self.error_message = error_message
        self.logs: List[str] = []
        self.step_states = {
            "preflight": "pending",
            "scan_media": "pending",
            "plan_media": "pending",
            "write_draft": "pending"
        }
        if self.status == "completed":
            self.step_states = {k: "done" for k in self.step_states}
        elif self.status in ("failed", "cancelled"):
            err_state = "cancelled" if self.status == "cancelled" else "error"
            if self.progress < 25:
                self.step_states["preflight"] = err_state
            elif self.progress < 50:
                self.step_states["preflight"] = "done"
                self.step_states["scan_media"] = err_state
            elif self.progress < 75:
                self.step_states["preflight"] = "done"
                self.step_states["scan_media"] = "done"
                self.step_states["plan_media"] = err_state
            else:
                self.step_states["preflight"] = "done"
                self.step_states["scan_media"] = "done"
                self.step_states["plan_media"] = "done"
                self.step_states["write_draft"] = err_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_name": self.project_name,
            "status": self.status,
            "progress": self.progress,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error_message": self.error_message,
        }


class QueuePipelineWorker(QObject):
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


class BatchQueueManager(QObject):
    # Signals for UI connection
    job_added = Signal(object)  # Emits BuildJob
    job_started = Signal(str)  # Emits job_id
    job_progress = Signal(str, int, str)  # job_id, progress%, message
    job_step_changed = Signal(str, str, str, str)  # job_id, step_code, status, message
    step_changed = Signal(str, str, str)  # step_code, status, message
    job_finished = Signal(str, str, str)  # job_id, status, error_message
    job_log_appended = Signal(str, str)  # job_id, log_line
    queue_status_changed = Signal(bool, bool)  # is_running, is_paused
    queue_cleared = Signal()
    job_removed = Signal(str) # job_id

    _instance = None

    @classmethod
    def get_instance(cls) -> "BatchQueueManager":
        if cls._instance is None:
            cls._instance = BatchQueueManager()
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        super().__init__()
        self._initialized = True
        self.jobs: List[BuildJob] = []
        self.is_running = False
        self.is_paused = False
        
        self.current_job_id: Optional[str] = None
        self.thread: Optional[QThread] = None
        self.worker: Optional[QueuePipelineWorker] = None
        # Recursive: _finish_current_job() tail-calls _run_next_job() to chain the
        # next job, so the lock is re-entered on the same thread. A plain QMutex
        # deadlocks there whenever a job finishes synchronously.
        self._mutex = QRecursiveMutex()
        
        self._load_jobs_from_db()

    def _load_jobs_from_db(self):
        """Loads jobs from the SQLite database and resets any stuck 'running' jobs to 'failed'."""
        try:
            conn = Database.get_connection()
            with conn:
                conn.execute(
                    "UPDATE build_jobs SET status = 'failed', error_message = 'Bị gián đoạn do tắt ứng dụng đột ngột' WHERE status = 'running'"
                )
            
            # Load all jobs
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM build_jobs ORDER BY started_at ASC, id ASC")
            rows = cursor.fetchall()
            for row in rows:
                try:
                    cfg_dict = json.loads(row["config_json"])
                    # Reconstruct ProjectConfig
                    cfg = ProjectConfig(
                        project_name=cfg_dict.get("project_name", ""),
                        draft_root=cfg_dict.get("draft_root", ""),
                        voice_path=cfg_dict.get("voice_path", ""),
                        media_dir=cfg_dict.get("media_dir", ""),
                        bgm_path=cfg_dict.get("bgm_path", ""),
                        srt_path=cfg_dict.get("srt_path", ""),
                        intro_path=cfg_dict.get("intro_path", ""),
                        outro_path=cfg_dict.get("outro_path", ""),
                        logo_path=cfg_dict.get("logo_path", ""),
                        logo_position=cfg_dict.get("logo_position", "top_right"),
                        logo_scale=cfg_dict.get("logo_scale", 15.0),
                        logo_opacity=cfg_dict.get("logo_opacity", 1.0),
                        anim_path=cfg_dict.get("anim_path", ""),
                        anim_position=cfg_dict.get("anim_position", "bottom_center"),
                        anim_scale=cfg_dict.get("anim_scale", 30.0),
                        anim_timing=cfg_dict.get("anim_timing", "end"),
                        canvas=cfg_dict.get("canvas", "9:16"),
                        clip_min_sec=cfg_dict.get("clip_min_sec", 5.0),
                        clip_max_sec=cfg_dict.get("clip_max_sec", 12.0),
                        selection_mode=cfg_dict.get("selection_mode", "shuffle_bag"),
                        short_video_mode=cfg_dict.get("short_video_mode", "stretch"),
                        recursive_scan=cfg_dict.get("recursive_scan", False),
                        auto_keyframe=cfg_dict.get("auto_keyframe", "none"),
                        auto_transition=cfg_dict.get("auto_transition", "none"),
                        auto_transition_duration=cfg_dict.get("auto_transition_duration", 0.4),
                        bg_switch_mode=cfg_dict.get("bg_switch_mode", "time"),
                        bg_switch_group_size=cfg_dict.get("bg_switch_group_size", 3),
                        chroma_enabled=cfg_dict.get("chroma_enabled", False),
                        chroma_mode=cfg_dict.get("chroma_mode", "green"),
                        chroma_threshold=cfg_dict.get("chroma_threshold", 32),
                        chroma_shadow=cfg_dict.get("chroma_shadow", 2),
                        subtitle_karaoke=cfg_dict.get("subtitle_karaoke", False),
                        allow_replace=cfg_dict.get("allow_replace", False),
                        logo_bg_mode=cfg_dict.get("logo_bg_mode", "none"),
                        anim_bg_mode=cfg_dict.get("anim_bg_mode", "none"),
                        ffmpeg_overlay_timeout_sec=cfg_dict.get("ffmpeg_overlay_timeout_sec", 60.0),
                        subtitle_font_size=cfg_dict.get("subtitle_font_size", 6.0),
                        subtitle_color=tuple(cfg_dict.get("subtitle_color", (1.0, 1.0, 1.0))) if "subtitle_color" in cfg_dict else (1.0, 1.0, 1.0),
                        subtitle_bold=cfg_dict.get("subtitle_bold", True),
                        subtitle_outline_width=cfg_dict.get("subtitle_outline_width", 40.0),
                        subtitle_shadow_alpha=cfg_dict.get("subtitle_shadow_alpha", 0.8),
                        subtitle_shadow_distance=cfg_dict.get("subtitle_shadow_distance", 5.0)
                    )
                    job = BuildJob(
                        job_id=row["id"],
                        project_name=row["project_name"] or cfg.project_name,
                        config=cfg,
                        status=row["status"],
                        progress=row["progress"],
                        started_at=row["started_at"],
                        finished_at=row["finished_at"],
                        error_message=row["error_message"]
                    )
                    # For completed/failed jobs, add a default log line
                    if job.status == "completed":
                        job.logs.append("[THÀNH CÔNG] Đã dựng thành công dự án nháp CapCut.")
                    elif job.status == "failed":
                        job.logs.append(f"[LỖI] Dựng thất bại: {job.error_message}")
                    
                    self.jobs.append(job)
                except Exception as parse_err:
                    logger.error(f"[QUEUE] Error parsing job config: {parse_err}")
        except Exception as db_err:
            logger.error(f"[QUEUE] Error loading jobs from DB: {db_err}")

    def add_job(self, config: ProjectConfig) -> str:
        """Adds a new ProjectConfig as a pending BuildJob in the queue."""
        job_id = str(uuid.uuid4())
        job = BuildJob(
            job_id=job_id,
            project_name=config.project_name,
            config=config,
            status="pending",
            progress=0
        )
        self.jobs.append(job)
        
        # Save to DB
        try:
            conn = Database.get_connection()
            cfg_json = json.dumps({
                k: v for k, v in config.__dict__.items()
                if not k.startswith("_")
            })
            with conn:
                conn.execute(
                    """
                    INSERT INTO build_jobs (id, status, progress, project_name, config_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (job_id, "pending", 0, config.project_name, cfg_json)
                )
        except Exception as db_err:
            logger.error(f"[QUEUE] Error inserting job in DB: {db_err}")

        # Log system event
        job.logs.append(f"[HỆ THỐNG] Đã thêm dự án '{config.project_name}' vào hàng đợi dựng.")
        self.job_added.emit(job)
        
        # Auto start queue if already running
        if self.is_running and not self.is_paused and self.current_job_id is None:
            self._run_next_job()
            
        return job_id

    def remove_job(self, job_id: str):
        """Removes a job from the queue. Cancels it if it is currently running."""
        # Find job
        job_idx = -1
        for idx, j in enumerate(self.jobs):
            if j.id == job_id:
                job_idx = idx
                break
        
        if job_idx == -1:
            return

        job = self.jobs[job_idx]
        
        # If running, cancel first
        if job.id == self.current_job_id:
            self.cancel_current_job()
            # We don't remove immediately; we wait for finished signal to clean up
            # But we mark it to be deleted
            job.status = "cancelled"
            
        # Delete from list and DB
        self.jobs.pop(job_idx)
        try:
            conn = Database.get_connection()
            with conn:
                conn.execute("DELETE FROM build_jobs WHERE id = ?", (job_id,))
        except Exception as db_err:
            logger.error(f"[QUEUE] Error deleting job from DB: {db_err}")
            
        self.job_removed.emit(job_id)

    def start_queue(self):
        """Starts processing jobs in the queue."""
        if self.is_running and not self.is_paused:
            return
            
        self.is_running = True
        self.is_paused = False
        self.queue_status_changed.emit(self.is_running, self.is_paused)
        
        self._run_next_job()

    def pause_queue(self):
        """Pauses the queue. The current job will finish running, but next jobs will not start."""
        self.is_paused = True
        self.queue_status_changed.emit(self.is_running, self.is_paused)

    def cancel_current_job(self):
        """Cancels the currently executing job."""
        if self.worker and self.current_job_id:
            self._append_log_to_current("[HỆ THỐNG] Đang gửi yêu cầu hủy bỏ tác vụ dựng...")
            self.worker.cancel()

    def clear_queue(self):
        """Removes all pending and completed/failed jobs from the queue."""
        # Clean from DB (only pending jobs or all of them)
        # Typically we keep running/paused and remove pending/completed
        running_job = None
        for j in self.jobs:
            if j.id == self.current_job_id:
                running_job = j
                break
                
        try:
            conn = Database.get_connection()
            with conn:
                if running_job:
                    conn.execute("DELETE FROM build_jobs WHERE id != ?", (running_job.id,))
                    self.jobs = [running_job]
                else:
                    conn.execute("DELETE FROM build_jobs")
                    self.jobs = []
        except Exception as db_err:
            logger.error(f"[QUEUE] Error clearing jobs in DB: {db_err}")

        self.queue_cleared.emit()

    def _run_next_job(self):
        """Finds and runs the next pending job in the queue."""
        locker = QMutexLocker(self._mutex)
        if not self.is_running or self.is_paused:
            return
        if self.current_job_id is not None:
            return

        # Find next pending job
        next_job: Optional[BuildJob] = None
        for job in self.jobs:
            if job.status == "pending":
                next_job = job
                break

        if next_job is None:
            # Queue complete
            self.is_running = False
            self.queue_status_changed.emit(self.is_running, self.is_paused)
            return

        self.current_job_id = next_job.id
        next_job.status = "running"
        next_job.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update DB status
        try:
            conn = Database.get_connection()
            with conn:
                conn.execute(
                    "UPDATE build_jobs SET status = 'running', started_at = ? WHERE id = ?",
                    (next_job.started_at, next_job.id)
                )
        except Exception as db_err:
            logger.error(f"[QUEUE] Error updating job status: {db_err}")

        self.job_started.emit(next_job.id)
        
        # Launch using QThread
        self.thread = QThread()
        self.worker = QueuePipelineWorker(next_job.config)
        self.worker.moveToThread(self.thread)
        
        # Signals
        self.thread.started.connect(self.worker.run, Qt.QueuedConnection)
        self.worker.log_signal.connect(self._on_worker_log, Qt.QueuedConnection)
        self.worker.step_signal.connect(self._on_worker_step, Qt.QueuedConnection)
        self.worker.finished_signal.connect(self._on_worker_finished, Qt.QueuedConnection)
        self.worker.failed_signal.connect(self._on_worker_failed, Qt.QueuedConnection)
        
        # Cleanup connection when finished
        self.worker.finished_signal.connect(self.thread.quit)
        self.worker.failed_signal.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._on_thread_finished)
        
        self._append_log_to_current("[HỆ THỐNG] Khởi động tiến trình xử lý hàng đợi trên QThread...")
        self.thread.start()

    def _append_log_to_current(self, text: str):
        if self.current_job_id:
            for j in self.jobs:
                if j.id == self.current_job_id:
                    j.logs.append(text)
                    self.job_log_appended.emit(self.current_job_id, text)
                    break

    @Slot(str)
    def _on_worker_log(self, text: str):
        self._append_log_to_current(text)

    @Slot(object)
    def _on_worker_step(self, step_res: StepResult):
        if not self.current_job_id:
            return
            
        # Map step code and status to progress percent (smoothly dividing it)
        if step_res.status == "running":
            progress_map = {
                "preflight": 5,
                "scan_media": 30,
                "plan_media": 55,
                "write_draft": 80
            }
        else: # done, error, cancelled
            progress_map = {
                "preflight": 25,
                "scan_media": 50,
                "plan_media": 75,
                "write_draft": 100
            }
        val = progress_map.get(step_res.code, 0)
        
        # Update in list
        for j in self.jobs:
            if j.id == self.current_job_id:
                j.progress = val
                
                # Update detailed step states based on backend step result
                code = step_res.code
                status = step_res.status  # "running", "done", "error", "cancelled"
                canonical_codes = ["preflight", "scan_media", "plan_media", "write_draft"]
                if code in canonical_codes:
                    code_idx = canonical_codes.index(code)
                    for prev_code in canonical_codes[:code_idx]:
                        j.step_states[prev_code] = "done"
                    j.step_states[code] = status
                
                # Update DB
                try:
                    conn = Database.get_connection()
                    with conn:
                        conn.execute("UPDATE build_jobs SET progress = ? WHERE id = ?", (val, j.id))
                except Exception as db_err:
                    logger.error(f"[QUEUE] Error updating progress in DB: {db_err}")
                    
                msg = step_res.message or f"Bước: {step_res.label} ({step_res.status.upper()})"
                self.job_progress.emit(self.current_job_id, val, msg)
                self.job_step_changed.emit(self.current_job_id, code, status, msg)
                self.step_changed.emit(code, status, msg)
                break

    @Slot(dict)
    def _on_worker_finished(self, result: dict):
        self._finish_current_job("completed")

    @Slot(str)
    def _on_worker_failed(self, error_msg: str):
        # If it was cancelled
        for j in self.jobs:
            if j.id == self.current_job_id:
                if "JobCancelled" in error_msg or j.status == "cancelled":
                    self._finish_current_job("cancelled", "Người dùng đã hủy bỏ tác vụ.")
                else:
                    self._finish_current_job("failed", error_msg)
                break

    def _finish_current_job(self, status: str, error_msg: Optional[str] = None):
        if not self.current_job_id:
            return
            
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        job_id = self.current_job_id
        
        # Update job
        job_obj = None
        for j in self.jobs:
            if j.id == job_id:
                j.status = status
                j.finished_at = finished_at
                j.error_message = error_msg
                if status == "completed":
                    j.progress = 100
                    j.step_states = {k: "done" for k in j.step_states}
                    j.logs.append("[THÀNH CÔNG] Đã hoàn thành tác vụ tạo dự án nháp CapCut.")
                elif status in ("cancelled", "failed"):
                    # Update running/non-done step to error state
                    step_status = "cancelled" if status == "cancelled" else "error"
                    canonical_codes = ["preflight", "scan_media", "plan_media", "write_draft"]
                    found_running = False
                    for step in canonical_codes:
                        if j.step_states.get(step) == "running":
                            j.step_states[step] = step_status
                            found_running = True
                            break
                    if not found_running:
                        for step in canonical_codes:
                            if j.step_states.get(step) != "done":
                                j.step_states[step] = step_status
                                break
                    
                    if status == "cancelled":
                        j.logs.append("[CẢNH BÁO] Tác vụ đã bị hủy bỏ bởi người dùng.")
                    else:
                        j.logs.append(f"[LỖI] Tiến trình thất bại: {error_msg}")
                job_obj = j
                break
                
        if job_obj:
            try:
                from app.history import write_job_history
                import dataclasses
                root_dir = Path(__file__).resolve().parent.parent
                config_dict = {}
                if job_obj.config:
                    if dataclasses.is_dataclass(job_obj.config):
                        config_dict = dataclasses.asdict(job_obj.config)
                    else:
                        for field in ("project_name", "draft_root", "voice_path", "media_dir", "bgm_path", "srt_path"):
                            if hasattr(job_obj.config, field):
                                config_dict[field] = getattr(job_obj.config, field)
                                
                job_data = {
                    "project_name": job_obj.project_name,
                    "started_at": job_obj.started_at or finished_at,
                    "finished_at": finished_at,
                    "status": "success" if status == "completed" else ("cancelled" if status == "cancelled" else "failed"),
                    "inputs": config_dict,
                    "error": error_msg or ""
                }
                write_job_history("pipeline", job_data, root_dir)
            except Exception as hist_err:
                logger.error(f"[QUEUE] Error writing job history JSON: {hist_err}")
                
        # Update DB
        try:
            conn = Database.get_connection()
            with conn:
                conn.execute(
                    "UPDATE build_jobs SET status = ?, finished_at = ?, error_message = ?, progress = ? WHERE id = ?",
                    (status, finished_at, error_msg, 100 if status == "completed" else 0, job_id)
                )
        except Exception as db_err:
            logger.error(f"[QUEUE] Error updating job final state in DB: {db_err}")

        # Emit finished
        self.job_finished.emit(job_id, status, error_msg or "")
        
        # Reset current and run next job
        self.current_job_id = None
        self.worker = None
        self.thread = None
        
        # Automatically run next job in queue only if actively running and not shutting down
        if self.is_running and not self.is_paused:
            self._run_next_job()

    @Slot()
    def _on_thread_finished(self):
        # Safe cleanup
        pass

    def shutdown(self, wait_ms: int = 5000) -> bool:
        """
        Shuts down the queue manager, cancels the current job,
        terminates all child processes (FFmpeg, yt-dlp, etc.),
        and cleanly waits for/terminates the running worker thread.
        """
        # 1. Stop queue processing
        self.is_running = False
        self.is_paused = True
        
        # 2. Cancel current job
        if self.current_job_id:
            self.cancel_current_job()
            
        # 3. Terminate all child processes to unblock threads
        self.terminate_child_processes()
        
        # 4. Wait for the worker thread to finish
        if self.thread is not None:
            try:
                if self.thread.isRunning():
                    self.thread.requestInterruption()
                    self.thread.quit()
                    if not self.thread.wait(wait_ms):
                        logger.warning("[QUEUE] Worker thread did not exit cleanly within timeout, terminating...")
                        self.thread.terminate()
                        self.thread.wait(1000)
            except Exception as e:
                logger.error(f"[QUEUE] Error waiting for thread shutdown: {e}")

        # Also wait for worker reference to clear if still processing
        if self.worker is not None:
            import time
            from PySide6.QtCore import QCoreApplication
            start_time = time.monotonic()
            while self.worker is not None and (time.monotonic() - start_time) * 1000 < min(1000, wait_ms):
                QCoreApplication.processEvents()
                time.sleep(0.05)
                
        return True

    def terminate_child_processes(self):
        """Terminates child subprocesses (FFmpeg, yt-dlp, etc.) spawned by the app using psutil."""
        import os
        try:
            import psutil
            target_names = {"ffmpeg", "ffprobe", "yt-dlp", "gallery-dl", "ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe", "gallery-dl.exe"}
            current_process = psutil.Process(os.getpid())
            children = current_process.children(recursive=True)
            
            targets = []
            for child in children:
                try:
                    name = child.name().lower()
                    cmdline = [arg.lower() for arg in (child.cmdline() or [])]
                    
                    is_target = (name in target_names)
                    if not is_target and "python" in name:
                        # Check if running a target module
                        if any(mod in cmdline for mod in ["yt_dlp", "gallery_dl"]):
                            is_target = True
                            
                    if is_target:
                        targets.append(child)
                except Exception:
                    pass
                    
            for child in targets:
                try:
                    child.terminate()
                except Exception:
                    pass
            # Wait up to 1 second for graceful termination, then force kill
            gone, alive = psutil.wait_procs(targets, timeout=1.0)
            for child in alive:
                try:
                    child.kill()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"[QUEUE] Error terminating child processes: {e}")
