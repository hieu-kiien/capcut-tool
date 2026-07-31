from __future__ import annotations

import concurrent.futures
import importlib.util
import os
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import runtime_tools

ProgressCallback = Callable[[str], None]

class YtDlpUnavailable(RuntimeError):
    pass

class DownloadCancelled(RuntimeError):
    pass

@dataclass(frozen=True)
class DownloadOptions:
    urls: list[str]
    output_dir: str
    cookies_file: str = ""
    use_archive: bool = True
    include_playlists: bool = False
    playlist_limit: int = 0
    workers: int = 2
    download_kind: str = "video"
    url_tools: list[str] = None
    max_file_size_mb: int = 4096
    stall_timeout_sec: int = 180
    item_timeout_sec: int = 7200

@dataclass
class DownloadItemResult:
    url: str
    status: str  # "waiting", "downloading", "completed", "failed", "cancelled"
    output_path: str = ""
    error: str = ""
    return_code: Optional[int] = None

@dataclass(frozen=True)
class DownloadSummary:
    total: int
    succeeded: int
    failed: int
    output_dir: str
    results: list[DownloadItemResult]

def parse_url_list(raw_text: str) -> list[str]:
    urls: list[str] = []
    for i, raw_line in enumerate(raw_text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            urls.append(_validate_url(line))
        except ValueError as e:
            raise ValueError(f"Dòng {i}: {e}")
    return urls

def _validate_url(url: str) -> str:
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in url):
        raise ValueError("URL không hợp lệ: chứa ký tự điều khiển hoặc khoảng trắng nguy hại.")
    if any(ch in url for ch in [";", "|", "`", "$"]):
        raise ValueError("URL không hợp lệ: chứa ký tự đặc biệt có nguy cơ bảo mật.")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Chỉ hỗ trợ URL http/https: {url}")
    return url

