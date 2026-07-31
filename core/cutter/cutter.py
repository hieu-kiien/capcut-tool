import os
import subprocess
import threading
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
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
    cancel_event: Optional[threading.Event] = None
) -> Path:
    """
    Performs lossless video cutting using FFmpeg (-c copy).
    Fast and does not lose quality. Supports progress and cancellation.
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
        
        # Read stderr line-by-line for progress reporting
        while True:
            if cancel_event and cancel_event.is_set():
                process.terminate()
                process.wait()
                raise VideoCutterError("Cắt video bị hủy bởi người dùng.")
                
            line = process.stderr.readline()
            if not isinstance(line, str) or not line:
                break
                
            if log_callback:
                log_callback(line.strip())
                
            # Parse progress time from line: time=00:00:11.72
            if "time=" in line:
                try:
                    time_part = line.split("time=")[1].split()[0]
                    if ":" in time_part:
                        h, m, s = time_part.split(":")
                        secs = int(h) * 3600 + int(m) * 60 + float(s)
                    else:
                        secs = float(time_part)
                    
                    if duration_sec > 0:
                        pct = min(100.0, max(0.0, (secs / duration_sec) * 100.0))
                        if progress_callback:
                            progress_callback(pct)
                except Exception:
                    pass
                    
        process.wait()

        if process.returncode != 0:
            remaining_err = process.stderr.read()
            err_msg = f"FFmpeg failed with exit code {process.returncode}.\nStderr: {remaining_err}"
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
