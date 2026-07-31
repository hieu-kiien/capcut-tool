import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import pyJianYingDraft as draft
# Text classes from pyJianYingDraft removed since we don't write subtitles.
from video_mixer import BackgroundSegment
from core.effects import apply_karaoke_to_segment

WRITING_MARKER_NAME = ".capcut_tool_writing"
_IMAGE_OVERLAY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_VIDEO_OVERLAY_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


class DraftGuard:
    def __init__(self, draft_root, project_name, resolved_draft_path: Optional[Path] = None):
        self.draft_root = Path(draft_root).resolve()
        self.project_name = project_name
        self.resolved_draft_path = Path(resolved_draft_path).resolve() if resolved_draft_path else None
        self.created_this_run = False
        self.backup_path = None
        self.partial_path = None

    @property
    def marker_path(self) -> Optional[Path]:
        if not self.resolved_draft_path:
            return None
        return self.resolved_draft_path / WRITING_MARKER_NAME

    def mark_writing(self) -> None:
        marker_path = self.marker_path
        if not marker_path:
            return
        marker_path.touch()
        self.created_this_run = True

    def clear_marker(self) -> None:
        marker_path = self.marker_path
        if marker_path and marker_path.exists():
            marker_path.unlink()

    def has_marker(self) -> bool:
        marker_path = self.marker_path
        return bool(marker_path and marker_path.exists())

    def next_partial_path(self) -> Path:
        if not self.resolved_draft_path:
            raise ValueError("Không thể xác định thư mục draft để lưu partial.")
        import time as _time

        timestamp = _time.strftime("%Y%m%d_%H%M%S")
        base = self.resolved_draft_path.with_name(f"_partial_{self.project_name}_{timestamp}")
        candidate = base
        counter = 1
        while candidate.exists():
            candidate = base.with_name(f"{base.name}_{counter}")
            counter += 1
        return candidate


def handle_partial_draft(func):
    import shutil as _shutil
    from contextlib import nullcontext
    from functools import wraps
    @wraps(func)
    def wrapper(draft_root, project_name, *args, **kwargs):
        try:
            from core.path_validation import validate_project_name
            resolved_draft_path = validate_project_name(project_name, draft_root)
        except ValueError:
            resolved_draft_path = None

        guard = DraftGuard(draft_root, project_name, resolved_draft_path)
        kwargs['guard'] = guard
        lock_context = nullcontext()
        if resolved_draft_path:
            from app.draft_lock import locked_draft
            lock_context = locked_draft(resolved_draft_path)
        try:
            with lock_context:
                res = func(draft_root, project_name, *args, **kwargs)
            try:
                guard.clear_marker()
            except Exception as marker_err:
                print(f"[DRAFT CREATOR] Warning: Could not remove marker: {marker_err}")
            
            if isinstance(res, dict):
                res["backup_path"] = str(guard.backup_path) if guard.backup_path else None
            elif isinstance(res, tuple):
                res = res + (str(guard.backup_path) if guard.backup_path else None,)
            return res
        except Exception as e:
            try:
                if guard.has_marker() and guard.resolved_draft_path and guard.resolved_draft_path.exists():
                    partial_path = guard.next_partial_path()
                    _shutil.move(str(guard.resolved_draft_path), str(partial_path))
                    moved_marker = partial_path / WRITING_MARKER_NAME
                    if moved_marker.exists():
                        moved_marker.unlink()
                    guard.partial_path = partial_path
                    e.partial_path = str(partial_path)
                    print(f"[DRAFT CREATOR] Cleaned up partial draft folder to {partial_path.name}")
                if guard.backup_path:
                    e.backup_path = str(guard.backup_path)
            except Exception as cleanup_err:
                print(f"[DRAFT CREATOR] Warning: Could not clean up partial draft folder: {cleanup_err}")
            raise e
    return wrapper


