import json
import os
import subprocess
import threading
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Callable, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from runtime_tools import resolve_ffprobe


PHOTO_DEFAULT_DURATION_US = 3 * 60 * 60 * 1_000_000

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
    ".wmv",
    ".flv",
    ".mpeg",
    ".mpg",
}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
    ".aac",
    ".ogg",
    ".wma",
}

SUPPORTED_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
SUPPORTED_VISUAL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


@dataclass
class MediaAsset:
    path: str
    media_type: str
    duration_us: int
    width: int = 0
    height: int = 0
    fps: float = 0.0
    source: str = ""
    error: str = ""

    @property
    def is_video(self) -> bool:
        return self.media_type == "video"

    @property
    def is_image(self) -> bool:
        return self.media_type == "image"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MediaAsset":
        return cls(
            path=str(data.get("path", "")),
            media_type=str(data.get("media_type", "")),
            duration_us=int(data.get("duration_us", 0)),
            width=int(data.get("width", 0) or 0),
            height=int(data.get("height", 0) or 0),
            fps=float(data.get("fps", 0.0) or 0.0),
            source=str(data.get("source", "")),
            error=str(data.get("error", "")),
        )


class MediaProbeCache:
    def __init__(self, max_size: int = 1000):
        self._validate_max_size(max_size)
        self._max_size = max_size
        self._cache: OrderedDict[str, Tuple[int, int, MediaAsset]] = OrderedDict()
        self._pending: Dict[str, "_PendingProbe"] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _validate_max_size(max_size: int) -> None:
        if isinstance(max_size, bool) or not isinstance(max_size, int) or max_size <= 0:
            raise ValueError("max_size must be a positive integer")

    @property
    def max_size(self) -> int:
        with self._lock:
            return self._max_size

    def resize(self, max_size: int) -> None:
        self._validate_max_size(max_size)
        with self._lock:
            self._max_size = max_size
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def begin_probe(self, resolved_path: Path) -> Tuple["_PendingProbe", bool]:
        path_str = str(resolved_path)
        with self._lock:
            pending = self._pending.get(path_str)
            if pending is not None:
                return pending, False
            pending = _PendingProbe()
            self._pending[path_str] = pending
            return pending, True

    def finish_probe(
        self,
        resolved_path: Path,
        pending: "_PendingProbe",
        result: Optional[MediaAsset],
        error: Optional[BaseException],
    ) -> None:
        path_str = str(resolved_path)
        with self._lock:
            pending.result = result
            pending.error = error
            if self._pending.get(path_str) is pending:
                self._pending.pop(path_str, None)
            pending.event.set()

    def get(self, resolved_path: Path) -> Optional[MediaAsset]:
        path_str = str(resolved_path)
        with self._lock:
            if path_str not in self._cache:
                return None
        
        try:
            stat = resolved_path.stat()
            size = stat.st_size
            mtime_ns = stat.st_mtime_ns
        except Exception:
            # File might be deleted or inaccessible, invalidate cache entry
            self.invalidate(resolved_path)
            return None
            
        with self._lock:
            # Recheck if it was evicted or changed while we were statting
            if path_str not in self._cache:
                return None
            cached_size, cached_mtime_ns, asset = self._cache[path_str]
            if cached_size != size or cached_mtime_ns != mtime_ns:
                # Mismatch: invalidate
                self._cache.pop(path_str, None)
                return None
            
            # Update order for LRU (O(1))
            self._cache.move_to_end(path_str)
            return asset

    def set(self, resolved_path: Path, asset: MediaAsset) -> None:
        if asset.error:
            # Do not cache transient or other errors
            return
            
        try:
            stat = resolved_path.stat()
            size = stat.st_size
            mtime_ns = stat.st_mtime_ns
        except Exception:
            # Cannot stat, do not cache
            return

        path_str = str(resolved_path)
        with self._lock:
            if path_str in self._cache:
                self._cache.move_to_end(path_str)
            elif len(self._cache) >= self._max_size:
                # Evict LRU element (O(1))
                self._cache.popitem(last=False)

            self._cache[path_str] = (size, mtime_ns, asset)

    def invalidate(self, resolved_path: Path) -> None:
        path_str = str(resolved_path)
        with self._lock:
            self._cache.pop(path_str, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


class _PendingProbe:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: Optional[MediaAsset] = None
        self.error: Optional[BaseException] = None


_MEDIA_PROBE_CACHE = MediaProbeCache(max_size=1000)


def clear_media_probe_cache() -> None:
    """Clear the media probe cache."""
    _MEDIA_PROBE_CACHE.clear()


def set_media_probe_cache_max_size(max_size: int) -> None:
    """Set the maximum size of the media probe cache."""
    _MEDIA_PROBE_CACHE.resize(max_size)


def is_supported_visual_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_VISUAL_EXTENSIONS


def iter_media_files(media_dir: str | Path, *, recursive: bool = False) -> Iterable[Path]:
    root = Path(media_dir)
    if not root.exists():
        raise FileNotFoundError(f"Media folder not found: {root}")
    if recursive:
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext in SUPPORTED_VISUAL_EXTENSIONS:
                    yield Path(dirpath) / fname
    else:
        with os.scandir(root) as it:
            for entry in it:
                try:
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in SUPPORTED_VISUAL_EXTENSIONS:
                            yield Path(entry.path)
                except OSError:
                    continue


def scan_media_folder(
    media_dir: str | Path,
    *,
    recursive: bool = False,
    include_errors: bool = False,
    cancel_check: Optional[Callable[[], bool]] = None,
    timeout_sec: float = 15.0,
) -> List[MediaAsset]:
    try:
        files = list(iter_media_files(media_dir, recursive=recursive))
    except Exception as exc:
        if include_errors:
            return [MediaAsset(str(media_dir), "unknown", 0, error=str(exc))]
        return []

    assets: List[MediaAsset] = []
    
    # Capped at CPU count or sensible defaults (conservative for lower-spec machines)
    max_workers = min(4, os.cpu_count() or 2)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(probe_media, path, timeout_sec=timeout_sec): path
            for path in files
        }
        
        for future in as_completed(future_to_path):
            if cancel_check and cancel_check():
                # Cancel pending futures
                for f in future_to_path:
                    f.cancel()
                break
                
            path = future_to_path[future]
            try:
                asset = future.result()
                if not asset.error or include_errors:
                    assets.append(asset)
            except Exception as exc:
                if include_errors:
                    assets.append(MediaAsset(str(path), "unknown", 0, error=str(exc)))
                    
    assets.sort(key=lambda item: item.path.lower())
    return assets


