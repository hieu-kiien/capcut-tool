from pathlib import Path
from typing import Optional, Dict
from PySide6.QtCore import QObject, Slot, QThread
from PySide6.QtWidgets import QMessageBox
import capcut_keyframe_tool as keyframe_tool
from app.workers import KeyframeWorker
from app.presets import KEYFRAME_PRESETS, TRANSITION_PRESETS

_PRESET_GROUP_MAP: Dict[str, tuple] = {
    "zoom_in_slow":      ("zoom",     {"zoom_from": 100.0, "zoom_to": 112.0}),
    "zoom_out_slow":     ("zoom",     {"zoom_from": 112.0, "zoom_to": 100.0}),
    "zoom_in_fast":      ("zoom",     {"zoom_from": 100.0, "zoom_to": 125.0}),
    "zoom_out_fast":     ("zoom",     {"zoom_from": 125.0, "zoom_to": 100.0}),
    "zoom_bounce":       ("bounce",   {"zoom_from": 100.0, "zoom_peak": 118.0, "zoom_peak_at": 60.0, "zoom_end": 108.0}),
    "pan_left_right":    ("pan",      {"pan_zoom": 115.0, "pan_from": -0.07, "pan_to":  0.07, "pan_axis": "pos_x", "axis_lbl": "X (Ngang)"}),
    "pan_right_left":    ("pan",      {"pan_zoom": 115.0, "pan_from":  0.07, "pan_to": -0.07, "pan_axis": "pos_x", "axis_lbl": "X (Ngang)"}),
    "pan_up_down":       ("pan",      {"pan_zoom": 115.0, "pan_from": -0.07, "pan_to":  0.07, "pan_axis": "pos_y", "axis_lbl": "Y (Dọc)"}),
    "pan_down_up":       ("pan",      {"pan_zoom": 115.0, "pan_from":  0.07, "pan_to": -0.07, "pan_axis": "pos_y", "axis_lbl": "Y (Dọc)"}),
    "zoom_in_pan_left":  ("zoompan",  {"zoom_from": 100.0, "zoom_to": 115.0, "pan_from":  0.0,  "pan_to": -0.06, "pan_axis": "pos_x", "axis_lbl": "X (Ngang)"}),
    "zoom_in_pan_right": ("zoompan",  {"zoom_from": 100.0, "zoom_to": 115.0, "pan_from":  0.0,  "pan_to":  0.06, "pan_axis": "pos_x", "axis_lbl": "X (Ngang)"}),
    "zoom_in_pan_up":    ("zoompan",  {"zoom_from": 100.0, "zoom_to": 115.0, "pan_from":  0.0,  "pan_to": -0.06, "pan_axis": "pos_y", "axis_lbl": "Y (Dọc)"}),
    "zoom_out_pan_down": ("zoompan",  {"zoom_from": 115.0, "zoom_to": 100.0, "pan_from": -0.06, "pan_to":  0.0,  "pan_axis": "pos_y", "axis_lbl": "Y (Dọc)"}),
    "subtle_rotate_cw":  ("rotate",   {"rot_zoom": 105.0, "rot_from": -1.5, "rot_to":  1.5}),
    "subtle_rotate_ccw": ("rotate",   {"rot_zoom": 105.0, "rot_from":  1.5, "rot_to": -1.5}),
    "fade_in":           ("fade",     {"fade_from": 0.0, "fade_to": 1.0}),
    "fade_out":          ("fade",     {"fade_from": 1.0, "fade_to": 0.0}),
    "fade_in_out":       ("fadeinout",{"fio_in_end": 15.0, "fio_out_start": 85.0}),
}


