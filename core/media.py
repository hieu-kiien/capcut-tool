import os
import json
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable
from runtime_tools import resolve_ffprobe

# Supported extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".wmv", ".flv", ".mpeg", ".mpg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

PHOTO_DEFAULT_DURATION_US = 3 * 60 * 60 * 1_000_000  # 3 hours default for images in CapCut

class MediaProber:
    @staticmethod
    def probe_file(file_path: str | Path, timeout_sec: float = 15.0) -> Dict[str, Any]:
        """
        Probes a single file using ffprobe.
        Returns a dict with metadata or error details.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            return {"path": str(path), "error": "Tệp không tồn tại", "media_type": "unknown"}

        filename = path.name
        suffix = path.suffix.lower()

        if suffix not in SUPPORTED_EXTENSIONS:
            return {"path": str(path), "error": f"Định dạng {suffix} không được hỗ trợ", "media_type": "unknown"}

        # HEIC / HEIF handling: directly mark as unsupported codec warning
        if suffix in {".heic", ".heif"}:
            return {
                "path": str(path),
                "filename": filename,
                "media_type": "image",
                "duration_us": PHOTO_DEFAULT_DURATION_US,
                "width": 0,
                "height": 0,
                "fps": 0.0,
                "error": "codec không hỗ trợ (HEIC/HEIF)"
            }

        ffprobe_path = resolve_ffprobe()
        if not ffprobe_path:
            return {"path": str(path), "error": "Không tìm thấy ffprobe", "media_type": "unknown"}

        try:
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-show_streams",
                "-show_format",
                "-of", "json",
                str(path)
            ]
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=timeout_sec,
                creationflags=creationflags
            )

            if result.returncode != 0:
                return {
                    "path": str(path),
                    "filename": filename,
                    "media_type": "unknown",
                    "error": "Lỗi đọc tệp (hỏng header hoặc định dạng lỗi)"
                }

            payload = json.loads(result.stdout or "{}")
            streams = payload.get("streams") or []
            fmt = payload.get("format") or {}

            video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

            if not video_stream and not audio_stream:
                return {
                    "path": str(path),
                    "filename": filename,
                    "media_type": "unknown",
                    "error": "Không phát hiện luồng video/hình ảnh hoặc âm thanh"
                }

            # Classify media type
            if suffix in AUDIO_EXTENSIONS:
                media_type = "audio"
                stream = audio_stream
            elif suffix in IMAGE_EXTENSIONS:
                media_type = "image"
                stream = video_stream or audio_stream
            else:
                media_type = "video"
                stream = video_stream or audio_stream

            # Parse duration
            duration_sec = 0.0
            if stream:
                duration_val = stream.get("duration") or fmt.get("duration")
                if duration_val:
                    try:
                        duration_sec = float(duration_val)
                    except ValueError:
                        pass

            duration_us = int(duration_sec * 1_000_000) if duration_sec > 0 else 0
            if media_type == "image":
                duration_us = PHOTO_DEFAULT_DURATION_US

            # Fallback for duration if video/audio has no duration info (corrupt header check)
            if media_type in {"video", "audio"} and duration_us <= 0:
                return {
                    "path": str(path),
                    "filename": filename,
                    "media_type": media_type,
                    "error": "không tìm thấy thông tin thời lượng (hỏng header)"
                }

            width = 0
            height = 0
            fps = 0.0
            if stream and media_type != "audio":
                width = int(stream.get("width") or 0)
                height = int(stream.get("height") or 0)
                
                # Parse FPS
                fps_val = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
                if fps_val and "/" in fps_val:
                    try:
                        num, den = fps_val.split("/")
                        if float(den) > 0:
                            fps = float(num) / float(den)
                    except (ValueError, ZeroDivisionError):
                        pass
                elif fps_val:
                    try:
                        fps = float(fps_val)
                    except ValueError:
                        pass

            # Corrupt check for video/image having dimensions of 0
            if media_type in {"video", "image"} and (width <= 0 or height <= 0):
                return {
                    "path": str(path),
                    "filename": filename,
                    "media_type": media_type,
                    "error": "Kích thước hình ảnh bằng 0 (hỏng header)"
                }

            return {
                "path": str(path),
                "filename": filename,
                "media_type": media_type,
                "duration_us": duration_us,
                "width": width,
                "height": height,
                "fps": fps,
                "error": ""
            }

        except subprocess.TimeoutExpired:
            return {"path": str(path), "filename": filename, "media_type": "unknown", "error": f"Quá thời gian quét ({timeout_sec}s)"}
        except Exception as e:
            return {"path": str(path), "filename": filename, "media_type": "unknown", "error": str(e)}


def scan_media_directory(
    directory: str | Path,
    recursive: bool = False,
    canvas_ratio: str = "9:16",
    cancel_check: Optional[Callable[[], bool]] = None,
    timeout_sec: float = 15.0
) -> Dict[str, Any]:
    """
    Recursively scans the directory and probes all supported media assets in parallel.
    Validates them based on canvas_ratio and classifies warnings/errors.
    """
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        return {"valid": [], "warnings": [{"filename": root.name, "path": str(root), "error": "Thư mục không tồn tại", "severity": "error"}]}

    # Find files
    files = []
    pattern = "**/*" if recursive else "*"
    try:
        for p in root.glob(pattern):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(p)
    except Exception as e:
        return {"valid": [], "warnings": [{"filename": root.name, "path": str(root), "error": f"Lỗi quét thư mục: {e}", "severity": "error"}]}

    valid_assets = []
    warnings = []

    if not files:
        return {"valid": [], "warnings": []}

    # Parallel processing
    max_workers = min(32, (os.cpu_count() or 4) + 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(MediaProber.probe_file, path, timeout_sec=timeout_sec): path
            for path in files
        }

        for future in as_completed(future_to_path):
            if cancel_check and cancel_check():
                for f in future_to_path:
                    f.cancel()
                break

            path = future_to_path[future]
            try:
                res = future.result()
                filename = res.get("filename", path.name)
                error_msg = res.get("error", "")

                if error_msg:
                    # Classify severity
                    severity = "error"
                    if "codec không hỗ trợ" in error_msg:
                        severity = "error"
                    elif "hỏng header" in error_msg or "hỏng" in error_msg:
                        severity = "error"
                    
                    warnings.append({
                        "filename": filename,
                        "path": str(path),
                        "error": error_msg,
                        "severity": severity
                    })
                else:
                    # Aspect ratio check
                    width = res.get("width", 0)
                    height = res.get("height", 0)
                    media_type = res.get("media_type", "")

                    if media_type in {"video", "image"} and width > 0 and height > 0:
                        is_vertical = width < height
                        is_horizontal = width > height
                        is_square = width == height

                        ratio_mismatch = False
                        ratio_desc = ""

                        if canvas_ratio == "9:16" and not is_vertical:
                            # Canvas is vertical, but media is horizontal/square
                            ratio_mismatch = True
                            ratio_desc = "sai tỉ lệ khung hình (media ngang/vuông trong canvas dọc 9:16)"
                        elif canvas_ratio == "16:9" and not is_horizontal:
                            # Canvas is horizontal, but media is vertical/square
                            ratio_mismatch = True
                            ratio_desc = "sai tỉ lệ khung hình (media dọc/vuông trong canvas ngang 16:9)"

                        if ratio_mismatch:
                            warnings.append({
                                "filename": filename,
                                "path": str(path),
                                "error": ratio_desc,
                                "severity": "warning"
                            })
                            # Still include in valid assets, but with a warning tag
                            res["warning"] = ratio_desc

                    valid_assets.append(res)

            except Exception as e:
                warnings.append({
                    "filename": path.name,
                    "path": str(path),
                    "error": f"Lỗi quét: {e}",
                    "severity": "error"
                })

    # Sort files alphabetically
    valid_assets.sort(key=lambda x: x["filename"].lower())
    warnings.sort(key=lambda x: x["filename"].lower())

    return {
        "valid": valid_assets,
        "warnings": warnings
    }