def probe_media(path: str | Path, timeout_sec: float = 15.0) -> MediaAsset:
    path = Path(path).resolve()
    
    cached = _MEDIA_PROBE_CACHE.get(path)
    if cached is not None:
        return cached

    if not path.exists():
        return MediaAsset(str(path), "unknown", 0, error="file not found")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_MEDIA_EXTENSIONS:
        return MediaAsset(str(path), "unknown", 0, error=f"unsupported extension: {ext}")

    pending, is_owner = _MEDIA_PROBE_CACHE.begin_probe(path)
    if not is_owner:
        pending.event.wait()
        if pending.error is not None:
            raise pending.error
        if pending.result is not None:
            return pending.result
        return MediaAsset(str(path), "unknown", 0, error="media probe did not return a result")

    asset: Optional[MediaAsset] = None
    probe_error: Optional[BaseException] = None
    try:
        cached = _MEDIA_PROBE_CACHE.get(path)
        if cached is not None:
            asset = cached
            return asset

        ffprobe_path = resolve_ffprobe()
        if ffprobe_path:
            asset = _probe_with_ffprobe(path, ffprobe_path, timeout_sec=timeout_sec)
            if not asset.error or "timed out" in asset.error:
                if not asset.error:
                    _MEDIA_PROBE_CACHE.set(path, asset)
                return asset

        asset = _probe_with_pymediainfo(path)
        if not asset.error:
            _MEDIA_PROBE_CACHE.set(path, asset)
        return asset
    except BaseException as exc:
        probe_error = exc
        raise
    finally:
        _MEDIA_PROBE_CACHE.finish_probe(path, pending, asset, probe_error)


