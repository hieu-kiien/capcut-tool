import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from core.db import Database
from app.pipeline import ProjectConfig
from app.queue_manager import BatchQueueManager
import draft_doctor

def test_clean_all_backups_retention(tmp_path):
    # Initialize DB
    Database.init_db()
    conn = Database.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM backups")
    conn.commit()

    # Create dummy backup files on disk
    old_file = tmp_path / "test_old_backup.bak"
    new_file = tmp_path / "test_new_backup.bak"
    old_file.write_text("old content")
    new_file.write_text("new content")

    # Insert backup records
    # Old backup: 10 days ago
    old_timestamp = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO backups (id, project_dir, backup_path, timestamp, note) VALUES (?, ?, ?, ?, ?)",
        ("id-old", str(tmp_path), str(old_file.resolve()), old_timestamp, "Old backup")
    )
    # New backup: 1 day ago
    new_timestamp = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO backups (id, project_dir, backup_path, timestamp, note) VALUES (?, ?, ?, ?, ?)",
        ("id-new", str(tmp_path), str(new_file.resolve()), new_timestamp, "New backup")
    )
    conn.commit()

    # Verify both records exist
    cursor.execute("SELECT count(*) as c FROM backups")
    assert cursor.fetchone()["c"] == 2
    assert old_file.exists()
    assert new_file.exists()

    # Run clean retention for older than 7 days
    deleted = draft_doctor.clean_all_backups_retention(7)
    
    # Assertions
    assert deleted == 1
    assert not old_file.exists()
    assert new_file.exists()

    cursor.execute("SELECT id FROM backups")
    remaining_ids = [r["id"] for r in cursor.fetchall()]
    assert "id-new" in remaining_ids
    assert "id-old" not in remaining_ids


@patch("PySide6.QtWidgets.QMessageBox.information")
def test_rerun_job(mock_info):
    from app.widgets.history_widget import HistoryWidget
    from PySide6.QtWidgets import QApplication
    import sys

    # Ensure QApplication exists for testing PySide widgets
    app = QApplication.instance() or QApplication(sys.argv)

    hw = HistoryWidget()
    # Mock window and build_widget
    mock_window = MagicMock()
    mock_build_widget = MagicMock()
    mock_window.build_widget = mock_build_widget
    hw.window = MagicMock(return_value=mock_window)

    job_data = {
        "project_name": "Test project",
        "inputs": {
            "project_name": "Test project",
            "draft_root": str(Path("dummy_root")),
            "voice_path": str(Path("dummy_voice")),
            "media_dir": str(Path("dummy_media")),
        }
    }

    # Clear queue first
    manager = BatchQueueManager.get_instance()
    manager.clear_queue()
    assert len(manager.jobs) == 0

    hw._rerun_job(job_data)

    # Verify the job was queued
    assert len(manager.jobs) == 1
    assert manager.jobs[0].project_name == "Test project"
    assert mock_build_widget.refresh_queue_table.called
    assert mock_window._switch_to_page.called
    mock_window._switch_to_page.assert_called_with("build-center")
