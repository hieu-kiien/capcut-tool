import sys
import os
import queue
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Add project root to path (in case run from outside)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import video_mixer
from media_probe import MediaAsset
import capcut_draft_creator


def _hold_draft_lock_child(project_path: str, ready, release, errors) -> None:
    try:
        from app.draft_lock import locked_draft

        with locked_draft(Path(project_path), timeout_sec=2.0):
            ready.set()
            release.wait(10)
    except BaseException as exc:
        errors.put(f"{type(exc).__name__}: {exc}")
        ready.set()


def test_video_mixer_ranges():
    print("Testing video_mixer with target_ranges...")
    
    # 1. Create dummy assets
    assets = [
        MediaAsset(path="video1.mp4", media_type="video", duration_us=10_000_000, width=1920, height=1080),
        MediaAsset(path="video2.mp4", media_type="video", duration_us=15_000_000, width=1920, height=1080)
    ]
    
    # 2. Define custom ranges
    target_ranges = [
        (0, 3_000_000),      # Subtitle 1: 3 seconds
        (3_000_000, 4_500_000),  # Subtitle 2: 4.5 seconds
        (7_500_000, 5_000_000)   # Subtitle 3: 5 seconds
    ]
    total_duration_us = 12_500_000
    
    # 3. Call planner
    segments = video_mixer.plan_background_segments(
        assets=assets,
        total_duration_us=total_duration_us,
        target_ranges=target_ranges
    )
    
    assert len(segments) == len(target_ranges), f"Expected {len(target_ranges)} segments, got {len(segments)}"
    
    for i, seg in enumerate(segments):
        expected_start, expected_duration = target_ranges[i]
        assert seg.target_start_us == expected_start, f"Segment {i} start mismatch"
        assert seg.target_duration_us == expected_duration, f"Segment {i} duration mismatch"
        print(f"  Segment {i}: start={seg.target_start_us/1e6:.1f}s, duration={seg.target_duration_us/1e6:.1f}s, file={Path(seg.path).name}")
        
    print("[OK] video_mixer target_ranges test passed!")

def test_create_draft_signature():
    print("Testing create_draft_from_files signature and default arguments...")
    import inspect
    sig = inspect.signature(capcut_draft_creator.create_draft_from_files)
    params = sig.parameters
    
    assert "subtitle_font_size" in params
    assert "subtitle_color" in params
    assert "subtitle_bold" in params
    assert "subtitle_outline_width" in params
    assert "subtitle_shadow_alpha" in params
    assert "subtitle_shadow_distance" in params
    
    print("  Custom subtitle parameters successfully verified in signature:")
    for name in ["subtitle_font_size", "subtitle_color", "subtitle_bold", "subtitle_outline_width", "subtitle_shadow_alpha", "subtitle_shadow_distance"]:
        print(f"    - {name}: default={params[name].default}")
        
    print("[OK] capcut_draft_creator signature test passed!")

def test_gui_splitter_widgets():
    print("Testing GUI splitter widgets and slot existence...")
    
    # Initialize a dummy QApplication for PySide6 widgets
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    
    from app.gui import MainWindow
    window = MainWindow()
    
    # Check widgets are defined
    assert hasattr(window, "split_source_edit"), "split_source_edit missing from MainWindow"
    assert hasattr(window, "split_time_spin"), "split_time_spin missing from MainWindow"
    assert hasattr(window, "split_out_edit"), "split_out_edit missing from MainWindow"
    assert hasattr(window, "btn_run_split"), "btn_run_split missing from MainWindow"
    
    # Check slots exist
    assert hasattr(window, "_browse_split_source_click"), "_browse_split_source_click slot missing"
    assert hasattr(window, "_browse_split_out_click"), "_browse_split_out_click slot missing"
    assert hasattr(window, "_run_split_click"), "_run_split_click slot missing"
    assert hasattr(window, "_on_media_dir_changed"), "_on_media_dir_changed slot missing"
    
    print("[OK] GUI splitter widgets and slots successfully verified!")

def test_project_name_validation():
    print("Testing project name validation...")
    from app.path_validation import validate_project_name
    
    draft_root = Path("C:/projects/drafts")
    
    # 1. Valid project name
    res = validate_project_name("My_Project", draft_root)
    assert res == (draft_root / "My_Project").resolve()
    
    # 2. Empty name
    try:
        validate_project_name("", draft_root)
        assert False, "Should raise ValueError for empty name"
    except ValueError:
        pass
        
    # 3. Path traversal
    try:
        validate_project_name("../OtherFolder", draft_root)
        assert False, "Should raise ValueError for path traversal"
    except ValueError:
        pass
        
    # 4. Invalid separator
    try:
        validate_project_name("abc/def", draft_root)
        assert False, "Should raise ValueError for separator"
    except ValueError:
        pass
        
    # 5. Invalid characters
    try:
        validate_project_name("abc*def", draft_root)
        assert False, "Should raise ValueError for asterisks"
    except ValueError:
        pass
        
    print("[OK] Project name validation tests passed!")

