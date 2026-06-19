import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from runtime_tools import (
    pymediainfo_available,
    resolve_ffmpeg,
    resolve_ffprobe,
    tool_first_line,
)


MAX_REPAIR_BACKUPS = 10


def _get_project_dir(draft_path: Path) -> Path:
    draft_path = Path(draft_path).resolve()
    if "Timelines" in draft_path.parts:
        idx = draft_path.parts.index("Timelines")
        return Path(*draft_path.parts[:idx])
    return draft_path.parent


def _add_backup_record(project_dir: Path, backup_path: Path, note: str = "") -> None:
    from core.db import Database
    try:
        import uuid
        conn = Database.get_connection()
        cursor = conn.cursor()
        backup_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT INTO backups (id, project_dir, backup_path, timestamp, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (backup_id, str(project_dir.resolve()), str(backup_path.resolve()), timestamp, note)
        )
        conn.commit()
    except Exception as e:
        print(f"Error adding backup record to SQLite: {e}")


def _remove_backup_record(backup_path: Path) -> None:
    from core.db import Database
    try:
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM backups WHERE backup_path = ?", (str(backup_path.resolve()),))
        conn.commit()
    except Exception as e:
        print(f"Error removing backup record from SQLite: {e}")


def _backup_and_write_text(path: Path, text: str, note: str = "") -> None:
    """Sao lưu file gốc (.bak) rồi ghi đè an toàn bằng temp + os.replace.

    Nếu không sao lưu được file gốc thì hủy để bảo vệ dữ liệu người dùng.
    """
    path = Path(path)
    if path.exists():
        import shutil
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = path.with_suffix(path.suffix + f".{ts}.bak")
        try:
            shutil.copy2(path, bak)
            # Ghi nhận vào SQLite
            proj_dir = _get_project_dir(path)
            _add_backup_record(proj_dir, bak, note)
        except Exception as exc:
            raise RuntimeError(
                f"Không thể tạo bản sao lưu cho '{path.name}' nên đã hủy để bảo vệ dữ liệu. "
                f"Vui lòng đóng CapCut rồi thử lại. Chi tiết: {exc}"
            ) from exc
        _prune_repair_backups(path)

    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def _prune_repair_backups(path: Path, keep: int = MAX_REPAIR_BACKUPS) -> None:
    try:
        prefix = path.name + "."
        backups = [
            f for f in path.parent.iterdir()
            if f.is_file() and f.name.startswith(prefix) and f.suffix == ".bak"
        ]
        if len(backups) <= keep:
            return
        backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        for old in backups[keep:]:
            try:
                old.unlink()
                # Xóa khỏi SQLite
                _remove_backup_record(old)
            except OSError:
                pass
    except OSError:
        pass


@dataclass
class DoctorIssue:
    severity: str
    code: str
    message: str
    path: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }


def issue(severity: str, code: str, message: str, path: str | Path = "") -> DoctorIssue:
    return DoctorIssue(severity, code, message, str(path) if path else "")


def check_ffmpeg_tools() -> List[DoctorIssue]:
    issues: List[DoctorIssue] = []
    tool_paths = {
        "ffmpeg": resolve_ffmpeg(),
        "ffprobe": resolve_ffprobe(),
    }
    for tool, path in tool_paths.items():
        if not path:
            if tool == "ffprobe" and pymediainfo_available():
                issues.append(
                    issue(
                        "info",
                        "ffprobe_missing_using_pymediainfo",
                        "ffprobe is not available, but MediaInfo fallback is available for media probing",
                    )
                )
            else:
                issues.append(issue("warn", f"{tool}_missing", f"{tool} is not available"))
            continue
        version = tool_first_line(path)
        if version:
            issues.append(issue("info", f"{tool}_found", version, path))
        else:
            issues.append(issue("warn", f"{tool}_version_failed", f"{tool} exists but version check failed", path))
    return issues


def check_srt_file(srt_path: str | Path, *, max_chars: int = 86) -> List[DoctorIssue]:
    path = Path(srt_path)
    issues: List[DoctorIssue] = []
    if not path.exists():
        return [issue("error", "srt_missing", "SRT file not found", path)]

    try:
        from capcut_draft_creator import parse_srt

        subtitles = parse_srt(str(path))
    except Exception as exc:
        return [issue("error", "srt_parse_failed", f"Cannot parse SRT: {exc}", path)]

    if not subtitles:
        issues.append(issue("warn", "srt_empty", "SRT has no subtitle entries", path))
        return issues

    previous_end = 0
    for idx, sub in enumerate(subtitles, start=1):
        start = int(sub.get("start", 0))
        duration = int(sub.get("duration", 0))
        end = start + duration
        text = str(sub.get("text", ""))
        if duration <= 0:
            issues.append(issue("error", "srt_bad_duration", f"Subtitle {idx} has non-positive duration", path))
        if start < previous_end:
            issues.append(issue("warn", "srt_overlap", f"Subtitle {idx} overlaps the previous one", path))
        if len(text) > max_chars:
            issues.append(issue("warn", "srt_line_long", f"Subtitle {idx} is longer than {max_chars} chars", path))
        previous_end = max(previous_end, end)
    return issues


