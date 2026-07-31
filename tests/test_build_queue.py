import pytest
import time
import json
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QThread, QThreadPool
from app.pipeline import ProjectConfig
from app.queue_manager import BatchQueueManager, BuildJob
from core.db import Database

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    # Đóng kết nối cũ nếu có để giải phóng DB thật
    Database.close_connection()
    
    test_db = tmp_path / "test_draft_studio.db"
    Database.init_db(test_db)
    
    # Làm mới manager để liên kết với database test mới
    manager = BatchQueueManager.get_instance()
    manager.jobs = []
    manager.current_job_id = None
    manager.is_running = False
    manager.is_paused = False
    manager._load_jobs_from_db()
    
    yield test_db
    
    # Đóng kết nối sau khi test xong
    Database.close_connection()

def test_add_remove_clear_queue():
    manager = BatchQueueManager.get_instance()
    manager.jobs = []
    manager.current_job_id = None

    config = ProjectConfig(
        project_name="Test_Proj_1",
        draft_root="C:/dummy_root",
        voice_path="C:/dummy_voice.mp3",
        media_dir="C:/dummy_media"
    )

    # 1. Test Add Job
    job_id = manager.add_job(config)
    assert len(manager.jobs) == 1
    assert manager.jobs[0].project_name == "Test_Proj_1"
    assert manager.jobs[0].status == "pending"

    # Kiểm tra lưu vào DB
    conn = Database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM build_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row["project_name"] == "Test_Proj_1"
    assert row["status"] == "pending"

    # 2. Test Remove Job
    manager.remove_job(job_id)
    assert len(manager.jobs) == 0
    
    cursor.execute("SELECT COUNT(*) as count FROM build_jobs")
    assert cursor.fetchone()["count"] == 0

    # 3. Test Clear Queue
    manager.add_job(config)
    manager.add_job(config)
    assert len(manager.jobs) == 2
    
    manager.clear_queue()
    assert len(manager.jobs) == 0

def test_queue_run_next_logic(monkeypatch):
    app = QCoreApplication.instance()
    if not app:
        app = QCoreApplication([])
        
    manager = BatchQueueManager.get_instance()
    
    # Mock QThread.start để chạy đồng bộ trên main thread
    def mock_thread_start(self_thread):
        manager.worker.run()
        QCoreApplication.processEvents()

    monkeypatch.setattr(QThread, "start", mock_thread_start)

    config_invalid = ProjectConfig(
        project_name="Invalid_Proj",
        draft_root="C:/invalid_root",
        voice_path="C:/invalid_voice.mp3",  # Bắt buộc phải fail ở preflight do file không tồn tại
        media_dir="C:/invalid_media"
    )

    job_id = manager.add_job(config_invalid)
    assert manager.jobs[0].status == "pending"

    # Chạy queue (sẽ chạy đồng bộ do đã mock QThread.start)
    manager.start_queue()

    # Sau khi chạy xong, job phải chuyển sang failed và queue dừng lại
    assert manager.jobs[0].status == "failed"
    assert manager.jobs[0].progress == 25
    assert manager.jobs[0].error_message is not None
    assert manager.is_running is False

def test_queue_load_restore_subtitle_styles():
    manager = BatchQueueManager.get_instance()
    manager.jobs = []
    manager.current_job_id = None

    config = ProjectConfig(
        project_name="Test_Proj_Restore",
        draft_root="C:/dummy_root",
        voice_path="C:/dummy_voice.mp3",
        media_dir="C:/dummy_media",
        subtitle_font_size=15.0,
        subtitle_color=(0.5, 1.0, 0.0),
        subtitle_bold=False,
        subtitle_outline_width=25.0,
        subtitle_shadow_alpha=0.3,
        subtitle_shadow_distance=8.0,
        chroma_enabled=True,
        subtitle_karaoke=True
    )

    # Add job to DB
    job_id = manager.add_job(config)
    assert len(manager.jobs) == 1

    # Clear memory queue state
    manager.jobs = []
    
    # Reload from DB
    manager._load_jobs_from_db()
    
    assert len(manager.jobs) == 1
    restored_config = manager.jobs[0].config
    
    assert restored_config.project_name == "Test_Proj_Restore"
    assert restored_config.subtitle_font_size == 15.0
    assert restored_config.subtitle_color == (0.5, 1.0, 0.0)
    assert restored_config.subtitle_bold is False
    assert restored_config.subtitle_outline_width == 25.0
    assert restored_config.subtitle_shadow_alpha == 0.3
    assert restored_config.subtitle_shadow_distance == 8.0
    assert restored_config.chroma_enabled is True
    assert restored_config.subtitle_karaoke is True