def test_transition_track_targeting():
    print("Testing transition track targeting...")
    import tempfile
    import json
    import capcut_keyframe_tool as kt
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        draft_file = tmp_path / "draft_content.json"
        
        # Create a mock draft content with 3 video tracks
        mock_draft = {
            "materials": {
                "videos": [
                    {"id": "v1", "type": "video"},
                    {"id": "v2", "type": "video"},
                    {"id": "v3", "type": "video"}
                ],
                "transitions": []
            },
            "tracks": [
                {
                    "type": "video",
                    "name": "long_story_background",
                    "segments": [
                        {"material_id": "v1", "type": "video", "target_timerange": {"start": 0, "duration": 3000000}},
                        {"material_id": "v1", "type": "video", "target_timerange": {"start": 3000000, "duration": 3000000}},
                        {"material_id": "v1", "type": "video", "target_timerange": {"start": 6000000, "duration": 3000000}}
                    ]
                },
                {
                    "type": "video",
                    "name": "long_story_logo",
                    "segments": [
                        {"material_id": "v2", "type": "video", "target_timerange": {"start": 0, "duration": 9000000}}
                    ]
                },
                {
                    "type": "video",
                    "name": "long_story_anim",
                    "segments": [
                        {"material_id": "v3", "type": "video", "target_timerange": {"start": 0, "duration": 3000000}},
                        {"material_id": "v3", "type": "video", "target_timerange": {"start": 3000000, "duration": 3000000}}
                    ]
                }
            ]
        }
        
        draft_file.write_text(json.dumps(mock_draft), encoding="utf-8")
        
        class DummyArgs:
            def __init__(self):
                self.segment_type = "video"
                self.mode = "replace"
                self.dry_run = False
                self.root = tmp_path
                self.transition_duration_sec = 0.4
                self.transition_apply_all = False
                
        presets = [{"name": "Mix", "duration": 400000}]
        
        # Run transition applier
        changed = kt.apply_random_transitions_to_file(draft_file, DummyArgs(), presets)
        
        # Load modified content
        data = json.loads(draft_file.read_text(encoding="utf-8"))
        tracks = data["tracks"]
        
        # Assertions
        # Background track should have transition refs on segment 0 and 1
        bg_segs = tracks[0]["segments"]
        assert len(bg_segs[0].get("extra_material_refs", [])) > 0, "First background segment should have transition ref"
        assert len(bg_segs[1].get("extra_material_refs", [])) > 0, "Second background segment should have transition ref"
        assert len(bg_segs[2].get("extra_material_refs", [])) == 0, "Last background segment should not have transition ref"
        
        # Logo track should not have transitions
        logo_segs = tracks[1]["segments"]
        assert len(logo_segs[0].get("extra_material_refs", [])) == 0, "Logo track should not have transitions"
        
        # Anim track should not have transitions
        anim_segs = tracks[2]["segments"]
        assert len(anim_segs[0].get("extra_material_refs", [])) == 0, "Anim track should not have transitions"
        assert len(anim_segs[1].get("extra_material_refs", [])) == 0, "Anim track should not have transitions"
        
        print("[OK] Transition track targeting tests passed!")

def test_draft_folder_remove_traversal():
    print("Testing DraftFolder remove path traversal protection...")
    import tempfile
    import pyJianYingDraft as draft
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        draft_root = tmp_path / "draft_root"
        draft_root.mkdir()
        
        # Create an outside folder that represents a "victim" directory
        outside_victim = tmp_path / "outside_victim"
        outside_victim.mkdir()
        (outside_victim / "secret.txt").write_text("sensitive data", encoding="utf-8")
        
        df = draft.DraftFolder(str(draft_root))
        
        # Verify remove rejects traversal
        try:
            df.remove("../outside_victim")
            assert False, "Should raise ValueError for path traversal in remove"
        except ValueError:
            pass
            
        # Assert the outside directory was NOT deleted
        assert outside_victim.exists(), "Outside folder was deleted by traversal in remove!"
        assert (outside_victim / "secret.txt").exists(), "Outside files were deleted!"
        print("[OK] DraftFolder remove traversal protection verified!")

def test_draft_folder_duplicate_traversal():
    print("Testing DraftFolder duplicate_as_template path traversal protection...")
    import tempfile
    import pyJianYingDraft as draft
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        draft_root = tmp_path / "draft_root"
        draft_root.mkdir()
        
        # Create a mock template inside draft_root
        template_name = "mock_template"
        template_path = draft_root / template_name
        template_path.mkdir()
        (template_path / "draft_content.json").write_text("{}", encoding="utf-8")
        
        df = draft.DraftFolder(str(draft_root))
        
        # Verify duplicate_as_template rejects traversal destination
        try:
            df.duplicate_as_template(template_name, "../outside_copy")
            assert False, "Should raise ValueError for path traversal in duplicate"
        except ValueError:
            pass
            
        # Assert the outside copy was not created
        outside_copy = draft_root.parent / "outside_copy"
        assert not outside_copy.exists(), "Outside copy was created in duplicate traversal!"
        print("[OK] DraftFolder duplicate traversal protection verified!")