def check_background_plan(background_data: Dict[str, Any]) -> List[DoctorIssue]:
    issues: List[DoctorIssue] = []
    segments = background_data.get("segments") or []
    if not segments:
        return [issue("warn", "background_segments_empty", "Background plan has no segments")]

    previous_end = 0
    for idx, segment in enumerate(segments, start=1):
        path = Path(str(segment.get("path", "")))
        start = int(segment.get("target_start_us", 0) or 0)
        duration = int(segment.get("target_duration_us", 0) or 0)
        if not path.exists():
            issues.append(issue("error", "background_media_missing", f"Background segment {idx} media is missing", path))
        if duration <= 0:
            issues.append(issue("error", "background_bad_duration", f"Background segment {idx} has invalid duration", path))
        if start < previous_end:
            issues.append(issue("warn", "background_overlap", f"Background segment {idx} overlaps the previous segment", path))
        previous_end = max(previous_end, start + duration)
    return issues


def check_draft_json(draft_path: str | Path) -> List[DoctorIssue]:
    path = Path(draft_path)
    issues: List[DoctorIssue] = []
    if not path.exists():
        return [issue("error", "draft_missing", "Draft JSON not found", path)]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [issue("error", "draft_json_invalid", f"Draft JSON cannot be read: {exc}", path)]

    materials = data.get("materials") or {}
    material_ids = _collect_material_ids(materials)
    issues.extend(_check_local_material_files(materials))

    tracks = data.get("tracks") or []
    if not tracks:
        issues.append(issue("warn", "draft_no_tracks", "Draft has no tracks", path))

    for track_idx, track in enumerate(tracks, start=1):
        track_name = str(track.get("name") or track.get("type") or track_idx)
        previous_end = 0
        segments = sorted(track.get("segments") or [], key=lambda seg: int((seg.get("target_timerange") or {}).get("start", 0) or 0))
        for seg_idx, seg in enumerate(segments, start=1):
            prefix = f"Track {track_name}, segment {seg_idx}"
            material_id = seg.get("material_id")
            if material_id and material_id not in material_ids:
                issues.append(issue("error", "draft_material_ref_missing", f"{prefix} references missing material {material_id}", path))

            target = seg.get("target_timerange") or {}
            start = int(target.get("start", 0) or 0)
            duration = int(target.get("duration", 0) or 0)
            end = start + duration
            if duration <= 0:
                issues.append(issue("error", "draft_bad_target_duration", f"{prefix} has invalid target duration", path))
            if start < previous_end:
                issues.append(issue("warn", "draft_segment_overlap", f"{prefix} overlaps the previous segment", path))
            previous_end = max(previous_end, end)

            source = seg.get("source_timerange")
            if source:
                source_duration = int(source.get("duration", 0) or 0)
                if source_duration <= 0:
                    issues.append(issue("error", "draft_bad_source_duration", f"{prefix} has invalid source duration", path))

            for ref in seg.get("extra_material_refs") or []:
                if ref and ref not in material_ids:
                    issues.append(issue("warn", "draft_extra_ref_missing", f"{prefix} extra material ref is missing: {ref}", path))

    return issues


def summarize_issues(issues: Iterable[DoctorIssue]) -> Dict[str, int]:
    summary = {"error": 0, "warn": 0, "info": 0}
    for item in issues:
        summary[item.severity] = summary.get(item.severity, 0) + 1
    return summary


def _collect_material_ids(materials: Dict[str, Any]) -> set:
    ids = set()
    for value in materials.values():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("id"):
                    ids.add(item["id"])
    return ids


def _check_local_material_files(materials: Dict[str, Any]) -> List[DoctorIssue]:
    issues: List[DoctorIssue] = []
    for key in ("videos", "audios"):
        for item in materials.get(key) or []:
            path_value = item.get("path")
            if not path_value:
                continue
            path = Path(path_value)
            if not path.exists():
                issues.append(issue("error", "draft_local_file_missing", f"Local {key[:-1]} file is missing", path))
    return issues