def resolve_ytdlp_command() -> list[str]:
    executable = runtime_tools.resolve_ytdlp()
    if executable:
        return [executable]
    if not getattr(sys, "frozen", False) and importlib.util.find_spec("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    return []

def resolve_gallerydl_command() -> list[str]:
    executable = runtime_tools.resolve_gallerydl()
    if executable:
        return [executable]
    if not getattr(sys, "frozen", False) and importlib.util.find_spec("gallery_dl"):
        return [sys.executable, "-m", "gallery_dl"]
    return []

def parse_gallerydl_line(line: str) -> tuple[Optional[str], Optional[str]]:
    line_strip = line.strip()
    if not line_strip:
        return None, None
    if line_strip.startswith("["):
        return "Đang tải", None
    if not line_strip.startswith("#") and ("/" in line_strip or "\\" in line_strip):
        return "Đang tải", line_strip
    return "Đang tải", None

def build_gallerydl_command(
    options: DownloadOptions,
    url: str,
    *,
    gallerydl_command: Optional[list[str]] = None,
) -> list[str]:
    command = list(gallerydl_command if gallerydl_command is not None else resolve_gallerydl_command())
    if not command:
        raise ValueError("Không tìm thấy gallery-dl.")

    output_dir = _prepare_output_dir(options.output_dir)
    archive_file = output_dir / ".gallery-dl-archive.txt"
    cookies_file = _validate_optional_file(options.cookies_file, "cookies")

    args = [
        *command,
        "--directory", str(output_dir),
    ]
    if cookies_file:
        args.extend(["--cookies", str(cookies_file)])
    if options.use_archive:
        args.extend(["--download-archive", str(archive_file)])
    max_file_size = _max_file_size_bytes(options)
    if max_file_size > 0:
        args.extend(["--filesize-max", str(max_file_size)])
    args.append(url)
    return args

def get_ytdlp_version(command: list[str]) -> str:
    if not command:
        try:
            import yt_dlp
            return getattr(yt_dlp, "__version__", "unknown")
        except Exception:
            return "unknown"
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [*command, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            creationflags=creationflags,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"

def parse_ytdlp_line(line: str) -> tuple[Optional[str], Optional[str]]:
    percent = None
    output_path = None
    
    m = re.search(r"\[download\]\s+([0-9.]+)%", line)
    if m:
        percent = m.group(1) + "%"
        
    dest_m = re.search(r"\[download\] Destination:\s+(.+)", line)
    if dest_m:
        output_path = dest_m.group(1)
    else:
        already_m = re.search(r"\[download\]\s+(.+?)\s+has already been downloaded", line)
        if already_m:
            output_path = already_m.group(1)
        else:
            merge_m = re.search(r"\[Merger\] Merging formats into\s+\"*(.+?)\"*$", line)
            if merge_m:
                output_path = merge_m.group(1)
            else:
                audio_m = re.search(r"\[ExtractAudio\] Destination:\s+(.+)", line)
                if audio_m:
                    output_path = audio_m.group(1)
                    
    return percent, output_path

def build_ytdlp_command(
    options: DownloadOptions,
    url: str,
    *,
    ytdlp_command: Optional[list[str]] = None,
    ffmpeg_path: Optional[str] = None,
) -> list[str]:
    command = list(ytdlp_command if ytdlp_command is not None else resolve_ytdlp_command())
    if not command:
        raise YtDlpUnavailable(_missing_ytdlp_message())

    output_dir = _prepare_output_dir(options.output_dir)
    cookies_file = _validate_optional_file(options.cookies_file, "cookies")
    archive_file = output_dir / ".yt-dlp-archive.txt"
    resolved_ffmpeg = ffmpeg_path if ffmpeg_path is not None else runtime_tools.resolve_ffmpeg()

    args = [
        *command,
        "--newline",
        "--continue",
        "--no-overwrites",
        "--windows-filenames",
        "--trim-filenames",
        "180",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--socket-timeout",
        "30",
        "--paths",
        str(output_dir),
        "-o",
        "%(extractor_key)s/%(title).180B [%(id)s].%(ext)s",
    ]

    if _max_file_size_bytes(options) > 0:
        args.extend(["--max-filesize", f"{int(options.max_file_size_mb)}M"])
    if resolved_ffmpeg:
        args.extend(["--ffmpeg-location", str(Path(resolved_ffmpeg).resolve().parent)])
    if options.use_archive:
        args.extend(["--download-archive", str(archive_file)])
    if cookies_file:
        args.extend(["--cookies", str(cookies_file)])
    if not options.include_playlists:
        args.append("--no-playlist")
    elif options.playlist_limit > 0:
        args.extend(["--playlist-end", str(options.playlist_limit)])

    if options.download_kind == "audio":
        args.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0"])
    else:
        args.extend(["-f", "bv*+ba/b", "--merge-output-format", "mp4"])

    args.append(_validate_url(url))
    return args

class YtDlpDownloadRunner:
    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._processes: dict[int, subprocess.Popen] = {}
        self._process_lock = threading.Lock()
        self._cancelled_indexes: set[int] = set()

    def cancel(self) -> None:
        self._cancel_event.set()
        with self._process_lock:
            processes = list(self._processes.values())
        for process in processes:
            try:
                if process.poll() is None:
                    _terminate_process(process)
            except Exception:
                pass

    def cancel_item(self, index: int) -> None:
        with self._process_lock:
            self._cancelled_indexes.add(index)
            process = self._processes.get(index)
        if process:
            try:
                if process.poll() is None:
                    _terminate_process(process)
            except Exception:
                pass

    def run(
        self,
        options: DownloadOptions,
        *,
        progress: Optional[ProgressCallback] = None,
        item_progress: Optional[Callable[[int, str, str, str, str], None]] = None,
    ) -> DownloadSummary:
        urls = [_validate_url(url.strip()) for url in options.urls if url.strip()]
        if not urls:
            raise ValueError("Chưa có URL nào để tải.")

        output_dir = _prepare_output_dir(options.output_dir)

        # Preflight Check 1: Write permission
        try:
            test_file = output_dir / f".write_test_{int(time.time())}"
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
        except Exception as exc:
            raise PermissionError(f"Không có quyền ghi vào thư mục lưu media: {exc}")

        # Preflight Check 2: Disk space check
        import shutil
        try:
            total, used, free = shutil.disk_usage(output_dir)
            free_gb = free / (1024 ** 3)
            if free_gb < 2.0:
                _emit(progress, f"[yt-dlp] [CẢNH BÁO] Ổ đĩa lưu media chỉ còn {free_gb:.2f} GB trống.")
        except Exception:
            pass

        workers = min(4, max(1, int(options.workers or 1)))
        url_tools = options.url_tools if options.url_tools else ["yt-dlp"] * len(urls)
        if len(url_tools) < len(urls):
            url_tools = list(url_tools) + ["yt-dlp"] * (len(urls) - len(url_tools))

        normalized = DownloadOptions(
            urls=urls,
            output_dir=str(output_dir),
            cookies_file=options.cookies_file,
            use_archive=options.use_archive,
            include_playlists=options.include_playlists,
            playlist_limit=max(0, int(options.playlist_limit or 0)),
            workers=workers,
            download_kind=options.download_kind if options.download_kind == "audio" else "video",
            url_tools=url_tools,
            max_file_size_mb=max(0, int(options.max_file_size_mb or 0)),
            stall_timeout_sec=max(30, int(options.stall_timeout_sec or 180)),
            item_timeout_sec=max(60, int(options.item_timeout_sec or 7200)),
        )

        command = resolve_ytdlp_command()
        use_library = not command and importlib.util.find_spec("yt_dlp") is not None
        if not command and not use_library:
            raise YtDlpUnavailable(_missing_ytdlp_message())

        ytdlp_ver = get_ytdlp_version(command)
        backend = "subprocess" if command else "python package"
        _emit(progress, f"[yt-dlp] Phiên bản: {ytdlp_ver} | Backend: {backend}. Thư mục lưu: {output_dir}")

        results = [DownloadItemResult(url=url, status="waiting") for url in urls]

        def wrapper_item_progress(idx: int, status: str, message: str, output_path: str, error: str):
            item = results[idx]
            item.status = status
            if output_path:
                item.output_path = output_path
            if error:
                item.error = error
            if item_progress:
                item_progress(idx, status, message, output_path, error)

        succeeded = 0
        failed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for index, url in enumerate(urls):
                tool = url_tools[index]
                if tool == "gallery-dl":
                    gallerydl_cmd = resolve_gallerydl_command()
                    if not gallerydl_cmd:
                        def fail_immediately(idx=index):
                            wrapper_item_progress(idx, "failed", "Lỗi", "", "gallery-dl chưa được cài/tích hợp")
                            return False
                        future = executor.submit(fail_immediately)
                    else:
                        future = executor.submit(
                            self._download_one_gallerydl_process, normalized, url, index, len(urls), gallerydl_cmd, progress, wrapper_item_progress
                        )
                else:
                    if use_library:
                        future = executor.submit(
                            self._download_one_library, normalized, url, index, len(urls), progress, wrapper_item_progress
                        )
                    else:
                        future = executor.submit(
                            self._download_one_process, normalized, url, index, len(urls), command, progress, wrapper_item_progress
                        )
                futures[future] = index

            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                if self._cancel_event.is_set():
                    for i, res in enumerate(results):
                        if res.status in ("waiting", "downloading"):
                            wrapper_item_progress(i, "cancelled", "Đã hủy", res.output_path, "")
                    raise DownloadCancelled("Đã hủy tải media.")
                try:
                    success = future.result()
                    if success:
                        succeeded += 1
                        results[idx].status = "completed"
                    else:
                        if results[idx].status != "cancelled":
                            failed += 1
                            results[idx].status = "failed"
                except DownloadCancelled:
                    self.cancel()
                    for i, res in enumerate(results):
                        if res.status in ("waiting", "downloading"):
                            wrapper_item_progress(i, "cancelled", "Đã hủy", res.output_path, "")
                    raise
                except Exception as exc:
                    failed += 1
                    err_msg = str(exc)
                    wrapper_item_progress(idx, "failed", "Lỗi", results[idx].output_path, err_msg)
                    _emit(progress, f"[yt-dlp] Lỗi URL {urls[idx]}: {exc}")

        return DownloadSummary(
            total=len(urls),
            succeeded=succeeded,
            failed=failed,
            output_dir=str(output_dir),
            results=results
        )

    def _download_one_process(
        self,
        options: DownloadOptions,
        url: str,
        index: int,
        total: int,
        command: list[str],
        progress: Optional[ProgressCallback],
        item_progress: Optional[Callable[[int, str, str, str, str], None]],
    ) -> bool:
        if self._cancel_event.is_set():
            if item_progress:
                item_progress(index, "cancelled", "Đã hủy", "", "")
            raise DownloadCancelled("Đã hủy tải media.")

        args = build_ytdlp_command(options, url, ytdlp_command=command)
        prefix = f"[yt-dlp {index+1}/{total}]"
        _emit(progress, f"{prefix} Bắt đầu: {url}")
        
        if item_progress:
            item_progress(index, "downloading", "0%", "", "")

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        with self._process_lock:
            self._processes[index] = process
        
        last_percent = "0%"
        output_path = ""
        try:
            for line in _iter_process_output(process, options, self._cancel_event):
                if self._cancel_event.is_set():
                    self.cancel()
                    if item_progress:
                        item_progress(index, "cancelled", "Đã hủy", output_path, "")
                    raise DownloadCancelled("Đã hủy tải media.")
                if index in self._cancelled_indexes:
                    try:
                        if process.poll() is None:
                            _terminate_process(process)
                    except Exception:
                        pass
                    if item_progress:
                        item_progress(index, "cancelled", "Đã hủy", output_path, "")
                    return False
                text = line.strip()
                if text:
                    _emit(progress, f"{prefix} {text}")
                    pct, out_p = parse_ytdlp_line(text)
                    if pct:
                        last_percent = pct
                    if out_p:
                        output_path = out_p
                    if pct or out_p:
                        if item_progress:
                            item_progress(index, "downloading", last_percent, output_path, "")
            return_code = _safe_wait(process)
        finally:
            with self._process_lock:
                self._processes.pop(index, None)

        if self._cancel_event.is_set() or index in self._cancelled_indexes:
            if item_progress:
                item_progress(index, "cancelled", "Đã hủy", output_path, "")
            if index in self._cancelled_indexes:
                return False
            raise DownloadCancelled("Đã hủy tải media.")
        if return_code != 0:
            _emit(progress, f"{prefix} Thất bại với mã thoát {return_code}.")
            if item_progress:
                item_progress(index, "failed", "Lỗi", output_path, f"Exit code {return_code}")
            return False
        if _output_exceeds_limit(output_path, options):
            error = f"File vượt quá giới hạn {int(options.max_file_size_mb)} MB"
            _emit(progress, f"{prefix} {error}.")
            if item_progress:
                item_progress(index, "failed", "Lỗi", output_path, error)
            return False

        _emit(progress, f"{prefix} Hoàn thành.")
        if item_progress:
            item_progress(index, "completed", "100%", output_path, "")
        return True

    def _download_one_gallerydl_process(
        self,
        options: DownloadOptions,
        url: str,
        index: int,
        total: int,
        command: list[str],
        progress: Optional[ProgressCallback],
        item_progress: Optional[Callable[[int, str, str, str, str], None]],
    ) -> bool:
        if self._cancel_event.is_set():
            if item_progress:
                item_progress(index, "cancelled", "Đã hủy", "", "")
            raise DownloadCancelled("Đã hủy tải media.")

        args = build_gallerydl_command(options, url, gallerydl_command=command)
        prefix = f"[gallery-dl {index+1}/{total}]"
        _emit(progress, f"{prefix} Bắt đầu: {url}")
        
        if item_progress:
            item_progress(index, "downloading", "Đang tải", "", "")

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        with self._process_lock:
            self._processes[index] = process
        
        output_path = ""
        try:
            for line in _iter_process_output(process, options, self._cancel_event):
                if self._cancel_event.is_set():
                    self.cancel()
                    if item_progress:
                        item_progress(index, "cancelled", "Đã hủy", output_path, "")
                    raise DownloadCancelled("Đã hủy tải media.")
                if index in self._cancelled_indexes:
                    try:
                        if process.poll() is None:
                            _terminate_process(process)
                    except Exception:
                        pass
                    if item_progress:
                        item_progress(index, "cancelled", "Đã hủy", output_path, "")
                    return False
                text = line.strip()
                if text:
                    _emit(progress, f"{prefix} {text}")
                    pct, out_p = parse_gallerydl_line(text)
                    if out_p:
                        output_path = out_p
                    if item_progress:
                        item_progress(index, "downloading", "Đang tải", output_path or "", "")
            return_code = _safe_wait(process)
        finally:
            with self._process_lock:
                self._processes.pop(index, None)

        if self._cancel_event.is_set() or index in self._cancelled_indexes:
            if item_progress:
                item_progress(index, "cancelled", "Đã hủy", output_path, "")
            if index in self._cancelled_indexes:
                return False
            raise DownloadCancelled("Đã hủy tải media.")
        if return_code != 0:
            _emit(progress, f"{prefix} Thất bại với mã thoát {return_code}.")
            if item_progress:
                item_progress(index, "failed", "Lỗi", output_path, f"Exit code {return_code}")
            return False
        if _output_exceeds_limit(output_path, options):
            error = f"File vượt quá giới hạn {int(options.max_file_size_mb)} MB"
            _emit(progress, f"{prefix} {error}.")
            if item_progress:
                item_progress(index, "failed", "Lỗi", output_path, error)
            return False

        _emit(progress, f"{prefix} Hoàn thành.")
        if item_progress:
            item_progress(index, "completed", "100%", output_path, "")
        return True

    def _download_one_library(
        self,
        options: DownloadOptions,
        url: str,
        index: int,
        total: int,
        progress: Optional[ProgressCallback],
        item_progress: Optional[Callable[[int, str, str, str, str], None]],
    ) -> bool:
        if self._cancel_event.is_set():
            if item_progress:
                item_progress(index, "cancelled", "Đã hủy", "", "")
            raise DownloadCancelled("Đã hủy tải media.")

        import yt_dlp

        prefix = f"[yt-dlp {index+1}/{total}]"
        _emit(progress, f"{prefix} Bắt đầu: {url}")
        
        if item_progress:
            item_progress(index, "downloading", "0%", "", "")

        ydl_opts = build_ytdlp_library_options(
            options,
            progress=progress,
            prefix=prefix,
            cancel_event=self._cancel_event,
            item_index=index,
            item_progress=item_progress,
        )
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result_code = ydl.download([_validate_url(url)])
        except DownloadCancelled:
            raise
        except Exception as exc:
            _emit(progress, f"{prefix} Thất bại: {exc}")
            if item_progress:
                item_progress(index, "failed", "Lỗi", "", str(exc))
            return False

        if self._cancel_event.is_set():
            raise DownloadCancelled("Đã hủy tải media.")
        if result_code != 0:
            _emit(progress, f"{prefix} Thất bại với mã thoát {result_code}.")
            if item_progress:
                item_progress(index, "failed", "Lỗi", "", f"Exit code {result_code}")
            return False

        _emit(progress, f"{prefix} Hoàn thành.")
        if item_progress:
            item_progress(index, "completed", "100%", "", "")
        return True


def build_ytdlp_library_options(
    options: DownloadOptions,
    *,
    progress: Optional[ProgressCallback] = None,
    prefix: str = "[yt-dlp]",
    cancel_event: Optional[threading.Event] = None,
    item_index: int = 0,
    item_progress: Optional[Callable[[int, str, str, str, str], None]] = None,
) -> dict:
    output_dir = _prepare_output_dir(options.output_dir)
    cookies_file = _validate_optional_file(options.cookies_file, "cookies")
    resolved_ffmpeg = runtime_tools.resolve_ffmpeg()

    outtmpl = str(output_dir / "%(extractor_key)s" / "%(title).180B [%(id)s].%(ext)s")
    ydl_opts: dict = {
        "outtmpl": outtmpl,
        "windowsfilenames": True,
        "trim_file_name": 180,
        "continuedl": True,
        "overwrites": False,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 30,
        "noplaylist": not options.include_playlists,
        "logger": _YtDlpLogger(progress, prefix),
        "progress_hooks": [_build_progress_hook(progress, prefix, cancel_event, item_index, item_progress)],
    }

    if resolved_ffmpeg:
        ydl_opts["ffmpeg_location"] = str(Path(resolved_ffmpeg).resolve().parent)
    if options.use_archive:
        ydl_opts["download_archive"] = str(output_dir / ".yt-dlp-archive.txt")
    if cookies_file:
        ydl_opts["cookiefile"] = str(cookies_file)
    if options.include_playlists and options.playlist_limit > 0:
        ydl_opts["playlistend"] = int(options.playlist_limit)
    max_file_size = _max_file_size_bytes(options)
    if max_file_size > 0:
        ydl_opts["max_filesize"] = max_file_size

    if options.download_kind == "audio":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}
        ]
    else:
        ydl_opts["format"] = "bv*+ba/b"
        ydl_opts["merge_output_format"] = "mp4"

    return ydl_opts


