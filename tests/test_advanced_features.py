import pytest
import tempfile
import json
import urllib.request
import urllib.error
from pathlib import Path
from PySide6.QtCore import QCoreApplication

from core.db import Database
from app.pipeline import ProjectConfig, PipelineRunner
from app.presets import load_all_presets, add_custom_preset, delete_custom_preset, KEYFRAME_PRESETS
from app.queue_manager import BatchQueueManager
import capcut_draft_creator as draft_creator
import capcut_keyframe_tool as kt
from profiles.manager import ProfileManager

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    # Release real DB connection
    Database.close_connection()
    test_db = tmp_path / "test_draft_studio.db"
    Database.init_db(test_db)
    yield test_db
    Database.close_connection()

def test_custom_preset_sqlite():
    # 1. Load initial presets - should be equal to KEYFRAME_PRESETS
    initial = load_all_presets()
    assert len(initial) == len(KEYFRAME_PRESETS)

    # 2. Add custom preset
    ops = [{"property": "scale_uniform", "from": 100.0, "to": 115.0}]
    preset_id = add_custom_preset("Test Custom 1", "media", ops)
    assert preset_id.startswith("custom_")

    # 3. Load presets again - should include custom preset
    current = load_all_presets()
    assert len(current) == len(KEYFRAME_PRESETS) + 1

    custom_loaded = [p for p in current if p["id"] == preset_id]
    assert len(custom_loaded) == 1
    assert custom_loaded[0]["name"] == "[Tự chế] Test Custom 1"
    assert custom_loaded[0]["segment"] == "media"
    assert custom_loaded[0]["operations"] == ops

    # 4. Delete custom preset
    deleted = delete_custom_preset(preset_id)
    assert deleted is True

    # 5. Load presets again - should revert to original length
    after_delete = load_all_presets()
    assert len(after_delete) == len(KEYFRAME_PRESETS)