def repair_draft_project(project_dir: str | Path, *, media_dirs: List[str | Path] = None) -> List[str]:
    import os
    import time
    from capcut_keyframe_tool import resolve_project_draft_paths
    
    project_dir = Path(project_dir).resolve()
    if not project_dir.exists() or not project_dir.is_dir():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    actions_taken = []

    # 1. Repair draft_meta_info.json
    meta_path = project_dir / "draft_meta_info.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            
            # Normalize fold path (always forward slashes)
            fold_path = str(project_dir).replace("\\", "/")
            # Normalize root path (backslashes on Windows)
            root_path = str(project_dir.parent)
            if os.name == "nt":
                root_path = root_path.replace("/", "\\")
            
            modified = False
            if meta.get("draft_fold_path") != fold_path:
                meta["draft_fold_path"] = fold_path
                modified = True
            if meta.get("draft_root_path") != root_path:
                meta["draft_root_path"] = root_path
                modified = True
                
            if modified:
                _backup_and_write_text(meta_path, json.dumps(meta, ensure_ascii=False, indent="\t"), "Đồng bộ đường dẫn cấu hình draft_meta_info.json")
                actions_taken.append("Đã sửa đổi đường dẫn thư mục gốc trong draft_meta_info.json cho khớp vị trí hiện tại.")
        except Exception as e:
            actions_taken.append(f"Không thể sửa draft_meta_info.json: {e}")

    # 2. Repair draft_content.json (both primary and mirrors)
    primary_draft, mirrors = resolve_project_draft_paths(project_dir)
    if not primary_draft.exists():
        raise FileNotFoundError(f"Primary draft file not found: {primary_draft}")

    # Resolve platform config from other drafts
    platform_info = _detect_local_platform_info(project_dir.parent, exclude_name=project_dir.name)

    all_drafts = [primary_draft] + mirrors
    for draft_path in all_drafts:
        try:
            data = json.loads(draft_path.read_text(encoding="utf-8"))
            modified = False

            # Update platform info
            if platform_info:
                platform_modified = False
                if "platform" not in data or data["platform"] != platform_info["platform"]:
                    data["platform"] = platform_info["platform"]
                    platform_modified = True
                if "last_modified_platform" not in data or data["last_modified_platform"] != platform_info["last_modified_platform"]:
                    data["last_modified_platform"] = platform_info["last_modified_platform"]
                    platform_modified = True
                if platform_modified:
                    modified = True
                    actions_taken.append(f"Đã đồng bộ thông tin phiên bản phần mềm ({platform_info['platform'].get('app_version')}) của máy tính vào tệp nháp ({draft_path.name}).")

            # Relink files
            materials = data.get("materials") or {}
            for key in ("videos", "audios"):
                for item in materials.get(key) or []:
                    path_val = item.get("path")
                    if not path_val:
                        continue
                    path_obj = Path(path_val)
                    if not path_obj.exists():
                        # File is missing! Let's search for it.
                        matches = _find_files_by_name(path_obj.name, media_dirs or [])
                        # Lọc trùng theo đường dẫn thực để gộp các bản giống nhau
                        unique = []
                        seen_keys = set()
                        for cand in matches:
                            try:
                                k = (cand.name.lower(), cand.stat().st_size)
                            except OSError:
                                k = (str(cand).lower(), -1)
                            if k not in seen_keys:
                                seen_keys.add(k)
                                unique.append(cand)
                        
                        if len(unique) > 1:
                            # Tối ưu hóa: Lọc bằng cách so sánh thông tin metadata của dự án nháp
                            filtered_candidates = []
                            target_duration = item.get("duration", 0)
                            target_width = item.get("width", 0)
                            target_height = item.get("height", 0)
                            target_type = item.get("type")  # "video" hoặc "photo" (cho videos)
                            
                            from media_probe import probe_media, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, AUDIO_EXTENSIONS
                            
                            for cand in unique:
                                try:
                                    ext = cand.suffix.lower()
                                    # 1. Kiểm tra loại phương tiện thô qua extension trước
                                    if key == "videos":
                                        if target_type == "photo" and ext not in IMAGE_EXTENSIONS:
                                            continue
                                        if target_type == "video" and ext not in VIDEO_EXTENSIONS:
                                            continue
                                    elif key == "audios":
                                        if ext not in AUDIO_EXTENSIONS:
                                            continue
                                            
                                    # 2. Probe chi tiết để so sánh duration, width, height
                                    asset = probe_media(cand)
                                    if asset.error:
                                        continue
                                        
                                    # So sánh duration (với sai số cho phép 1.0 giây = 1,000,000 us)
                                    if target_duration > 0 and target_type != "photo":
                                        diff = abs(asset.duration_us - target_duration)
                                        if diff > 1000000:  # lệch quá 1 giây
                                            continue
                                            
                                    # So sánh độ phân giải nếu có (chỉ cho video/photo)
                                    if key == "videos" and target_width > 0 and target_height > 0:
                                        if asset.width != target_width or asset.height != target_height:
                                            continue
                                            
                                    filtered_candidates.append(cand)
                                except Exception:
                                    pass
                                    
                            if len(filtered_candidates) == 1:
                                unique = filtered_candidates

                        if len(unique) == 1:
                            found_path = unique[0]
                            item["path"] = str(found_path)
                            # Update category to local if needed
                            item["category_name"] = "local"
                            modified = True
                            actions_taken.append(f"Đã tìm thấy file '{path_obj.name}' tại '{found_path.parent}' và liên kết lại.")
                        elif len(unique) > 1:
                            # Nhiều file trùng tên nhưng khác nhau -> KHÔNG tự đoán để tránh gắn nhầm cảnh
                            locs = ", ".join(str(p.parent) for p in unique[:5])
                            actions_taken.append(
                                f"CẢNH BÁO: Có {len(unique)} file tên '{path_obj.name}' khác nhau ({locs}). "
                                f"Không tự liên kết để tránh chọn nhầm — vui lòng sửa thủ công."
                            )
                        else:
                            actions_taken.append(f"CẢNH BÁO: Không tìm thấy file '{path_obj.name}' trên máy tính để liên kết lại.")

            if modified:
                data['update_time'] = int(time.time() * 1000)
                # Write back safely (backup + atomic replace)
                _backup_and_write_text(draft_path, json.dumps(data, ensure_ascii=False, separators=(',', ':')), "Tự động sửa lỗi dự án (Draft Doctor)")
                actions_taken.append(f"Đã cập nhật cấu trúc và lưu tệp nháp thành công: {draft_path.name}")
                
        except Exception as e:
            actions_taken.append(f"Lỗi khi sửa file {draft_path.name}: {e}")

    return actions_taken


