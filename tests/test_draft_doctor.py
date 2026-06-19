import pytest
import json
import shutil
import time
from pathlib import Path
from core.db import Database
import draft_doctor
import capcut_keyframe_tool as kt
from media_probe import MediaAsset

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    # Đóng kết nối cũ nếu có để giải phóng DB thật
    Database.close_connection()
    
    test_db = tmp_path / "test_draft_studio.db"
    Database.init_db(test_db)
    
    yield test_db
    
    # Đóng kết nối sau khi test xong
    Database.close_connection()

def test_check_draft_json(tmp_path):
    # 1. Test draft file not found
    issues = draft_doctor.check_draft_json(tmp_path / "nonexistent.json")
    assert len(issues) == 1
    assert issues[0].code == "draft_missing"

    # 2. Test invalid JSON format
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("invalid json {", encoding="utf-8")
    issues = draft_doctor.check_draft_json(bad_json)
    assert len(issues) == 1
    assert issues[0].code == "draft_json_invalid"

    # 3. Test basic valid draft structure but missing files
    draft_file = tmp_path / "draft_content.json"
    draft_data = {
        "materials": {
            "videos": [
                {"id": "vid_1", "path": str(tmp_path / "missing_video.mp4")}
            ],
            "audios": []
        },
        "tracks": [
            {
                "name": "Video Track",
                "type": "video",
                "segments": [
                    {
                        "material_id": "vid_1",
                        "target_timerange": {"start": 0, "duration": 5000000}
                    }
                ]
            }
        ]
    }
    draft_file.write_text(json.dumps(draft_data), encoding="utf-8")
    
    issues = draft_doctor.check_draft_json(draft_file)
    # Phải phát hiện ra video file bị thiếu
    assert any(i.code == "draft_local_file_missing" for i in issues)

def test_sqlite_backup_sync_and_prune(tmp_path):
    # Tạo dự án giả lập
    proj_dir = tmp_path / "test_project"
    proj_dir.mkdir()
    draft_file = proj_dir / "draft_content.json"
    draft_file.write_text("{}", encoding="utf-8")

    # 1. Thử tạo bản sao lưu qua draft_doctor
    draft_doctor._backup_and_write_text(draft_file, "{}", "Kiểm thử sao lưu SQLite")
    
    # Kiểm tra tệp .bak trên đĩa
    baks = list(proj_dir.glob("*.bak"))
    assert len(baks) == 1
    bak_file = baks[0]

    # Kiểm tra bản ghi trong database
    conn = Database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM backups WHERE project_dir = ?", (str(proj_dir.resolve()),))
    row = cursor.fetchone()
    assert row is not None
    assert row["backup_path"] == str(bak_file.resolve())
    assert row["note"] == "Kiểm thử sao lưu SQLite"

    # 2. Thử dọn dẹp sao lưu (prune)
    # Mock số lượng giữ lại là 0 để kích hoạt xóa
    draft_doctor._prune_repair_backups(draft_file, keep=0)
    
    # Đĩa phải trống tệp .bak
    assert not bak_file.exists()

    # SQLite phải xóa bản ghi
    cursor.execute("SELECT COUNT(*) as count FROM backups")
    assert cursor.fetchone()["count"] == 0

def test_smart_relink_with_metadata_matching(tmp_path, monkeypatch):
    # Mock probe_media để giả lập đọc metadata tệp
    def mock_probe_media(path, timeout_sec=15.0):
        p = str(Path(path).resolve())
        # Trả về asset khớp cho tệp correct và asset lệch cho tệp wrong
        if "correct" in p:
            return MediaAsset(path=p, media_type="video", duration_us=5000000, width=1920, height=1080)
        else:
            return MediaAsset(path=p, media_type="video", duration_us=9000000, width=1280, height=720)

    monkeypatch.setattr("media_probe.probe_media", mock_probe_media)

    # Khởi tạo thư mục dự án
    proj_dir = tmp_path / "my_project"
    proj_dir.mkdir()
    draft_file = proj_dir / "draft_content.json"
    
    # File gốc trỏ tới đường dẫn không tồn tại
    draft_data = {
        "materials": {
            "videos": [
                {
                    "id": "vid_1",
                    "path": "C:\\old_path\\clip.mp4",
                    "type": "video",
                    "duration": 5000000, # 5 giây
                    "width": 1920,
                    "height": 1080
                }
            ],
            "audios": []
        }
    }
    draft_file.write_text(json.dumps(draft_data), encoding="utf-8")

    # Tạo 2 thư mục media giả lập chứa 2 tệp trùng tên nhưng khác metadata
    media_dir_1 = tmp_path / "media_wrong"
    media_dir_2 = tmp_path / "media_correct"
    media_dir_1.mkdir()
    media_dir_2.mkdir()

    file_wrong = media_dir_1 / "clip.mp4"
    file_correct = media_dir_2 / "clip.mp4"
    file_wrong.write_text("wrong video", encoding="utf-8")
    file_correct.write_text("correct video", encoding="utf-8")

    # Chạy tự động sửa lỗi dự án, truyền cả 2 thư mục tìm kiếm
    actions = draft_doctor.repair_draft_project(proj_dir, media_dirs=[str(media_dir_1), str(media_dir_2)])

    # Đọc lại file draft_content.json đã sửa
    data_repaired = json.loads(draft_file.read_text(encoding="utf-8"))
    relinked_path = data_repaired["materials"]["videos"][0]["path"]

    # Phải tự động tìm thấy và liên kết vào tệp tin đúng dựa trên thời lượng và độ phân giải
    assert relinked_path == str(file_correct.resolve())
    assert any("Đã tìm thấy file" in act and "media_correct" in act for act in actions)

