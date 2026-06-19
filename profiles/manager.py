import uuid
import json
from pathlib import Path
from core.db import Database

def _row_to_dict(row) -> dict:
    if row is None:
        return None
    return dict(row)

class ProfileManager:
    @staticmethod
    def create_profile(
        name: str,
        canvas: str = '9:16',
        clip_min_sec: float = 5.0,
        clip_max_sec: float = 9.0,
        selection_mode: str = 'shuffle_bag',
        short_video_mode: str = 'stretch',
        recursive_scan: bool = False,
        subtitle_style_json: str = '{}',
        auto_keyframe: str = 'none',
        auto_transition: str = 'none',
        auto_transition_duration: float = 0.4,
        logo_path: str = '',
        logo_position: str = 'top_right',
        logo_scale: float = 15.0,
        logo_opacity: float = 1.0,
        anim_path: str = '',
        anim_position: str = 'bottom_center',
        anim_scale: float = 30.0,
        anim_timing: str = 'end',
        bgm_path: str = '',
        chroma_enabled: bool = False,
        chroma_mode: str = 'green',
        chroma_threshold: int = 32,
        chroma_shadow: int = 2,
        subtitle_karaoke: bool = False
    ) -> str:
        """
        Creates a new profile configuration.
        """
        conn = Database.get_connection()
        profile_id = str(uuid.uuid4())
        
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO profiles (
                id, name, canvas, clip_min_sec, clip_max_sec, selection_mode,
                short_video_mode, recursive_scan, subtitle_style_json,
                auto_keyframe, auto_transition, auto_transition_duration,
                logo_path, logo_position, logo_scale, logo_opacity, anim_path, anim_position,
                anim_scale, anim_timing, bgm_path, chroma_enabled, chroma_mode,
                chroma_threshold, chroma_shadow, subtitle_karaoke, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id, name, canvas, clip_min_sec, clip_max_sec, selection_mode,
                short_video_mode, 1 if recursive_scan else 0, subtitle_style_json,
                auto_keyframe, auto_transition, auto_transition_duration,
                logo_path, logo_position, logo_scale, logo_opacity, anim_path, anim_position,
                anim_scale, anim_timing, bgm_path, 
                1 if chroma_enabled else 0, chroma_mode, chroma_threshold, chroma_shadow,
                1 if subtitle_karaoke else 0, 1
            )
        )
        conn.commit()
        return profile_id

    @staticmethod
    def get_profile(profile_id: str) -> dict | None:
        """
        Retrieves a profile configuration by its ID.
        """
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,))
        return _row_to_dict(cursor.fetchone())

    @staticmethod
    def get_profile_by_name(name: str) -> dict | None:
        """
        Retrieves a profile configuration by its name.
        """
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM profiles WHERE name = ?", (name,))
        return _row_to_dict(cursor.fetchone())

    @staticmethod
    def list_profiles() -> list[dict]:
        """
        Lists all profile configurations in alphabetical order of their names.
        """
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM profiles ORDER BY name ASC")
        return [_row_to_dict(r) for r in cursor.fetchall()]

    @staticmethod
    def update_profile(profile_id: str, **kwargs) -> bool:
        """
        Updates profile configuration fields.
        Increments the profile version and records a version backup in profile_versions.
        """
        # Exclude read-only fields
        kwargs.pop("id", None)
        kwargs.pop("created_at", None)
        
        current = ProfileManager.get_profile(profile_id)
        if not current:
            return False

        conn = Database.get_connection()
        cursor = conn.cursor()

        # 1. Save historical version in profile_versions
        version_id = str(uuid.uuid4())
        # Convert row dict to json
        history_json = json.dumps(current, ensure_ascii=False)
        
        cursor.execute(
            """
            INSERT INTO profile_versions (id, profile_id, version, profile_data_json, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (version_id, profile_id, current["version"], history_json, kwargs.get("update_note", "Auto backup before update"))
        )

        # 2. Build dynamic update query
        kwargs.pop("update_note", None)
        kwargs["version"] = current["version"] + 1

        fields = []
        values = []
        for k, v in kwargs.items():
            if k in ("recursive_scan", "chroma_enabled", "subtitle_karaoke"):
                v = 1 if v else 0
            fields.append(f"{k} = ?")
            values.append(v)
            
        values.append(profile_id)
        
        query = f"UPDATE profiles SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, tuple(values))
        conn.commit()
        return True

    @staticmethod
    def delete_profile(profile_id: str) -> bool:
        """
        Deletes a profile configuration.
        """
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def clone_profile(profile_id: str, new_name: str) -> str | None:
        """
        Clones an existing profile under a new name.
        """
        current = ProfileManager.get_profile(profile_id)
        if not current:
            return None
            
        # Check if name is unique
        if ProfileManager.get_profile_by_name(new_name):
            return None

        conn = Database.get_connection()
        new_id = str(uuid.uuid4())
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO profiles (
                id, name, canvas, clip_min_sec, clip_max_sec, selection_mode,
                short_video_mode, recursive_scan, subtitle_style_json,
                auto_keyframe, auto_transition, auto_transition_duration,
                logo_path, logo_position, logo_scale, anim_path, anim_position,
                anim_scale, anim_timing, bgm_path, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id, new_name, current["canvas"], current["clip_min_sec"], current["clip_max_sec"], current["selection_mode"],
                current["short_video_mode"], current["recursive_scan"], current["subtitle_style_json"],
                current["auto_keyframe"], current["auto_transition"], current["auto_transition_duration"],
                current["logo_path"], current["logo_position"], current["logo_scale"], current["anim_path"], current["anim_position"],
                current["anim_scale"], current["anim_timing"], current["bgm_path"], 1
            )
        )
        conn.commit()
        return new_id

    @staticmethod
    def export_profile(profile_id: str, output_path: str | Path) -> bool:
        """
        Exports a profile to a JSON file.
        """
        current = ProfileManager.get_profile(profile_id)
        if not current:
            return False
            
        # Clean metadata before exporting
        export_data = current.copy()
        export_data.pop("id", None)
        export_data.pop("created_at", None)
        export_data["version"] = 1
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=4)
            return True
        except Exception:
            return False

    @staticmethod
    def import_profile(file_path: str | Path, override_name: str = None) -> str | None:
        """
        Imports a profile configuration from a JSON file.
        Gracefully resolves name conflicts by suffixing import names.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return None

        # Validate required fields
        if not isinstance(data, dict) or "name" not in data:
            return None

        name = override_name or data["name"]
        
        # Check name collision and suffix if necessary
        base_name = name
        counter = 1
        while ProfileManager.get_profile_by_name(name):
            name = f"{base_name}_import_{counter}"
            counter += 1

        # Use defaults if fields are missing
        canvas = data.get("canvas", "9:16")
        clip_min_sec = data.get("clip_min_sec", 5.0)
        clip_max_sec = data.get("clip_max_sec", 9.0)
        selection_mode = data.get("selection_mode", "shuffle_bag")
        short_video_mode = data.get("short_video_mode", "stretch")
        recursive_scan = bool(data.get("recursive_scan", 0))
        subtitle_style_json = data.get("subtitle_style_json", "{}")
        auto_keyframe = data.get("auto_keyframe", "none")
        auto_transition = data.get("auto_transition", "none")
        auto_transition_duration = data.get("auto_transition_duration", 0.4)
        logo_path = data.get("logo_path", "")
        logo_position = data.get("logo_position", "top_right")
        logo_scale = data.get("logo_scale", 15.0)
        anim_path = data.get("anim_path", "")
        anim_position = data.get("anim_position", "bottom_center")
        anim_scale = data.get("anim_scale", 30.0)
        anim_timing = data.get("anim_timing", "end")
        bgm_path = data.get("bgm_path", "")

        return ProfileManager.create_profile(
            name=name,
            canvas=canvas,
            clip_min_sec=clip_min_sec,
            clip_max_sec=clip_max_sec,
            selection_mode=selection_mode,
            short_video_mode=short_video_mode,
            recursive_scan=recursive_scan,
            subtitle_style_json=subtitle_style_json,
            auto_keyframe=auto_keyframe,
            auto_transition=auto_transition,
            auto_transition_duration=auto_transition_duration,
            logo_path=logo_path,
            logo_position=logo_position,
            logo_scale=logo_scale,
            anim_path=anim_path,
            anim_position=anim_position,
            anim_scale=anim_scale,
            anim_timing=anim_timing,
            bgm_path=bgm_path
        )

    @staticmethod
    def get_versions(profile_id: str) -> list[dict]:
        """
        Retrieves all historical version records for a profile.
        """
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM profile_versions WHERE profile_id = ? ORDER BY version DESC", (profile_id,))
        return [_row_to_dict(r) for r in cursor.fetchall()]

    @staticmethod
    def rollback_profile(profile_id: str, version_num: int) -> bool:
        """
        Rollbacks a profile configuration to a previous version record.
        """
        conn = Database.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM profile_versions WHERE profile_id = ? AND version = ?",
            (profile_id, version_num)
        )
        version_row = cursor.fetchone()
        if not version_row:
            return False

        version_data = json.loads(version_row["profile_data_json"])
        
        # Save the current state as backup
        current = ProfileManager.get_profile(profile_id)
        if current:
            version_id = str(uuid.uuid4())
            history_json = json.dumps(current, ensure_ascii=False)
            cursor.execute(
                """
                INSERT INTO profile_versions (id, profile_id, version, profile_data_json, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (version_id, profile_id, current["version"], history_json, f"Rollback backup of version {current['version']}")
            )

        # Update profiles to the old configuration
        new_version = max(current["version"] if current else 0, version_num) + 1
        
        cursor.execute(
            """
            UPDATE profiles SET
                canvas = ?, clip_min_sec = ?, clip_max_sec = ?, selection_mode = ?,
                short_video_mode = ?, recursive_scan = ?, subtitle_style_json = ?,
                auto_keyframe = ?, auto_transition = ?, auto_transition_duration = ?,
                logo_path = ?, logo_position = ?, logo_scale = ?, anim_path = ?,
                anim_position = ?, anim_scale = ?, anim_timing = ?, bgm_path = ?,
                version = ?
            WHERE id = ?
            """,
            (
                version_data["canvas"], version_data["clip_min_sec"], version_data["clip_max_sec"], version_data["selection_mode"],
                version_data["short_video_mode"], version_data["recursive_scan"], version_data["subtitle_style_json"],
                version_data["auto_keyframe"], version_data["auto_transition"], version_data["auto_transition_duration"],
                version_data["logo_path"], version_data["logo_position"], version_data["logo_scale"], version_data["anim_path"],
                version_data["anim_position"], version_data["anim_scale"], version_data["anim_timing"], version_data["bgm_path"],
                new_version, profile_id
            )
        )
        conn.commit()
        return True