def _find_files_by_name(filename: str, search_dirs: List[str | Path]) -> List[Path]:
    """Tìm TẤT CẢ file khớp tên trong các thư mục (đệ quy), hỗ trợ không phân biệt hoa thường và các phần mở rộng tương đương."""
    from pathlib import Path
    results: List[Path] = []
    
    filename_lower = filename.lower()
    base_name = Path(filename).stem.lower()
    ext = Path(filename).suffix.lower()
    
    # Các định dạng mở rộng tương đương
    ext_aliases = {
        ".jpeg": [".jpg", ".jpeg"],
        ".jpg": [".jpg", ".jpeg"],
        ".tiff": [".tif", ".tiff"],
        ".tif": [".tif", ".tiff"],
    }
    allowed_exts = ext_aliases.get(ext, [ext])
    
    for directory in search_dirs:
        if not directory:
            continue
        try:
            dir_path = Path(directory).resolve()
            if not dir_path.exists():
                continue
            
            # Quét đệ quy
            for match in dir_path.rglob("*"):
                if match.is_file():
                    m_name_lower = match.name.lower()
                    m_stem_lower = match.stem.lower()
                    m_ext_lower = match.suffix.lower()
                    
                    if m_name_lower == filename_lower:
                        results.append(match)
                    elif m_stem_lower == base_name and m_ext_lower in allowed_exts:
                        results.append(match)
        except Exception:
            pass
            
    # Lọc trùng
    seen = set()
    unique_results = []
    for r in results:
        r_resolved = str(r.resolve())
        if r_resolved not in seen:
            seen.add(r_resolved)
            unique_results.append(r)
            
    return unique_results


