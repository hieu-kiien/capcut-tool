import os
import sys
import json
import time
import tracemalloc
import inspect
from pathlib import Path
import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pyJianYingDraft as draft
import capcut_draft_creator


def test_compact_vs_pretty_format():
    """Verify that compact=True has no indentation/newlines, while compact=False is pretty-printed."""
    script = draft.ScriptFile(1080, 1920, 30, True)
    
    # Add track and segments to make it non-trivial
    track_name = "text_track"
    script.add_track(track_type=draft.TrackType.text, track_name=track_name)
    style = draft.TextStyle()
    seg = draft.TextSegment("Hello World", timerange=draft.trange(start=0, duration=2_000_000), style=style)
    script.add_segment(seg, track_name)

    # Test pretty format (default)
    pretty_json = script.dumps(compact=False)
    assert "\n" in pretty_json
    assert "    " in pretty_json  # Uses indent=4

    # Test compact format
    compact_json = script.dumps(compact=True)
    assert "\n" not in compact_json
    assert "  " not in compact_json
    
    # Test setting compact_json attribute
    script.compact_json = True
    compact_json_attr = script.dumps()
    assert "\n" not in compact_json_attr
    assert compact_json_attr == compact_json

    # Test override even with compact_json attribute set to True
    pretty_override = script.dumps(compact=False)
    assert "\n" in pretty_override
    assert "    " in pretty_override


def test_draft_creators_default_to_pretty_json():
    local_default = inspect.signature(capcut_draft_creator.create_local_draft).parameters["compact"].default
    files_default = inspect.signature(capcut_draft_creator.create_draft_from_files).parameters["compact"].default
    assert local_default is False
    assert files_default is False


def test_unicode_preservation():
    """Verify that Unicode characters (like Vietnamese or Chinese) are preserved directly and not escaped."""
    script = draft.ScriptFile(1080, 1920, 30, True)
    track_name = "unicode_track"
    script.add_track(track_type=draft.TrackType.text, track_name=track_name)
    
    unicode_text = "Xin chào Việt Nam! 🌟 剪映草稿"
    style = draft.TextStyle()
    seg = draft.TextSegment(unicode_text, timerange=draft.trange(start=0, duration=2_000_000), style=style)
    script.add_segment(seg, track_name)

    for compact_val in [True, False]:
        json_str = script.dumps(compact=compact_val)
        
        # Verify Unicode text is present exactly and not escaped as \uXXXX
        assert unicode_text in json_str
        assert "\\u" not in json_str.replace("\\u0026", "")  # exclude standard json-safe chars if any, but ensure our text is intact
        
        # Check parsed structure
        parsed = json.loads(json_str)
        # In CapCut/pyJianYingDraft, TextSegment stores content serialized in a "content" string inside materials.texts
        text_material = parsed["materials"]["texts"][0]
        content_json = json.loads(text_material["content"])
        assert unicode_text in content_json["text"]


def test_dual_file_writes(tmp_path):
    """Verify that saving a draft writes both files and respects compact settings when dual_file_compatibility is enabled."""
    script = draft.ScriptFile(1080, 1920, 30, True)
    script.dual_file_compatibility = True
    
    save_file = tmp_path / "draft_content.json"
    alt_file = tmp_path / "draft_info.json"
    
    script.save_path = str(save_file)
    
    # 1. Test pretty dual save
    script.save(compact=False)
    assert save_file.exists()
    assert alt_file.exists()
    
    save_content_pretty = save_file.read_text(encoding="utf-8")
    alt_content_pretty = alt_file.read_text(encoding="utf-8")
    
    assert "\n" in save_content_pretty
    assert "\n" in alt_content_pretty
    
    # 2. Test compact dual save
    script.save(compact=True)
    save_content_compact = save_file.read_text(encoding="utf-8")
    alt_content_compact = alt_file.read_text(encoding="utf-8")
    
    assert "\n" not in save_content_compact
    assert "\n" not in alt_content_compact
    assert len(save_content_compact) < len(save_content_pretty)
    assert len(alt_content_compact) < len(alt_content_pretty)


def test_round_trip_load_save(tmp_path):
    """Verify that saving as compact and loading back produces a structurally identical ScriptFile."""
    script = draft.ScriptFile(1080, 1920, 30, True)
    
    # Populate with various elements to test complexity
    # 1. Tracks
    script.add_track(track_type=draft.TrackType.text, track_name="texts")
    script.add_track(track_type=draft.TrackType.video, track_name="videos")
    
    # 2. Segments
    style = draft.TextStyle()
    text_seg = draft.TextSegment("Xin chào", timerange=draft.trange(start=0, duration=2_000_000), style=style)
    script.add_segment(text_seg, "texts")
    
    # Save as compact
    save_file = tmp_path / "draft_content.json"
    script.save_path = str(save_file)
    script.save(compact=True)
    
    # Load back
    loaded = draft.ScriptFile.load_template(str(save_file))
    
    # Assert contents are identical
    # Compare self.content directly
    assert loaded.content == script.content
    assert loaded.width == script.width
    assert loaded.height == script.height
    assert loaded.fps == script.fps
    assert loaded.duration == script.duration
    assert loaded.maintrack_adsorb == script.maintrack_adsorb


def test_performance_comparison(tmp_path):
    """Compare performance metrics between compact and pretty formatting: size, time, and RAM."""
    script = draft.ScriptFile(1080, 1920, 30, True)
    
    # Add a relatively large number of segments to make performance differences measurable
    script.add_track(track_type=draft.TrackType.text, track_name="heavy_track")
    style = draft.TextStyle()
    for i in range(100):
        seg = draft.TextSegment(
            f"Segment {i} with some Unicode characters: Xin chào Việt Nam {i}!",
            timerange=draft.trange(start=i * 2_000_000, duration=1_500_000),
            style=style
        )
        script.add_segment(seg, "heavy_track")
        
    # Measure Pretty serialization
    tracemalloc.start()
    t0 = time.perf_counter()
    pretty_json = script.dumps(compact=False)
    t_pretty = time.perf_counter() - t0
    pretty_ram_current, pretty_ram_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Measure Compact serialization
    tracemalloc.start()
    t0 = time.perf_counter()
    compact_json = script.dumps(compact=True)
    t_compact = time.perf_counter() - t0
    compact_ram_current, compact_ram_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Sizes
    size_pretty = len(pretty_json.encode("utf-8"))
    size_compact = len(compact_json.encode("utf-8"))
    
    print("\n=== Performance Comparison (100 Text Segments) ===")
    print(f"Format   | Size (bytes) | Time (ms) | Peak RAM (bytes)")
    print(f"---------+--------------+-----------+-----------------")
    print(f"Pretty   | {size_pretty:<12} | {t_pretty*1000:<9.2f} | {pretty_ram_peak:<15}")
    print(f"Compact  | {size_compact:<12} | {t_compact*1000:<9.2f} | {compact_ram_peak:<15}")
    print(f"Saving   | {(size_pretty-size_compact)/size_pretty*100:.1f}% space | {(t_pretty-t_compact)/t_pretty*100:.1f}% faster | peak RAM difference: {compact_ram_peak - pretty_ram_peak} bytes")
    
    # Assert compact is smaller
    assert size_compact < size_pretty
    # Assert content matches when parsed
    assert json.loads(compact_json) == json.loads(pretty_json)
