from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import time

import capcut_draft_creator as draft_creator
import video_mixer
from runtime_tools import pymediainfo_available, resolve_ffmpeg, resolve_ffprobe


ProgressCallback = Callable[[str], None]
StepCallback = Callable[["StepResult"], None]
CancelCheck = Callable[[], bool]


STEP_PREFLIGHT = "preflight"
STEP_SCAN = "scan_media"
STEP_PLAN = "plan_media"
STEP_DRAFT = "write_draft"

DEFAULT_STEPS = [
    (STEP_PREFLIGHT, "Kiểm tra đầu vào"),
    (STEP_SCAN, "Quét kho media"),
    (STEP_PLAN, "Phân bổ video nền"),
    (STEP_DRAFT, "Tạo dự án CapCut"),
]


from app.job_control import JobCancelled, raise_if_cancelled


@dataclass(frozen=True)
class ProjectConfig:
    project_name: str
    draft_root: str
    voice_path: str
    media_dir: str
    bgm_path: str = ""
    srt_path: str = ""
    intro_path: str = ""
    outro_path: str = ""
    allow_replace: bool = False
    
    # Logo Settings
    logo_path: str = ""
    logo_position: str = "top_right"
    logo_scale: float = 15.0
    logo_opacity: float = 1.0
    logo_bg_mode: str = "none"

    # Animation Settings
    anim_path: str = ""
    anim_position: str = "bottom_center"
    anim_scale: float = 30.0
    anim_timing: str = "end"
    anim_bg_mode: str = "none"
    
    # Chroma & Karaoke Settings
    chroma_enabled: bool = False
    chroma_mode: str = "green"
    chroma_threshold: int = 32
    chroma_shadow: int = 2
    subtitle_karaoke: bool = False
    
    canvas: str = "9:16"  # "9:16" or "16:9"
    
    # Video Mixer Settings
    clip_min_sec: float = 5.0
    clip_max_sec: float = 12.0
    selection_mode: str = "shuffle_bag"
    recursive_scan: bool = False
    short_video_mode: str = "stretch"  # "stretch" or "loop"

    # Auto-Apply Keyframe/Transition Settings
    auto_keyframe: str = "none"
    auto_transition: str = "none"
    auto_transition_duration: float = 0.4

    # Subtitle Style Settings
    subtitle_font_size: float = 6.0
    subtitle_color: tuple = (1.0, 1.0, 1.0)
    subtitle_bold: bool = True
    subtitle_outline_width: float = 40.0
    subtitle_shadow_alpha: float = 0.8
    subtitle_shadow_distance: float = 5.0

    # Media Switching Settings
    bg_switch_mode: str = "time"  # "time", "subtitle", "subtitle_group"
    bg_switch_group_size: int = 3
    ffmpeg_overlay_timeout_sec: float = 60.0