def auto_wrap_subtitle(text: str, max_words: int = 8) -> str:
    """
    Wrap subtitle text containing > max_words into two lines (\n)
    for clean 9:16 vertical video framing.
    """
    if not text:
        return ""
    lines = text.split("\n")
    wrapped_lines = []
    for line in lines:
        words = line.split()
        if len(words) > max_words:
            mid = len(words) // 2
            wrapped_lines.append(" ".join(words[:mid]) + "\n" + " ".join(words[mid:]))
        else:
            wrapped_lines.append(line)
    return "\n".join(wrapped_lines)


def calculate_bgm_volume(voice_path: str = None, voice_duration: float = 0.0, default_volume: float = 1.0) -> float:
    """
    Calculates BGM volume with Audio Auto-Ducking (20%).
    Scales BGM volume factor to 0.20 (20%) when voice narration is present.
    """
    from video_mixer import calculate_bgm_volume as _calc
    return _calc(voice_path, voice_duration, default_volume)


# SRT parsing helper methods.
def parse_srt(srt_path: str) -> list:
    """
    Parses an SRT file and returns a list of dictionaries with:
      - 'start': start time in microseconds (int)
      - 'duration': duration in microseconds (int)
      - 'text': subtitle text (str)
    """
    import re
    from pathlib import Path
    
    path = Path(srt_path)
    if not path.exists():
        return []
        
    try:
        content = path.read_text(encoding="utf-8-sig")
    except Exception:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return []
    
    # Chuẩn hóa line endings
    content = content.replace("\r\n", "\n")
    
    # Pattern khớp các block SRT chuẩn
    pattern = re.compile(
        r"(\d+)\s*\n"
        r"(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})\s*\n"
        r"([\s\S]*?)(?=\n\s*\n|\n\s*$|$)"
    )
    
    results = []
    for match in pattern.finditer(content):
        sh, sm, ss, sms = map(int, match.group(2, 3, 4, 5))
        eh, em, es, ems = map(int, match.group(6, 7, 8, 9))

        start_us = (((sh * 3600 + sm * 60 + ss) * 1000) + sms) * 1000
        end_us = (((eh * 3600 + em * 60 + es) * 1000) + ems) * 1000
        duration_us = end_us - start_us

        # Bỏ qua block có thời lượng <= 0 (end <= start) để tránh phụ đề lỗi
        if duration_us <= 0:
            continue

        raw_text = match.group(10).strip()
        if not raw_text:
            continue
            
        # Dynamic Caption Auto-Wrap: break any sentence > 8 words into two lines (\n) for 9:16 framing
        text = auto_wrap_subtitle(raw_text, max_words=8)

        results.append({
            "start": start_us,
            "end": end_us,
            "duration": duration_us,
            "text": text
        })

    # Sắp xếp theo thời điểm bắt đầu để đảm bảo thứ tự đơn điệu cho việc căn media
    results.sort(key=lambda s: s["start"])
    return results


def _prepare_overlay_asset(
    source: str | Path,
    *,
    bg_mode: str,
    output_dir: Path,
    prefix: str,
    similarity: float = 0.18,
    blend: float = 0.08,
    cancel_check: Any = None,
) -> Path:
    from core.chroma import prepare_overlay_asset
    return prepare_overlay_asset(source, bg_mode, output_dir, prefix, similarity, blend, cancel_check=cancel_check)

