import sys
import os
from pathlib import Path
import json

# Thêm thư mục gốc vào sys.path để import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from runtime_tools import configure_environment
configure_environment()

from capcut_draft_creator import create_draft_from_files
from video_mixer import BackgroundSegment

# Prepare dummy files
run_dir = Path(__file__).parent
dummy_voice = run_dir / "dummy_voice.m4a"
dummy_bg = run_dir / "dummy_bg.mp4"

# Generate dummy files using ffmpeg if they don't exist
if not dummy_voice.exists() or not dummy_bg.exists():
    os.system(f'ffmpeg -f lavfi -i color=c=blue:s=1080x1920:d=10 -c:v libx264 -y "{dummy_bg}"')
    os.system(f'ffmpeg -f lavfi -i sine=f=440:d=10 -c:a aac -y "{dummy_voice}"')

draft_root = run_dir / "Drafts"
draft_root.mkdir(exist_ok=True)

# Generate Draft 1: Non-compact
res_normal = create_draft_from_files(
    draft_root=draft_root,
    project_name="TestDraft_Normal",
    voice_path=str(dummy_voice),
    background_segments=[BackgroundSegment(
        path=str(dummy_bg),
        media_type="video",
        target_start_us=0,
        target_duration_us=10000000,
        source_start_us=0,
        source_duration_us=10000000,
        asset_index=0
    )],
    compact=False
)

# Generate Draft 2: Compact
res_compact = create_draft_from_files(
    draft_root=draft_root,
    project_name="TestDraft_Compact",
    voice_path=str(dummy_voice),
    background_segments=[BackgroundSegment(
        path=str(dummy_bg),
        media_type="video",
        target_start_us=0,
        target_duration_us=10000000,
        source_start_us=0,
        source_duration_us=10000000,
        asset_index=0
    )],
    compact=True
)

# In kết quả kiểm tra
print("Normal Draft Size:", Path(res_normal['draft_path']).stat().st_size)
print("Compact Draft Size:", Path(res_compact['draft_path']).stat().st_size)
print("Normal draft_path:", res_normal['draft_path'])
print("Compact draft_path:", res_compact['draft_path'])
