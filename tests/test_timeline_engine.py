import pytest
import random
from pathlib import Path
from media_probe import MediaAsset
import video_mixer
from video_mixer import (
    VideoMixerConfig,
    BackgroundSegment,
    plan_background_segments,
    MODE_EVERY_X_SECONDS,
    MODE_SUBTITLE,
    MODE_SUBTITLE_GROUP,
    SELECTION_SHUFFLE_BAG,
    SELECTION_SEQUENTIAL,
    SELECTION_RANDOM,
    SELECTION_DUPLICATE_THEN_SHUFFLE,
    SELECTION_SHUFFLE_DUPLICATES_ONLY,
)

def test_subtitle_aligned_timeline():
    # Giả lập 3 câu phụ đề
    subtitles = [
        {"start": 1_000_000, "duration": 2_000_000, "text": "Câu thoại 1"},
        {"start": 4_000_000, "duration": 1_500_000, "text": "Câu thoại 2"},
        {"start": 6_000_000, "duration": 3_000_000, "text": "Câu thoại 3"},
    ]
    total_duration_us = 10_000_000 # Giọng đọc dài 10 giây
    
    # 2 video assets dài
    assets = [
        MediaAsset(path="v1.mp4", media_type="video", duration_us=15_000_000, width=1920, height=1080),
        MediaAsset(path="v2.mp4", media_type="video", duration_us=20_000_000, width=1920, height=1080),
    ]
    
    # Dựng cấu hình mode subtitle
    cfg = VideoMixerConfig(
        mode=MODE_SUBTITLE,
        short_video_mode="stretch",
        seed=42
    )
    
    segments = plan_background_segments(
        assets=assets,
        total_duration_us=total_duration_us,
        config=cfg,
        subtitles=subtitles
    )
    
    # Dự kiến: có 3 phân đoạn:
    # 1. 0s -> 4s (thời lượng 4s, vì câu thoại 2 bắt đầu lúc 4s, câu thoại 1 bắt đầu tại 0s sau khi align)
    # 2. 4s -> 6s (thời lượng 2s, câu thoại 3 bắt đầu lúc 6s)
    # 3. 6s -> 10s (thời lượng 4s, kết thúc khít tại 10s là total_duration)
    assert len(segments) == 3
    
    # Kiểm tra segment 1
    assert segments[0].target_start_us == 0
    assert segments[0].target_duration_us == 4_000_000
    
    # Kiểm tra segment 2
    assert segments[1].target_start_us == 4_000_000
    assert segments[1].target_duration_us == 2_000_000
    
    # Kiểm tra segment 3
    assert segments[2].target_start_us == 6_000_000
    assert segments[2].target_duration_us == 4_000_000
    
    # Kiểm toán không chồng lấp và không có khoảng trống đen (gap)
    cursor = 0
    for seg in segments:
        assert seg.target_start_us == cursor
        cursor += seg.target_duration_us
    assert cursor == total_duration_us

def test_subtitle_group_aligned_timeline():
    # Giả lập 5 câu phụ đề
    subtitles = [
        {"start": 1_000_000, "duration": 1_000_000, "text": "Câu 1"},
        {"start": 3_000_000, "duration": 1_000_000, "text": "Câu 2"},
        {"start": 5_000_000, "duration": 1_000_000, "text": "Câu 3"},
        {"start": 7_000_000, "duration": 1_000_000, "text": "Câu 4"},
        {"start": 9_000_000, "duration": 1_000_000, "text": "Câu 5"},
    ]
    total_duration_us = 12_000_000 # Giọng đọc dài 12 giây
    
    assets = [
        MediaAsset(path="v1.mp4", media_type="video", duration_us=15_000_000, width=1920, height=1080),
        MediaAsset(path="v2.mp4", media_type="video", duration_us=20_000_000, width=1920, height=1080),
    ]
    
    # Gom nhóm 2 câu thoại làm 1 cảnh
    cfg = VideoMixerConfig(
        mode=MODE_SUBTITLE_GROUP,
        group_size=2,
        short_video_mode="stretch",
        seed=42
    )
    
    segments = plan_background_segments(
        assets=assets,
        total_duration_us=total_duration_us,
        config=cfg,
        subtitles=subtitles
    )
    
    # Phân nhóm dự kiến (group size = 2):
    # Nhóm 1: Câu 1, Câu 2. Bắt đầu: 0 (align từ 1s). Kết thúc tại điểm bắt đầu Nhóm 2 (Câu 3 bắt đầu lúc 5s) -> Thời lượng 5s.
    # Nhóm 2: Câu 3, Câu 4. Bắt đầu: 5s. Kết thúc tại điểm bắt đầu Nhóm 3 (Câu 5 bắt đầu lúc 9s) -> Thời lượng 4s.
    # Nhóm 3: Câu 5. Bắt đầu: 9s. Kết thúc tại total_duration hoặc cuối câu 5 (9s + 1s = 10s). Lấy max(12s, 10s) = 12s -> Thời lượng 3s.
    assert len(segments) == 3
    
    assert segments[0].target_start_us == 0
    assert segments[0].target_duration_us == 5_000_000
    
    assert segments[1].target_start_us == 5_000_000
    assert segments[1].target_duration_us == 4_000_000
    
    assert segments[2].target_start_us == 9_000_000
    assert segments[2].target_duration_us == 3_000_000
    
    # Kiểm toán không overlap, không gap
    cursor = 0
    for seg in segments:
        assert seg.target_start_us == cursor
        cursor += seg.target_duration_us
    assert cursor == total_duration_us

