import json
import uuid
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, Signal, Slot, QThread, QRunnable, QThreadPool

from core.db import Database
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


class WorkerSignals(QObject):
    log_signal = Signal(str)
    step_signal = Signal(object)
    finished_signal = Signal(dict)
    failed_signal = Signal(str)


class QueuePipelineWorker(QRunnable):
    def __init__(self, config: ProjectConfig):
        super().__init__()
        self.config = config
        self.signals = WorkerSignals()
        self.cancel_requested = False
        
        # Expose signals directly for backward compatibility
        self.log_signal = self.signals.log_signal
        self.step_signal = self.signals.step_signal
        self.finished_signal = self.signals.finished_signal
        self.failed_signal = self.signals.failed_signal

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
        
        self._load_jobs_from_db()

    def _load_jobs_from_db(self):
        """Loads jobs from the SQLite database and resets any stuck 'running' jobs to 'failed'."""
        try:
            conn = Database.get_connection()
            cursor = conn.cursor()
            
            # Reset stuck running jobs
            cursor.execute(
                "UPDATE build_jobs SET status = 'failed', error_message = 'Bị gián đoạn do tắt ứng dụng đột ngột' WHERE status = 'running'"
            )
            conn.commit()
            
            # Load all jobs
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
                        subtitle_karaoke=cfg_dict.get("subtitle_karaoke", False)
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
                    print(f"Error parsing job config: {parse_err}")
        except Exception as db_err:
            print(f"Error loading jobs from DB: {db_err}")

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
            cursor = conn.cursor()
            cfg_json = json.dumps({
                k: v for k, v in config.__dict__.items()
                if not k.startswith("_")
            })
            cursor.execute(
                """
                INSERT INTO build_jobs (id, status, progress, project_name, config_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, "pending", 0, config.project_name, cfg_json)
            )
            conn.commit()
        except Exception as db_err:
            print(f"Error inserting job in DB: {db_err}")

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
            cursor = conn.cursor()
            cursor.execute("DELETE FROM build_jobs WHERE id = ?", (job_id,))
            conn.commit()
        except Exception as db_err:
            print(f"Error deleting job from DB: {db_err}")
            
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
            cursor = conn.cursor()
            if running_job:
                cursor.execute("DELETE FROM build_jobs WHERE id != ?", (running_job.id,))
                self.jobs = [running_job]
            else:
                cursor.execute("DELETE FROM build_jobs")
                self.jobs = []
            conn.commit()
        except Exception as db_err:
            print(f"Error clearing jobs in DB: {db_err}")

        self.queue_cleared.emit()

    def _run_next_job(self):
        """Finds and runs the next pending job in the queue."""
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
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE build_jobs SET status = 'running', started_at = ? WHERE id = ?",
                (next_job.started_at, next_job.id)
            )
            conn.commit()
        except Exception as db_err:
            print(f"Error updating job status: {db_err}")

        self.job_started.emit(next_job.id)
        
        # Launch using QThreadPool
        self.worker = QueuePipelineWorker(next_job.config)
        
        # Signals
        self.worker.log_signal.connect(self._on_worker_log)
        self.worker.step_signal.connect(self._on_worker_step)
        self.worker.finished_signal.connect(self._on_worker_finished)
        self.worker.failed_signal.connect(self._on_worker_failed)
        
        self._append_log_to_current("[HỆ THỐNG] Khởi động tiến trình xử lý hàng đợi trên QThreadPool...")
        QThreadPool.globalInstance().start(self.worker)

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
            
        # Map step code to progress percent
        step_progress_map = {
            "preflight": 25,
            "scan_media": 50,
            "plan_media": 75,
            "write_draft": 100
        }
        val = step_progress_map.get(step_res.code, 0)
        
        # Update in list
        for j in self.jobs:
            if j.id == self.current_job_id:
                j.progress = val
                
                # Update DB
                try:
                    conn = Database.get_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE build_jobs SET progress = ? WHERE id = ?", (val, j.id))
                    conn.commit()
                except Exception as db_err:
                    print(f"Error updating progress in DB: {db_err}")
                    
                msg = f"Bước: {step_res.label} ({step_res.status.upper()})"
                self.job_progress.emit(self.current_job_id, val, msg)
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
                    j.logs.append("[THÀNH CÔNG] Đã hoàn thành tác vụ tạo dự án nháp CapCut.")
                elif status == "cancelled":
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
                print(f"Error writing job history JSON: {hist_err}")
                
        # Update DB
        try:
            conn = Database.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE build_jobs SET status = ?, finished_at = ?, error_message = ?, progress = ? WHERE id = ?",
                (status, finished_at, error_msg, 100 if status == "completed" else 0, job_id)
            )
            conn.commit()
        except Exception as db_err:
            print(f"Error updating job final state in DB: {db_err}")

        # Emit finished
        self.job_finished.emit(job_id, status, error_msg or "")
        
        # Reset current and run next job
        self.current_job_id = None
        self.worker = None
        self.thread = None
        
        # Automatically run next job in queue (non-blocking)
        self._run_next_job()

    @Slot()
    def _on_thread_finished(self):
        # Safe cleanup
        pass