@dataclass
class StepResult:
    code: str
    label: str
    status: str
    message: str = ""
    path: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PipelineRunner:
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.steps: List[StepResult] = []
        self.started_at = time.time()

    def run_all(
        self,
        *,
        progress: Optional[ProgressCallback] = None,
        step: Optional[StepCallback] = None,
        cancel_check: Optional[CancelCheck] = None,
    ) -> Dict[str, Any]:
        self.steps = []
        self.started_at = time.time()
        
        self._run_step(
            STEP_PREFLIGHT,
            "Kiểm tra đầu vào",
            lambda: self.preflight(progress=progress, cancel_check=cancel_check),
            step,
            cancel_check,
        )
        
        assets = self._run_step(STEP_SCAN, "Quét kho media", lambda: self.scan_media(progress=progress, cancel_check=cancel_check), step, cancel_check)
        
        segments = self._run_step(
            STEP_PLAN,
            "Phân bổ video nền",
            lambda: self.plan_media(assets, progress=progress, cancel_check=cancel_check),
            step,
            cancel_check
        )
        
        draft_result = self._run_step(
            STEP_DRAFT,
            "Tạo dự án CapCut",
            lambda: self.write_draft(segments, progress=progress, cancel_check=cancel_check),
            step,
            cancel_check
        )
        
        draft_path = Path(draft_result.get("draft_path", "")) if draft_result else Path("")
        if draft_path.exists():
            try:
                raise_if_cancelled(cancel_check)
                import capcut_keyframe_tool as kt
                from app.presets import KEYFRAME_PRESETS, TRANSITION_PRESETS
                
                class DummyArgs:
                    def __init__(self, **kwargs):
                        self.__dict__.update(kwargs)
                
                # 1. Auto Keyframe
                auto_kf = self.config.auto_keyframe
                if auto_kf and auto_kf != "none":
                    raise_if_cancelled(cancel_check)
                    self._emit(progress, f"[HỆ THỐNG] Tự động áp dụng hiệu ứng keyframe: {auto_kf}")
                    presets_to_apply = []
                    if auto_kf == "random":
                        presets_to_apply = KEYFRAME_PRESETS
                    else:
                        for p in KEYFRAME_PRESETS:
                            if p["id"] == auto_kf:
                                presets_to_apply = [p]
                                break
                                
                    if presets_to_apply:
                        args = DummyArgs(
                            segment_type="video",
                            mode="replace",
                            dry_run=False,
                            intro_path=self.config.intro_path,
                            outro_path=self.config.outro_path
                        )
                        changed = kt.apply_random_presets_to_file(draft_path, args, presets_to_apply, cancel_check=cancel_check)
                        self._emit(progress, f"[OK] Đã tự động áp dụng keyframe cho {changed} phân đoạn.")
                
                # 2. Auto Transition
                auto_trans = self.config.auto_transition
                if auto_trans and auto_trans != "none":
                    raise_if_cancelled(cancel_check)
                    self._emit(progress, f"[HỆ THỐNG] Tự động áp dụng hiệu ứng chuyển cảnh: {auto_trans}")
                    duration_us = int(self.config.auto_transition_duration * 1_000_000)
                    if auto_trans == "random":
                        transition_presets = [{"name": p["name"], "duration": p["duration"]} for p in TRANSITION_PRESETS]
                    else:
                        transition_presets = [{"name": auto_trans, "duration": duration_us}]
                        
                    root_dir = draft_path.parents[1]
                    args = DummyArgs(
                        root=root_dir,
                        transition_duration_sec=self.config.auto_transition_duration,
                        transition_apply_all=False,
                        segment_type="video",
                        mode="replace",
                        dry_run=False,
                        intro_path=self.config.intro_path,
                        outro_path=self.config.outro_path
                    )
                    changed = kt.apply_random_transitions_to_file(draft_path, args, transition_presets, cancel_check=cancel_check)
                    self._emit(progress, f"[OK] Đã tự động chèn chuyển cảnh thành công cho {changed} điểm cắt.")
            except Exception as e:
                if isinstance(e, JobCancelled):
                    raise
                self._emit(progress, f"[CẢNH BÁO] Không thể tự động áp dụng hiệu ứng: {e}")
        
        return {
            "status": "success",
            "project_name": self.config.project_name,
            "duration": round(time.time() - self.started_at, 2),
            "draft_path": draft_result.get("draft_path", ""),
            "video_segments": draft_result.get("video_segments", 0),
            "voice_duration_sec": draft_result.get("voice_duration_sec", 0.0),
            "backup_path": draft_result.get("backup_path", ""),
            "steps": [s.to_dict() for s in self.steps],
        }

    def preflight(
        self,
        *,
        progress: Optional[ProgressCallback] = None,
        cancel_check: Optional[CancelCheck] = None,
    ) -> List[str]:
        raise_if_cancelled(cancel_check)
        from app.preflight import run_preflight
        report = run_preflight(self.config, fast_mode=True)
        raise_if_cancelled(cancel_check)
        for issue in report.issues:
            icon = "[THÔNG TIN]"
            if issue.severity == "error":
                icon = "[LỖI]"
            elif issue.severity == "warning":
                icon = "[CẢNH BÁO]"
            
            self._emit(progress, f"{icon} {issue.message}")
            if issue.suggestion:
                self._emit(progress, f"   Gợi ý: {issue.suggestion}")

        if not report.can_run:
            errors = [i.message for i in report.issues if i.blocks_run]
            raise ValueError("Kiểm tra đầu vào thất bại:\n" + "\n".join(errors))

        self._emit(progress, "[OK] Kiểm tra đầu vào thành công.")
        return ["OK"]

    def scan_media(self, *, progress: Optional[ProgressCallback] = None, cancel_check: Optional[CancelCheck] = None) -> List[Any]:
        self._emit(progress, f"Đang quét thư mục video nền: {self.config.media_dir}")
        assets = video_mixer.scan_media_folder(
            self.config.media_dir,
            recursive=self.config.recursive_scan,
            cancel_check=cancel_check
        )
        raise_if_cancelled(cancel_check)
        usable = [a for a in assets if not a.error]
        
        self._emit(progress, f"Tìm thấy {len(assets)} tệp tin. Có {len(usable)} tệp khả dụng (video/ảnh).")
        if not usable:
            raise ValueError("Không tìm thấy video hay ảnh nền nào khả dụng trong thư mục được chọn.")
        return usable

    def plan_media(
        self,
        assets: List[Any],
        *,
        progress: Optional[ProgressCallback] = None,
        cancel_check: Optional[CancelCheck] = None,
    ) -> List[Any]:
        import media_probe
        
        raise_if_cancelled(cancel_check)
        # Get total duration from voice file
        voice_asset = media_probe.probe_media(self.config.voice_path)
        if voice_asset.error:
            raise ValueError(f"Không thể đọc thông tin tệp giọng đọc: {voice_asset.error}")
        total_duration_us = voice_asset.duration_us
        raise_if_cancelled(cancel_check)

        # Determine subtitles if switching mode is subtitle-based
        subtitles = None
        mode_label = "Theo thời gian cố định"
        
        if self.config.bg_switch_mode in ("subtitle", "subtitle_group") and self.config.srt_path:
            srt_path_obj = Path(self.config.srt_path).expanduser()
            if srt_path_obj.exists() and srt_path_obj.is_file():
                self._emit(progress, f"Đang phân tích tệp phụ đề cho quy tắc chuyển cảnh: {self.config.bg_switch_mode}...")
                subtitles = draft_creator.parse_srt(str(srt_path_obj))
                if subtitles:
                    if self.config.bg_switch_mode == "subtitle":
                        mode_label = "Theo từng câu thoại SRT"
                    else:
                        mode_label = f"Theo cụm {self.config.bg_switch_group_size} câu thoại SRT"
                else:
                    self._emit(progress, "[CẢNH BÁO] Không thể phân tích câu phụ đề nào từ tệp SRT. Tự động chuyển sang chế độ đổi nền theo thời gian.")
            else:
                self._emit(progress, "[CẢNH BÁO] Không tìm thấy tệp phụ đề SRT. Tự động chuyển sang chế độ đổi nền theo thời gian.")

        # Map bg_switch_mode to video_mixer mode
        mixer_mode = video_mixer.MODE_EVERY_X_SECONDS
        if subtitles:
            if self.config.bg_switch_mode == "subtitle":
                mixer_mode = video_mixer.MODE_SUBTITLE
            elif self.config.bg_switch_mode == "subtitle_group":
                mixer_mode = video_mixer.MODE_SUBTITLE_GROUP

        mixer_cfg = video_mixer.VideoMixerConfig(
            mode=mixer_mode,
            clip_min_sec=self.config.clip_min_sec,
            clip_max_sec=self.config.clip_max_sec,
            selection_mode=self.config.selection_mode,
            recursive=self.config.recursive_scan,
            group_size=self.config.bg_switch_group_size,
            short_video_mode=self.config.short_video_mode,
        )
        
        if mixer_mode == video_mixer.MODE_EVERY_X_SECONDS:
            self._emit(progress, f"Lập kế hoạch chuyển cảnh ({mode_label}): Cắt clip ngẫu nhiên từ {self.config.clip_min_sec} đến {self.config.clip_max_sec} giây.")
        else:
            self._emit(progress, f"Lập kế hoạch chuyển cảnh ({mode_label}): Xếp hình ảnh/video khớp timing phụ đề.")

        raise_if_cancelled(cancel_check)
        segments = video_mixer.plan_background_segments(
            assets=assets,
            total_duration_us=total_duration_us,
            config=mixer_cfg,
            subtitles=subtitles,
        )
        self._emit(progress, f"Lập kế hoạch thành công: {len(segments)} phân đoạn video nền.")
        return segments

    def write_draft(self, segments: List[Any], *, progress: Optional[ProgressCallback] = None, cancel_check: Optional[CancelCheck] = None) -> Dict[str, Any]:
        self._emit(progress, "Đang đóng gói và tạo dự án CapCut...")
        canvas_w = 1080 if self.config.canvas == "9:16" else 1920
        canvas_h = 1920 if self.config.canvas == "9:16" else 1080
        
        raise_if_cancelled(cancel_check)
        
        result = draft_creator.create_draft_from_files(
            draft_root=Path(self.config.draft_root),
            project_name=self.config.project_name,
            voice_path=Path(self.config.voice_path),
            background_segments=segments,
            bgm_path=Path(self.config.bgm_path) if self.config.bgm_path else None,
            canvas_width=canvas_w,
            canvas_height=canvas_h,
            allow_replace=self.config.allow_replace,
            short_video_mode=self.config.short_video_mode,
            srt_path=Path(self.config.srt_path) if self.config.srt_path else None,
            intro_path=Path(self.config.intro_path) if self.config.intro_path else None,
            outro_path=Path(self.config.outro_path) if self.config.outro_path else None,
            logo_path=Path(self.config.logo_path) if self.config.logo_path else None,
            logo_position=self.config.logo_position,
            logo_scale=self.config.logo_scale,
            logo_opacity=self.config.logo_opacity,
            logo_bg_mode=self.config.chroma_mode if self.config.chroma_enabled else "none",
            anim_path=Path(self.config.anim_path) if self.config.anim_path else None,
            anim_position=self.config.anim_position,
            anim_scale=self.config.anim_scale,
            anim_timing=self.config.anim_timing,
            anim_bg_mode=self.config.chroma_mode if self.config.chroma_enabled else "none",
            subtitle_font_size=self.config.subtitle_font_size,
            subtitle_color=self.config.subtitle_color,
            subtitle_bold=self.config.subtitle_bold,
            subtitle_outline_width=self.config.subtitle_outline_width,
            subtitle_shadow_alpha=self.config.subtitle_shadow_alpha,
            subtitle_shadow_distance=self.config.subtitle_shadow_distance,
            subtitle_karaoke=self.config.subtitle_karaoke,
            chroma_threshold=float(self.config.chroma_threshold),
            chroma_shadow=float(self.config.chroma_shadow),
            cancel_check=cancel_check,
        )
        
        self._emit(progress, f"[OK] Tạo dự án CapCut thành công! Dự án được lưu tại: {result.get('draft_path')}")
        return result

    def _run_step(
        self,
        code: str,
        label: str,
        fn: Callable[[], Any],
        step_callback: Optional[StepCallback],
        cancel_check: Optional[CancelCheck],
    ) -> Any:
        self._check_cancel(cancel_check)
        running = StepResult(code=code, label=label, status="running", started_at=_timestamp())
        self._emit_step(running, step_callback)
        try:
            value = fn()
            self._check_cancel(cancel_check)
            done = StepResult(
                code=code,
                label=label,
                status="done",
                message=_summarize_value(value),
                started_at=running.started_at,
                finished_at=_timestamp(),
            )
            self.steps.append(done)
            self._emit_step(done, step_callback)
            return value
        except Exception as exc:
            status = "cancelled" if isinstance(exc, JobCancelled) else "error"
            failed = StepResult(
                code=code,
                label=label,
                status=status,
                message=str(exc),
                started_at=running.started_at,
                finished_at=_timestamp(),
            )
            self.steps.append(failed)
            self._emit_step(failed, step_callback)
            raise

    def _check_cancel(self, cancel_check: Optional[CancelCheck]) -> None:
        raise_if_cancelled(cancel_check)

    def _emit(self, progress: Optional[ProgressCallback], message: str) -> None:
        if progress:
            progress(message)

    def _emit_step(self, result: StepResult, callback: Optional[StepCallback]) -> None:
        if callback:
            callback(result)


def _timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _summarize_value(value: Any) -> str:
    if isinstance(value, list):
        return f"Tìm thấy {len(value)} phần tử"
    if isinstance(value, dict):
        return f"Hoàn thành: {value.get('project_name', '')}"
    return str(value)[:100]
