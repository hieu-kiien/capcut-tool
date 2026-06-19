from dataclasses import dataclass, field
from pathlib import Path
import os
import shutil
import time
from typing import Any, Dict, List, Union

from runtime_tools import pymediainfo_available, resolve_ffmpeg, resolve_ffprobe, tool_first_line
from app.path_validation import validate_project_name
import media_probe
from capcut_draft_creator import parse_srt

@dataclass
class PreflightIssue:
    code: str
    severity: str  # "error", "warning", "info"
    message: str
    suggestion: str = ""
    blocks_run: bool = False

@dataclass
class PreflightReport:
    issues: List[PreflightIssue] = field(default_factory=list)
    voice_duration_sec: float = 0.0
    media_count: int = 0
    invalid_media_count: int = 0
    srt_lines_count: int = 0
    free_space_gb: float = 0.0
    draft_action: str = "Tạo mới"
    can_run: bool = True

def run_preflight(config: Any) -> PreflightReport:
    """
    Perform all preflight checks based on the provided configuration.
    config can be a ProjectConfig instance or a dict.
    """
    def get_val(key: str, default: Any = "") -> Any:
        if hasattr(config, key):
            return getattr(config, key)
        elif isinstance(config, dict):
            return config.get(key, default)
        return default

    issues: List[PreflightIssue] = []
    voice_duration_sec = 0.0
    media_count = 0
    invalid_media_count = 0
    free_space_gb = 0.0
    draft_action = "Tạo mới"

    # 1. FFmpeg/ffprobe version & existence
    ffmpeg_bin = resolve_ffmpeg()
    if ffmpeg_bin:
        ffmpeg_ver = tool_first_line(ffmpeg_bin)
        ffmpeg_msg = f"FFmpeg có sẵn ({ffmpeg_ver or 'Không rõ phiên bản'})"
        issues.append(PreflightIssue(code="tools", severity="info", message=ffmpeg_msg))
    else:
        issues.append(PreflightIssue(
            code="tools",
            severity="error",
            message="Không tìm thấy FFmpeg trong hệ thống (cần thiết để xử lý âm thanh).",
            suggestion="Cài đặt FFmpeg hoặc sao chép ffmpeg.exe vào thư mục chứa công cụ.",
            blocks_run=True
        ))

    ffprobe_bin = resolve_ffprobe()
    if ffprobe_bin:
        ffprobe_ver = tool_first_line(ffprobe_bin)
        ffprobe_msg = f"ffprobe có sẵn ({ffprobe_ver or 'Không rõ phiên bản'})"
        issues.append(PreflightIssue(code="tools", severity="info", message=ffprobe_msg))
    elif not pymediainfo_available():
        issues.append(PreflightIssue(
            code="tools",
            severity="error",
            message="Cần cài đặt ffprobe hoặc thư viện MediaInfo để đọc thông tin video.",
            suggestion="Cài đặt ffprobe hoặc cài thư viện pymediainfo qua pip.",
            blocks_run=True
        ))

    # 2. Project name validation
    project_name = get_val("project_name")
    draft_root_str = get_val("draft_root")
    project_name_ok = False

    try:
        resolved_proj_path = validate_project_name(project_name, draft_root_str)
        project_name_ok = True
        if resolved_proj_path.exists():
            draft_action = "Ghi đè & Sao lưu cũ"
            issues.append(PreflightIssue(
                code="project_name",
                severity="info",
                message="Dự án đã tồn tại. Hệ thống sẽ tự động sao lưu và ghi đè khi chạy.",
                suggestion="Bạn có thể đổi tên dự án nếu muốn giữ bản hiện tại trong CapCut."
            ))
    except ValueError as exc:
        issues.append(PreflightIssue(
            code="project_name",
            severity="error",
            message=str(exc),
            blocks_run=True
        ))

    # 3. CapCut project root directory permission and space
    draft_root_ok = False
    if draft_root_str:
        draft_root = Path(draft_root_str).expanduser()
        if not draft_root.exists() or not draft_root.is_dir():
            issues.append(PreflightIssue(
                code="write",
                severity="error",
                message=f"Không tìm thấy thư mục lưu dự án CapCut: {draft_root}",
                blocks_run=True
            ))
        else:
            # Check draft root write permission
            try:
                test_file = draft_root / f".write_test_{int(time.time())}"
                test_file.write_text("test", encoding="utf-8")
                test_file.unlink()
                draft_root_ok = True
            except Exception as exc:
                issues.append(PreflightIssue(
                    code="write",
                    severity="error",
                    message=f"Không có quyền ghi vào thư mục lưu dự án CapCut: {exc}",
                    blocks_run=True
                ))

            # Check draft root free space
            try:
                total, used, free = shutil.disk_usage(draft_root)
                free_space_gb = free / (1024 ** 3)
                if free_space_gb < 2.0:
                    issues.append(PreflightIssue(
                        code="space",
                        severity="warning",
                        message=f"Dung lượng ổ đĩa chứa dự án CapCut sắp hết (chỉ còn {free_space_gb:.2f} GB).",
                        suggestion="Dọn dẹp bớt ổ đĩa để đảm bảo tạo dự án không bị gián đoạn."
                    ))
            except Exception:
                pass

    # 4. Voice path validation & duration
    voice_path_str = get_val("voice_path")
    voice_ok = False
    if voice_path_str:
        voice_path = Path(voice_path_str).expanduser()
        if not voice_path.exists() or not voice_path.is_file():
            issues.append(PreflightIssue(
                code="voice",
                severity="error",
                message=f"Không tìm thấy file giọng đọc: {voice_path}",
                blocks_run=True
            ))
        else:
            voice_asset = media_probe.probe_media(voice_path)
            if voice_asset.error:
                issues.append(PreflightIssue(
                    code="voice",
                    severity="error",
                    message=f"Không thể đọc thông tin tệp giọng đọc: {voice_asset.error}",
                    blocks_run=True
                ))
            else:
                voice_duration_sec = voice_asset.duration_us / 1e6
                voice_ok = True
    else:
        issues.append(PreflightIssue(
            code="voice",
            severity="error",
            message="Chưa cấu hình tệp giọng đọc chính.",
            blocks_run=True
        ))

    # 5. Media directory validation & file counts
    media_dir_str = get_val("media_dir")
    media_ok = False
    if media_dir_str:
        media_dir = Path(media_dir_str).expanduser()
        if not media_dir.exists() or not media_dir.is_dir():
            issues.append(PreflightIssue(
                code="media",
                severity="error",
                message=f"Không tìm thấy thư mục chứa video/hình nền: {media_dir}",
                blocks_run=True
            ))
        else:
            # Check media dir write permission (optional warning, but original did error)
            try:
                test_file = media_dir / f".write_test_{int(time.time())}"
                test_file.write_text("test", encoding="utf-8")
                test_file.unlink()
                media_ok = True
            except Exception as exc:
                issues.append(PreflightIssue(
                    code="media",
                    severity="error",
                    message=f"Không có quyền ghi vào thư mục video/hình nền: {exc}",
                    blocks_run=True
                ))

            # Scan and count media files
            if media_ok:
                extensions = media_probe.SUPPORTED_VISUAL_EXTENSIONS
                recursive_scan = get_val("recursive_scan", False)
                try:
                    iterator = media_dir.rglob("*") if recursive_scan else media_dir.iterdir()
                    for p in iterator:
                        if p.is_file() and p.suffix.lower() in extensions:
                            asset = media_probe.probe_media(p)
                            if asset.error:
                                invalid_media_count += 1
                            else:
                                media_count += 1
                except Exception as exc:
                    issues.append(PreflightIssue(
                        code="media",
                        severity="error",
                        message=f"Lỗi khi quét thư mục media nền: {exc}",
                        blocks_run=True
                    ))
                
                if media_count == 0:
                    issues.append(PreflightIssue(
                        code="media",
                        severity="error",
                        message="Không tìm thấy video hay ảnh nền nào khả dụng trong thư mục được chọn.",
                        blocks_run=True
                    ))
                if invalid_media_count > 0:
                    issues.append(PreflightIssue(
                        code="media",
                        severity="warning",
                        message=f"Tìm thấy {invalid_media_count} tệp media lỗi trong thư mục media.",
                        suggestion="Hệ thống sẽ bỏ qua các tệp lỗi này khi phân bổ video nền."
                    ))
    else:
        issues.append(PreflightIssue(
            code="media",
            severity="error",
            message="Chưa cấu hình thư mục chứa video/hình nền.",
            blocks_run=True
        ))

    # 6. Optional input fields validation
    bgm_path_str = get_val("bgm_path")
    if bgm_path_str:
        bgm_path = Path(bgm_path_str).expanduser()
        if not bgm_path.exists() or not bgm_path.is_file():
            issues.append(PreflightIssue(
                code="bgm",
                severity="error",
                message=f"Không tìm thấy file nhạc nền: {bgm_path}",
                blocks_run=True
            ))

    srt_path_str = get_val("srt_path")
    srt_lines_count = 0
    if srt_path_str:
        srt_path = Path(srt_path_str).expanduser()
        if not srt_path.exists() or not srt_path.is_file():
            issues.append(PreflightIssue(
                code="srt",
                severity="error",
                message=f"Không tìm thấy file phụ đề (SRT): {srt_path}",
                blocks_run=True
            ))
        else:
            # Parse SRT lines count & verify duration
            subtitles = parse_srt(str(srt_path))
            srt_lines_count = len(subtitles)
            if not subtitles:
                issues.append(PreflightIssue(
                    code="srt",
                    severity="error",
                    message="File phụ đề SRT rỗng hoặc không thể parse.",
                    blocks_run=True
                ))
            else:
                srt_duration_sec = (subtitles[-1]["start"] + subtitles[-1]["duration"]) / 1e6
                if voice_ok and srt_duration_sec > voice_duration_sec:
                    issues.append(PreflightIssue(
                        code="srt",
                        severity="warning",
                        message=f"Thời lượng phụ đề SRT ({srt_duration_sec:.1f}s) dài hơn giọng đọc ({voice_duration_sec:.1f}s).",
                        suggestion="Kiểm tra lại xem tệp SRT có bị lệch timeline hoặc dài hơn audio giọng đọc không."
                    ))
                
                # Check for short subtitles (duration < 0.8s = 800,000 microseconds)
                short_subs = [i + 1 for i, sub in enumerate(subtitles) if sub.get("duration", 0) < 800000]
                if short_subs:
                    issues.append(PreflightIssue(
                        code="srt_duration_too_short",
                        severity="warning",
                        message=f"Phát hiện {len(short_subs)} dòng phụ đề có thời lượng hiển thị dưới 0.8 giây (dòng: {', '.join(map(str, short_subs[:5]))}{'...' if len(short_subs) > 5 else ''}).",
                        suggestion="Thời lượng hiển thị dưới 0.8s quá nhanh để người xem kịp đọc. Cân nhắc gộp phụ đề hoặc kéo dài thời lượng của các câu này."
                    ))

    logo_path_str = get_val("logo_path")
    if not logo_path_str:
        issues.append(PreflightIssue(
            code="logo_missing",
            severity="warning",
            message="Dự án chưa cấu hình tệp logo thương hiệu (watermark).",
            suggestion="Bạn có thể thêm logo trong tab Hiệu ứng & Thương hiệu để tăng tính nhận diện thương hiệu."
        ))
    else:
        logo_path = Path(logo_path_str).expanduser()
        if not logo_path.exists() or not logo_path.is_file():
            issues.append(PreflightIssue(
                code="logo",
                severity="error",
                message=f"Không tìm thấy file logo: {logo_path}",
                blocks_run=True
            ))

    anim_path_str = get_val("anim_path")
    if anim_path_str:
        anim_path = Path(anim_path_str).expanduser()
        if not anim_path.exists() or not anim_path.is_file():
            issues.append(PreflightIssue(
                code="anim",
                severity="error",
                message=f"Không tìm thấy file hoạt ảnh: {anim_path}",
                blocks_run=True
            ))

    # Determine can_run status
    can_run = not any(issue.blocks_run for issue in issues)

    report = PreflightReport(
        issues=issues,
        voice_duration_sec=voice_duration_sec,
        media_count=media_count,
        invalid_media_count=invalid_media_count,
        srt_lines_count=srt_lines_count,
        free_space_gb=free_space_gb,
        draft_action=draft_action,
        can_run=can_run
    )
    return report