def _probe_with_ffprobe(path: Path, ffprobe_path: str, timeout_sec: float = 15.0) -> MediaAsset:
    try:
        cmd = [
            ffprobe_path,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                check=False,
                timeout=timeout_sec,
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired:
            return MediaAsset(
                path=str(path),
                media_type="unknown",
                duration_us=0,
                source="ffprobe",
                error=f"ffprobe timed out after {timeout_sec}s",
            )
        if result.returncode != 0:
            return MediaAsset(str(path), "unknown", 0, source="ffprobe", error=result.stderr.strip() or "ffprobe failed")

        payload = json.loads(result.stdout or "{}")
        streams = payload.get("streams") or []
        fmt = payload.get("format") or {}
        
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        
        if not video_stream and not audio_stream:
            return MediaAsset(str(path), "unknown", 0, source="ffprobe", error="no video/image or audio stream")

        ext = path.suffix.lower()
        if ext in AUDIO_EXTENSIONS:
            media_type = "audio"
            stream = audio_stream
        else:
            media_type = "image" if ext in IMAGE_EXTENSIONS else "video"
            stream = video_stream if video_stream else audio_stream

        duration_sec = _first_float(stream.get("duration"), fmt.get("duration")) if stream else 0.0
        duration_us = int(duration_sec * 1_000_000) if duration_sec > 0 else 0
        if media_type == "image":
            duration_us = PHOTO_DEFAULT_DURATION_US
        elif duration_us <= 0:
            return MediaAsset(str(path), media_type, 0, source="ffprobe", error="duration not found")

        return MediaAsset(
            path=str(path),
            media_type=media_type,
            duration_us=duration_us,
            width=int(stream.get("width") or 0) if (stream and media_type != "audio") else 0,
            height=int(stream.get("height") or 0) if (stream and media_type != "audio") else 0,
            fps=_parse_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate")) if (stream and media_type != "audio") else 0.0,
            source="ffprobe",
        )
    except Exception as exc:
        return MediaAsset(str(path), "unknown", 0, source="ffprobe", error=str(exc))


def _probe_with_pymediainfo(path: Path) -> MediaAsset:
    try:
        import pymediainfo
    except Exception as exc:
        return MediaAsset(str(path), "unknown", 0, source="pymediainfo", error=f"pymediainfo unavailable: {exc}")

    try:
        if not pymediainfo.MediaInfo.can_parse():
            return MediaAsset(str(path), "unknown", 0, source="pymediainfo", error="MediaInfo cannot parse files")

        info = pymediainfo.MediaInfo.parse(
            str(path),
            mediainfo_options={"File_TestContinuousFileNames": "0"},
        )

        ext = path.suffix.lower()
        if ext in AUDIO_EXTENSIONS:
            if info.audio_tracks:
                track = info.audio_tracks[0]
                duration_us = int((track.duration or 0) * 1000)
                if duration_us <= 0:
                    return MediaAsset(str(path), "audio", 0, source="pymediainfo", error="duration not found")
                return MediaAsset(
                    path=str(path),
                    media_type="audio",
                    duration_us=duration_us,
                    source="pymediainfo",
                )
            return MediaAsset(str(path), "unknown", 0, source="pymediainfo", error="no audio track")

        if info.video_tracks:
            track = info.video_tracks[0]
            media_type = "image" if ext in IMAGE_EXTENSIONS else "video"
            duration_us = PHOTO_DEFAULT_DURATION_US if media_type == "image" else int((track.duration or 0) * 1000)
            if media_type == "video" and duration_us <= 0:
                return MediaAsset(str(path), media_type, 0, source="pymediainfo", error="duration not found")
            return MediaAsset(
                path=str(path),
                media_type=media_type,
                duration_us=duration_us,
                width=int(track.width or 0),
                height=int(track.height or 0),
                fps=float(track.frame_rate or 0.0),
                source="pymediainfo",
            )

        if info.image_tracks:
            track = info.image_tracks[0]
            return MediaAsset(
                path=str(path),
                media_type="image",
                duration_us=PHOTO_DEFAULT_DURATION_US,
                width=int(track.width or 0),
                height=int(track.height or 0),
                source="pymediainfo",
            )

        return MediaAsset(str(path), "unknown", 0, source="pymediainfo", error="no visual or audio track")
    except Exception as exc:
        return MediaAsset(str(path), "unknown", 0, source="pymediainfo", error=str(exc))


def _first_float(*values: Any) -> float:
    for value in values:
        try:
            if value is None:
                continue
            parsed = float(value)
            if parsed > 0:
                return parsed
        except Exception:
            continue
    return 0.0


def _parse_fps(value: Any) -> float:
    if not value:
        return 0.0
    value = str(value)
    try:
        if "/" in value:
            left, right = value.split("/", 1)
            denominator = float(right)
            if denominator == 0:
                return 0.0
            return float(left) / denominator
        return float(value)
    except Exception:
        return 0.0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scan visual media files for CapCut Long Story.")
    parser.add_argument("media_dir")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--include-errors", action="store_true")
    args = parser.parse_args()

    for item in scan_media_folder(args.media_dir, recursive=args.recursive, include_errors=args.include_errors):
        print(json.dumps(item.to_dict(), ensure_ascii=False))