class _YtDlpLogger:
    def __init__(self, progress: Optional[ProgressCallback], prefix: str) -> None:
        self.progress = progress
        self.prefix = prefix

    def debug(self, message: str) -> None:
        if message.startswith("[debug]"):
            return
        _emit(self.progress, f"{self.prefix} {message}")

    def warning(self, message: str) -> None:
        _emit(self.progress, f"{self.prefix} Cảnh báo: {message}")

    def error(self, message: str) -> None:
        _emit(self.progress, f"{self.prefix} Lỗi: {message}")


def _build_progress_hook(
    progress: Optional[ProgressCallback],
    prefix: str,
    cancel_event: Optional[threading.Event],
    item_index: int,
    item_progress: Optional[Callable[[int, str, str, str, str], None]],
) -> Callable[[dict], None]:
    def hook(data: dict) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled("Đã hủy tải media.")
        status = data.get("status")
        filename = data.get("filename") or ""
        if not filename:
            filename = data.get("info_dict", {}).get("_filename") or ""

        if status == "downloading":
            percent = data.get("_percent_str", "").strip()
            speed = data.get("_speed_str", "").strip()
            eta = data.get("_eta_str", "").strip()
            parts = [part for part in [percent, speed, f"ETA {eta}" if eta else ""] if part]
            if parts:
                _emit(progress, f"{prefix} Đang tải: {' | '.join(parts)}")
            if item_progress:
                item_progress(item_index, "downloading", percent or "0%", filename, "")
        elif status == "finished":
            _emit(progress, f"{prefix} Đã tải xong file nguồn: {Path(filename).name}")
            if item_progress:
                item_progress(item_index, "completed", "100%", filename, "")

    return hook


