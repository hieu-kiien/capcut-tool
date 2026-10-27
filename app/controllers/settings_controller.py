import json
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QObject
import capcut_keyframe_tool as keyframe_tool


class SettingsController(QObject):
    """Manages loading and saving application configuration and UI state."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    def load_config(self, config_path: Path) -> None:
        mw = self.main_window
        if config_path.exists():
            try:
                cfg = json.loads(config_path.read_text(encoding="utf-8"))
                mw.setup_widget.project_name.setText(cfg.get("project_name", "Du_An_CapCut"))

                saved_root = cfg.get("draft_root", "")
                if saved_root and Path(saved_root).exists():
                    mw.setup_widget.draft_root.setText(saved_root)
                else:
                    detected = keyframe_tool.detect_capcut_draft_root()
                    if detected:
                        mw.setup_widget.draft_root.setText(str(detected))
                    elif saved_root:
                        mw.setup_widget.draft_root.setText(saved_root)

                mw.setup_widget.voice_path.setText(cfg.get("voice_path", ""))
                mw.setup_widget.media_dir.setText(cfg.get("media_dir", ""))
                mw.setup_widget.bgm_path.setText(cfg.get("bgm_path", ""))
                mw.setup_widget.srt_path.setText(cfg.get("srt_path", ""))

                mw.effects_widget.logo_path.setText(cfg.get("logo_path", ""))
                logo_pos = cfg.get("logo_position", "top_right")
                idx = mw.effects_widget.logo_position.findData(logo_pos)
                if idx >= 0:
                    mw.effects_widget.logo_position.setCurrentIndex(idx)
                mw.effects_widget.logo_scale.setValue(cfg.get("logo_scale", 15.0))

                mw.effects_widget.anim_path.setText(cfg.get("anim_path", ""))
                anim_pos = cfg.get("anim_position", "bottom_center")
                idx = mw.effects_widget.anim_position.findData(anim_pos)
                if idx >= 0:
                    mw.effects_widget.anim_position.setCurrentIndex(idx)
                mw.effects_widget.anim_scale.setValue(cfg.get("anim_scale", 30.0))
                anim_time = cfg.get("anim_timing", "end")
                idx = mw.effects_widget.anim_timing.findData(anim_time)
                if idx >= 0:
                    mw.effects_widget.anim_timing.setCurrentIndex(idx)

                if cfg.get("canvas") == "16:9":
                    mw.setup_widget.ratio_16_9.setChecked(True)
                else:
                    mw.setup_widget.ratio_9_16.setChecked(True)

                mw.setup_widget.clip_min.setValue(cfg.get("clip_min_sec", 5.0))
                mw.setup_widget.clip_max.setValue(cfg.get("clip_max_sec", 9.0))

                mode_str = cfg.get("selection_mode", "shuffle_bag")
                if "sequential" in mode_str:
                    mw.setup_widget.selection_mode.setCurrentIndex(1)
                elif "random" in mode_str:
                    mw.setup_widget.selection_mode.setCurrentIndex(2)
                elif "duplicate_then_shuffle" in mode_str:
                    mw.setup_widget.selection_mode.setCurrentIndex(3)
                elif "shuffle_duplicates_only" in mode_str:
                    mw.setup_widget.selection_mode.setCurrentIndex(4)
                else:
                    mw.setup_widget.selection_mode.setCurrentIndex(0)

                short_video_mode = cfg.get("short_video_mode", "stretch")
                if short_video_mode == "loop":
                    mw.setup_widget.short_video_mode.setCurrentIndex(1)
                else:
                    mw.setup_widget.short_video_mode.setCurrentIndex(0)

                bg_switch_mode = cfg.get("bg_switch_mode", "time")
                idx = mw.setup_widget.bg_switch_mode.findData(bg_switch_mode)
                if idx >= 0:
                    mw.setup_widget.bg_switch_mode.setCurrentIndex(idx)
                mw.setup_widget.bg_switch_group_size.setValue(cfg.get("bg_switch_group_size", 3))

                mw.setup_widget.recursive_scan.setChecked(cfg.get("recursive_scan", False))

                auto_kf_id = cfg.get("auto_kf_id")
                if auto_kf_id:
                    idx = mw.setup_widget.auto_kf_combo.findData(auto_kf_id)
                    mw.setup_widget.auto_kf_combo.setCurrentIndex(max(0, idx))

                auto_trans_id = cfg.get("auto_trans_id")
                if auto_trans_id:
                    idx = mw.setup_widget.auto_trans_combo.findData(auto_trans_id)
                    mw.setup_widget.auto_trans_combo.setCurrentIndex(max(0, idx))

                mw.setup_widget.auto_trans_dur.setValue(cfg.get("auto_trans_dur_val", 0.4))

                # Load subtitle styling settings
                subtitle_font = cfg.get("subtitle_font", "SystemFont")
                idx = mw.setup_widget.subtitle_font.findText(subtitle_font)
                if idx >= 0:
                    mw.setup_widget.subtitle_font.setCurrentIndex(idx)
                mw.setup_widget.subtitle_font_size.setValue(cfg.get("subtitle_font_size", 6.0))
                mw.setup_widget.subtitle_color.setText(cfg.get("subtitle_color", "#FFFFFF"))

                align = cfg.get("subtitle_align", "bottom_center")
                idx = mw.setup_widget.subtitle_align.findData(align)
                if idx >= 0:
                    mw.setup_widget.subtitle_align.setCurrentIndex(idx)

                mw.setup_widget.subtitle_outline_width.setValue(cfg.get("subtitle_outline_width", 40.0))
                mw.setup_widget.subtitle_shadow_alpha.setValue(cfg.get("subtitle_shadow_alpha", 0.8))
                mw.setup_widget.subtitle_shadow_distance.setValue(cfg.get("subtitle_shadow_distance", 5.0))

                mw.setup_widget.subtitle_bold.setChecked(cfg.get("subtitle_bold", True))
                mw.setup_widget.subtitle_italic.setChecked(cfg.get("subtitle_italic", False))
                mw.setup_widget.subtitle_underline.setChecked(cfg.get("subtitle_underline", False))
                mw.setup_widget.subtitle_shadow.setChecked(cfg.get("subtitle_shadow", True))
                mw.setup_widget._update_subtitle_preview()

                mw._refresh_projects()
                last_project = cfg.get("last_selected_project", "")
                if last_project:
                    idx = mw.effects_widget.project_combo.findText(last_project)
                    if idx >= 0:
                        mw.effects_widget.project_combo.setCurrentIndex(idx)
                    idx_hist = mw.history_widget.project_combo.findText(last_project)
                    if idx_hist >= 0:
                        mw.history_widget.project_combo.setCurrentIndex(idx_hist)
                mw.history_widget.backup_keep_days.setValue(cfg.get("backup_keep_days", 7.0))
                mw._current_profile_name = cfg.get("last_selected_profile", "Mặc định")
                return
            except Exception as e:
                try:
                    mw._append_log(f"[CẢNH BÁO] Không đọc được config.json (sẽ tự dò tìm lại): {e}")
                except Exception:
                    pass

        detected = keyframe_tool.detect_capcut_draft_root()
        if detected:
            mw.setup_widget.draft_root.setText(str(detected))
        mw._refresh_projects()

    def save_config(self, config_path: Path) -> None:
        mw = self.main_window
        canvas = "9:16"
        if mw.setup_widget.ratio_16_9.isChecked():
            canvas = "16:9"

        selection_idx = mw.setup_widget.selection_mode.currentIndex()
        selection_mode = {
            1: "sequential",
            2: "random",
            3: "duplicate_then_shuffle",
            4: "shuffle_duplicates_only",
        }.get(selection_idx, "shuffle_bag")

        short_video_mode = "loop" if mw.setup_widget.short_video_mode.currentIndex() == 1 else "stretch"

        cfg = {
            "project_name": mw.setup_widget.project_name.text().strip(),
            "draft_root": mw.setup_widget.draft_root.text().strip(),
            "voice_path": mw.setup_widget.voice_path.text().strip(),
            "media_dir": mw.setup_widget.media_dir.text().strip(),
            "bgm_path": mw.setup_widget.bgm_path.text().strip(),
            "srt_path": mw.setup_widget.srt_path.text().strip(),
            "logo_path": mw.effects_widget.logo_path.text().strip(),
            "logo_position": mw.effects_widget.logo_position.currentData() or "top_right",
            "logo_scale": mw.effects_widget.logo_scale.value(),
            "anim_path": mw.effects_widget.anim_path.text().strip(),
            "anim_position": mw.effects_widget.anim_position.currentData() or "bottom_center",
            "anim_scale": mw.effects_widget.anim_scale.value(),
            "anim_timing": mw.effects_widget.anim_timing.currentData() or "end",
            "canvas": canvas,
            "clip_min_sec": mw.setup_widget.clip_min.value(),
            "clip_max_sec": mw.setup_widget.clip_max.value(),
            "selection_mode": selection_mode,
            "short_video_mode": short_video_mode,
            "bg_switch_mode": mw.setup_widget.bg_switch_mode.currentData() or "time",
            "bg_switch_group_size": mw.setup_widget.bg_switch_group_size.value(),
            "recursive_scan": mw.setup_widget.recursive_scan.isChecked(),
            "auto_kf_id": mw.setup_widget.auto_kf_combo.currentData() or "none",
            "auto_trans_id": mw.setup_widget.auto_trans_combo.currentData() or "none",
            "auto_trans_dur_val": mw.setup_widget.auto_trans_dur.value(),
            "last_selected_project": mw.effects_widget.project_combo.currentText(),
            "last_selected_profile": getattr(mw, "_current_profile_name", "Mặc định"),
            "backup_keep_days": mw.history_widget.backup_keep_days.value(),

            # Subtitle styling settings
            "subtitle_font": mw.setup_widget.subtitle_font.currentText(),
            "subtitle_font_size": mw.setup_widget.subtitle_font_size.value(),
            "subtitle_color": mw.setup_widget.subtitle_color.text().strip(),
            "subtitle_align": mw.setup_widget.subtitle_align.currentData() or "bottom_center",
            "subtitle_outline_width": mw.setup_widget.subtitle_outline_width.value(),
            "subtitle_shadow_alpha": mw.setup_widget.subtitle_shadow_alpha.value(),
            "subtitle_shadow_distance": mw.setup_widget.subtitle_shadow_distance.value(),
            "subtitle_bold": mw.setup_widget.subtitle_bold.isChecked(),
            "subtitle_italic": mw.setup_widget.subtitle_italic.isChecked(),
            "subtitle_underline": mw.setup_widget.subtitle_underline.isChecked(),
            "subtitle_shadow": mw.setup_widget.subtitle_shadow.isChecked()
        }

        try:
            config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            try:
                mw._append_log(f"[LỖI] Không lưu được config.json: {e}")
            except Exception:
                pass
