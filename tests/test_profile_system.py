import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from core.db import Database
from profiles.manager import ProfileManager

@pytest.fixture(scope="function")
def temp_db():
    # Use a temporary file for the database instead of in-memory to ensure WAL and path logic work correctly
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = Path(f.name)
    
    # Close any existing connections and init new temp DB
    Database.close_connection()
    Database.init_db(temp_db_path)
    
    yield temp_db_path
    
    Database.close_connection()
    try:
        temp_db_path.unlink()
        # Clean up WAL and SHM files
        wal_path = temp_db_path.with_name(temp_db_path.name + "-wal")
        shm_path = temp_db_path.with_name(temp_db_path.name + "-shm")
        if wal_path.exists():
            wal_path.unlink()
        if shm_path.exists():
            shm_path.unlink()
    except Exception:
        pass

def test_db_initialization(temp_db):
    conn = Database.get_connection()
    cursor = conn.cursor()
    
    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r["name"] for r in cursor.fetchall()]
    
    assert "profiles" in tables
    assert "profile_versions" in tables
    assert "projects" in tables
    assert "templates" in tables
    assert "assets" in tables
    assert "build_jobs" in tables
    assert "history" in tables
    assert "backups" in tables

def test_profile_crud(temp_db):
    # Create profile
    p_id = ProfileManager.create_profile(
        name="Test_Profile_1",
        canvas="16:9",
        clip_min_sec=3.0,
        clip_max_sec=10.0,
        selection_mode="sequential",
        logo_path="C:/logos/logo.png"
    )
    assert p_id is not None
    
    # Get profile
    profile = ProfileManager.get_profile(p_id)
    assert profile is not None
    assert profile["name"] == "Test_Profile_1"
    assert profile["canvas"] == "16:9"
    assert profile["clip_min_sec"] == 3.0
    assert profile["clip_max_sec"] == 10.0
    assert profile["selection_mode"] == "sequential"
    assert profile["logo_path"] == "C:/logos/logo.png"
    assert profile["version"] == 1
    
    # Get by name
    profile_by_name = ProfileManager.get_profile_by_name("Test_Profile_1")
    assert profile_by_name is not None
    assert profile_by_name["id"] == p_id
    
    # List profiles
    profiles = ProfileManager.list_profiles()
    assert any(p["name"] == "Test_Profile_1" for p in profiles)
    
    # Update profile (should increment version and save history)
    success = ProfileManager.update_profile(
        p_id,
        canvas="9:16",
        logo_scale=20.0,
        update_note="Changed canvas and scale"
    )
    assert success is True
    
    updated = ProfileManager.get_profile(p_id)
    assert updated["canvas"] == "9:16"
    assert updated["logo_scale"] == 20.0
    assert updated["version"] == 2
    
    # Check history record
    versions = ProfileManager.get_versions(p_id)
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert versions[0]["note"] == "Changed canvas and scale"
    
    # Delete profile
    deleted = ProfileManager.delete_profile(p_id)
    assert deleted is True
    assert ProfileManager.get_profile(p_id) is None
    # Cascaded delete of history
    assert len(ProfileManager.get_versions(p_id)) == 0

def test_profile_cloning(temp_db):
    p_id = ProfileManager.create_profile(
        name="Source_Profile",
        canvas="9:16",
        clip_min_sec=4.0,
        logo_path="C:/logo.png"
    )
    
    # Clone
    clone_id = ProfileManager.clone_profile(p_id, "Cloned_Profile")
    assert clone_id is not None
    assert clone_id != p_id
    
    clone = ProfileManager.get_profile(clone_id)
    assert clone is not None
    assert clone["name"] == "Cloned_Profile"
    assert clone["canvas"] == "9:16"
    assert clone["clip_min_sec"] == 4.0
    assert clone["logo_path"] == "C:/logo.png"
    assert clone["version"] == 1
    
    # Try cloning with same name (should fail)
    fail_clone = ProfileManager.clone_profile(p_id, "Cloned_Profile")
    assert fail_clone is None