@handle_partial_draft
def create_local_draft(
    draft_root: Path,
    project_name: str,
    media_paths: list,
    audio_path: str = None,
    srt_path: str = None,
    canvas_width: int = 1080,
    canvas_height: int = 1920,
    subtitle_font_size: float = 6.0,
    subtitle_color: tuple = (1.0, 1.0, 1.0),
    subtitle_bold: bool = True,
    cancel_check = None,
    guard = None,
    compact: bool = False,
):
    """
    Creates a brand new CapCut project, adds media files sequentially,
    optionally adds a background audio track, and optionally inserts subtitle tracks.
    All paths should be local.
    """
    import time as _time
    import shutil as _shutil
    from core.path_validation import validate_project_name
    from app.job_control import raise_if_cancelled

    # Validate project name and safety
    resolved_draft_path = validate_project_name(project_name, draft_root)
    raise_if_cancelled(cancel_check)

    # 1. Initialize draft folder manager
    draft_folder = draft.DraftFolder(str(draft_root))
    
    # Backup old draft if it exists to prevent silent deletion
    if resolved_draft_path.exists():
        timestamp = _time.strftime("%Y%m%d_%H%M%S")
        backup_path = resolved_draft_path.with_name(f"{resolved_draft_path.name}_bak_{timestamp}")
        counter = 1
        while backup_path.exists():
            backup_path = resolved_draft_path.with_name(f"{resolved_draft_path.name}_bak_{timestamp}_{counter}")
            counter += 1
        try:
            _shutil.move(str(resolved_draft_path), str(backup_path))
            print(f"[DRAFT CREATOR] Backed up existing draft folder to {backup_path.name}")
            if guard:
                guard.backup_path = backup_path
        except Exception as e:
            raise RuntimeError(f"Không thể sao lưu thư mục dự án cũ: {e}. Vui lòng đóng CapCut nếu đang mở.")

    # 2. Create draft
    script = draft_folder.create_draft(project_name, width=canvas_width, height=canvas_height, allow_replace=True)
    script.dual_file_compatibility = True
    
    try:
        if guard:
            guard.mark_writing()
        else:
            (resolved_draft_path / WRITING_MARKER_NAME).touch()
    except Exception as marker_err:
        print(f"[DRAFT CREATOR] Warning: Could not create marker file: {marker_err}")

    raise_if_cancelled(cancel_check)
    
    # 3. Add a video track for our media files
    video_track_name = "main_video_track"
    script.add_track(track_type=draft.TrackType.video, track_name=video_track_name, relative_index=0)
    
    # 4. If we have an audio file, add an audio track and add the audio material
    audio_duration_us = 0
    if audio_path and os.path.exists(audio_path):
        audio_material = draft.AudioMaterial(audio_path)
        audio_duration_us = audio_material.duration
        
        audio_track_name = "background_music_track"
        script.add_track(track_type=draft.TrackType.audio, track_name=audio_track_name, relative_index=0)
        
        # Add audio segment starting at 0
        audio_segment = draft.AudioSegment(
            material=audio_material,
            target_timerange=draft.trange(start=0, duration=audio_duration_us),
            source_timerange=draft.trange(start=0, duration=audio_duration_us)
        )
        script.add_segment(audio_segment, audio_track_name)

    raise_if_cancelled(cancel_check)
        
    # 5. Add Subtitle Track if SRT file is provided
    subtitles = []
    if srt_path and os.path.exists(srt_path):
        subtitles = parse_srt(srt_path)
        if not subtitles:
            print(f"[DRAFT CREATOR] WARNING: SRT file '{srt_path}' is empty or failed to parse. Falling back to even distribution mode.")
        
    if subtitles:
        text_track_name = "subtitles_track"
        script.add_track(track_type=draft.TrackType.text, track_name=text_track_name, relative_index=0)
        
        style = draft.TextStyle(
            size=subtitle_font_size,
            bold=subtitle_bold,
            color=subtitle_color,
            auto_wrapping=True
        )
        border = draft.TextBorder(color=(0.0, 0.0, 0.0), width=40.0) # Black outline
        shadow = draft.TextShadow(color=(0.0, 0.0, 0.0), alpha=0.8, distance=5.0) # Soft shadow
        
        for sub in subtitles:
            raise_if_cancelled(cancel_check)
            # Avoid inserting 0-duration or negative segments
            if sub["duration"] <= 0:
                continue
                
            text_segment = draft.TextSegment(
                text=sub["text"],
                timerange=draft.trange(start=sub["start"], duration=sub["duration"]),
                style=style,
                border=border,
                shadow=shadow
            )
            script.add_segment(text_segment, text_track_name)
        print(f"[DRAFT CREATOR] Added {len(subtitles)} subtitles from SRT file.")
        
    # 6. Process media files (images or videos)
    valid_media_paths = [p for p in media_paths if os.path.exists(p)]
    if not valid_media_paths:
        raise_if_cancelled(cancel_check)
        script.save(compact=compact)
        return 0, audio_duration_us
        
    if subtitles:
        # Paragraph-based matching for storytelling
        print(f"[DRAFT CREATOR] Aligning {len(valid_media_paths)} media files to {len(subtitles)} subtitle scenes...")
        for idx, sub in enumerate(subtitles):
            raise_if_cancelled(cancel_check)
            start_time = sub["start"]
            
            # The segment covers from the start of this subtitle until the start of the next subtitle
            if idx < len(subtitles) - 1:
                end_time = subtitles[idx+1]["start"]
            else:
                end_time = max(audio_duration_us, sub["start"] + sub["duration"])
                
            target_duration = end_time - start_time
            if target_duration <= 0:
                target_duration = 1000000
                
            # Map index to media files circularly
            m_path = valid_media_paths[idx % len(valid_media_paths)]
            video_material = draft.VideoMaterial(m_path)
            
            # Clip source if it's a video shorter than target duration
            source_duration = min(video_material.duration, target_duration)
            if source_duration <= 0:
                source_duration = 1000000
                
            clip_settings = draft.ClipSettings(
                alpha=1.0,
                scale_x=1.0,
                scale_y=1.0,
                transform_x=0.0,
                transform_y=0.0
            )
            
            video_segment = draft.VideoSegment(
                material=video_material,
                target_timerange=draft.trange(start=start_time, duration=target_duration),
                source_timerange=draft.trange(start=0, duration=source_duration),
                speed=1.0,
                clip_settings=clip_settings
            )
            script.add_segment(video_segment, video_track_name)

        raise_if_cancelled(cancel_check)
        script.save(compact=compact)
        total_len = max(subtitles[-1]["start"] + subtitles[-1]["duration"], audio_duration_us)
        return len(subtitles), total_len
        
    else:
        # Fallback to even distribution along the timeline
        if audio_duration_us > 0:
            segment_duration_us = int(audio_duration_us / len(valid_media_paths))
        else:
            segment_duration_us = 3000000 # 3 seconds
            
        current_time_us = 0
        for idx, m_path in enumerate(valid_media_paths):
            raise_if_cancelled(cancel_check)
            video_material = draft.VideoMaterial(m_path)
            
            start_time = current_time_us
            if idx == len(valid_media_paths) - 1 and audio_duration_us > 0:
                duration = audio_duration_us - start_time
            else:
                duration = segment_duration_us
                
            if duration <= 0:
                duration = 1000000
                
            if video_material.material_type == "video" and video_material.duration < duration:
                target_duration = video_material.duration
            else:
                target_duration = duration
                
            source_duration = min(video_material.duration, target_duration)
            if source_duration <= 0:
                source_duration = 1000000
                
            clip_settings = draft.ClipSettings(
                alpha=1.0,
                scale_x=1.0,
                scale_y=1.0,
                transform_x=0.0,
                transform_y=0.0
            )
            
            video_segment = draft.VideoSegment(
                material=video_material,
                target_timerange=draft.trange(start=start_time, duration=target_duration),
                source_timerange=draft.trange(start=0, duration=source_duration),
                speed=1.0,
                clip_settings=clip_settings
            )
            
            script.add_segment(video_segment, video_track_name)
            current_time_us += target_duration

        raise_if_cancelled(cancel_check)
        script.save(compact=compact)
        return len(valid_media_paths), max(current_time_us, audio_duration_us)