def _iter_process_output(
    process: subprocess.Popen,
    options: DownloadOptions,
    cancel_event: threading.Event,
):
    if process.stdout is None:
        return

    lines = queue.Queue()
    sentinel = object()

    def reader() -> None:
        try:
            for line in process.stdout:
                lines.put(line)
        finally:
            lines.put(sentinel)

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    started_at = time.monotonic()
    last_output_at = started_at
    stall_timeout = max(1.0, float(options.stall_timeout_sec or 0))
    item_timeout = max(1.0, float(options.item_timeout_sec or 0))

    while True:
        if cancel_event.is_set():
            _terminate_process(process)
            raise DownloadCancelled("Đã hủy tải media.")

        now = time.monotonic()
        if item_timeout > 0 and now - started_at > item_timeout:
            _terminate_process(process)
            raise TimeoutError(f"Download vượt quá timeout {int(item_timeout)} giây.")
        if stall_timeout > 0 and process.poll() is None and now - last_output_at > stall_timeout:
            _terminate_process(process)
            raise TimeoutError(f"Download không có tiến triển trong {int(stall_timeout)} giây.")

        try:
            item = lines.get(timeout=0.25)
        except queue.Empty:
            if process.poll() is not None and not reader_thread.is_alive():
                break
            continue

        if item is sentinel:
            break
        last_output_at = time.monotonic()
        yield item


