import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from media_probe import MediaAsset, scan_media_folder


US_PER_SEC = 1_000_000

MODE_EVERY_X_SECONDS = "every_x_seconds"
MODE_SUBTITLE = "subtitle"
MODE_SUBTITLE_GROUP = "subtitle_group"

VALID_MODES = {MODE_EVERY_X_SECONDS, MODE_SUBTITLE, MODE_SUBTITLE_GROUP}

SELECTION_SHUFFLE_BAG = "shuffle_bag"
SELECTION_SEQUENTIAL = "sequential"
SELECTION_RANDOM = "random"
SELECTION_DUPLICATE_THEN_SHUFFLE = "duplicate_then_shuffle"
SELECTION_SHUFFLE_DUPLICATES_ONLY = "shuffle_duplicates_only"

VALID_SELECTION_MODES = {
    SELECTION_SHUFFLE_BAG,
    SELECTION_SEQUENTIAL,
    SELECTION_RANDOM,
    SELECTION_DUPLICATE_THEN_SHUFFLE,
    SELECTION_SHUFFLE_DUPLICATES_ONLY,
}


@dataclass
class VideoMixerConfig:
    mode: str = MODE_EVERY_X_SECONDS
    clip_min_sec: float = 5.0
    clip_max_sec: float = 12.0
    fixed_clip_sec: float = 0.0
    recursive: bool = False
    seed: Optional[int] = None
    avoid_same_consecutive: bool = True
    selection_mode: str = SELECTION_SHUFFLE_BAG
    random_source_start: bool = True
    include_images: bool = True
    include_videos: bool = True
    use_scene_detection: bool = False
    scene_threshold: float = 27.0
    scene_min_sec: float = 1.0
    group_size: int = 3
    short_video_mode: str = "stretch"

    def normalized(self) -> "VideoMixerConfig":
        mode = self.mode if self.mode in VALID_MODES else MODE_EVERY_X_SECONDS
        selection_mode = (
            self.selection_mode if self.selection_mode in VALID_SELECTION_MODES else SELECTION_SHUFFLE_BAG
        )
        min_sec = max(0.5, float(self.clip_min_sec))
        max_sec = max(min_sec, float(self.clip_max_sec))
        fixed_sec = max(0.0, float(self.fixed_clip_sec))
        group_size = max(1, int(self.group_size or 3))
        short_video_mode = self.short_video_mode if self.short_video_mode in ("stretch", "loop") else "stretch"
        return VideoMixerConfig(
            mode=mode,
            clip_min_sec=min_sec,
            clip_max_sec=max_sec,
            fixed_clip_sec=fixed_sec,
            recursive=bool(self.recursive),
            seed=self.seed,
            avoid_same_consecutive=bool(self.avoid_same_consecutive),
            selection_mode=selection_mode,
            random_source_start=bool(self.random_source_start),
            include_images=bool(self.include_images),
            include_videos=bool(self.include_videos),
            use_scene_detection=bool(self.use_scene_detection),
            scene_threshold=max(1.0, float(self.scene_threshold or 27.0)),
            scene_min_sec=max(0.1, float(self.scene_min_sec or 1.0)),
            group_size=group_size,
            short_video_mode=short_video_mode,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "VideoMixerConfig":
        data = data or {}
        return cls(
            mode=str(data.get("mode", MODE_EVERY_X_SECONDS)),
            clip_min_sec=float(data.get("clip_min_sec", 5.0)),
            clip_max_sec=float(data.get("clip_max_sec", 12.0)),
            fixed_clip_sec=float(data.get("fixed_clip_sec", 0.0)),
            recursive=bool(data.get("recursive", False)),
            seed=data.get("seed"),
            avoid_same_consecutive=bool(data.get("avoid_same_consecutive", True)),
            selection_mode=str(data.get("selection_mode", SELECTION_SHUFFLE_BAG)),
            random_source_start=bool(data.get("random_source_start", True)),
            include_images=bool(data.get("include_images", True)),
            include_videos=bool(data.get("include_videos", True)),
            use_scene_detection=bool(data.get("use_scene_detection", False)),
            scene_threshold=float(data.get("scene_threshold", 27.0)),
            scene_min_sec=float(data.get("scene_min_sec", 1.0)),
            group_size=int(data.get("group_size", 3)),
            short_video_mode=str(data.get("short_video_mode", "stretch")),
        ).normalized()


@dataclass
class BackgroundSegment:
    path: str
    media_type: str
    target_start_us: int
    target_duration_us: int
    source_start_us: int
    source_duration_us: int
    asset_index: int

    @property
    def target_end_us(self) -> int:
        return self.target_start_us + self.target_duration_us

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackgroundSegment":
        return cls(
            path=str(data.get("path", "")),
            media_type=str(data.get("media_type", "")),
            target_start_us=int(data.get("target_start_us", 0)),
            target_duration_us=int(data.get("target_duration_us", 0)),
            source_start_us=int(data.get("source_start_us", 0)),
            source_duration_us=int(data.get("source_duration_us", 0)),
            asset_index=int(data.get("asset_index", -1)),
        )


def build_background_for_duration(
    media_dir: str | Path,
    total_duration_us: int,
    *,
    config: Optional[VideoMixerConfig] = None,
    subtitles: Optional[List[Dict[str, Any]]] = None,
) -> List[BackgroundSegment]:
    cfg = (config or VideoMixerConfig()).normalized()
    assets = scan_media_folder(media_dir, recursive=cfg.recursive)
    segments = plan_background_segments(
        assets,
        total_duration_us,
        config=cfg,
        subtitles=subtitles,
    )
    return segments


def plan_background_segments(
    assets: Sequence[MediaAsset | Dict[str, Any]],
    total_duration_us: int,
    *,
    config: Optional[VideoMixerConfig] = None,
    target_ranges: Optional[List[Tuple[int, int]]] = None,
    subtitles: Optional[List[Dict[str, Any]]] = None,
) -> List[BackgroundSegment]:
    cfg = (config or VideoMixerConfig()).normalized()
    rng = random.Random(cfg.seed)
    normalized_assets = _filter_assets([_asset_from_any(asset) for asset in assets], cfg)
    if not normalized_assets:
        raise ValueError("No usable background media assets")
    if total_duration_us <= 0:
        raise ValueError("Total duration must be greater than zero")

    if target_ranges is not None:
        ranges = target_ranges
    elif cfg.mode in (MODE_SUBTITLE, MODE_SUBTITLE_GROUP) and subtitles:
        ranges = []
        num_subs = len(subtitles)
        if cfg.mode == MODE_SUBTITLE:
            for i in range(num_subs):
                start = subtitles[i]["start"]
                if i < num_subs - 1:
                    end = subtitles[i+1]["start"]
                else:
                    end = max(total_duration_us, subtitles[i]["start"] + subtitles[i]["duration"])
                if i == 0:
                    start = 0
                duration = max(1, end - start)
                ranges.append((start, duration))
        else: # MODE_SUBTITLE_GROUP
            group_size = max(1, cfg.group_size)
            i = 0
            while i < num_subs:
                start = subtitles[i]["start"]
                next_group_idx = i + group_size
                if next_group_idx < num_subs:
                    end = subtitles[next_group_idx]["start"]
                else:
                    end = max(total_duration_us, subtitles[-1]["start"] + subtitles[-1]["duration"])
                if i == 0:
                    start = 0
                duration = max(1, end - start)
                ranges.append((start, duration))
                i = next_group_idx
    else:
        ranges = _make_interval_ranges(total_duration_us, cfg, rng)

    segments: List[BackgroundSegment] = []
    picker = _AssetPicker(normalized_assets, cfg, rng, num_segments=len(ranges))
    scene_ranges_by_path = _build_scene_ranges_by_path(normalized_assets, cfg)
    for start_us, duration_us in ranges:
        if duration_us <= 0:
            continue
        asset_index, asset = picker.pick()
        
        if asset.media_type == "video" and asset.duration_us < duration_us and cfg.short_video_mode == "loop":
            # Loop video to cover target duration
            remaining = duration_us
            curr_start = start_us
            video_dur = asset.duration_us
            while remaining > 0:
                curr_dur = min(video_dur, remaining)
                segments.append(
                    BackgroundSegment(
                        path=asset.path,
                        media_type=asset.media_type,
                        target_start_us=curr_start,
                        target_duration_us=curr_dur,
                        source_start_us=0,
                        source_duration_us=curr_dur,
                        asset_index=asset_index,
                    )
                )
                curr_start += curr_dur
                remaining -= curr_dur
        else:
            source_start_us, source_duration_us = _pick_source_range(
                asset,
                duration_us,
                cfg,
                rng,
                scene_ranges_by_path,
            )
            segments.append(
                BackgroundSegment(
                    path=asset.path,
                    media_type=asset.media_type,
                    target_start_us=start_us,
                    target_duration_us=duration_us,
                    source_start_us=source_start_us,
                    source_duration_us=source_duration_us,
                    asset_index=asset_index,
                )
            )

    return segments


# Manifest caching functions removed. Plan is generated on the fly.


def _asset_from_any(asset: MediaAsset | Dict[str, Any]) -> MediaAsset:
    if isinstance(asset, MediaAsset):
        return asset
    return MediaAsset.from_dict(asset)


def _filter_assets(assets: Sequence[MediaAsset], cfg: VideoMixerConfig) -> List[MediaAsset]:
    out: List[MediaAsset] = []
    for asset in assets:
        if asset.error:
            continue
        if asset.media_type == "image" and not cfg.include_images:
            continue
        if asset.media_type == "video" and not cfg.include_videos:
            continue
        if asset.media_type not in {"image", "video"}:
            continue
        if asset.duration_us <= 0:
            continue
        out.append(asset)
    return out


# Anchor ranges helpers removed. Slicing is interval-based.


def _make_interval_ranges(total_duration_us: int, cfg: VideoMixerConfig, rng: random.Random) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    cursor = 0
    while cursor < total_duration_us:
        if cfg.fixed_clip_sec > 0:
            duration_us = int(cfg.fixed_clip_sec * US_PER_SEC)
        else:
            duration_sec = rng.uniform(cfg.clip_min_sec, cfg.clip_max_sec)
            duration_us = int(duration_sec * US_PER_SEC)
        duration_us = max(1, min(duration_us, total_duration_us - cursor))
        ranges.append((cursor, duration_us))
        cursor += duration_us
    return ranges


class _AssetPicker:
    def __init__(self, assets: Sequence[MediaAsset], cfg: VideoMixerConfig, rng: random.Random, num_segments: int = 0):
        self.assets = assets
        self.cfg = cfg
        self.rng = rng
        self.last_asset_index: Optional[int] = None
        self.cursor = 0
        self.bag: List[int] = []

        self.pool: List[int] = []
        num_assets = len(assets)
        if num_assets > 0:
            if self.cfg.selection_mode == SELECTION_DUPLICATE_THEN_SHUFFLE:
                copies = (num_segments + num_assets - 1) // num_assets
                base_indices = list(range(num_assets))
                for _ in range(copies):
                    self.pool.extend(base_indices)
                self.rng.shuffle(self.pool)
            elif self.cfg.selection_mode == SELECTION_SHUFFLE_DUPLICATES_ONLY:
                # First pass: play all assets exactly once sequentially (0, 1, 2... num_assets-1)
                self.pool = list(range(num_assets))
                
                # Second pass: duplicate the rest and shuffle them
                extra_needed = num_segments - num_assets
                if extra_needed > 0:
                    extra_pool = []
                    copies = (extra_needed + num_assets - 1) // num_assets
                    base_indices = list(range(num_assets))
                    for _ in range(copies):
                        extra_pool.extend(base_indices)
                    self.rng.shuffle(extra_pool)
                    self.pool.extend(extra_pool)

    def pick(self) -> Tuple[int, MediaAsset]:
        if self.cfg.selection_mode == SELECTION_SEQUENTIAL:
            picked = self._pick_sequential()
        elif self.cfg.selection_mode == SELECTION_RANDOM:
            picked = self._pick_random()
        elif self.cfg.selection_mode in (SELECTION_DUPLICATE_THEN_SHUFFLE, SELECTION_SHUFFLE_DUPLICATES_ONLY):
            picked = self._pick_from_pool()
        else:
            picked = self._pick_shuffle_bag()
        self.last_asset_index = picked
        return picked, self.assets[picked]

    def _eligible(self, indexes: Sequence[int]) -> List[int]:
        out = list(indexes)
        if self.cfg.avoid_same_consecutive and len(self.assets) > 1 and self.last_asset_index is not None:
            out = [idx for idx in out if idx != self.last_asset_index]
        return out or list(indexes)

    def _is_allowed(self, idx: int) -> bool:
        return (
            not self.cfg.avoid_same_consecutive
            or len(self.assets) <= 1
            or self.last_asset_index is None
            or idx != self.last_asset_index
        )

    def _pick_sequential(self) -> int:
        count = len(self.assets)
        for _ in range(count):
            idx = self.cursor % count
            self.cursor += 1
            if self._is_allowed(idx):
                return idx
        return self._eligible(range(count))[0]

    def _pick_random(self) -> int:
        return self.rng.choice(self._eligible(range(len(self.assets))))

    def _pick_from_pool(self) -> int:
        if not self.pool:
            self.pool = list(range(len(self.assets)))
            self.rng.shuffle(self.pool)

        if self.cfg.avoid_same_consecutive and len(self.assets) > 1 and self.last_asset_index is not None:
            for i, idx in enumerate(self.pool):
                if idx != self.last_asset_index:
                    return self.pool.pop(i)
            return self.pool.pop(0)
        else:
            return self.pool.pop(0)

    def _pick_shuffle_bag(self) -> int:
        if not self.bag:
            self.bag = list(range(len(self.assets)))
            self.rng.shuffle(self.bag)

        if self._is_allowed(self.bag[-1]):
            return self.bag.pop()

        # If the last item is not allowed (matches last_asset_index), find an allowed item and swap to end
        for i in range(len(self.bag) - 2, -1, -1):
            if self._is_allowed(self.bag[i]):
                self.bag[i], self.bag[-1] = self.bag[-1], self.bag[i]
                return self.bag.pop()

        return self.bag.pop()


def _pick_source_range(
    asset: MediaAsset,
    target_duration_us: int,
    cfg: VideoMixerConfig,
    rng: random.Random,
    scene_ranges_by_path: Optional[Dict[str, List[Any]]] = None,
) -> Tuple[int, int]:
    if asset.media_type == "image":
        return 0, target_duration_us

    scenes = (scene_ranges_by_path or {}).get(str(Path(asset.path).resolve()), [])
    if scenes:
        target = max(1, int(target_duration_us))
        eligible = [scene for scene in scenes if int(scene.duration_us) >= target]
        picked = rng.choice(eligible or scenes)
        source_start_us = max(0, int(picked.start_us))
        source_duration_us = min(max(1, int(picked.duration_us)), target)
        return source_start_us, source_duration_us

    source_duration_us = min(asset.duration_us, target_duration_us)
    max_start = max(0, asset.duration_us - source_duration_us)
    if cfg.random_source_start and max_start > 0:
        source_start_us = rng.randint(0, max_start)
    else:
        source_start_us = 0
    return source_start_us, source_duration_us


def _build_scene_ranges_by_path(assets: Sequence[MediaAsset], cfg: VideoMixerConfig) -> Dict[str, List[Any]]:
    return {}


def calculate_bgm_volume(voice_path: Optional[str] = None, voice_duration: float = 0.0, default_volume: float = 1.0) -> float:
    """
    Calculates BGM volume with Audio Auto-Ducking (20%).
    Scales BGM volume factor to 0.20 (20%) when voice narration is present.
    """
    if voice_path and (voice_duration > 0 or voice_duration == 0.0):
        try:
            if Path(voice_path).exists():
                return 0.20
        except Exception:
            return 0.20
    return default_volume


# SRT parsing methods removed.


# Command-line entrypoint deprecated.