@handle_partial_draft
def create_draft_from_files(
    draft_root: Path,
    project_name: str,
    voice_path: str | Path,
    background_segments: List[BackgroundSegment],
    *,
    bgm_path: Optional[str | Path] = None,
    canvas_width: int = 1080,
    canvas_height: int = 1920,
    allow_replace: bool = True,
    short_video_mode: str = "stretch",
    srt_path: Optional[str | Path] = None,
    intro_path: Optional[str | Path] = None,
    outro_path: Optional[str | Path] = None,
    logo_path: Optional[str | Path] = None,
    logo_position: str = "top_right",
    logo_scale: float = 15.0,
    logo_opacity: float = 1.0,
    logo_bg_mode: str = "none",
    anim_path: Optional[str | Path] = None,
    anim_position: str = "bottom_center",
    anim_scale: float = 30.0,
    anim_timing: str = "end",
    anim_bg_mode: str = "none",
    subtitle_font_size: float = 6.0,
    subtitle_color: tuple = (1.0, 1.0, 1.0),
    subtitle_bold: bool = True,
    subtitle_outline_width: float = 40.0,
    subtitle_shadow_alpha: float = 0.8,
    subtitle_shadow_distance: float = 5.0,
    subtitle_karaoke: bool = False,
    chroma_threshold: float = 32.0,
    chroma_shadow: float = 2.0,
    cancel_check = None,
    guard = None,
    compact: bool = False,
) -> Dict[str, Any]:
    """
    Create a CapCut draft from pre-prepared voice and background segments.
    """
    import time as _time
    import shutil as _shutil
    from core.path_validation import validate_project_name
    from app.job_control import raise_if_cancelled

    # Validate project name and safety
    resolved_draft_path = validate_project_name(project_name, draft_root)
    raise_if_cancelled(cancel_check)

    draft_folder = draft.DraftFolder(str(draft_root))
    
    # Backup old draft if it exists and replace is allowed
    if resolved_draft_path.exists() and allow_replace:
        timestamp = _time.strftime("%Y%m%d_%H%M%S")
        backup_path = resolved_draft_path.with_name(f"{resolved_draft_path.name}_bak_{timestamp}")
        counter = 1
        while backup_path.exists():
            backup_path = resolved_draft_path.with_name(f"{resolved_draft_path.name}_bak_{timestamp}_{counter}")
            counter += 1
        try:
            _shutil.move(str(resolved_draft_path), str(backup_path))
            print(f"[DRAFT CREATOR] Backed up existing draft folder to {backup_path.name}")
            if guard:
                guard.backup_path = backup_path
        except Exception as e:
            raise RuntimeError(f"Không thể sao lưu thư mục dự án cũ: {e}. Vui lòng đóng CapCut nếu đang mở.")

    script = draft_folder.create_draft(project_name, width=canvas_width, height=canvas_height, allow_replace=allow_replace)
    script.dual_file_compatibility = True
    
    try:
        if guard:
            guard.mark_writing()
        else:
            (resolved_draft_path / WRITING_MARKER_NAME).touch()
    except Exception as marker_err:
        print(f"[DRAFT CREATOR] Warning: Could not create marker file: {marker_err}")

    raise_if_cancelled(cancel_check)

    intro_duration = 0
    intro_material = None
    if intro_path and Path(intro_path).exists():
        intro_material = draft.VideoMaterial(str(intro_path))
        intro_duration = intro_material.duration

    outro_duration = 0
    outro_material = None
    if outro_path and Path(outro_path).exists():
        outro_material = draft.VideoMaterial(str(outro_path))
        outro_duration = outro_material.duration

    generated_overlay_dir = resolved_draft_path / "_generated_overlay"

    video_track_name = "long_story_background"
    script.add_track(track_type=draft.TrackType.video, track_name=video_track_name, relative_index=0)

    audio_segments_added = 0
    voice_track_name = "long_story_voice"
    voice_duration = 0
    if voice_path and Path(voice_path).exists():
        audio_material = draft.AudioMaterial(str(voice_path))
        voice_duration = audio_material.duration
        script.add_track(track_type=draft.TrackType.audio, track_name=voice_track_name, relative_index=0)
        audio_segment = draft.AudioSegment(
            material=audio_material,
            target_timerange=draft.trange(start=intro_duration, duration=voice_duration),
            source_timerange=draft.trange(start=0, duration=voice_duration)
        )
        script.add_segment(audio_segment, voice_track_name)
        audio_segments_added += 1

    raise_if_cancelled(cancel_check)

    bgm_segments_added = 0
    bgm_track_name = "long_story_bgm"
    if bgm_path and Path(bgm_path).exists():
        bgm_material = draft.AudioMaterial(str(bgm_path))
        script.add_track(track_type=draft.TrackType.audio, track_name=bgm_track_name, relative_index=0)
        
        target_bgm_duration = voice_duration if voice_duration > 0 else bgm_material.duration
        bgm_duration = min(bgm_material.duration, target_bgm_duration)
        if bgm_duration > 0:
            # Audio Auto-Ducking (20%): Scale BGM volume to 0.2 if voice narration is present
            bgm_volume = calculate_bgm_volume(voice_path, voice_duration)
            bgm_segment = draft.AudioSegment(
                material=bgm_material,
                target_timerange=draft.trange(start=intro_duration, duration=bgm_duration),
                source_timerange=draft.trange(start=0, duration=bgm_duration),
                volume=bgm_volume
            )
            script.add_segment(bgm_segment, bgm_track_name)
            bgm_segments_added += 1

    raise_if_cancelled(cancel_check)

    video_segments_added = 0
    if intro_material and intro_duration > 0:
        intro_settings = draft.ClipSettings(
            alpha=1.0,
            scale_x=1.0,
            scale_y=1.0,
            transform_x=0.0,
            transform_y=0.0
        )
        intro_segment = draft.VideoSegment(
            material=intro_material,
            target_timerange=draft.trange(start=0, duration=intro_duration),
            source_timerange=draft.trange(start=0, duration=intro_duration),
            clip_settings=intro_settings
        )
        script.add_segment(intro_segment, video_track_name)
        video_segments_added += 1

    coerced_segments = _coerce_background_segments(background_segments)
    if intro_duration > 0:
        for seg in coerced_segments:
            seg.target_start_us += intro_duration

    video_segments_added += _add_background_segments(
        script,
        video_track_name,
        coerced_segments,
        short_video_mode=short_video_mode,
        cancel_check=cancel_check
    )

    if outro_material and outro_duration > 0:
        outro_settings = draft.ClipSettings(
            alpha=1.0,
            scale_x=1.0,
            scale_y=1.0,
            transform_x=0.0,
            transform_y=0.0
        )
        outro_segment = draft.VideoSegment(
            material=outro_material,
            target_timerange=draft.trange(start=intro_duration + voice_duration, duration=outro_duration),
            source_timerange=draft.trange(start=0, duration=outro_duration),
            clip_settings=outro_settings
        )
        script.add_segment(outro_segment, video_track_name)
        video_segments_added += 1

    # Add Subtitles if SRT file is provided
    subtitle_segments_added = 0
    if srt_path and Path(srt_path).exists():
        subtitles = parse_srt(str(srt_path))
        if subtitles:
            text_track_name = "long_story_subtitles"
            script.add_track(track_type=draft.TrackType.text, track_name=text_track_name, relative_index=0)
            
            style = draft.TextStyle(
                size=subtitle_font_size,
                bold=subtitle_bold,
                color=subtitle_color,
                auto_wrapping=True
            )
            border = draft.TextBorder(color=(0.0, 0.0, 0.0), width=subtitle_outline_width) # Black outline
            shadow = draft.TextShadow(color=(0.0, 0.0, 0.0), alpha=subtitle_shadow_alpha, distance=subtitle_shadow_distance) # Soft shadow
            
            for sub in subtitles:
                raise_if_cancelled(cancel_check)
                if sub["duration"] <= 0:
                    continue
                    
                text_segment = draft.TextSegment(
                    text=sub["text"],
                    timerange=draft.trange(start=sub["start"] + intro_duration, duration=sub["duration"]),
                    style=style,
                    border=border,
                    shadow=shadow
                )
                if subtitle_karaoke:
                    apply_karaoke_to_segment(text_segment, sub["duration"])
                script.add_segment(text_segment, text_track_name)
                subtitle_segments_added += 1
            print(f"[DRAFT CREATOR] Added {subtitle_segments_added} subtitles from SRT file.")

    # Add Logo overlay if provided
    logo_segments_added = 0
    if logo_path and Path(logo_path).exists() and voice_duration > 0:
        logo_path = _prepare_overlay_asset(
            logo_path,
            bg_mode=logo_bg_mode,
            output_dir=generated_overlay_dir,
            prefix="logo",
            similarity=chroma_threshold / 100.0,
            blend=chroma_shadow / 100.0,
            cancel_check=cancel_check,
        )
        raise_if_cancelled(cancel_check)
        logo_track_name = "long_story_logo"
        script.add_track(track_type=draft.TrackType.video, track_name=logo_track_name, relative_index=1)
        
        lx, ly = 0.75, 0.75
        if logo_position == "top_left":
            lx, ly = -0.75, 0.75
        elif logo_position == "top_right":
            lx, ly = 0.75, 0.75
        elif logo_position == "bottom_left":
            lx, ly = -0.75, -0.75
        elif logo_position == "bottom_right":
            lx, ly = 0.75, -0.75
            
        logo_scale_val = max(0.01, min(1.0, logo_scale / 100.0))
        logo_material = draft.VideoMaterial(str(logo_path))
        
        logo_settings = draft.ClipSettings(
            alpha=logo_opacity,
            scale_x=logo_scale_val,
            scale_y=logo_scale_val,
            transform_x=lx,
            transform_y=ly
        )
        logo_segment = draft.VideoSegment(
            material=logo_material,
            target_timerange=draft.trange(start=intro_duration, duration=voice_duration),
            source_timerange=draft.trange(start=0, duration=voice_duration),
            clip_settings=logo_settings
        )
        script.add_segment(logo_segment, logo_track_name)
        logo_segments_added += 1
        print(f"[DRAFT CREATOR] Added logo overlay track at {logo_position}.")

    # Add Animation overlay if provided
    anim_segments_added = 0
    if anim_path and Path(anim_path).exists() and voice_duration > 0:
        anim_path = _prepare_overlay_asset(
            anim_path,
            bg_mode=anim_bg_mode,
            output_dir=generated_overlay_dir,
            prefix="animation",
            similarity=chroma_threshold / 100.0,
            blend=chroma_shadow / 100.0,
            cancel_check=cancel_check,
        )
        raise_if_cancelled(cancel_check)
        anim_track_name = "long_story_anim"
        script.add_track(track_type=draft.TrackType.video, track_name=anim_track_name, relative_index=2)
        
        ax, ay = 0.0, -0.70
        if anim_position == "center":
            ax, ay = 0.0, 0.0
        elif anim_position == "bottom_left":
            ax, ay = -0.70, -0.70
        elif anim_position == "bottom_right":
            ax, ay = 0.70, -0.70
        elif anim_position == "bottom_center":
            ax, ay = 0.0, -0.70
            
        anim_scale_val = max(0.01, min(1.0, anim_scale / 100.0))
        anim_material = draft.VideoMaterial(str(anim_path))
        anim_duration = anim_material.duration
        
        anim_settings = draft.ClipSettings(
            alpha=1.0,
            scale_x=anim_scale_val,
            scale_y=anim_scale_val,
            transform_x=ax,
            transform_y=ay
        )
        
        placement_times = []
        if anim_timing == "start":
            placement_times.append(0)
        elif anim_timing == "middle":
            placement_times.append(max(0, (voice_duration - anim_duration) // 2))
        elif anim_timing == "end":
            placement_times.append(max(0, voice_duration - anim_duration))
        elif anim_timing == "repeat_60s":
            t = 60_000_000
            while t + anim_duration < voice_duration:
                placement_times.append(t)
                t += 60_000_000
                
        for start_time in placement_times:
            raise_if_cancelled(cancel_check)
            curr_duration = min(anim_duration, voice_duration - start_time)
            if curr_duration <= 0:
                continue
            anim_segment = draft.VideoSegment(
                material=anim_material,
                target_timerange=draft.trange(start=start_time + intro_duration, duration=curr_duration),
                source_timerange=draft.trange(start=0, duration=curr_duration),
                clip_settings=anim_settings
            )
            script.add_segment(anim_segment, anim_track_name)
            anim_segments_added += 1
        print(f"[DRAFT CREATOR] Added {anim_segments_added} overlay animation segments ({anim_timing}).")

    raise_if_cancelled(cancel_check)

    script.save(compact=compact)
    return {
        "project_name": project_name,
        "audio_segments": audio_segments_added + bgm_segments_added,
        "video_segments": video_segments_added,
        "subtitle_segments": subtitle_segments_added,
        "logo_segments": logo_segments_added,
        "animation_segments": anim_segments_added,
        "total_duration_us": script.duration,
        "draft_path": str(Path(draft_root) / project_name / "draft_content.json"),
        "voice_duration_sec": voice_duration / 1_000_000,
    }

# Subtitle rendering helpers removed.


def _add_background_segments(script, video_track_name: str, segments: List[BackgroundSegment], short_video_mode: str = "stretch", cancel_check = None) -> int:
    if not segments:
        return 0

    from app.job_control import raise_if_cancelled
    material_cache = {}
    added = 0
    for segment in segments:
        raise_if_cancelled(cancel_check)
        media_path = Path(segment.path)
        if not media_path.exists():
            print(f"[DRAFT CREATOR] Missing background media, skipped: {media_path}")
            continue

        key = str(media_path.resolve())
        if key not in material_cache:
            material_cache[key] = draft.VideoMaterial(str(media_path))
        video_material = material_cache[key]

        target_duration = max(1, int(segment.target_duration_us))
        source_start = max(0, int(segment.source_start_us))
        source_duration = max(1, int(segment.source_duration_us or target_duration))

        clip_settings = draft.ClipSettings(
            alpha=1.0,
            scale_x=1.0,
            scale_y=1.0,
            transform_x=0.0,
            transform_y=0.0
        )

        if video_material.material_type == "photo":
            source_start = 0
            source_duration = target_duration
            
            video_segment = draft.VideoSegment(
                material=video_material,
                target_timerange=draft.trange(start=segment.target_start_us, duration=target_duration),
                source_timerange=draft.trange(start=source_start, duration=source_duration),
                clip_settings=clip_settings
            )
            script.add_segment(video_segment, video_track_name)
            added += 1
        else:
            video_duration = video_material.duration
            if video_duration <= 0:
                continue

            max_available = max(0, video_duration - source_start)
            source_duration = min(source_duration, max_available)
            if source_duration <= 0:
                source_start = 0
                source_duration = min(video_duration, target_duration)
            if source_duration <= 0:
                continue

            video_segment = draft.VideoSegment(
                material=video_material,
                target_timerange=draft.trange(start=segment.target_start_us, duration=target_duration),
                source_timerange=draft.trange(start=source_start, duration=source_duration),
                clip_settings=clip_settings
            )
            script.add_segment(video_segment, video_track_name)
            added += 1

    print(f"[DRAFT CREATOR] Added {added} background media segments.")
    return added


def _coerce_background_segments(items: List[BackgroundSegment | Dict[str, Any]]) -> List[BackgroundSegment]:
    out: List[BackgroundSegment] = []
    for item in items:
        if isinstance(item, BackgroundSegment):
            out.append(item)
        else:
            out.append(BackgroundSegment.from_dict(item))
    return out

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--name", type=str, default="Test_Local_Creator")
    parser.add_argument("--media", nargs="*", default=None, required=True)
    parser.add_argument("--audio", type=str, default=None)
    parser.add_argument("--srt", type=str, default=None)
    args = parser.parse_args()
    
    num, dur, *extra = create_local_draft(
        draft_root=args.root,
        project_name=args.name,
        media_paths=args.media,
        audio_path=args.audio,
        srt_path=args.srt
    )
    print(f"Created draft '{args.name}' with {num} media files. Total duration: {dur/1000000:.2f}s")