def test_media_probe_no_fallback_on_timeout():
    print("Testing media_probe does not fallback to pymediainfo on timeout...")
    import media_probe
    import subprocess
    import tempfile
    
    # Mock resolve_ffprobe to return a dummy path
    orig_resolve_ffprobe = media_probe.resolve_ffprobe
    media_probe.resolve_ffprobe = lambda: "dummy_ffprobe"
    
    # Mock subprocess.run to raise subprocess.TimeoutExpired
    orig_run = media_probe.subprocess.run
    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=15)
    media_probe.subprocess.run = mock_run
    
    # Mock _probe_with_pymediainfo to record if it was called
    pymediainfo_called = False
    orig_pymediainfo = media_probe._probe_with_pymediainfo
    def mock_pymediainfo(path):
        nonlocal pymediainfo_called
        pymediainfo_called = True
        return media_probe.MediaAsset(str(path), "unknown", 0)
    media_probe._probe_with_pymediainfo = mock_pymediainfo
    
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        tmp_file_path = tmp_file.name
        
    try:
        asset = media_probe.probe_media(tmp_file_path, timeout_sec=15)
        # Assert timeout error is captured
        assert "timed out" in asset.error, f"Expected timeout error, got {asset.error}"
        # Assert fallback was NOT called
        assert not pymediainfo_called, "Fallback to pymediainfo was called on timeout!"
        print("[OK] Media probe timeout fallback prevention verified!")
    finally:
        # Restore mocks
        media_probe.resolve_ffprobe = orig_resolve_ffprobe
        media_probe.subprocess.run = orig_run
        media_probe._probe_with_pymediainfo = orig_pymediainfo
        try:
            os.unlink(tmp_file_path)
        except Exception:
            pass

def test_transition_strict_targeting():
    print("Testing strict transition targeting without fallback...")
    import tempfile
    import json
    import capcut_keyframe_tool as kt
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        draft_file = tmp_path / "draft_content.json"
        
        # Mock draft with NO long_story_background track, but has other video tracks
        mock_draft = {
            "materials": {
                "videos": [
                    {"id": "v1", "type": "video"}
                ],
                "transitions": []
            },
            "tracks": [
                {
                    "type": "video",
                    "name": "random_overlay_track",
                    "segments": [
                        {"material_id": "v1", "type": "video", "target_timerange": {"start": 0, "duration": 3000000}},
                        {"material_id": "v1", "type": "video", "target_timerange": {"start": 3000000, "duration": 3000000}}
                    ]
                }
            ]
        }
        
        draft_file.write_text(json.dumps(mock_draft), encoding="utf-8")
        
        class DummyArgs:
            def __init__(self):
                self.segment_type = "video"
                self.mode = "replace"
                self.dry_run = False
                self.root = tmp_path
                self.transition_duration_sec = 0.4
                self.transition_apply_all = False
                self.transition_allow_primary_fallback = False # Strict targeting
                
        presets = [{"name": "Mix", "duration": 400000}]
        
        changed = kt.apply_random_transitions_to_file(draft_file, DummyArgs(), presets)
        
        # Assertions
        assert changed == 0, f"Expected 0 changes, got {changed}"
        
        data = json.loads(draft_file.read_text(encoding="utf-8"))
        assert len(data["materials"].get("transitions", [])) == 0, "Transitions were added to materials!"
        assert "extra_material_refs" not in data["tracks"][0]["segments"][0], "Transitions were applied!"
        
        print("[OK] Strict transition targeting verified!")


def test_ytdlp_downloader_validation_and_command():
    print("Testing yt-dlp downloader URL validation and command construction...")
    import tempfile
    from app.downloader import (
        DownloadOptions,
        build_ytdlp_command,
        build_ytdlp_library_options,
        parse_url_list,
    )

    urls = parse_url_list("# comment\nhttps://example.com/watch?v=abc\n\n")
    assert urls == ["https://example.com/watch?v=abc"]

    try:
        parse_url_list("file:///C:/Windows/win.ini")
        assert False, "Should reject non-http URL schemes"
    except ValueError:
        pass

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        out_dir = tmp_path / "media"
        cookies = tmp_path / "cookies.txt"
        cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
        fake_ffmpeg = tmp_path / "ffmpeg.exe"
        fake_ffmpeg.write_text("", encoding="utf-8")

        options = DownloadOptions(
            urls=urls,
            output_dir=str(out_dir),
            cookies_file=str(cookies),
            use_archive=True,
            include_playlists=True,
            playlist_limit=5,
            workers=3,
            download_kind="video",
        )
        cmd = build_ytdlp_command(
            options,
            urls[0],
            ytdlp_command=["yt-dlp"],
            ffmpeg_path=str(fake_ffmpeg),
        )

        assert isinstance(cmd, list), "yt-dlp command should be an argv list"
        assert cmd[0] == "yt-dlp"
        assert cmd[-1] == urls[0]
        assert "--cookies" in cmd and str(cookies.resolve()) in cmd
        assert "--download-archive" in cmd
        assert "--playlist-end" in cmd and "5" in cmd
        assert "--ffmpeg-location" in cmd and str(tmp_path.resolve()) in cmd
        assert "--max-filesize" in cmd and "4096M" in cmd
        assert "--no-playlist" not in cmd

        lib_opts = build_ytdlp_library_options(options)
        assert lib_opts["noplaylist"] is False
        assert lib_opts["playlistend"] == 5
        assert lib_opts["download_archive"].endswith(".yt-dlp-archive.txt")
        assert lib_opts["max_filesize"] == 4096 * 1024 * 1024

    print("[OK] yt-dlp downloader validation and command construction verified!")