def test_intro_outro_timeline_shift(tmp_path, monkeypatch):
    # Giả lập file intro, outro, voice, srt, bg và overlays
    intro_file = tmp_path / "intro.mp4"
    intro_file.write_text("dummy_intro")
    outro_file = tmp_path / "outro.mp4"
    outro_file.write_text("dummy_outro")
    voice_file = tmp_path / "voice.mp3"
    voice_file.write_text("dummy_voice")
    bg1_file = tmp_path / "bg1.mp4"
    bg1_file.write_text("dummy_bg1")
    bg2_file = tmp_path / "bg2.mp4"
    bg2_file.write_text("dummy_bg2")
    logo_file = tmp_path / "logo.png"
    logo_file.write_text("dummy_logo")
    anim_file = tmp_path / "anim.mp4"
    anim_file.write_text("dummy_anim")

    srt_file = tmp_path / "subtitles.srt"
    srt_content = (
        "1\n"
        "00:00:01,000 --> 00:00:03,500\n"
        "Hello World\n\n"
        "2\n"
        "00:00:04,000 --> 00:00:06,000\n"
        "Second Line\n"
    )
    srt_file.write_text(srt_content, encoding="utf-8")

    # Mock pymediainfo / probe_media
    import media_probe
    class DummyAsset:
        def __init__(self, duration_us, media_type="video", error=None):
            self.duration_us = duration_us
            self.duration = duration_us
            self.media_type = media_type
            self.width = 1920
            self.height = 1080
            self.fps = 30.0
            self.error = error

    def mock_probe_media(path):
        p = Path(path)
        if p.name == "intro.mp4":
            return DummyAsset(3_000_000, "video") # Intro 3s
        if p.name == "outro.mp4":
            return DummyAsset(2_000_000, "video") # Outro 2s
        if p.name == "voice.mp3":
            return DummyAsset(10_000_000, "audio") # Voice 10s
        if p.name == "anim.mp4":
            return DummyAsset(5_000_000, "video") # Anim 5s
        if p.name == "logo.png":
            return DummyAsset(100_000_000, "image") # Logo 100s
        return DummyAsset(5_000_000, "video")

    # Áp dụng mock
    monkeypatch.setattr(media_probe, "probe_media", mock_probe_media)

    # We create a dummy bg segment
    from video_mixer import BackgroundSegment
    bg_segments = [
        BackgroundSegment(
            path=str(tmp_path / "bg1.mp4"),
            media_type="video",
            target_start_us=0,
            target_duration_us=5_000_000,
            source_start_us=0,
            source_duration_us=5_000_000,
            asset_index=0
        ),
        BackgroundSegment(
            path=str(tmp_path / "bg2.mp4"),
            media_type="video",
            target_start_us=5_000_000,
            target_duration_us=5_000_000,
            source_start_us=0,
            source_duration_us=5_000_000,
            asset_index=1
        )
    ]

    # Mocking pyJianYingDraft classes: VideoMaterial, AudioMaterial, TextSegment, TextStyle, VideoSegment, trange
    # to inspect segments being added
    added_segments = {}

    import pyJianYingDraft as draft

    original_add_segment = draft.ScriptFile.add_segment
    def mock_add_segment(self_script, segment, track_name):
        added_segments.setdefault(track_name, []).append(segment)
        return original_add_segment(self_script, segment, track_name)

    monkeypatch.setattr(draft.ScriptFile, "add_segment", mock_add_segment)

    draft_root = tmp_path / "CapCutDrafts"
    draft_root.mkdir()

    # Run creation
    res = draft_creator.create_draft_from_files(
        draft_root=draft_root,
        project_name="TestProjIntroOutro",
        voice_path=voice_file,
        background_segments=bg_segments,
        srt_path=srt_file,
        intro_path=intro_file,
        outro_path=outro_file,
        logo_path=tmp_path / "logo.png",
        logo_position="top_right",
        logo_scale=15.0,
        anim_path=tmp_path / "anim.mp4",
        anim_position="bottom_center",
        anim_scale=30.0,
        anim_timing="end"
    )

    assert res is not None
    assert res["voice_duration_sec"] == 10.0

    # Verify shifts:
    # intro_duration = 3_000_000 (3s)
    # voice_duration = 10_000_000 (10s)
    # outro_duration = 2_000_000 (2s)

    # 1. Voice track: should start at 3,000,000
    voice_segs = added_segments.get("long_story_voice", [])
    assert len(voice_segs) == 1
    assert voice_segs[0].target_timerange.start == 3_000_000
    assert voice_segs[0].target_timerange.duration == 10_000_000

    # 2. Background track (long_story_background):
    # First clip is Intro: start 0, dur 3,000,000
    # Next are background segments, shifted by 3,000,000
    # Last clip is Outro: start 13,000,000 (3M intro + 10M voice), dur 2,000,000
    bg_segs = added_segments.get("long_story_background", [])
    assert len(bg_segs) == 4 # Intro + 2 main + Outro

    # Intro
    assert bg_segs[0].target_timerange.start == 0
    assert bg_segs[0].target_timerange.duration == 3_000_000

    # Main segments
    assert bg_segs[1].target_timerange.start == 3_000_000
    assert bg_segs[2].target_timerange.start == 8_000_000

    # Outro
    assert bg_segs[3].target_timerange.start == 13_000_000
    assert bg_segs[3].target_timerange.duration == 2_000_000

    # 3. Subtitles (long_story_subtitles):
    # srt 1: 1.0s -> 3.5s (1M -> 3.5M) -> shifted to 4M -> 6.5M
    sub_segs = added_segments.get("long_story_subtitles", [])
    assert len(sub_segs) == 2
    assert sub_segs[0].target_timerange.start == 4_000_000
    assert sub_segs[1].target_timerange.start == 7_000_000

    # 4. Logo (long_story_logo): starts at 3,000,000
    logo_segs = added_segments.get("long_story_logo", [])
    assert len(logo_segs) == 1
    assert logo_segs[0].target_timerange.start == 3_000_000

    # 5. Animation (long_story_anim): timing="end" -> voice_duration - anim_duration
    # mock anim_duration = 5_000_000
    # starts at 3,000,000 + (10,000,000 - 5,000,000) = 8,000,000
    anim_segs = added_segments.get("long_story_anim", [])
    assert len(anim_segs) == 1
    assert anim_segs[0].target_timerange.start == 8_000_000
    # Monkeypatch fixture cleans up automatically

