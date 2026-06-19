import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from core.db import Database
from assets.manager import AssetManager, get_md5_hash
from media_probe import MediaAsset, scan_media_folder

@pytest.fixture(scope="function")
def temp_db():
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_db_path = Path(tmp_dir) / "test_studio.db"
        Database.close_connection()
        Database.init_db(temp_db_path)
        yield temp_db_path
        Database.close_connection()

def test_assets_table_migration(temp_db):
    conn = Database.get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(assets);")
    columns = [row["name"] for row in cursor.fetchall()]
    
    assert "category_name" in columns
    assert "md5_hash" in columns

def test_md5_hashing(temp_db):
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp_path = Path(f.name)
        tmp_path.write_text("Hello World of CapCut!")
        
    try:
        md5_1 = get_md5_hash(tmp_path)
        assert len(md5_1) == 32
        
        # Verify idempotency
        md5_2 = get_md5_hash(tmp_path)
        assert md5_1 == md5_2
        
        # Verify mismatch
        tmp_path.write_text("Modified content")
        md5_3 = get_md5_hash(tmp_path)
        assert md5_1 != md5_3
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass

@patch("assets.manager.probe_media")
def test_asset_import_crud(mock_probe, temp_db):
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        tmp_path = Path(f.name)
        tmp_path.write_text("mock binary data")
        
    try:
        mock_probe.return_value = MediaAsset(
            path=str(tmp_path),
            media_type="video",
            duration_us=5000000,
            width=1280,
            height=720,
            fps=25.0
        )
        
        # 1. Import
        asset_id = AssetManager.import_single_asset(tmp_path, category_name="intro", tags="gaming, intro")
        assert asset_id is not None
        
        # 2. Get and Verify
        asset = AssetManager.get_asset(asset_id)
        assert asset is not None
        assert asset["filename"] == tmp_path.name
        assert asset["category_name"] == "intro"
        assert asset["tags"] == "gaming, intro"
        assert asset["width"] == 1280
        assert asset["height"] == 720
        assert asset["fps"] == 25.0
        assert asset["duration_us"] == 5000000
        
        # 3. Deduplication (Same MD5 hash should return the same asset ID)
        duplicate_id = AssetManager.import_single_asset(tmp_path, category_name="outro")
        assert duplicate_id == asset_id
        
        # 4. Search & List
        assets_all = AssetManager.list_assets()
        assert len(assets_all) == 1
        
        assets_filtered = AssetManager.list_assets(category_name="outro")
        assert len(assets_filtered) == 0  # Deduplication kept it as "intro"
        
        assets_search = AssetManager.list_assets(search_query="gaming")
        assert len(assets_search) == 1
        
        # 5. Update Metadata
        update_ok = AssetManager.update_asset_metadata(asset_id, tags="vlog", category_name="outro")
        assert update_ok is True
        
        updated = AssetManager.get_asset(asset_id)
        assert updated["tags"] == "vlog"
        assert updated["category_name"] == "outro"
        
        # 6. Delete
        delete_ok = AssetManager.delete_asset(asset_id)
        assert delete_ok is True
        assert AssetManager.get_asset(asset_id) is None
        
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass

def test_parallel_media_scanning(temp_db):
    # Tests ThreadPoolExecutor parallel scan in media_probe.py
    import tempfile
    import runtime_tools
    ffmpeg_exe = runtime_tools.resolve_ffmpeg()
    if not ffmpeg_exe:
        pytest.skip("ffmpeg not found, skipping parallel scan E2E test")
        
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create 3 dummy mp4 files (silence color videos) using ffmpeg
        import subprocess
        for i in range(3):
            video_file = tmp_path / f"video_{i}.mp4"
            cmd = [
                ffmpeg_exe, "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=1",
                "-t", "1", str(video_file)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
        # Run parallel scan
        assets = scan_media_folder(tmp_path, recursive=False)
        assert len(assets) == 3
        for idx, asset in enumerate(assets):
            assert asset.media_type == "video"
            assert asset.width == 160
            assert asset.height == 120
            assert asset.duration_us >= 900000  # approximately 1s

def test_gui_media_studio_integration(temp_db):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    
    from app.gui import MainWindow
    window = MainWindow()
    
    try:
        # Check widgets exist
        assert hasattr(window, "media_studio_widget"), "media_studio_widget missing"
        assert hasattr(window.media_studio_widget, "table"), "media_studio_widget table missing"
        assert hasattr(window.media_studio_widget, "search_edit"), "search_edit missing"
        assert hasattr(window.media_studio_widget, "filter_category"), "filter_category missing"
        assert hasattr(window.media_studio_widget, "btn_import_files"), "btn_import_files missing"
        assert hasattr(window.media_studio_widget, "btn_import_dir"), "btn_import_dir missing"
    finally:
        window.close()