def test_draft_folder_duplicate_cleanup():
    print("Testing DraftFolder duplicate_as_template load failure cleanup...")
    import tempfile
    import pyJianYingDraft as draft
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        draft_root = tmp_path / "draft_root"
        draft_root.mkdir()
        
        # Create a mock BAD template inside draft_root with invalid/empty draft_content.json (which raises KeyError)
        template_name = "bad_template"
        template_path = draft_root / template_name
        template_path.mkdir()
        
        (template_path / "draft_content.json").write_text("{}", encoding="utf-8")
        (template_path / "draft_meta_info.json").write_text("{}", encoding="utf-8")
        
        df = draft.DraftFolder(str(draft_root))
        
        # Verify duplicate_as_template raises KeyError/Exception
        new_copy_name = "failed_copy"
        try:
            df.duplicate_as_template(template_name, new_copy_name)
            assert False, "Should raise an exception for empty template draft_content.json"
        except KeyError as e:
            print(f"  Caught expected KeyError: {e}")
        except Exception as e:
            print(f"  Caught expected exception: {type(e).__name__}: {e}")
            
        # Assert that the new copy folder does NOT exist anymore (cleaned up)
        new_copy_path = draft_root / new_copy_name
        assert not new_copy_path.exists(), "Corrupt destination copy folder was not cleaned up!"
        print("[OK] DraftFolder duplicate load failure cleanup verified!")

def test_ytdlp_downloader_security_validation():
    print("Testing yt-dlp downloader security and URL validation...")
    from app.downloader import _validate_url, parse_url_list
    
    # Valid URLs
    assert _validate_url("https://youtube.com/watch?v=123") == "https://youtube.com/watch?v=123"
    # YouTube URLs with multiple query parameters should be valid
    assert _validate_url("https://youtube.com/watch?v=abc&list=xyz") == "https://youtube.com/watch?v=abc&list=xyz"
    assert _validate_url("https://youtube.com/watch?v=abc&list=xyz&index=1") == "https://youtube.com/watch?v=abc&list=xyz&index=1"
    assert _validate_url("https://www.youtube.com/watch?v=abc&list=PL123&index=2") == "https://www.youtube.com/watch?v=abc&list=PL123&index=2"
    
    # Regular URL with query parameters and URL encoding
    assert _validate_url("https://example.com/path?a=1&b=two%20words") == "https://example.com/path?a=1&b=two%20words"
    
    # Reject file://
    try:
        _validate_url("file:///etc/passwd")
        assert False, "Should reject file scheme"
    except ValueError:
        print("  Successfully rejected invalid scheme")
        
    # Reject command injection characters and control chars (newlines, null bytes, etc.)
    bad_urls = [
        "https://youtube.com/watch?v=123; rm -rf /",
        "https://youtube.com/watch?v=123 | format C:",
        "https://youtube.com/watch?v=123`id`",
        "https://youtube.com/watch?v=123$()",
        "https://youtube.com/watch?v=123\n",
        "https://youtube.com/watch?v=123\r",
        "https://youtube.com/watch?v=123" + chr(0),
        "https://youtube.com/watch?v=123" + chr(31),
        "https://youtube.com/watch?v=123" + chr(127),
    ]
    for bad in bad_urls:
        try:
            _validate_url(bad)
            assert False, f"Should reject dangerous URL: {bad}"
        except ValueError as e:
            pass
            
    print("[OK] Downloader security validation tests passed!")


def test_config_no_urls():
    print("Testing config.json doesn't save downloader URL list...")
    from app.gui import MainWindow
    from PySide6.QtWidgets import QApplication
    
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    
    window.download_urls_edit.setPlainText("https://youtube.com/watch?v=abc\nhttps://youtube.com/watch?v=def")
    window._save_config()
    
    import json
    from app.gui import CONFIG_PATH
    
    assert CONFIG_PATH.exists()
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    
    for key, value in cfg.items():
        if isinstance(value, str):
            assert "youtube.com" not in value, f"URL list should not be saved in config under key: {key}"
        elif isinstance(value, list):
            for val in value:
                if isinstance(val, str):
                    assert "youtube.com" not in val, "URL list should not be saved in config"
                    
    print("[OK] Config URL exclusion test passed!")