def test_intro_outro_effect_skip(tmp_path):
    # Setup mock draft file
    draft_file = tmp_path / "draft_content.json"

    # Paths we want to mock
    intro_path = str(tmp_path / "intro.mp4")
    outro_path = str(tmp_path / "outro.mp4")
    main_path = str(tmp_path / "main.mp4")

    mock_draft = {
        "materials": {
            "videos": [
                {"id": "mat_intro", "path": intro_path, "type": "video"},
                {"id": "mat_main", "path": main_path, "type": "video"},
                {"id": "mat_outro", "path": outro_path, "type": "video"}
            ],
            "transitions": []
        },
        "tracks": [
            {
                "type": "video",
                "name": "long_story_background",
                "segments": [
                    {
                        "material_id": "mat_intro",
                        "type": "video",
                        "target_timerange": {"start": 0, "duration": 3000000},
                        "common_keyframes": []
                    },
                    {
                        "material_id": "mat_main",
                        "type": "video",
                        "target_timerange": {"start": 3000000, "duration": 5000000},
                        "common_keyframes": []
                    },
                    {
                        "material_id": "mat_outro",
                        "type": "video",
                        "target_timerange": {"start": 8000000, "duration": 2000000},
                        "common_keyframes": []
                    }
                ]
            }
        ]
    }

    draft_file.write_text(json.dumps(mock_draft), encoding="utf-8")

    # 1. Test Keyframe skipping
    class DummyArgs:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    args = DummyArgs(
        segment_type="video",
        mode="replace",
        dry_run=False,
        intro_path=intro_path,
        outro_path=outro_path
    )

    # Apply a keyframe preset (e.g. Zoom In Slow)
    presets = [KEYFRAME_PRESETS[0]]
    changed = kt.apply_random_presets_to_file(draft_file, args, presets)

    # Verify: only mat_main got updated
    assert changed == 1

    updated_data = json.loads(draft_file.read_text(encoding="utf-8"))
    segs = updated_data["tracks"][0]["segments"]

    # Intro: common_keyframes empty
    assert len(segs[0].get("common_keyframes", [])) == 0
    # Main: common_keyframes populated
    assert len(segs[1].get("common_keyframes", [])) > 0
    # Outro: common_keyframes empty
    assert len(segs[2].get("common_keyframes", [])) == 0

    # Reset common_keyframes
    for s in segs:
        s["common_keyframes"] = []
    draft_file.write_text(json.dumps(updated_data), encoding="utf-8")

    # 2. Test Transition skipping
    # We apply transition to cuts
    trans_presets = [{"name": "Mix", "duration": 400000}]
    args_trans = DummyArgs(
        root=tmp_path,
        transition_duration_sec=0.4,
        transition_apply_all=False,
        segment_type="video",
        mode="replace",
        dry_run=False,
        intro_path=intro_path,
        outro_path=outro_path
    )

    changed_trans = kt.apply_random_transitions_to_file(draft_file, args_trans, trans_presets)
    assert changed_trans == 1

    updated_data2 = json.loads(draft_file.read_text(encoding="utf-8"))
    segs2 = updated_data2["tracks"][0]["segments"]

    # Segment 0 (Intro): extra_material_refs empty
    assert len(segs2[0].get("extra_material_refs", [])) == 0
    # Segment 1 (Main): extra_material_refs has transition
    assert len(segs2[1].get("extra_material_refs", [])) == 1