def _terminate_process(process: subprocess.Popen, *, kill_after_sec: float = 5.0) -> None:
    try:
        if process.poll() is not None:
            return
    except Exception:
        pass

    try:
        process.terminate()
    except Exception:
        pass

    try:
        process.wait(timeout=kill_after_sec)
        return
    except TypeError:
        deadline = time.monotonic() + kill_after_sec
        while time.monotonic() < deadline:
            try:
                if process.poll() is not None:
                    return
            except Exception:
                return
            time.sleep(0.1)
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    try:
        if process.poll() is None:
            process.kill()
    except Exception:
        pass

    try:
        process.wait(timeout=2)
    except TypeError:
        try:
            process.wait()
        except Exception:
            pass
    except Exception:
        pass


def _safe_wait(process: subprocess.Popen, *, timeout_sec: float = 5.0) -> int:
    try:
        code = process.wait(timeout=timeout_sec)
    except TypeError:
        code = process.wait()
    except subprocess.TimeoutExpired:
        _terminate_process(process)
        try:
            code = process.wait(timeout=2)
        except TypeError:
            code = process.wait()
    return 0 if code is None else int(code)


def _max_file_size_bytes(options: DownloadOptions) -> int:
    try:
        max_mb = int(options.max_file_size_mb or 0)
    except (TypeError, ValueError):
        max_mb = 0
    return max(0, max_mb) * 1024 * 1024