def test_downloader_queue_runner_simulation():
    print("Testing downloader queue runner simulation...")
    from app.downloader import YtDlpDownloadRunner, DownloadOptions, DownloadItemResult
    
    runner = YtDlpDownloadRunner()
    
    import subprocess
    orig_popen = subprocess.Popen
    
    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.stdout = [
                "[download] Destination: mock_output_video.mp4\n",
                "[download]  10% of 10.00MiB\n",
                "[download]  50% of 10.00MiB\n",
                "[download] 100% of 10.00MiB\n",
            ]
            self.returncode = 0
            
        def poll(self):
            return self.returncode
            
        def wait(self, timeout=None):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9
            
    subprocess.Popen = MockProcess
    
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            options = DownloadOptions(
                urls=["https://youtube.com/watch?v=simulated1"],
                output_dir=tmp_dir,
                workers=1,
            )
            
            progress_events = []
            item_progress_events = []
            
            def log_cb(msg):
                progress_events.append(msg)
                
            def item_progress_cb(index, status, message, output_path, error):
                item_progress_events.append((index, status, message, output_path, error))
                
            summary = runner.run(options, progress=log_cb, item_progress=item_progress_cb)
            
            assert summary.total == 1
            assert summary.succeeded == 1
            assert len(summary.results) == 1
            
            res = summary.results[0]
            assert res.url == "https://youtube.com/watch?v=simulated1"
            assert res.status == "completed"
            assert res.output_path == "mock_output_video.mp4"
            
            assert len(item_progress_events) > 0
            last_event = item_progress_events[-1]
            assert last_event[0] == 0
            assert last_event[1] == "completed"
            assert last_event[2] == "100%"
            assert last_event[3] == "mock_output_video.mp4"
            
            print("[OK] Downloader queue runner simulation passed!")
    finally:
        subprocess.Popen = orig_popen


def test_history_redaction_and_cookies():
    print("Testing history URL redaction and cookie path sanitization...")
    from app.history import safe_url_for_history, safe_cookie_info

    # Test URL Redaction
    raw_url = "https://example.com/watch?v=abc&token=secret#frag"
    redacted = safe_url_for_history(raw_url)
    assert "?" not in redacted
    assert "token" not in redacted
    assert "secret" not in redacted
    assert "#frag" not in redacted
    assert redacted == "https://example.com/watch"

    # Test Cookie Info Path Sanitization
    full_path = "C:/Users/hieuk/Desktop/cookies.txt"
    info = safe_cookie_info(full_path)
    assert info["cookies_used"] is True
    assert info["cookies_file_name"] == "cookies.txt"
    assert "Desktop" not in info["cookies_file_name"]

    # Test Empty Cookie
    assert safe_cookie_info("") == {"cookies_used": False, "cookies_file_name": ""}
    print("[OK] URL redaction and cookie info tests passed!")


def test_history_file_io():
    print("Testing history file I/O operations and write collisions...")
    import tempfile
    import json
    from app.history import write_job_history, load_job_history

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Test basic write
        job_data1 = {"status": "success", "inputs": {"url": "https://example.com"}}
        file1 = write_job_history("download", job_data1, tmp_path)
        
        assert file1.exists()
        
        # Test overwrite/collision avoidance
        job_data2 = {"status": "failed", "inputs": {"url": "https://example.org"}}
        file2 = write_job_history("download", job_data2, tmp_path)
        
        assert file2.exists()
        assert file1 != file2  # Paths must be distinct!

        # Test load
        history = load_job_history(tmp_path)
        assert len(history) == 2
        # Ensure schema version and job_type are injected
        assert history[0]["schema_version"] == 1
        assert history[0]["job_type"] == "download"
        assert history[0]["_filename"] in [file1.name, file2.name]

    print("[OK] History file I/O and collision avoidance tests passed!")


