import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parent


def resolve_ffmpeg() -> Optional[str]:
    return _resolve_tool("ffmpeg")


def resolve_ffprobe() -> Optional[str]:
    return _resolve_tool("ffprobe")


def resolve_ytdlp() -> Optional[str]:
    return _resolve_tool("yt-dlp")


def resolve_gallerydl() -> Optional[str]:
    return _resolve_tool("gallery-dl")


def configure_environment() -> dict:
    """Resolve bundled tools and add their directories to the process environment PATH."""
    ffmpeg_path = resolve_ffmpeg()
    ffprobe_path = resolve_ffprobe()
    ytdlp_path = resolve_ytdlp()
    gallerydl_path = resolve_gallerydl()
    _add_tool_dirs_to_process_path(ffmpeg_path, ffprobe_path, ytdlp_path, gallerydl_path)
    return {
        "ffmpeg": ffmpeg_path or "",
        "ffprobe": ffprobe_path or "",
        "yt-dlp": ytdlp_path or "",
        "gallery-dl": gallerydl_path or "",
    }


def tool_first_line(executable: str) -> str:
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [executable, "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            timeout=8,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            return ""
        return (result.stdout or "").splitlines()[0].strip()
    except Exception:
        return ""


def get_ffmpeg_license_info(executable: Optional[str] = None) -> dict:
    """Inspects FFmpeg binary configuration to identify GPL vs LGPL licensing."""
    exe = executable or resolve_ffmpeg()
    if not exe:
        return {"available": False, "is_lgpl": False, "license": "Unknown", "details": "FFmpeg not found"}

    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [exe, "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            timeout=8,
            creationflags=creationflags,
        )
        output = result.stdout or ""
        is_gpl = "--enable-gpl" in output
        is_version3 = "--enable-version3" in output
        is_nonfree = "--enable-nonfree" in output

        if is_nonfree:
            lic = "Non-Free / Proprietary"
        elif is_gpl:
            lic = "GPL v3" if is_version3 else "GPL v2+"
        else:
            lic = "LGPL v3" if is_version3 else "LGPL v2.1+"

        return {
            "available": True,
            "executable": exe,
            "is_lgpl": not is_gpl and not is_nonfree,
            "license": lic,
            "details": output.splitlines()[0].strip() if output else ""
        }
    except Exception as e:
        return {"available": False, "is_lgpl": False, "license": "Unknown", "details": str(e)}


def is_ffmpeg_lgpl(executable: Optional[str] = None) -> bool:
    """Returns True if the resolved FFmpeg executable is compliant with LGPL (non-GPL)."""
    return get_ffmpeg_license_info(executable).get("is_lgpl", False)


def pymediainfo_available() -> bool:
    try:
        import pymediainfo

        return bool(pymediainfo.MediaInfo.can_parse())
    except Exception:
        return False


@lru_cache(maxsize=None)
def _resolve_tool(tool_name: str) -> Optional[str]:
    for candidate in _tool_candidates(tool_name):
        resolved = _existing_file(candidate)
        if resolved:
            return resolved
    return None


def _tool_candidates(tool_name: str) -> Iterable[str | Path | None]:
    yield _env_tool_candidate(tool_name)
    yield shutil.which(tool_name)

    for root in _known_roots(tool_name):
        for name in _executable_names(tool_name):
            yield root / name

    if tool_name == "ffmpeg":
        yield _imageio_ffmpeg_candidate()


def _env_tool_candidate(tool_name: str) -> Optional[str]:
    env_names = {
        "ffmpeg": ("CAPCUT_TOOL_FFMPEG", "FFMPEG_BINARY", "IMAGEIO_FFMPEG_EXE"),
        "ffprobe": ("CAPCUT_TOOL_FFPROBE", "FFPROBE_BINARY"),
        "yt-dlp": ("CAPCUT_TOOL_YTDLP", "YTDLP_BINARY", "YT_DLP_BINARY"),
        "gallery-dl": ("CAPCUT_TOOL_GALLERYDL", "GALLERYDL_BINARY", "GALLERY_DL_BINARY"),
    }.get(tool_name, ())
    for name in env_names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _known_roots(tool_name: str) -> Iterable[Path]:
    env_roots_by_tool = {
        "ffmpeg": ("CAPCUT_TOOL_FFMPEG_DIR", "FFMPEG_HOME", "FFMPEG_ROOT"),
        "ffprobe": ("CAPCUT_TOOL_FFMPEG_DIR", "FFMPEG_HOME", "FFMPEG_ROOT"),
        "yt-dlp": ("CAPCUT_TOOL_YTDLP_DIR", "YTDLP_HOME", "YTDLP_ROOT"),
        "gallery-dl": ("CAPCUT_TOOL_GALLERYDL_DIR", "GALLERYDL_HOME", "GALLERYDL_ROOT"),
    }
    env_roots = env_roots_by_tool.get(tool_name, ())
    for name in env_roots:
        value = os.environ.get(name)
        if value:
            path = Path(value).expanduser()
            yield path
            yield path / "bin"

    if tool_name == "yt-dlp":
        roots = [
            PROJECT_ROOT / "bin",
            PROJECT_ROOT / "tools",
            PROJECT_ROOT / "tools" / "yt-dlp",
            PROJECT_ROOT / "tools" / "ytdlp",
            PROJECT_ROOT / "yt-dlp",
        ]
    elif tool_name == "gallery-dl":
        roots = [
            PROJECT_ROOT / "bin",
            PROJECT_ROOT / "tools",
            PROJECT_ROOT / "tools" / "gallery-dl",
            PROJECT_ROOT / "tools" / "gallerydl",
            PROJECT_ROOT / "gallery-dl",
        ]
    else:
        roots = [
            PROJECT_ROOT / "bin",
            PROJECT_ROOT / "tools" / "ffmpeg",
            PROJECT_ROOT / "tools" / "ffmpeg" / "bin",
            PROJECT_ROOT / "ffmpeg",
            PROJECT_ROOT / "ffmpeg" / "bin",
        ]
    for root in roots:
        yield root

    portable_root = PROJECT_ROOT / "tools" / "ffmpeg"
    if portable_root.exists():
        for child in portable_root.iterdir():
            if child.is_dir():
                yield child
                yield child / "bin"


def _executable_names(tool_name: str) -> Iterable[str]:
    if tool_name in ("yt-dlp", "gallery-dl"):
        if os.name == "nt":
            yield f"{tool_name}.exe"
            yield f"{tool_name.replace('-', '_')}.exe"
        yield tool_name
        yield tool_name.replace('-', '_')
        return
    if os.name == "nt":
        yield f"{tool_name}.exe"
    yield tool_name


def _imageio_ffmpeg_candidate() -> Optional[str]:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _existing_file(candidate: str | Path | None) -> Optional[str]:
    if not candidate:
        return None
    try:
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path.resolve())
    except Exception:
        return None
    return None


def _add_tool_dirs_to_process_path(*tool_paths: Optional[str]) -> None:
    current = os.environ.get("PATH", "")
    current_parts = [part for part in current.split(os.pathsep) if part]
    current_norm = {str(Path(part)).lower() for part in current_parts}
    prepend = []
    for value in tool_paths:
        if not value:
            continue
        try:
            directory = str(Path(value).resolve().parent)
        except Exception:
            continue
        if directory.lower() not in current_norm:
            prepend.append(directory)
            current_norm.add(directory.lower())
    if prepend:
        os.environ["PATH"] = os.pathsep.join(prepend + current_parts)