def test_short_video_loop_strategy():
    # Video ngắn chỉ 3 giây
    assets = [
        MediaAsset(path="short.mp4", media_type="video", duration_us=3_000_000, width=1920, height=1080),
    ]
    total_duration_us = 10_000_000 # Cần phủ 10 giây
    
    # Cài đặt chế độ lặp (loop)
    cfg = VideoMixerConfig(
        mode=MODE_EVERY_X_SECONDS,
        fixed_clip_sec=10.0, # Yêu cầu 1 clip 10 giây
        short_video_mode="loop",
        seed=100
    )
    
    segments = plan_background_segments(
        assets=assets,
        total_duration_us=total_duration_us,
        config=cfg
    )
    
    # Dự kiến: Phân đoạn 10s sẽ được chia nhỏ thành 4 sub-segments lặp video ngắn 3s:
    # 1. target: 0s -> 3s, source: 0s -> 3s
    # 2. target: 3s -> 6s, source: 0s -> 3s
    # 3. target: 6s -> 9s, source: 0s -> 3s
    # 4. target: 9s -> 10s, source: 0s -> 1s
    assert len(segments) == 4
    
    assert segments[0].target_start_us == 0
    assert segments[0].target_duration_us == 3_000_000
    assert segments[0].source_start_us == 0
    assert segments[0].source_duration_us == 3_000_000
    
    assert segments[1].target_start_us == 3_000_000
    assert segments[1].target_duration_us == 3_000_000
    assert segments[1].source_start_us == 0
    assert segments[1].source_duration_us == 3_000_000
    
    assert segments[2].target_start_us == 6_000_000
    assert segments[2].target_duration_us == 3_000_000
    assert segments[2].source_start_us == 0
    assert segments[2].source_duration_us == 3_000_000
    
    assert segments[3].target_start_us == 9_000_000
    assert segments[3].target_duration_us == 1_000_000
    assert segments[3].source_start_us == 0
    assert segments[3].source_duration_us == 1_000_000
    
    # Kiểm toán không gap, không overlap
    cursor = 0
    for seg in segments:
        assert seg.target_start_us == cursor
        cursor += seg.target_duration_us
    assert cursor == total_duration_us

def test_short_video_stretch_strategy():
    # Video ngắn chỉ 3 giây
    assets = [
        MediaAsset(path="short.mp4", media_type="video", duration_us=3_000_000, width=1920, height=1080),
    ]
    total_duration_us = 10_000_000 # Cần phủ 10 giây
    
    # Cài đặt chế độ kéo giãn (stretch)
    cfg = VideoMixerConfig(
        mode=MODE_EVERY_X_SECONDS,
        fixed_clip_sec=10.0,
        short_video_mode="stretch",
        seed=100
    )
    
    segments = plan_background_segments(
        assets=assets,
        total_duration_us=total_duration_us,
        config=cfg
    )
    
    # Dự kiến: Chỉ có đúng 1 segment, target: 0s -> 10s, source: 0s -> 3s (stretch)
    assert len(segments) == 1
    assert segments[0].target_start_us == 0
    assert segments[0].target_duration_us == 10_000_000
    assert segments[0].source_start_us == 0
    assert segments[0].source_duration_us == 3_000_000

def test_asset_picker_algorithms():
    assets = [
        MediaAsset(path="v1.mp4", media_type="video", duration_us=10_000_000, width=1920, height=1080),
        MediaAsset(path="v2.mp4", media_type="video", duration_us=10_000_000, width=1920, height=1080),
        MediaAsset(path="v3.mp4", media_type="video", duration_us=10_000_000, width=1920, height=1080),
    ]
    total_duration_us = 60_000_000 # 6 phân đoạn
    
    # 1. Test Sequential Mode
    cfg_seq = VideoMixerConfig(
        mode=MODE_EVERY_X_SECONDS,
        fixed_clip_sec=10.0,
        selection_mode=SELECTION_SEQUENTIAL,
        avoid_same_consecutive=True
    )
    segs_seq = plan_background_segments(assets, total_duration_us, config=cfg_seq)
    # Kỳ vọng thứ tự chọn asset index lần lượt: 0, 1, 2, 0, 1, 2
    assert [s.asset_index for s in segs_seq] == [0, 1, 2, 0, 1, 2]
    
    # 2. Test Shuffle Bag Mode
    cfg_bag = VideoMixerConfig(
        mode=MODE_EVERY_X_SECONDS,
        fixed_clip_sec=10.0,
        selection_mode=SELECTION_SHUFFLE_BAG,
        avoid_same_consecutive=True,
        seed=10
    )
    segs_bag = plan_background_segments(assets, total_duration_us, config=cfg_bag)
    # Kiểm tra không có clip trùng nhau đứng cạnh nhau
    for i in range(len(segs_bag) - 1):
        assert segs_bag[i].asset_index != segs_bag[i+1].asset_index

    # 3. Test single asset with shuffle bag (phải chạy được, không crash)
    single_asset = [assets[0]]
    segs_single = plan_background_segments(single_asset, total_duration_us, config=cfg_bag)
    assert len(segs_single) == 6
    assert [s.asset_index for s in segs_single] == [0, 0, 0, 0, 0, 0]
