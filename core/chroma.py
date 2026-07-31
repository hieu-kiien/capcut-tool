import os
import subprocess
from pathlib import Path
from typing import Dict, Tuple, Any
from core.logger import logger


# Map color mode to RGB and hex for FFmpeg/Pillow
_OVERLAY_BG_COLORS = {
    "green": ((0, 255, 0), "0x00FF00", "xanh lá"),
    "blue": ((0, 0, 255), "0x0000FF", "xanh dương"),
    "white": ((255, 255, 255), "0xFFFFFF", "trắng"),
    "black": ((0, 0, 0), "0x000000", "đen"),
}

_IMAGE_OVERLAY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_VIDEO_OVERLAY_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}

def remove_solid_bg_from_image(
    source_path: Path,
    output_dir: Path,
    prefix: str,
    mode: str,
    similarity: float,
    blend: float,
) -> Path:
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError(f"Thiếu Pillow để xóa nền ảnh logo: {exc}")

    target_rgb, _, label = _OVERLAY_BG_COLORS.get(mode, ((0, 255, 0), "0x00FF00", "xanh lá"))
    output_path = output_dir / f"{prefix}_{source_path.stem}_{mode}_transparent.png"
    output_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(source_path).convert("RGBA")
    threshold = max(8.0, min(255.0, 255.0 * float(similarity) * 1.7))
    feather = max(1.0, min(255.0, 255.0 * float(blend) * 1.7))
    tr, tg, tb = target_rgb
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            dist = ((r - tr) ** 2 + (g - tg) ** 2 + (b - tb) ** 2) ** 0.5
            if dist <= threshold:
                pixels[x, y] = (r, g, b, 0)
            elif dist <= threshold + feather:
                keep = (dist - threshold) / feather
                pixels[x, y] = (r, g, b, int(a * keep))
    image.save(output_path)
    logger.info(f"[CHROMA] Removed {mode} background from image overlay: {output_path.name}")
    return output_path
def remove_solid_bg_from_video(
    source_path: Path,
    output_dir: Path,
    prefix: str,
    mode: str,
    similarity: float,
    blend: float,
    cancel_check: Any = None,
) -> Path:
    from runtime_tools import resolve_ffmpeg
    from app.job_control import JobCancelled
    import time

    _, ffmpeg_color, label = _OVERLAY_BG_COLORS.get(mode, ((0, 255, 0), "0x00FF00", "xanh lá"))
    ffmpeg_path = resolve_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("Không tìm thấy FFmpeg để xóa nền hoạt ảnh.")

    output_path = output_dir / f"{prefix}_{source_path.stem}_{mode}_transparent.mov"
    filter_name = "colorkey" if mode in {"black", "white"} else "chromakey"
    vf = f"{filter_name}={ffmpeg_color}:{float(similarity):.3f}:{float(blend):.3f},format=argb"
    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        str(source_path),
        "-vf",
        vf,
        "-an",
        "-c:v",
        "qtrle",
        str(output_path),
    ]
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        creationflags=creationflags,
    )
    
    try:
        while process.poll() is None:
            if cancel_check and cancel_check():
                process.terminate()
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise JobCancelled("Quy trình xóa nền video đã bị hủy bởi người dùng.")
            time.sleep(0.1)
        
        stdout, stderr = process.communicate()
        return_code = process.returncode
    except Exception:
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2.0)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        raise

    if return_code != 0 or not output_path.exists():
        detail = (stderr or stdout or "FFmpeg failed").strip()
        raise RuntimeError(f"Không thể xóa nền {label} khỏi hoạt ảnh: {detail}")
    logger.info(f"[CHROMA] Removed {mode} background from video overlay: {output_path.name}")
    return output_path

def prepare_overlay_asset(
    source: str | Path,
    bg_mode: str,
    output_dir: Path,
    prefix: str,
    similarity: float = 0.18,
    blend: float = 0.08,
    cancel_check: Any = None,
) -> Path:
    source_path = Path(source)
    mode = (bg_mode or "none").strip().lower()
    if mode in {"", "none"}:
        return source_path
    if mode not in _OVERLAY_BG_COLORS:
        raise RuntimeError(f"Chế độ xóa nền overlay không hợp lệ: {bg_mode}")

    output_dir.mkdir(parents=True, exist_ok=True)
    ext = source_path.suffix.lower()
    if ext in _IMAGE_OVERLAY_EXTENSIONS:
        return remove_solid_bg_from_image(source_path, output_dir, prefix, mode, similarity, blend)
    if ext in _VIDEO_OVERLAY_EXTENSIONS:
        return remove_solid_bg_from_video(source_path, output_dir, prefix, mode, similarity, blend, cancel_check=cancel_check)
    raise RuntimeError(f"Không hỗ trợ xóa nền cho định dạng overlay: {ext or '(không rõ)'}")
