from datetime import datetime
from pathlib import Path
import re
import uuid
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QMessageBox
import capcut_keyframe_tool as keyframe_tool
from core.db import Database


class DoctorController(QObject):
    """Manages project drafts inspection, backup rotation, sync with SQLite, and repairs."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    def refresh_projects(self) -> None:
        mw = self.main_window
        mw.effects_widget.project_combo.clear()
        mw.history_widget.project_combo.clear()
        root_str = mw.setup_widget.draft_root.text().strip()
        if not root_str:
            return

        root_path = Path(root_str)
        if not root_path.exists() or not root_path.is_dir():
            return

        try:
            projects = []
            for p in root_path.iterdir():
                if p.is_dir() and not p.name.startswith('.'):
                    if (p / 'draft_content.json').exists() or (p / 'Timelines').exists():
                        projects.append(p.name)

            projects.sort()
            mw.effects_widget.project_combo.blockSignals(True)
            mw.history_widget.project_combo.blockSignals(True)

            mw.effects_widget.project_combo.addItems(projects)
            mw.history_widget.project_combo.addItems(projects)

            mw.effects_widget.project_combo.blockSignals(False)
            mw.history_widget.project_combo.blockSignals(False)

            if projects:
                mw.effects_widget.project_combo.setCurrentIndex(0)
                mw.history_widget.project_combo.setCurrentIndex(0)
                self.refresh_backups_for_project(projects[0])
        except Exception as e:
            mw._append_log(f"[LỖI] Không thể quét danh sách dự án: {e}")

    def refresh_backups_for_project(self, project_name: str) -> None:
        mw = self.main_window
        mw.history_widget.backup_combo.clear()
        if not project_name:
            mw.history_widget.btn_restore_backup.setEnabled(False)
            return

        root_str = mw.setup_widget.draft_root.text().strip()
        if not root_str:
            return

        project_dir = Path(root_str) / project_name
        primary_draft, _ = keyframe_tool.resolve_project_draft_paths(project_dir)

        if not primary_draft or not primary_draft.exists():
            mw.history_widget.btn_restore_backup.setEnabled(False)
            return

        draft_dir = primary_draft.parent
        project_dir_str = str(project_dir.resolve())

        # 1. Quét các tệp sao lưu .bak thực tế trên đĩa
        scanned_backups = {}
        try:
            if draft_dir.exists():
                for f in draft_dir.iterdir():
                    if f.is_file() and f.name.startswith(primary_draft.name) and f.suffix == '.bak':
                        scanned_backups[str(f.resolve())] = f
        except Exception as e:
            mw._append_log(f"[LỖI] Không thể quét danh sách bản sao lưu trên đĩa: {e}")
            mw.history_widget.btn_restore_backup.setEnabled(False)
            return

        # 2. Đồng bộ hóa với SQLite
        try:
            conn = Database.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, backup_path, timestamp, note FROM backups WHERE project_dir = ?",
                (project_dir_str,)
            )
            db_records = cursor.fetchall()
            db_paths = {row["backup_path"]: row for row in db_records}

            # Xóa các bản ghi mồ côi (có trong DB nhưng không có trên đĩa)
            for db_path_str in list(db_paths.keys()):
                if db_path_str not in scanned_backups:
                    cursor.execute("DELETE FROM backups WHERE backup_path = ?", (db_path_str,))
                    conn.commit()
                    del db_paths[db_path_str]

            # Thêm các tệp mới quét được trên đĩa nhưng chưa có trong DB
            for disk_path_str, f in scanned_backups.items():
                if disk_path_str not in db_paths:
                    backup_id = str(uuid.uuid4())
                    ts_str = ""
                    match = re.search(r"(\d{8})_(\d{6})", f.name)
                    if match:
                        try:
                            dt = datetime.strptime(match.group(0), "%Y%m%d_%H%M%S")
                            ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass
                    if not ts_str:
                        ts_str = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                    cursor.execute(
                        """
                        INSERT INTO backups (id, project_dir, backup_path, timestamp, note)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (backup_id, project_dir_str, disk_path_str, ts_str, "Bản sao lưu tự động (đồng bộ đĩa)")
                    )
                    conn.commit()

            # 3. Nạp danh sách hoàn chỉnh từ SQLite đã được đồng bộ
            cursor.execute(
                "SELECT backup_path, timestamp, note FROM backups WHERE project_dir = ? ORDER BY timestamp DESC",
                (project_dir_str,)
            )
            rows = cursor.fetchall()

            for row in rows:
                bp = Path(row["backup_path"])
                display_text = f"{row['timestamp']} - {bp.name}"
                if row["note"]:
                    display_text += f" ({row['note']})"
                mw.history_widget.backup_combo.addItem(display_text, row["backup_path"])

            mw.history_widget.btn_restore_backup.setEnabled(len(rows) > 0)

        except Exception as e:
            mw._append_log(f"[LỖI] Không thể đồng bộ SQLite bản sao lưu: {e}")
            mw.history_widget.btn_restore_backup.setEnabled(False)

    def restore_backup_click(self) -> None:
        mw = self.main_window
        idx = mw.history_widget.backup_combo.currentIndex()
        if idx < 0:
            return
        backup_path_str = mw.history_widget.backup_combo.itemData(idx)
        if not backup_path_str:
            return

        backup_path = Path(backup_path_str)
        backup_display = mw.history_widget.backup_combo.itemText(idx)

        reply = QMessageBox.question(
            mw,
            "Xác nhận khôi phục",
            f"Bạn có thực sự muốn khôi phục timeline dự án về bản sao lưu:\n'{backup_display}' không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            params = {
                "backup_path": str(backup_path)
            }
            proj = mw.history_widget.project_combo.currentText()
            mw._run_keyframe_action("restore_backup", params, project_name=proj)

    def clean_backups_click(self) -> None:
        mw = self.main_window
        proj = mw.history_widget.project_combo.currentText()
        if not proj:
            QMessageBox.warning(mw, "Cảnh báo", "Vui lòng chọn một dự án trước!")
            return

        root_str = mw.setup_widget.draft_root.text().strip()
        if not root_str:
            return

        project_dir = Path(root_str) / proj
        primary_draft, _ = keyframe_tool.resolve_project_draft_paths(project_dir)
        if not primary_draft:
            return

        keep_days = int(mw.history_widget.backup_keep_days.value())

        try:
            import draft_doctor
            deleted, skipped = draft_doctor.clean_project_backups(primary_draft, keep_days)
        except Exception as e:
            QMessageBox.critical(mw, "Lỗi", f"Không thể dọn backup: {e}")
            return

        mw._append_log(
            f"[THÀNH CÔNG] Dọn backup: đã xóa {deleted} file, giữ lại {skipped} file (chưa đủ {keep_days} ngày)."
        )
        QMessageBox.information(
            mw, "Hoàn thành",
            f"Đã xóa {deleted} tệp sao lưu cũ hơn {keep_days} ngày khỏi đĩa và SQLite.\nGiữ lại {skipped} tệp gần đây."
        )
        self.refresh_backups_for_project(proj)

    def repair_project_click(self) -> None:
        mw = self.main_window
        proj = mw.history_widget.project_combo.currentText()
        if not proj:
            QMessageBox.critical(mw, "Lỗi", "Vui lòng chọn một dự án nháp mục tiêu cần sửa!")
            return

        reply = QMessageBox.question(
            mw,
            "Xác nhận tự động sửa lỗi",
            f"Bạn có chắc muốn tự động sửa các lỗi tương thích, đường dẫn và liên kết file của dự án '{proj}' không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        media_dir_val = mw.history_widget.relink_media_dir.text().strip()
        if not media_dir_val:
            media_dir_val = mw.setup_widget.media_dir.text().strip()

        params = {
            "media_dir": media_dir_val
        }
        mw._run_keyframe_action("repair_project", params, project_name=proj)