def test_keyframe_tool_backup_integration(tmp_path):
    # Khởi tạo cấu trúc dự án
    proj_dir = tmp_path / "keyframe_project"
    proj_dir.mkdir()
    draft_file = proj_dir / "draft_content.json"
    draft_file.write_text("{}", encoding="utf-8")

    # Thử gọi hàm lưu của keyframe tool
    kt._save_draft(draft_file, {"test": "data"}, "Sao lưu trước khi chỉnh keyframe")

    # Kiểm tra xem tệp .bak có được ghi vào SQLite hay không
    conn = Database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM backups WHERE project_dir = ?", (str(proj_dir.resolve()),))
    row = cursor.fetchone()
    assert row is not None
    assert "draft_content.json" in row["backup_path"]
    assert row["note"] == "Sao lưu trước khi chỉnh keyframe"


def test_case_insensitive_find_files_by_name(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    
    file_lower = media_dir / "my_video.mp4"
    file_lower.write_text("dummy", encoding="utf-8")
    
    matches = draft_doctor._find_files_by_name("MY_VIDEO.MP4", [media_dir])
    assert len(matches) == 1
    assert matches[0].resolve() == file_lower.resolve()
    
    file_jpg = media_dir / "photo.jpg"
    file_jpg.write_text("photo", encoding="utf-8")
    
    matches_jpeg = draft_doctor._find_files_by_name("photo.jpeg", [media_dir])
    assert len(matches_jpeg) == 1
    assert matches_jpeg[0].resolve() == file_jpg.resolve()


def test_restore_draft_backup(tmp_path):
    proj_dir = tmp_path / "project_restore"
    proj_dir.mkdir()
    
    draft_file = proj_dir / "draft_content.json"
    draft_file.write_text("original content", encoding="utf-8")
    
    backup_file = tmp_path / "backup_content.json"
    backup_file.write_text("backup content", encoding="utf-8")
    
    draft_doctor.restore_draft_backup(draft_file, backup_file)
    
    assert draft_file.read_text(encoding="utf-8") == "backup content"
    
    baks = list(proj_dir.glob("*.pre_restore.bak"))
    assert len(baks) == 1
    assert baks[0].read_text(encoding="utf-8") == "original content"
    
    conn = Database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM backups WHERE backup_path LIKE '%pre_restore%'")
    row = cursor.fetchone()
    assert row is not None


def test_clean_project_backups(tmp_path):
    import os
    proj_dir = tmp_path / "project_clean"
    proj_dir.mkdir()
    
    draft_file = proj_dir / "draft_content.json"
    draft_file.write_text("{}", encoding="utf-8")
    
    bak_old = proj_dir / "draft_content.json.old.bak"
    bak_old.write_text("old", encoding="utf-8")
    
    bak_new = proj_dir / "draft_content.json.new.bak"
    bak_new.write_text("new", encoding="utf-8")
    
    conn = Database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO backups (id, project_dir, backup_path, timestamp, note) VALUES (?, ?, ?, ?, ?)",
        ("1", str(proj_dir.resolve()), str(bak_old.resolve()), "2026-06-01 00:00:00", "old backup")
    )
    cursor.execute(
        "INSERT INTO backups (id, project_dir, backup_path, timestamp, note) VALUES (?, ?, ?, ?, ?)",
        ("2", str(proj_dir.resolve()), str(bak_new.resolve()), "2026-06-16 00:00:00", "new backup")
    )
    conn.commit()
    
    old_time = time.time() - 10 * 86400
    os.utime(bak_old, (old_time, old_time))
    os.utime(bak_new, (time.time(), time.time()))
    
    deleted, kept = draft_doctor.clean_project_backups(draft_file, keep_days=5)
    
    assert deleted == 1
    assert kept == 1
    assert not bak_old.exists()
    assert bak_new.exists()
    
    cursor.execute("SELECT COUNT(*) as count FROM backups WHERE id = '1'")
    assert cursor.fetchone()["count"] == 0
    cursor.execute("SELECT COUNT(*) as count FROM backups WHERE id = '2'")
    assert cursor.fetchone()["count"] == 1
