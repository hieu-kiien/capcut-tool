import json
import random
import string
import urllib.request
import urllib.error
from datetime import datetime
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QMessageBox, QInputDialog, QDialog, QListWidget, QDialogButtonBox, QVBoxLayout, QLabel, QLineEdit
from profiles.manager import ProfileManager
from core.db import Database
from app.utils import hex_to_rgb_tuple, rgb_tuple_to_hex

class ProfileController(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    def _refresh_profiles_list(self, select_name: str = None) -> None:
        self.main_window.profile_combo.blockSignals(True)
        self.main_window.profile_combo.clear()
        
        profiles = ProfileManager.list_profiles()
        for p in profiles:
            self.main_window.profile_combo.addItem(p["name"], p["id"])
            
        if select_name:
            idx = self.main_window.profile_combo.findText(select_name)
            if idx >= 0:
                self.main_window.profile_combo.setCurrentIndex(idx)
        else:
            last_profile = getattr(self.main_window, "_current_profile_name", "Mặc định")
            idx = self.main_window.profile_combo.findText(last_profile)
            if idx >= 0:
                self.main_window.profile_combo.setCurrentIndex(idx)
            else:
                self.main_window.profile_combo.setCurrentIndex(0)
                
        self.main_window.profile_combo.blockSignals(False)
        self._on_profile_selection_changed()

    @Slot()
    def _on_profile_selection_changed(self) -> None:
        # Save active profile if set before switching
        if getattr(self.main_window, "_current_profile_id", None):
            self._save_current_profile()

        idx = self.main_window.profile_combo.currentIndex()
        if idx < 0:
            return
            
        profile_id = self.main_window.profile_combo.itemData(idx)
        profile = ProfileManager.get_profile(profile_id)
        if profile:
            self._populate_ui_from_profile(profile)

    def _populate_ui_from_profile(self, profile: dict) -> None:
        if not profile:
            return
            
        self.main_window._current_profile_id = profile["id"]
        self.main_window._current_profile_name = profile["name"]
        
        # Populate SetupWidget inputs
        if profile["canvas"] == "16:9":
            self.main_window.setup_widget.ratio_16_9.setChecked(True)
        else:
            self.main_window.setup_widget.ratio_9_16.setChecked(True)
            
        self.main_window.setup_widget.clip_min.setValue(profile["clip_min_sec"])
        self.main_window.setup_widget.clip_max.setValue(profile["clip_max_sec"])
        
        mode_str = profile["selection_mode"]
        if "sequential" in mode_str:
            self.main_window.setup_widget.selection_mode.setCurrentIndex(1)
        elif "random" in mode_str:
            self.main_window.setup_widget.selection_mode.setCurrentIndex(2)
        elif "duplicate_then_shuffle" in mode_str:
            self.main_window.setup_widget.selection_mode.setCurrentIndex(3)
        elif "shuffle_duplicates_only" in mode_str:
            self.main_window.setup_widget.selection_mode.setCurrentIndex(4)
        else:
            self.main_window.setup_widget.selection_mode.setCurrentIndex(0)
            
        short_video_mode = profile["short_video_mode"]
        if short_video_mode == "loop":
            self.main_window.setup_widget.short_video_mode.setCurrentIndex(1)
        else:
            self.main_window.setup_widget.short_video_mode.setCurrentIndex(0)
            
        self.main_window.setup_widget.recursive_scan.setChecked(bool(profile["recursive_scan"]))
        
        auto_kf_id = profile["auto_keyframe"]
        if auto_kf_id:
            idx = self.main_window.setup_widget.auto_kf_combo.findData(auto_kf_id)
            self.main_window.setup_widget.auto_kf_combo.setCurrentIndex(max(0, idx))
            
        auto_trans_id = profile["auto_transition"]
        if auto_trans_id:
            idx = self.main_window.setup_widget.auto_trans_combo.findData(auto_trans_id)
            self.main_window.setup_widget.auto_trans_combo.setCurrentIndex(max(0, idx))
            
        self.main_window.setup_widget.auto_trans_dur.setValue(profile["auto_transition_duration"])
        
        # Populate EffectsWidget inputs
        self.main_window.effects_widget.logo_path.setText(profile["logo_path"])
        logo_pos = profile["logo_position"]
        idx = self.main_window.effects_widget.logo_position.findData(logo_pos)
        if idx >= 0:
            self.main_window.effects_widget.logo_position.setCurrentIndex(idx)
        self.main_window.effects_widget.logo_scale.setValue(profile["logo_scale"])
        self.main_window.effects_widget.logo_opacity.setValue(int(profile.get("logo_opacity", 1.0) * 100))
        
        self.main_window.effects_widget.anim_path.setText(profile["anim_path"])
        anim_pos = profile["anim_position"]
        idx = self.main_window.effects_widget.anim_position.findData(anim_pos)
        if idx >= 0:
            self.main_window.effects_widget.anim_position.setCurrentIndex(idx)
        self.main_window.effects_widget.anim_scale.setValue(profile["anim_scale"])
        
        anim_time = profile["anim_timing"]
        idx = self.main_window.effects_widget.anim_timing.findData(anim_time)
        if idx >= 0:
            self.main_window.effects_widget.anim_timing.setCurrentIndex(idx)
            
        self.main_window.effects_widget.chroma_enabled.setChecked(bool(profile.get("chroma_enabled", 0)))
        chroma_m = profile.get("chroma_mode", "green")
        idx = self.main_window.effects_widget.chroma_mode.findData(chroma_m)
        if idx >= 0:
            self.main_window.effects_widget.chroma_mode.setCurrentIndex(idx)
        self.main_window.effects_widget.chroma_threshold.setValue(profile.get("chroma_threshold", 32))
        self.main_window.effects_widget.chroma_shadow.setValue(profile.get("chroma_shadow", 2))
        self.main_window.effects_widget.subtitle_karaoke.setChecked(bool(profile.get("subtitle_karaoke", 0)))
            
        self.main_window.setup_widget.bgm_path.setText(profile["bgm_path"])
        
        # Populate subtitle styles from profile
        subtitle_style_json = profile.get("subtitle_style_json", "{}")
        if subtitle_style_json:
            try:
                sub_style = json.loads(subtitle_style_json)
                font = sub_style.get("font", "SystemFont")
                idx = self.main_window.setup_widget.subtitle_font.findText(font)
                if idx >= 0:
                    self.main_window.setup_widget.subtitle_font.setCurrentIndex(idx)
                    
                self.main_window.setup_widget.subtitle_font_size.setValue(sub_style.get("font_size", 6.0))
                self.main_window.setup_widget.subtitle_color.setText(sub_style.get("color", "#FFFFFF"))
                
                align = sub_style.get("align", "bottom_center")
                idx = self.main_window.setup_widget.subtitle_align.findData(align)
                if idx >= 0:
                    self.main_window.setup_widget.subtitle_align.setCurrentIndex(idx)
                    
                self.main_window.setup_widget.subtitle_outline_width.setValue(sub_style.get("outline_width", 40.0))
                self.main_window.setup_widget.subtitle_shadow_alpha.setValue(sub_style.get("shadow_alpha", 0.8))
                self.main_window.setup_widget.subtitle_shadow_distance.setValue(sub_style.get("shadow_distance", 5.0))
                
                self.main_window.setup_widget.subtitle_bold.setChecked(sub_style.get("bold", True))
                self.main_window.setup_widget.subtitle_italic.setChecked(sub_style.get("italic", False))
                self.main_window.setup_widget.subtitle_underline.setChecked(sub_style.get("underline", False))
                self.main_window.setup_widget.subtitle_shadow.setChecked(sub_style.get("shadow", True))
                self.main_window.setup_widget._update_subtitle_preview()
            except Exception:
                pass
                
        self.main_window._update_dashboard_summary()

    @Slot()
    def _save_current_profile(self, silent: bool = True) -> None:
        if not getattr(self.main_window, "_current_profile_id", None):
            return
            
        canvas = "16:9" if self.main_window.setup_widget.ratio_16_9.isChecked() else "9:16"
        clip_min_sec = self.main_window.setup_widget.clip_min.value()
        clip_max_sec = self.main_window.setup_widget.clip_max.value()
        
        selection_idx = self.main_window.setup_widget.selection_mode.currentIndex()
        selection_mode = {
            0: "shuffle_bag",
            1: "sequential",
            2: "random",
            3: "duplicate_then_shuffle",
            4: "shuffle_duplicates_only",
        }.get(selection_idx, "shuffle_bag")
        
        short_video_mode = "loop" if self.main_window.setup_widget.short_video_mode.currentIndex() == 1 else "stretch"
        recursive_scan = 1 if self.main_window.setup_widget.recursive_scan.isChecked() else 0
        auto_keyframe = self.main_window.setup_widget.auto_kf_combo.currentData() or "none"
        auto_transition = self.main_window.setup_widget.auto_trans_combo.currentData() or "none"
        auto_transition_duration = self.main_window.setup_widget.auto_trans_dur.value()
        
        logo_path = self.main_window.effects_widget.logo_path.text().strip()
        logo_position = self.main_window.effects_widget.logo_position.currentData() or "top_right"
        logo_scale = self.main_window.effects_widget.logo_scale.value()
        logo_opacity = self.main_window.effects_widget.logo_opacity.value() / 100.0
        
        anim_path = self.main_window.effects_widget.anim_path.text().strip()
        anim_position = self.main_window.effects_widget.anim_position.currentData() or "bottom_center"
        anim_scale = self.main_window.effects_widget.anim_scale.value()
        anim_timing = self.main_window.effects_widget.anim_timing.currentData() or "end"
        
        chroma_enabled = self.main_window.effects_widget.chroma_enabled.isChecked()
        chroma_mode = self.main_window.effects_widget.chroma_mode.currentData() or "green"
        chroma_threshold = self.main_window.effects_widget.chroma_threshold.value()
        chroma_shadow = self.main_window.effects_widget.chroma_shadow.value()
        subtitle_karaoke = self.main_window.effects_widget.subtitle_karaoke.isChecked()
        
        bgm_path = self.main_window.setup_widget.bgm_path.text().strip()
        
        # Build subtitle style JSON
        sub_style = {
            "font": self.main_window.setup_widget.subtitle_font.currentText(),
            "font_size": self.main_window.setup_widget.subtitle_font_size.value(),
            "color": self.main_window.setup_widget.subtitle_color.text().strip(),
            "align": self.main_window.setup_widget.subtitle_align.currentData() or "bottom_center",
            "outline_width": self.main_window.setup_widget.subtitle_outline_width.value(),
            "shadow_alpha": self.main_window.setup_widget.subtitle_shadow_alpha.value(),
            "shadow_distance": self.main_window.setup_widget.subtitle_shadow_distance.value(),
            "bold": self.main_window.setup_widget.subtitle_bold.isChecked(),
            "italic": self.main_window.setup_widget.subtitle_italic.isChecked(),
            "underline": self.main_window.setup_widget.subtitle_underline.isChecked(),
            "shadow": self.main_window.setup_widget.subtitle_shadow.isChecked()
        }
        subtitle_style_json = json.dumps(sub_style, ensure_ascii=False)
        
        success = ProfileManager.update_profile(
            self.main_window._current_profile_id,
            canvas=canvas,
            clip_min_sec=clip_min_sec,
            clip_max_sec=clip_max_sec,
            selection_mode=selection_mode,
            short_video_mode=short_video_mode,
            recursive_scan=recursive_scan,
            auto_keyframe=auto_keyframe,
            auto_transition=auto_transition,
            auto_transition_duration=auto_transition_duration,
            logo_path=logo_path,
            logo_position=logo_position,
            logo_scale=logo_scale,
            logo_opacity=logo_opacity,
            anim_path=anim_path,
            anim_position=anim_position,
            anim_scale=anim_scale,
            anim_timing=anim_timing,
            bgm_path=bgm_path,
            chroma_enabled=chroma_enabled,
            chroma_mode=chroma_mode,
            chroma_threshold=chroma_threshold,
            chroma_shadow=chroma_shadow,
            subtitle_karaoke=subtitle_karaoke,
            subtitle_style_json=subtitle_style_json,
            update_note=f"Đã lưu thủ công từ giao diện lúc {datetime.now().strftime('%H:%M:%S')}"
        )
        
        if success:
            self.main_window._append_log(f"[HỆ THỐNG] Đã lưu thay đổi vào hồ sơ '{self.main_window._current_profile_name}' thành công.")
            if not silent and hasattr(self.main_window, "show_toast"):
                self.main_window.show_toast("Thành công", f"Đã lưu cấu hình hồ sơ '{self.main_window._current_profile_name}' thành công!", level="success")
        else:
            self.main_window._append_log("[LỖI] Không thể cập nhật hồ sơ cấu hình.")

    @Slot()
    def _create_new_profile_click(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self.main_window, "Tạo hồ sơ mới", "Nhập tên hồ sơ mới (không dấu):")
        if not ok or not name.strip():
            return
            
        name = name.strip()
        if ProfileManager.get_profile_by_name(name):
            QMessageBox.warning(self.main_window, "Lỗi", f"Hồ sơ '{name}' đã tồn tại!")
            return
            
        p_id = ProfileManager.create_profile(name=name)
        if p_id:
            self._refresh_profiles_list(select_name=name)
            self.main_window._append_log(f"[HỆ THỐNG] Đã tạo hồ sơ cấu hình mới: '{name}'")

    @Slot()
    def _clone_profile_click(self) -> None:
        if not getattr(self.main_window, "_current_profile_id", None):
            return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self.main_window, "Nhân bản hồ sơ", f"Nhập tên mới cho bản sao của '{self.main_window._current_profile_name}':")
        if not ok or not name.strip():
            return
            
        name = name.strip()
        if ProfileManager.get_profile_by_name(name):
            QMessageBox.warning(self.main_window, "Lỗi", f"Hồ sơ '{name}' đã tồn tại!")
            return
            
        new_id = ProfileManager.clone_profile(self.main_window._current_profile_id, name)
        if new_id:
            self._refresh_profiles_list(select_name=name)
            self.main_window._append_log(f"[HỆ THỐNG] Đã nhân bản hồ sơ thành '{name}'")

    @Slot()
    def _rename_profile_click(self) -> None:
        if not getattr(self.main_window, "_current_profile_id", None):
            return
        if self.main_window._current_profile_name == "Mặc định":
            QMessageBox.warning(self.main_window, "Không cho phép", "Không thể đổi tên hồ sơ mặc định!")
            return
            
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self.main_window, "Đổi tên hồ sơ", "Nhập tên mới:", text=self.main_window._current_profile_name)
        if not ok or not name.strip() or name.strip() == self.main_window._current_profile_name:
            return
            
        name = name.strip()
        if ProfileManager.get_profile_by_name(name):
            QMessageBox.warning(self.main_window, "Lỗi", f"Hồ sơ '{name}' đã tồn tại!")
            return
            
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE profiles SET name = ? WHERE id = ?", (name, self.main_window._current_profile_id))
        conn.commit()
        
        self._refresh_profiles_list(select_name=name)
        self.main_window._append_log(f"[HỆ THỐNG] Đã đổi tên hồ sơ thành '{name}'")

    @Slot()
    def _delete_profile_click(self) -> None:
        if not getattr(self.main_window, "_current_profile_id", None):
            return
        if self.main_window._current_profile_name == "Mặc định":
            QMessageBox.warning(self.main_window, "Không cho phép", "Không thể xóa hồ sơ mặc định!")
            return
            
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa hồ sơ '{self.main_window._current_profile_name}' và tất cả các phiên bản lịch sử của nó?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        deleted = ProfileManager.delete_profile(self.main_window._current_profile_id)
        if deleted:
            self.main_window._append_log(f"[HỆ THỐNG] Đã xóa hồ sơ '{self.main_window._current_profile_name}'")
            self.main_window._current_profile_name = "Mặc định"
            self._refresh_profiles_list(select_name="Mặc định")

    @Slot()
    def _export_profile_click(self) -> None:
        if not getattr(self.main_window, "_current_profile_id", None):
            return
            
        profile_data = ProfileManager.get_profile(self.main_window._current_profile_id)
        if not profile_data:
            QMessageBox.critical(self.main_window, "Lỗi", "Không thể tìm thấy dữ liệu cấu hình hồ sơ hiện tại.")
            return

        import random
        import string
        import urllib.request
        
        # Sinh Share Code ngẫu nhiên
        code = "PF-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Loại bỏ các trường cục bộ
        export_data = dict(profile_data)
        export_data.pop('id', None)
        export_data.pop('created_at', None)
        export_data.pop('version', None)
        
        url = f"https://kvdb.io/capcut_draft_studio_v1/{code}"
        
        self.main_window._append_log(f"[HỆ THỐNG] Đang xuất hồ sơ '{self.main_window._current_profile_name}' lên đám mây...")
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(export_data, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='PUT'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in (200, 201):
                    self.main_window._append_log(f"[THÀNH CÔNG] Đã xuất hồ sơ lên đám mây. Mã chia sẻ: {code}")
                    from PySide6.QtWidgets import QInputDialog
                    QInputDialog.getText(
                        self,
                        "Xuất hồ sơ thành công",
                        "Đã xuất cấu hình thành công! Hãy sao chép Mã chia sẻ (Share Code) bên dưới:",
                        QLineEdit.EchoMode.Normal,
                        code
                    )
                else:
                    raise RuntimeError(f"Máy chủ phản hồi với mã trạng thái: {response.status}")
        except Exception as e:
            self.main_window._append_log(f"[LỖI] Không thể xuất hồ sơ lên đám mây: {e}")
            QMessageBox.critical(self.main_window, "Lỗi", f"Không thể xuất hồ sơ lên đám mây: {e}")

    @Slot()
    def _import_profile_click(self) -> None:
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        code, ok = QInputDialog.getText(self.main_window, "Nhập hồ sơ từ đám mây", "Nhập Mã chia sẻ (Share Code):")
        if not ok or not code.strip():
            return
        code = code.strip().upper()
        
        import urllib.request
        url = f"https://kvdb.io/capcut_draft_studio_v1/{code}"
        
        self.main_window._append_log(f"[HỆ THỐNG] Đang tải cấu hình cho mã chia sẻ '{code}'...")
        
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=10) as response:
                data_bytes = response.read()
                profile_data = json.loads(data_bytes.decode('utf-8'))
        except urllib.error.HTTPError as he:
            if he.code == 404:
                self.main_window._append_log(f"[LỖI] Mã chia sẻ '{code}' không tồn tại hoặc đã hết hạn.")
                QMessageBox.critical(self.main_window, "Lỗi", "Mã chia sẻ không tồn tại hoặc đã hết hạn!")
            else:
                self.main_window._append_log(f"[LỖI] Lỗi HTTP khi tải cấu hình: {he}")
                QMessageBox.critical(self.main_window, "Lỗi", f"Lỗi kết nối máy chủ: {he}")
            return
        except Exception as e:
            self.main_window._append_log(f"[LỖI] Lỗi kết nối đám mây: {e}")
            QMessageBox.critical(self.main_window, "Lỗi", f"Không thể tải cấu hình từ đám mây: {e}")
            return
            
        original_name = profile_data.get('name', 'Đồng bộ')
        new_name = original_name
        
        counter = 1
        while ProfileManager.get_profile_by_name(new_name):
            new_name = f"{original_name} (Đồng bộ {counter})"
            counter += 1
            
        try:
            new_id = ProfileManager.create_profile(
                name=new_name,
                canvas=profile_data.get('canvas', '9:16'),
                clip_min_sec=float(profile_data.get('clip_min_sec', 5.0)),
                clip_max_sec=float(profile_data.get('clip_max_sec', 9.0)),
                selection_mode=profile_data.get('selection_mode', 'shuffle_bag'),
                short_video_mode=profile_data.get('short_video_mode', 'stretch'),
                recursive_scan=bool(profile_data.get('recursive_scan', False)),
                subtitle_style_json=profile_data.get('subtitle_style_json', '{}'),
                auto_keyframe=profile_data.get('auto_keyframe', 'none'),
                auto_transition=profile_data.get('auto_transition', 'none'),
                auto_transition_duration=float(profile_data.get('auto_transition_duration', 0.4)),
                logo_path=profile_data.get('logo_path', ''),
                logo_position=profile_data.get('logo_position', 'top_right'),
                logo_scale=float(profile_data.get('logo_scale', 15.0)),
                anim_path=profile_data.get('anim_path', ''),
                anim_position=profile_data.get('anim_position', 'bottom_center'),
                anim_scale=float(profile_data.get('anim_scale', 30.0)),
                anim_timing=profile_data.get('anim_timing', 'end'),
                bgm_path=profile_data.get('bgm_path', '')
            )
            
            if new_id:
                self._refresh_profiles_list(select_name=new_name)
                self.main_window._append_log(f"[THÀNH CÔNG] Đã nhập hồ sơ mới: '{new_name}'")
                QMessageBox.information(self.main_window, "Thành công", f"Đã nhập hồ sơ '{new_name}' thành công từ đám mây!")
            else:
                raise RuntimeError("Không thể tạo hồ sơ mới trong cơ sở dữ liệu.")
        except Exception as e:
            self.main_window._append_log(f"[LỖI] Không thể lưu cấu hình nhập về: {e}")
            QMessageBox.critical(self.main_window, "Lỗi", f"Không thể lưu cấu hình: {e}")

    @Slot()
    def _rollback_profile_click(self) -> None:
        if not getattr(self.main_window, "_current_profile_id", None):
            return
            
        versions = ProfileManager.get_versions(self.main_window._current_profile_id)
        if not versions:
            QMessageBox.information(self.main_window, "Lịch sử phiên bản", "Hồ sơ này chưa có lịch sử chỉnh sửa.")
            return
            
        from PySide6.QtWidgets import QDialog, QListWidget, QDialogButtonBox
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle(f"Lịch sử phiên bản - {self.main_window._current_profile_name}")
        dialog.resize(450, 300)
        
        dialog_layout = QVBoxLayout(dialog)
        
        lbl = QLabel("Chọn một phiên bản để hoàn tác (Rollback):")
        dialog_layout.addWidget(lbl)
        
        list_widget = QListWidget()
        for v in versions:
            date_str = v.get("created_at", "")
            ver_num = v.get("version", 0)
            note = v.get("note", "Không có mô tả")
            list_widget.addItem(f"Phiên bản {ver_num} ({date_str}) - {note}")
            
        dialog_layout.addWidget(list_widget)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(btn_box)
        
        if dialog.exec() == QDialog.Accepted:
            row_idx = list_widget.currentRow()
            if row_idx >= 0:
                selected_ver = versions[row_idx]["version"]
                success = ProfileManager.rollback_profile(self.main_window._current_profile_id, selected_ver)
                if success:
                    profile = ProfileManager.get_profile(self.main_window._current_profile_id)
                    self._populate_ui_from_profile(profile)
                    self.main_window._append_log(f"[HỆ THỐNG] Đã hoàn tác hồ sơ '{self.main_window._current_profile_name}' về phiên bản {selected_ver}.")
                    QMessageBox.information(self.main_window, "Thành công", f"Đã hoàn tác cấu hình về phiên bản {selected_ver}!")
                else:
                    QMessageBox.critical(self.main_window, "Lỗi", "Không thể khôi phục phiên bản.")