def test_gallerydl_resolver_and_command():
    print("Testing gallery-dl resolver and command construction...")
    import tempfile
    import runtime_tools
    from app.downloader import (
        DownloadOptions,
        build_gallerydl_command,
        parse_gallerydl_line,
        resolve_gallerydl_command,
    )

    # 1. Test resolver mock environment variables
    import os
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix="-gallery-dl.exe", delete=False) as tmp_file:
        fake_path = Path(tmp_file.name).resolve()
        
    orig_env = os.environ.get("CAPCUT_TOOL_GALLERYDL")
    os.environ["CAPCUT_TOOL_GALLERYDL"] = str(fake_path)
    
    try:
        runtime_tools._resolve_tool.cache_clear()
        resolved = runtime_tools.resolve_gallerydl()
        assert resolved is not None
        assert Path(resolved).resolve() == fake_path
    finally:
        if orig_env:
            os.environ["CAPCUT_TOOL_GALLERYDL"] = orig_env
        else:
            os.environ.pop("CAPCUT_TOOL_GALLERYDL", None)
        runtime_tools._resolve_tool.cache_clear()
        try:
            os.unlink(fake_path)
        except Exception:
            pass

    # 2. Test command construction
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        out_dir = tmp_path / "media"
        cookies = tmp_path / "cookies.txt"
        cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

        options = DownloadOptions(
            urls=["https://instagram.com/p/abc"],
            output_dir=str(out_dir),
            cookies_file=str(cookies),
            use_archive=True,
        )

        cmd = build_gallerydl_command(
            options,
            "https://instagram.com/p/abc",
            gallerydl_command=["gallery-dl"],
        )

        assert isinstance(cmd, list)
        assert cmd[0] == "gallery-dl"
        assert "--directory" in cmd and str(out_dir.resolve()) in cmd
        assert "--cookies" in cmd and str(cookies.resolve()) in cmd
        assert "--download-archive" in cmd
        assert "--filesize-max" in cmd and str(4096 * 1024 * 1024) in cmd
        assert cmd[-1] == "https://instagram.com/p/abc"

    # 3. Test parse line
    pct, out_path = parse_gallerydl_line("[instagram][info] Downloading...")
    assert pct == "Đang tải"
    assert out_path is None

    pct, out_path = parse_gallerydl_line("C:/fake/path/Instagram/img.jpg")
    assert pct == "Đang tải"
    assert out_path == "C:/fake/path/Instagram/img.jpg"

    print("[OK] gallery-dl resolver and command construction tests passed!")


def test_windows_reserved_names():
    print("Testing Windows reserved project names and edge constraints...")
    from app.path_validation import validate_project_name
    draft_root = Path("C:/projects/drafts")

    # Reserved words
    for rw in ["CON", "prn", "AUX", "NUL", "COM1", "LPT9", "CONIN$", "CONOUT$"]:
        try:
            validate_project_name(rw, draft_root)
            assert False, f"Should have blocked reserved name: {rw}"
        except ValueError as e:
            assert "Windows" in str(e) or "trùng" in str(e)

    # Reserved word prefix before dot
    for rw in ["CON.txt", "COM3.mp4", "lpt5.png"]:
        try:
            validate_project_name(rw, draft_root)
            assert False, f"Should have blocked reserved name prefix: {rw}"
        except ValueError as e:
            assert "Windows" in str(e) or "trùng" in str(e)

    # Control characters
    try:
        validate_project_name("Hello\x00World", draft_root)
        assert False, "Should have blocked control characters"
    except ValueError as e:
        assert "điều khiển" in str(e)

    # Ends with space or dot
    for bad in ["Hello ", "World."]:
        try:
            validate_project_name(bad, draft_root)
            assert False, f"Should have blocked name ending with space/dot: {bad}"
        except ValueError as e:
            assert "dấu cách" in str(e) or "dấu chấm" in str(e)

    # Length limit
    too_long = "a" * 121
    try:
        validate_project_name(too_long, draft_root)
        assert False, "Should have blocked too long project name"
    except ValueError as e:
        assert "tối đa 120" in str(e)

    # Internal prefix and backup pattern
    try:
        validate_project_name("_partial_test", draft_root)
        assert False, "Should block _partial_ prefix"
    except ValueError as e:
        assert "_partial_" in str(e)

    try:
        validate_project_name("test_bak_20241010_121212_extra", draft_root)
        assert False, "Should block backup pattern"
    except ValueError as e:
        assert "sao lưu" in str(e)

    print("[OK] Windows reserved name tests passed!")


def test_draft_guard_and_marker():
    print("Testing DraftGuard and marker logic...")
    import tempfile
    import shutil
    import capcut_draft_creator
    from capcut_draft_creator import create_local_draft

    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = Path(tmpdir)

        # 1. Create a dummy media file
        media_file = root_path / "dummy.mp4"
        media_file.write_text("dummy content")

        # 2. Test successful creation removes marker
        # Since pyJianYingDraft template assets need to be available, we simulate template assets copy
        # Wait, instead of calling the heavy create_local_draft which writes templates, we can directly unit test the decorator or simulation
        from capcut_draft_creator import handle_partial_draft

        @handle_partial_draft
        def mock_succeed(draft_root, project_name, *, guard=None):
            resolved = Path(draft_root) / project_name
            resolved.mkdir(parents=True, exist_ok=True)
            # Create marker
            (resolved / ".capcut_tool_writing").touch()
            return {"status": "ok"}

        @handle_partial_draft
        def mock_fail(draft_root, project_name, *, guard=None):
            resolved = Path(draft_root) / project_name
            resolved.mkdir(parents=True, exist_ok=True)
            # Create marker
            (resolved / ".capcut_tool_writing").touch()
            raise RuntimeError("something went wrong")

        # Succeeded run: marker should be removed
        res = mock_succeed(str(root_path), "ProjectA")
        proj_dir = root_path / "ProjectA"
        assert proj_dir.exists()
        assert not (proj_dir / ".capcut_tool_writing").exists()

        # Failed run: marker exists, moves folder to partial
        try:
            mock_fail(str(root_path), "ProjectB")
            assert False, "Should have failed"
        except Exception as e:
            assert getattr(e, "partial_path", None) is not None
            partial_dir = Path(e.partial_path)
            assert partial_dir.exists()
            assert not (partial_dir / ".capcut_tool_writing").exists()
            assert "_partial_ProjectB_" in partial_dir.name

        # Failed run, but NO marker exists: should NOT move or rename
        @handle_partial_draft
        def mock_fail_no_marker(draft_root, project_name, *, guard=None):
            resolved = Path(draft_root) / project_name
            resolved.mkdir(parents=True, exist_ok=True)
            # DO NOT create marker
            raise RuntimeError("no marker fail")

        try:
            mock_fail_no_marker(str(root_path), "ProjectC")
            assert False, "Should have failed"
        except Exception as e:
            assert getattr(e, "partial_path", None) is None
            assert (root_path / "ProjectC").exists()

    print("[OK] DraftGuard and marker logic tests passed!")