def test_cloud_sync_mock(monkeypatch):
    import urllib.request
    from io import BytesIO

    class MockResponse:
        def __init__(self, data, status=200):
            self.data = data
            self.status = status

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    # Mock profiles database
    profile_id = ProfileManager.create_profile(
        name="Cloud Test Profile",
        canvas="16:9",
        clip_min_sec=4.0,
        clip_max_sec=10.0,
        logo_path="C:/test/logo.png"
    )

    # 1. Test Export (PUT Request)
    put_urls = []
    put_data = []

    def mock_urlopen(req, timeout=10):
        url = req.full_url if hasattr(req, "full_url") else req
        if isinstance(req, urllib.request.Request):
            method = req.method
            if method == "PUT":
                put_urls.append(url)
                put_data.append(req.data)
                return MockResponse(b"OK", 200)
            elif method == "GET":
                profile_json = {
                    "name": "Cloud Test Profile Sync",
                    "canvas": "16:9",
                    "clip_min_sec": 4.0,
                    "clip_max_sec": 10.0,
                    "logo_path": "C:/sync/logo.png"
                }
                return MockResponse(json.dumps(profile_json).encode("utf-8"), 200)
        return MockResponse(b"", 404)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    # Get current profile data
    profile_data = ProfileManager.get_profile(profile_id)
    assert profile_data is not None

    export_data = dict(profile_data)
    export_data.pop('id', None)
    export_data.pop('created_at', None)
    export_data.pop('version', None)

    code = "PF-TEST12"
    url = f"https://kvdb.io/capcut_draft_studio_v1/{code}"

    req = urllib.request.Request(
        url,
        data=json.dumps(export_data, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='PUT'
    )

    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200

    assert len(put_urls) == 1
    assert put_urls[0] == url
    uploaded = json.loads(put_data[0].decode("utf-8"))
    assert uploaded["name"] == "Cloud Test Profile"
    assert uploaded["canvas"] == "16:9"
    assert uploaded["logo_path"] == "C:/test/logo.png"

    # 2. Test Import (GET Request)
    req_get = urllib.request.Request(url, method='GET')
    with urllib.request.urlopen(req_get) as resp_get:
        imported_data = json.loads(resp_get.read().decode("utf-8"))

    assert imported_data["name"] == "Cloud Test Profile Sync"

    # Verify save logic
    counter = 1
    new_name = imported_data["name"]
    while ProfileManager.get_profile_by_name(new_name):
        new_name = f"{imported_data['name']} (Đồng bộ {counter})"
        counter += 1

    imported_id = ProfileManager.create_profile(
        name=new_name,
        canvas=imported_data["canvas"],
        clip_min_sec=imported_data["clip_min_sec"],
        clip_max_sec=imported_data["clip_max_sec"],
        logo_path=imported_data["logo_path"]
    )

    assert imported_id is not None
    saved = ProfileManager.get_profile(imported_id)
    assert saved["name"] == "Cloud Test Profile Sync"
    assert saved["canvas"] == "16:9"
    assert saved["logo_path"] == "C:/sync/logo.png"

from contextlib import contextmanager
import io
import logging

class StrictCP1252StreamHandler(logging.StreamHandler):
    def handleError(self, record):
        raise

@contextmanager
def cp1252_logger_ctx():
    from core.logger import logger
    old_level = logger.level
    old_propagate = logger.propagate
    old_handlers = list(logger.handlers)
    logger.handlers = []

    bio = io.BytesIO()
    stream = io.TextIOWrapper(bio, encoding="cp1252", errors="strict")
    handler = StrictCP1252StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        yield stream, bio
    finally:
        logger.handlers = old_handlers
        logger.level = old_level
        logger.propagate = old_propagate

def test_chroma_image_removal(tmp_path, monkeypatch):
    from PIL import Image
    from core.chroma import remove_solid_bg_from_image

    # Tạo ảnh dummy với 3 pixel: 1 pixel xanh lá thuần, 1 pixel hơi xanh lá, 1 pixel màu đỏ
    img_path = tmp_path / "test_logo.png"
    img = Image.new("RGBA", (3, 1))
    img.putdata([
        (0, 255, 0, 255),    # Xanh lá thuần (chắc chắn xóa)
        (30, 240, 20, 255),  # Gần xanh lá (nằm trong ngưỡng similarity)
        (255, 0, 0, 255)     # Đỏ (chắc chắn giữ)
    ])
    img.save(img_path)

    out_dir = tmp_path / "output_overlay"

    with cp1252_logger_ctx() as (stream, bio):
        # 1. Test green overlay
        out_path_green = remove_solid_bg_from_image(
            source_path=img_path,
            output_dir=out_dir,
            prefix="logo",
            mode="green",
            similarity=0.32,
            blend=0.02
        )
        assert out_path_green.exists()
        assert out_path_green.name == "logo_test_logo_green_transparent.png"

        # Đọc lại ảnh kết quả để xác minh
        res_img = Image.open(out_path_green)
        pixels = res_img.load()
        assert pixels[0, 0][3] == 0
        assert pixels[1, 0][3] == 0
        assert pixels[2, 0][3] == 255

        # 2. Test black overlay
        out_path_black = remove_solid_bg_from_image(
            source_path=img_path,
            output_dir=out_dir,
            prefix="logo",
            mode="black",
            similarity=0.32,
            blend=0.02
        )
        assert out_path_black.exists()
        assert out_path_black.name == "logo_test_logo_black_transparent.png"

        # 3. Test white overlay
        out_path_white = remove_solid_bg_from_image(
            source_path=img_path,
            output_dir=out_dir,
            prefix="logo",
            mode="white",
            similarity=0.32,
            blend=0.02
        )
        assert out_path_white.exists()
        assert out_path_white.name == "logo_test_logo_white_transparent.png"

        stream.flush()
        log_content = bio.getvalue().decode("cp1252")
        assert "[CHROMA]" in log_content

def test_chroma_video_removal_ffmpeg(tmp_path, monkeypatch):
    import subprocess
    import runtime_tools
    from core.chroma import remove_solid_bg_from_video

    # Mock resolve_ffmpeg để trả về path dummy
    monkeypatch.setattr(runtime_tools, "resolve_ffmpeg", lambda: "mock_ffmpeg.exe")

    # Mock subprocess.Popen
    captured_cmds = []
    class DummyPopen:
        def __init__(self, cmd, **kwargs):
            captured_cmds.append(cmd)
            out_file = Path(cmd[-1])
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.touch()
            self.returncode = 0

        def poll(self):
            return 0

        def communicate(self):
            return ("", "")

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

    monkeypatch.setattr(subprocess, "Popen", DummyPopen)

    video_path = tmp_path / "subscribe.mp4"
    video_path.touch()

    out_dir = tmp_path / "output_overlay"

    with cp1252_logger_ctx() as (stream, bio):
        # 1. Test green screen (should use chromakey)
        res_green = remove_solid_bg_from_video(
            source_path=video_path,
            output_dir=out_dir,
            prefix="anim",
            mode="green",
            similarity=0.15,
            blend=0.05
        )
        assert res_green.exists()
        # verify chromakey is used in the command argument
        flat_cmds = [str(x) for x in captured_cmds[0]]
        vf_arg = next(arg for arg in flat_cmds if "chromakey" in arg)
        assert "chromakey=0x00FF00:0.150:0.050,format=argb" in vf_arg

        # 2. Test black screen (should use colorkey)
        res_black = remove_solid_bg_from_video(
            source_path=video_path,
            output_dir=out_dir,
            prefix="anim",
            mode="black",
            similarity=0.20,
            blend=0.10
        )
        assert res_black.exists()
        flat_cmds_black = [str(x) for x in captured_cmds[1]]
        vf_arg_black = next(arg for arg in flat_cmds_black if "colorkey" in arg)
        assert "colorkey=0x000000:0.200:0.100,format=argb" in vf_arg_black

        # 3. Test white screen (should use colorkey)
        res_white = remove_solid_bg_from_video(
            source_path=video_path,
            output_dir=out_dir,
            prefix="anim",
            mode="white",
            similarity=0.25,
            blend=0.15
        )
        assert res_white.exists()
        flat_cmds_white = [str(x) for x in captured_cmds[2]]
        vf_arg_white = next(arg for arg in flat_cmds_white if "colorkey" in arg)
        assert "colorkey=0xFFFFFF:0.250:0.150,format=argb" in vf_arg_white

        stream.flush()
        log_content = bio.getvalue().decode("cp1252")
        assert "[CHROMA]" in log_content

def test_chroma_prepare_overlay_smoke(tmp_path, monkeypatch):
    import subprocess
    import runtime_tools
    from core.chroma import prepare_overlay_asset

    monkeypatch.setattr(runtime_tools, "resolve_ffmpeg", lambda: "mock_ffmpeg.exe")

    class DummyPopen:
        def __init__(self, cmd, **kwargs):
            out_file = Path(cmd[-1])
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.touch()
            self.returncode = 0

        def poll(self):
            return 0

        def communicate(self):
            return ("", "")

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

    monkeypatch.setattr(subprocess, "Popen", DummyPopen)

    # 1. Smoke test image overlay
    from PIL import Image
    img_path = tmp_path / "smoke_logo.png"
    img = Image.new("RGBA", (1, 1), (0, 255, 0, 255))
    img.save(img_path)

    out_dir = tmp_path / "output_smoke"

    with cp1252_logger_ctx() as (stream, bio):
        out_img = prepare_overlay_asset(
            source=img_path,
            bg_mode="green",
            output_dir=out_dir,
            prefix="logo",
            similarity=0.18,
            blend=0.08
        )
        assert out_img.exists()

        # 2. Smoke test video overlay
        video_path = tmp_path / "smoke_video.mp4"
        video_path.touch()
        out_vid = prepare_overlay_asset(
            source=video_path,
            bg_mode="black",
            output_dir=out_dir,
            prefix="video",
            similarity=0.18,
            blend=0.08
        )
        assert out_vid.exists()

        stream.flush()
        log_content = bio.getvalue().decode("cp1252")
        assert "[CHROMA]" in log_content

def test_effects_karaoke_subtitles():
    import pyJianYingDraft as draft
    from core.effects import apply_karaoke_subtitles

    # Tạo ScriptFile
    script = draft.ScriptFile(1080, 1920, 30, True)
    track_name = "test_sub_track"
    script.add_track(track_type=draft.TrackType.text, track_name=track_name, relative_index=0)

    style = draft.TextStyle()
    # Thêm 2 segment text
    seg1 = draft.TextSegment("Hello", timerange=draft.trange(start=0, duration=3_000_000), style=style)
    seg2 = draft.TextSegment("World", timerange=draft.trange(start=4_000_000, duration=2_500_000), style=style)

    script.add_segment(seg1, track_name)
    script.add_segment(seg2, track_name)

    # Apply karaoke animation
    count = apply_karaoke_subtitles(script, track_name)
    assert count == 2

    # Verify segment 1 has karaoke animation
    assert seg1.animations_instance is not None
    anims = seg1.animations_instance.animations
    assert len(anims) == 1
    assert anims[0].name == "卡拉OK"
    assert anims[0].duration == 3_000_000
    assert anims[0].start == 0

    # Verify segment 2 has karaoke animation with correct duration
    anims2 = seg2.animations_instance.animations
    assert len(anims2) == 1
    assert anims2[0].name == "卡拉OK"
    assert anims2[0].duration == 2_500_000