def test_profile_version_rollback(temp_db):
    p_id = ProfileManager.create_profile(name="Rollback_Profile", canvas="9:16")
    
    # Version 1 -> Version 2
    ProfileManager.update_profile(p_id, canvas="16:9")
    # Version 2 -> Version 3
    ProfileManager.update_profile(p_id, selection_mode="random")
    
    # Verify current state (Version 3)
    current = ProfileManager.get_profile(p_id)
    assert current["canvas"] == "16:9"
    assert current["selection_mode"] == "random"
    assert current["version"] == 3
    
    # Check history contains versions 1 and 2
    versions = ProfileManager.get_versions(p_id)
    assert len(versions) == 2
    
    # Rollback to Version 1 (should have canvas="9:16" and selection_mode="shuffle_bag")
    success = ProfileManager.rollback_profile(p_id, 1)
    assert success is True
    
    rolled_back = ProfileManager.get_profile(p_id)
    assert rolled_back["canvas"] == "9:16"
    assert rolled_back["selection_mode"] == "shuffle_bag"
    assert rolled_back["version"] == 4  # version increments when modified/rolled back
    
    # History should now have rollback backup of version 3
    versions = ProfileManager.get_versions(p_id)
    assert len(versions) == 3
    assert versions[0]["note"] == "Rollback backup of version 3"

def test_profile_import_export(temp_db):
    p_id = ProfileManager.create_profile(
        name="Exportable_Profile",
        canvas="9:16",
        clip_max_sec=12.0
    )
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_json:
        tmp_json_path = Path(tmp_json.name)
        
    try:
        # Export
        export_ok = ProfileManager.export_profile(p_id, tmp_json_path)
        assert export_ok is True
        
        # Import under same name (should auto-suffix to avoid collision)
        imported_id_1 = ProfileManager.import_profile(tmp_json_path)
        assert imported_id_1 is not None
        
        imported_1 = ProfileManager.get_profile(imported_id_1)
        assert imported_1["name"] == "Exportable_Profile_import_1"
        assert imported_1["canvas"] == "9:16"
        assert imported_1["clip_max_sec"] == 12.0
        assert imported_1["version"] == 1
        
        # Import with manual override name
        imported_id_2 = ProfileManager.import_profile(tmp_json_path, override_name="Manual_Import_Name")
        assert imported_id_2 is not None
        
        imported_2 = ProfileManager.get_profile(imported_id_2)
        assert imported_2["name"] == "Manual_Import_Name"
        
    finally:
        try:
            tmp_json_path.unlink()
        except Exception:
            pass

def test_gui_profile_integration(temp_db):
    # Initialize dummy QApplication
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    
    from app.gui import MainWindow
    window = MainWindow()
    
    try:
        # Check GUI widgets exist
        assert hasattr(window, "profile_combo"), "profile_combo missing"
        assert hasattr(window, "btn_save_profile"), "btn_save_profile missing"
        assert hasattr(window, "btn_profile_opts"), "btn_profile_opts missing"
        assert hasattr(window, "profile_menu"), "profile_menu missing"
        
        # Check slots exist
        assert hasattr(window, "_save_current_profile"), "_save_current_profile slot missing"
        assert hasattr(window, "_create_new_profile_click"), "_create_new_profile_click slot missing"
        assert hasattr(window, "_clone_profile_click"), "_clone_profile_click slot missing"
        assert hasattr(window, "_rename_profile_click"), "_rename_profile_click slot missing"
        assert hasattr(window, "_delete_profile_click"), "_delete_profile_click slot missing"
        assert hasattr(window, "_export_profile_click"), "_export_profile_click slot missing"
        assert hasattr(window, "_import_profile_click"), "_import_profile_click slot missing"
        assert hasattr(window, "_rollback_profile_click"), "_rollback_profile_click slot missing"
        
        # Check ScanWorker and scan thread variables exist
        assert hasattr(window, "_scan_thread"), "_scan_thread missing"
        assert hasattr(window, "_scan_worker"), "_scan_worker missing"
        assert hasattr(window, "_on_media_dir_changed"), "_on_media_dir_changed slot missing"
        assert hasattr(window, "_on_scan_finished"), "_on_scan_finished slot missing"
        assert hasattr(window, "_on_scan_failed"), "_on_scan_failed slot missing"
        
        # Verify default profile is loaded
        assert window.profile_combo.count() >= 1
        assert window._current_profile_name == "Mặc định"
    finally:
        window.close()