def restore_draft_backup(draft_path: str | Path, backup_path: str | Path) -> None:
    """Khôi phục tệp nháp từ bản sao lưu và đồng bộ sang các tệp gương (mirrors)."""
    import shutil
    import capcut_keyframe_tool as kt
    
    draft_path = Path(draft_path).resolve()
    backup_path = Path(backup_path).resolve()
    
    if not backup_path.exists():
        raise FileNotFoundError(f"Không tìm thấy bản sao lưu: {backup_path}")
        
    # Tạo bản sao lưu của bản nháp hiện tại trước khi đè (để có thể hoàn tác nếu cần)
    if draft_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        curr_bak = draft_path.with_suffix(draft_path.suffix + f".{ts}.pre_restore.bak")
        shutil.copy2(draft_path, curr_bak)
        proj_dir = _get_project_dir(draft_path)
        _add_backup_record(proj_dir, curr_bak, f"Sao lưu tự động trước khi khôi phục từ {backup_path.name}")
        
    # Sao chép đè
    shutil.copy2(backup_path, draft_path)
    
    # Đồng bộ sang các file mirror
    proj_dir = _get_project_dir(draft_path)
    _, mirrors = kt.resolve_project_draft_paths(proj_dir)
    if mirrors:
        kt.mirror_draft_file(draft_path, mirrors)


def clean_project_backups(draft_path: str | Path, keep_days: int) -> tuple[int, int]:
    """Dọn dẹp các bản sao lưu cũ hơn keep_days ngày của dự án nháp.
    
    Trả về: (số file đã xóa, số file giữ lại)
    """
    import time as _time
    from core.db import Database
    
    draft_path = Path(draft_path).resolve()
    draft_dir = draft_path.parent
    cutoff = _time.time() - keep_days * 86400
    
    deleted = 0
    kept = 0
    
    try:
        conn = Database.get_connection()
        cursor = conn.cursor()
        
        # Quét các file .bak thực tế trên đĩa
        if draft_dir.exists():
            for f in list(draft_dir.iterdir()):
                if f.is_file() and f.name.startswith(draft_path.name) and f.suffix == '.bak':
                    if f.stat().st_mtime < cutoff:
                        path_str = str(f.resolve())
                        f.unlink()
                        cursor.execute("DELETE FROM backups WHERE backup_path = ?", (path_str,))
                        deleted += 1
                    else:
                        kept += 1
            conn.commit()
    except Exception as e:
        print(f"Error in clean_project_backups: {e}")
        raise
        
    return deleted, kept


def _detect_local_platform_info(draft_root: Path, exclude_name: str = None) -> Optional[dict]:
    # Try to scan siblings of our draft to get a working platform block
    try:
        for child in draft_root.iterdir():
            if child.is_dir() and not child.name.startswith('.') and (exclude_name is None or child.name != exclude_name):
                p1 = child / "draft_content.json"
                if p1.exists():
                    try:
                        data = json.loads(p1.read_text(encoding="utf-8"))
                        plat = data.get("platform")
                        if plat and "app_source" in plat:
                            return {
                                "platform": plat,
                                "last_modified_platform": data.get("last_modified_platform") or plat
                            }
                    except Exception:
                        pass
                
                timelines_dir = child / "Timelines"
                if timelines_dir.exists() and timelines_dir.is_dir():
                    for sub in timelines_dir.iterdir():
                        if sub.is_dir():
                            p2 = sub / "draft_content.json"
                            if p2.exists():
                                try:
                                    data = json.loads(p2.read_text(encoding="utf-8"))
                                    plat = data.get("platform")
                                    if plat and "app_source" in plat:
                                        return {
                                            "platform": plat,
                                            "last_modified_platform": data.get("last_modified_platform") or plat
                                        }
                                except Exception:
                                    pass
    except Exception:
        pass

    # Default fallback to cc version 8.7.0 on Windows
    return {
        "platform": {
            "app_id": 359289,
            "app_source": "cc",
            "app_version": "8.7.0",
            "os": "windows",
            "os_version": "",
            "device_id": "",
            "hard_disk_id": "",
            "mac_address": ""
        },
        "last_modified_platform": {
            "app_id": 359289,
            "app_source": "cc",
            "app_version": "8.7.0",
            "os": "windows",
            "os_version": "",
            "device_id": "",
            "hard_disk_id": "",
            "mac_address": ""
        }
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Basic doctor checks for Long Story and CapCut drafts.")
    parser.add_argument("--draft")
    parser.add_argument("--srt")
    parser.add_argument("--max-subtitle-chars", type=int, default=86)
    parser.add_argument("--ffmpeg", action="store_true")
    args = parser.parse_args()

    all_issues: List[DoctorIssue] = []
    if args.ffmpeg:
        all_issues.extend(check_ffmpeg_tools())
    if args.srt:
        all_issues.extend(check_srt_file(args.srt, max_chars=args.max_subtitle_chars))
    if args.draft:
        all_issues.extend(check_draft_json(args.draft))

    for item in all_issues:
        where = f" | {item.path}" if item.path else ""
        print(f"[{item.severity.upper()}] {item.code}: {item.message}{where}")
    print("Summary:", summarize_issues(all_issues))