class EffectsController(QObject):
    """Manages Keyframe Presets, Transitions, Speed, and Scale effect compilation and worker execution."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    def run_keyframe_action(self, action: str, params: dict, project_name: str = None) -> None:
        mw = self.main_window
        if mw.thread and mw.thread.isRunning():
            QMessageBox.warning(mw, "Cảnh báo", "Một tiến trình khác đang thực thi, vui lòng đợi.")
            return

        proj = project_name or mw.effects_widget.project_combo.currentText()
        if not proj:
            QMessageBox.critical(mw, "Lỗi", "Vui lòng chọn một dự án nháp mục tiêu!")
            return

        root_str = mw.setup_widget.draft_root.text().strip()
        project_dir = Path(root_str) / proj
        primary_draft, _ = keyframe_tool.resolve_project_draft_paths(project_dir)

        if not primary_draft or not primary_draft.exists():
            QMessageBox.critical(mw, "Lỗi", f"Không tìm thấy tệp draft_content.json tại {project_dir}")
            return

        mw._save_config()
        mw.build_widget.clear_logs()
        mw._switch_to_page("build-center")

        mw.thread = QThread(mw)
        mw.worker = KeyframeWorker(action, primary_draft, params)
        mw.worker.moveToThread(mw.thread)

        mw.worker.log_signal.connect(mw._append_log)
        mw.worker.finished_signal.connect(self._on_keyframe_finished)
        mw.worker.failed_signal.connect(self._on_keyframe_failed)

        mw.thread.started.connect(mw.worker.run)
        mw.worker.finished_signal.connect(mw.thread.quit)
        mw.worker.failed_signal.connect(mw.thread.quit)

        mw.worker.finished_signal.connect(mw.worker.deleteLater)
        mw.worker.failed_signal.connect(mw.worker.deleteLater)
        mw.thread.finished.connect(mw.thread.deleteLater)
        mw.thread.finished.connect(self._on_keyframe_thread_finished)

        self.set_keyframe_ui_enabled(False)
        mw.build_widget.btn_run.setEnabled(False)

        mw.thread.start()

    @Slot(dict)
    def _on_keyframe_finished(self, result: dict) -> None:
        mw = self.main_window
        action = result.get("action")
        if action == "restore_backup":
            QMessageBox.information(mw, "Thành công", f"Khôi phục thành công dự án về bản sao lưu {result.get('backup_name')}!")
        elif action == "repair_project":
            actions_taken = result.get("actions_taken", [])
            if actions_taken:
                details = "\n".join(f"- {act}" for act in actions_taken)
                msg = f"Đã thực hiện các hành động sửa lỗi sau:\n\n{details}"
            else:
                msg = "Không phát hiện lỗi nào cần sửa hoặc dự án đã tương thích hoàn toàn."
            QMessageBox.information(mw, "Kết quả sửa lỗi", msg)
            mw.history_widget.run_diagnose()
        else:
            changed = result.get("changed", 0)
            QMessageBox.information(mw, "Thành công", f"Đã áp dụng hiệu ứng thành công cho {changed} phân đoạn!")

        mw._refresh_backups_for_project(mw.effects_widget.project_combo.currentText())

    @Slot(str)
    def _on_keyframe_failed(self, message: str) -> None:
        mw = self.main_window
        mw._append_log(f"[LỖI] Thao tác thất bại: {message}")
        QMessageBox.critical(mw, "Thất bại", f"Thao tác thất bại:\n{message}")

    @Slot()
    def _on_keyframe_thread_finished(self) -> None:
        mw = self.main_window
        self.set_keyframe_ui_enabled(True)
        mw.build_widget.btn_run.setEnabled(True)
        mw.thread = None
        mw.worker = None

    def set_keyframe_ui_enabled(self, enabled: bool) -> None:
        mw = self.main_window
        mw.effects_widget.setEnabled(enabled)
        mw.history_widget.setEnabled(enabled)

    def apply_effect_click(self) -> None:
        mw = self.main_window
        action = mw.effects_widget.effect_type_combo.currentData()
        segment = mw.effects_widget.shared_segment_combo.currentData()
        mode = mw.effects_widget.shared_mode_combo.currentData()

        if action == "presets":
            preset_id = mw.effects_widget.kf_preset_combo.currentData()
            presets = []
            if preset_id == "random":
                presets = KEYFRAME_PRESETS
            else:
                custom = self.build_preset_from_params(preset_id, segment)
                if custom:
                    presets = [custom]
                else:
                    for p in KEYFRAME_PRESETS:
                        if p["id"] == preset_id:
                            presets = [p]
                            break
            if not presets:
                return
            params = {
                "presets": presets,
                "segment_type": segment,
                "mode": mode
            }
            self.run_keyframe_action("apply_preset", params)

        elif action == "custom":
            prop = mw.effects_widget.custom_prop_combo.currentData()
            unit = mw.effects_widget.custom_unit_combo.currentData()
            from_val = mw.effects_widget.custom_from_spin.value()
            to_val = mw.effects_widget.custom_to_spin.value()

            keyframes = [{"at": 0.0, "value": from_val}]
            if mw.effects_widget.custom_mid_chk.isChecked():
                mid_val = mw.effects_widget.custom_mid_spin.value()
                mid_at = mw.effects_widget.custom_mid_time_spin.value() / 100.0
                keyframes.append({"at": mid_at, "value": mid_val})
            keyframes.append({"at": 1.0, "value": to_val})

            op = {
                "property": prop,
                "keyframes": keyframes
            }
            if unit != "raw":
                op["unit"] = unit
            if prop in ("pos_x", "pos_y") and mw.effects_widget.custom_clamp_chk.isChecked():
                op["clamp_to_frame"] = True

            presets = [{
                "name": "Custom Dynamic Effect",
                "segment": segment,
                "operations": [op]
            }]

            params = {
                "presets": presets,
                "segment_type": segment,
                "mode": mode
            }
            self.run_keyframe_action("apply_preset", params)

        elif action == "transition":
            trans_name = mw.effects_widget.trans_preset_combo.currentData()
            if trans_name == "custom":
                name = mw.effects_widget.trans_custom_name.text().strip()
                if not name:
                    QMessageBox.critical(mw, "Lỗi", "Vui lòng nhập tên hiệu ứng chuyển cảnh tự chọn!")
                    return
            else:
                name = trans_name

            duration_sec = mw.effects_widget.trans_duration_spin.value()
            apply_all = mw.effects_widget.trans_apply_all_chk.isChecked()

            if trans_name == "random":
                presets = [{"name": p["name"], "duration": p["duration"]} for p in TRANSITION_PRESETS]
            else:
                duration_us = int(duration_sec * 1_000_000)
                presets = [{"name": name, "duration": duration_us}]

            params = {
                "transition_presets": presets,
                "duration_sec": duration_sec,
                "apply_all": apply_all,
                "segment_type": segment,
                "mode": mode
            }
            self.run_keyframe_action("apply_transition", params)

        elif action == "speed":
            speed_mode = mw.effects_widget.speed_mode_combo.currentData()
            speed_val = mw.effects_widget.speed_val_spin.value()
            params = {
                "speed_mode": speed_mode,
                "speed_value": speed_val
            }
            self.run_keyframe_action("apply_speed", params)

        elif action == "scale":
            scale_pct = mw.effects_widget.scale_pct_spin.value()
            skip_first = mw.effects_widget.scale_skip_first_chk.isChecked()
            params = {
                "scale_percent": scale_pct,
                "skip_first": skip_first
            }
            self.run_keyframe_action("apply_scale", params)

    def build_preset_from_params(self, preset_id: str, segment: str) -> Optional[dict]:
        mw = self.main_window
        mapping = _PRESET_GROUP_MAP.get(preset_id)
        if not mapping:
            return None
        group, defaults = mapping
        pan_axis = defaults.get("pan_axis", "pos_x")

        if group == "zoom":
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {"property": "scale_uniform",
                     "from": mw.effects_widget.param_zoom_from.value(),
                     "to":   mw.effects_widget.param_zoom_to.value(),
                     "unit": "pct_base"}
                ]
            }
        elif group == "bounce":
            at = mw.effects_widget.param_bounce_peak_at.value() / 100.0
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {
                        "property": "scale_uniform",
                        "keyframes": [
                            {"at": 0.0, "value": mw.effects_widget.param_bounce_from.value()},
                            {"at": at,  "value": mw.effects_widget.param_bounce_peak.value()},
                            {"at": 1.0, "value": mw.effects_widget.param_bounce_end.value()},
                        ],
                        "unit": "pct_base"
                    }
                ]
            }
        elif group == "pan":
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {"property": "scale_uniform",
                     "from": mw.effects_widget.param_pan_zoom.value(),
                     "to":   mw.effects_widget.param_pan_zoom.value(),
                     "unit": "pct_base"},
                    {"property": pan_axis,
                     "from": mw.effects_widget.param_pan_from.value(),
                     "to":   mw.effects_widget.param_pan_to.value()}
                ]
            }
        elif group == "zoompan":
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {"property": "scale_uniform",
                     "from": mw.effects_widget.param_zp_zoom_from.value(),
                     "to":   mw.effects_widget.param_zp_zoom_to.value(),
                     "unit": "pct_base"},
                    {"property": pan_axis,
                     "from": mw.effects_widget.param_zp_pan_from.value(),
                     "to":   mw.effects_widget.param_zp_pan_to.value()}
                ]
            }
        elif group == "rotate":
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {"property": "scale_uniform",
                     "from": mw.effects_widget.param_rot_zoom.value(),
                     "to":   mw.effects_widget.param_rot_zoom.value(),
                     "unit": "pct_base"},
                    {"property": "rotation",
                     "from": mw.effects_widget.param_rot_from.value(),
                     "to":   mw.effects_widget.param_rot_to.value()}
                ]
            }
        elif group == "fade":
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {"property": "alpha",
                     "from": mw.effects_widget.param_fade_from.value(),
                     "to":   mw.effects_widget.param_fade_to.value()}
                ]
            }
        elif group == "fadeinout":
            in_end     = mw.effects_widget.param_fio_in_end.value() / 100.0
            out_start  = mw.effects_widget.param_fio_out_start.value() / 100.0
            return {
                "id": preset_id, "name": preset_id, "segment": segment,
                "operations": [
                    {
                        "property": "alpha",
                        "keyframes": [
                            {"at": 0.0,       "value": 0.0},
                            {"at": in_end,    "value": 1.0},
                            {"at": out_start, "value": 1.0},
                            {"at": 1.0,       "value": 0.0},
                        ]
                    }
                ]
            }
        return None
