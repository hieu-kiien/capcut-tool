import pytest
import json
import tempfile
from pathlib import Path

import capcut_keyframe_tool as kt
from app.presets import KEYFRAME_PRESETS, TRANSITION_PRESETS
from app.job_control import JobCancelled


class DummyArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _create_minimal_draft(path: Path) -> None:
    """Create a minimal valid draft_content.json with a primary video track and segments."""
    data = {
        "canvas_config": {"width": 1080, "height": 1920, "ratio": "original"},
        "fps": 30,
        "duration": 10_000_000,
        "materials": {
            "videos": [
                {
                    "id": "vid_mat_1",
                    "path": "d:/test/video1.mp4",
                    "type": "video",
                    "duration": 5_000_000,
                },
                {
                    "id": "vid_mat_2",
                    "path": "d:/test/video2.mp4",
                    "type": "video",
                    "duration": 5_000_000,
                },
            ],
            "transitions": [],
        },
        "tracks": [
            {
                "id": "track_bg",
                "name": "long_story_background",
                "type": "video",
                "segments": [
                    {
                        "id": "seg_1",
                        "material_id": "vid_mat_1",
                        "source_timerange": {"start": 0, "duration": 5_000_000},
                        "target_timerange": {"start": 0, "duration": 5_000_000},
                        "common_keyframes": [],
                        "extra_material_refs": [],
                    },
                    {
                        "id": "seg_2",
                        "material_id": "vid_mat_2",
                        "source_timerange": {"start": 0, "duration": 5_000_000},
                        "target_timerange": {"start": 5_000_000, "duration": 5_000_000},
                        "common_keyframes": [],
                        "extra_material_refs": [],
                    },
                ],
            }
        ],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_apply_batch_effects_empty(tmp_path):
    draft_file = tmp_path / "draft_content.json"
    _create_minimal_draft(draft_file)

    args = DummyArgs(segment_type="video", mode="replace", dry_run=False)
    res = kt.apply_batch_effects_to_file(draft_file, args, keyframe_presets=[], transition_presets=[])
    assert res == {"keyframes": 0, "transitions": 0}


def test_apply_batch_effects_both(tmp_path):
    draft_file = tmp_path / "draft_content.json"
    _create_minimal_draft(draft_file)

    kf_preset = [p for p in KEYFRAME_PRESETS if p["id"] == "zoom_in_slow"]
    assert len(kf_preset) == 1

    trans_preset = [{"name": "mix", "duration": 400_000}]

    args = DummyArgs(
        root=tmp_path,
        segment_type="video",
        mode="replace",
        dry_run=False,
        transition_duration_sec=0.4,
        transition_apply_all=False,
        transition_allow_primary_fallback=True,
    )

    res = kt.apply_batch_effects_to_file(
        draft_file,
        args,
        keyframe_presets=kf_preset,
        transition_presets=trans_preset,
    )

    assert res["keyframes"] >= 1
    assert res["transitions"] >= 1

    # Verify content was updated on disk
    loaded, _, _, _, _ = kt._load_draft(draft_file)
    segs = loaded["tracks"][0]["segments"]
    # Check keyframe was added
    assert len(segs[0].get("common_keyframes", [])) > 0
    # Check transition was added
    assert len(loaded["materials"].get("transitions", [])) > 0


def test_apply_batch_effects_cancelled(tmp_path):
    draft_file = tmp_path / "draft_content.json"
    _create_minimal_draft(draft_file)

    kf_preset = [p for p in KEYFRAME_PRESETS if p["id"] == "zoom_in_slow"]
    args = DummyArgs(segment_type="video", mode="replace", dry_run=False)

    with pytest.raises(JobCancelled):
        kt.apply_batch_effects_to_file(
            draft_file,
            args,
            keyframe_presets=kf_preset,
            cancel_check=lambda: True,
        )