def test_pipeline_cancel_propagation():
    print("Testing pipeline cancel propagation...")
    from app.job_control import raise_if_cancelled, JobCancelled

    # Check raise_if_cancelled
    called = []
    def cancel_true():
        called.append(True)
        return True

    def cancel_false():
        called.append(False)
        return False

    raise_if_cancelled(cancel_false)
    assert called == [False]

    try:
        raise_if_cancelled(cancel_true)
        assert False, "Should have raised JobCancelled"
    except JobCancelled as e:
        assert "hủy bởi người dùng" in str(e)
    assert called == [False, True]

    print("[OK] Pipeline cancel propagation tests passed!")


def test_draft_lock_blocks_parallel_writer():
    print("Testing per-project draft write lock...")
    import tempfile
    import threading
    from app.draft_lock import DraftBusyError, locked_draft

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir) / "ProjectA"
        project_dir.mkdir()
        outcomes = []

        with locked_draft(project_dir):
            def attempt_lock():
                try:
                    with locked_draft(project_dir, timeout_sec=0.05):
                        outcomes.append("acquired")
                except DraftBusyError:
                    outcomes.append("busy")

            thread = threading.Thread(target=attempt_lock)
            thread.start()
            thread.join(timeout=2)

        assert outcomes == ["busy"], f"Expected busy lock result, got {outcomes}"
    print("[OK] Per-project draft write lock blocks parallel writers.")


def test_draft_lock_reentrant_same_process():
    print("Testing per-project draft write lock reentrant behavior...")
    import tempfile
    from app.draft_lock import locked_draft

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir) / "ProjectReentrant"
        with locked_draft(project_dir):
            with locked_draft(project_dir, timeout_sec=0.05):
                pass

    print("[OK] Per-project draft write lock is reentrant in the same thread.")


def test_draft_lock_blocks_other_process():
    print("Testing cross-process draft write lock...")
    import multiprocessing
    import tempfile
    from app.draft_lock import DraftBusyError, locked_draft

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir) / "ProjectProcess"
        ctx = multiprocessing.get_context("spawn" if os.name == "nt" else "fork")
        ready = ctx.Event()
        release = ctx.Event()
        errors = ctx.Queue()
        process = ctx.Process(
            target=_hold_draft_lock_child,
            args=(str(project_dir), ready, release, errors),
        )
        process.start()
        try:
            assert ready.wait(5), "Child process did not acquire draft lock in time"
            try:
                child_error = errors.get_nowait()
            except queue.Empty:
                child_error = ""
            assert not child_error, f"Child process failed while acquiring lock: {child_error}"

            try:
                with locked_draft(project_dir, timeout_sec=0.2):
                    assert False, "Parent should not acquire a draft lock held by another process"
            except DraftBusyError:
                pass
        finally:
            release.set()
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join(5)

        assert process.exitcode == 0, f"Child process exited with code {process.exitcode}"

    print("[OK] Cross-process draft write lock blocks parallel writers.")


