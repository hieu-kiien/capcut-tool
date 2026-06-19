import os
import subprocess
from pathlib import Path
from typing import Optional, Callable
from runtime_tools import resolve_ffmpeg

class VideoCutterError(Exception):
    pass

def lossless_cut_video(
    input_path: str | Path,
    output_path: str | Path,
    start_sec: float,
    duration_sec: float,
    log_callback: Optional[Callable[[str], None]] = None
) -> Path:
    """
    Performs lossless video cutting using FFmpeg (-c copy).
    Fast and does not lose quality.
    
    Args:
        input_path: Path to the source video file.
        output_path: Target path for the cut video.
        start_sec: Start time in seconds (float).
        duration_sec: Duration in seconds (float).
        log_callback: Optional callback to receive execution logs.
        
    Returns:
        Path object pointing to the output file.
    """
    src = Path(input_path).resolve()
    dst = Path(output_path).resolve()

    if not src.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp video nguồn: {src}")

    if start_sec < 0:
        start_sec = 0.0
    if duration_sec <= 0:
        raise ValueError("Thời lượng cắt phải lớn hơn 0 giây.")

    # Resolve FFmpeg path
    ffmpeg_exe = resolve_ffmpeg()
    if not ffmpeg_exe:
        raise VideoCutterError("Không tìm thấy FFmpeg trên hệ thống.")

    # Ensure output directory exists
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Build FFmpeg command
    # -ss before -i is extremely fast (jumps directly to target keyframe)
    # -to can specify end time, but -t specifies duration. We use -t for duration.
    cmd = [
        ffmpeg_exe,
        "-y",
        "-ss", f"{start_sec:.3f}",
        "-i", str(src),
        "-t", f"{duration_sec:.3f}",
        "-c", "copy",
        "-map", "0",
        str(dst)
    ]

    log_msg = f"FFmpeg Command: {' '.join(cmd)}"
    if log_callback:
        log_callback(f"[HỆ THỐNG] Khởi chạy FFmpeg lossless cut...")
        log_callback(f"[HỆ THỐNG] {log_msg}")

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags
        )
        
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            err_msg = f"FFmpeg failed with exit code {process.returncode}.\nStderr: {stderr}"
            if log_callback:
                log_callback(f"[LỖI] {err_msg}")
            raise VideoCutterError(err_msg)

        if log_callback:
            log_callback(f"[THÀNH CÔNG] Đã cắt video thành công: {dst.name}")

        return dst

    except Exception as e:
        if not isinstance(e, (VideoCutterError, FileNotFoundError, ValueError)):
            e = VideoCutterError(f"Lỗi không xác định khi chạy FFmpeg: {e}")
        if log_callback:
            log_callback(f"[LỖI] {e}")
        raise e