def _output_exceeds_limit(output_path: str, options: DownloadOptions) -> bool:
    max_bytes = _max_file_size_bytes(options)
    if max_bytes <= 0 or not output_path:
        return False

    path = Path(output_path).expanduser()
    if not path.is_absolute():
        path = Path(options.output_dir).expanduser() / path
    try:
        if path.is_file():
            return path.stat().st_size > max_bytes
    except OSError:
        return False
    return False


def _prepare_output_dir(output_dir: str | Path) -> Path:
    if not str(output_dir).strip():
        raise ValueError("Chưa chọn thư mục lưu media.")
    path = Path(output_dir).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    resolved = path.resolve()
    if not resolved.is_dir():
        raise ValueError(f"Thư mục lưu media không hợp lệ: {resolved}")
    return resolved


def _validate_optional_file(value: str, label: str) -> Optional[Path]:
    if not value:
        return None
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Không tìm thấy file {label}: {path}")
    return path


def _missing_ytdlp_message() -> str:
    return (
        "Không tìm thấy yt-dlp. Hãy cài bằng `pip install yt-dlp`, "
        "hoặc đặt yt-dlp.exe vào thư mục tools/yt-dlp."
    )


def _emit(progress: Optional[ProgressCallback], message: str) -> None:
    if progress:
        progress(message)