def test_draft_cleanup_safe_artifacts():
    print("Testing safe draft cleanup service...")
    import tempfile
    import time
    from app.draft_cleanup import cleanup_draft_artifacts

    def mark_old(path: Path) -> None:
        old_time = time.time() - 30 * 86400
        if path.is_dir():
            for child in path.rglob("*"):
                os.utime(child, (old_time, old_time))
        os.utime(path, (old_time, old_time))

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        project = root / "ProjectA"
        project.mkdir()

        bak_file = project / "draft_content.json.bak"
        bak_file.write_text("backup", encoding="utf-8")
        mark_old(bak_file)

        backup_dir = root / "ProjectA_bak_20200101_010101"
        backup_dir.mkdir()
        (backup_dir / "draft_content.json").write_text("{}", encoding="utf-8")
        mark_old(backup_dir)

        partial_dir = root / "_partial_ProjectA_20200101_010101"
        partial_dir.mkdir()
        (partial_dir / "draft_content.json").write_text("{}", encoding="utf-8")
        mark_old(partial_dir)

        real_media = project / "voice.mp3"
        real_media.write_text("voice", encoding="utf-8")

        unrelated_backup = root / "Other_bak_20200101_010101"
        unrelated_backup.mkdir()
        mark_old(unrelated_backup)

        preview = cleanup_draft_artifacts(root, project_name="ProjectA", keep_days=7, dry_run=True)
        assert preview.dry_run is True
        assert preview.planned == 3, f"Expected 3 planned artifacts, got {preview.planned}"
        assert len(preview.artifacts) == 3, f"Expected 3 preview artifacts, got {len(preview.artifacts)}"
        assert preview.bytes_planned > 0, "Expected preview to estimate bytes"
        assert preview.deleted == 0, "Dry-run should not delete artifacts"
        assert bak_file.exists()
        assert backup_dir.exists()
        assert partial_dir.exists()
        assert {artifact.type for artifact in preview.artifacts} == {"bak_file", "backup_dir", "partial_dir"}

        result = cleanup_draft_artifacts(root, project_name="ProjectA", keep_days=7)

        assert result.deleted == 3, f"Expected 3 deleted artifacts, got {result.deleted}"
        assert not bak_file.exists()
        assert not backup_dir.exists()
        assert not partial_dir.exists()
        assert project.exists(), "Real project folder should remain"
        assert real_media.exists(), "Original media should not be deleted"
        assert unrelated_backup.exists(), "Other project backup should not be deleted"
        assert not result.errors, f"Unexpected cleanup errors: {result.errors}"
    print("[OK] Safe draft cleanup service verified.")


def test_downloader_ui_options_settings():
    print("Testing downloader UI settings are passed to DownloadOptions...")
    import tempfile
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from app.gui import MainWindow

    with tempfile.TemporaryDirectory() as tmp_dir:
        window = MainWindow()
        try:
            window.download_out_edit.setText(tmp_dir)
            window.download_cookies_edit.setText("")
            window.download_max_file_size_mb.setValue(1234)
            window.download_stall_timeout_sec.setValue(321)
            window.download_item_timeout_sec.setValue(6543)

            options = window._download_options_from_ui(
                ["https://example.com/video"],
                ["yt-dlp"],
            )

            assert options.max_file_size_mb == 1234
            assert options.stall_timeout_sec == 321
            assert options.item_timeout_sec == 6543
            assert options.output_dir == tmp_dir
            assert options.url_tools == ["yt-dlp"]
        finally:
            window.close()

    print("[OK] Downloader UI settings are passed to DownloadOptions.")


def test_scan_worker_cancel():
    print("Testing ScanWorker cancel logic...")
    import tempfile
    from pathlib import Path
    from app.gui import ScanWorker
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for i in range(10):
            (tmp_path / f"test_{i}.mp4").write_text("dummy")
            
        worker = ScanWorker(tmp_path)
        
        assert not worker.cancel_requested
        worker.cancel()
        assert worker.cancel_requested
        
        captured_result = {}
        def handle_finished(res):
            nonlocal captured_result
            captured_result = res
            
        worker.finished.connect(handle_finished)
        worker.run()
        
        assert captured_result.get("cancelled") is True
        print("[OK] ScanWorker cancel logic verified.")


if __name__ == "__main__":
    try:
        test_video_mixer_ranges()
        print("-" * 50)
        test_create_draft_signature()
        print("-" * 50)
        test_gui_splitter_widgets()
        print("-" * 50)
        test_project_name_validation()
        print("-" * 50)
        test_transition_track_targeting()
        print("-" * 50)
        test_draft_folder_remove_traversal()
        print("-" * 50)
        test_draft_folder_duplicate_traversal()
        print("-" * 50)
        test_draft_folder_duplicate_cleanup()
        print("-" * 50)
        test_media_probe_no_fallback_on_timeout()
        print("-" * 50)
        test_transition_strict_targeting()
        print("-" * 50)
        test_ytdlp_downloader_validation_and_command()
        print("-" * 50)
        test_ytdlp_downloader_security_validation()
        print("-" * 50)
        test_config_no_urls()
        print("-" * 50)
        test_downloader_queue_runner_simulation()
        print("-" * 50)
        test_history_redaction_and_cookies()
        print("-" * 50)
        test_history_file_io()
        print("-" * 50)
        test_gallerydl_resolver_and_command()
        print("-" * 50)
        test_windows_reserved_names()
        print("-" * 50)
        test_draft_guard_and_marker()
        print("-" * 50)
        test_pipeline_cancel_propagation()
        print("-" * 50)
        test_draft_lock_blocks_parallel_writer()
        print("-" * 50)
        test_draft_lock_reentrant_same_process()
        print("-" * 50)
        test_draft_lock_blocks_other_process()
        print("-" * 50)
        test_draft_cleanup_safe_artifacts()
        print("-" * 50)
        test_downloader_ui_options_settings()
        print("-" * 50)
        test_scan_worker_cancel()
        print("-" * 50)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
