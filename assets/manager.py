import uuid
import hashlib
import sqlite3
from pathlib import Path
from core.db import Database
from media_probe import probe_media

def get_md5_hash(file_path: str | Path) -> str:
    """
    Computes the MD5 hash of a file for duplicate detection.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return ""
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def _row_to_dict(row) -> dict:
    if row is None:
        return None
    return dict(row)

class AssetManager:
    @staticmethod
    def import_single_asset(
        file_path: str | Path,
        category_name: str = "overlay",
        tags: str = ""
    ) -> str | None:
        """
        Imports a media file into the asset library.
        Performs MD5 hash duplicate check and ffprobe scanning.
        """
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            return None

        md5 = get_md5_hash(path)
        if not md5:
            return None

        conn = Database.get_connection()
        cursor = conn.cursor()

        # 1. Deduplication: check if MD5 hash already exists
        cursor.execute("SELECT id FROM assets WHERE md5_hash = ?", (md5,))
        row = cursor.fetchone()
        if row:
            # Asset already imported (possibly at a different path)
            # Update path in case the file was moved
            cursor.execute("UPDATE assets SET path = ? WHERE id = ?", (str(path), row["id"]))
            conn.commit()
            return row["id"]

        # 2. Check if path already exists
        cursor.execute("SELECT id FROM assets WHERE path = ?", (str(path),))
        row = cursor.fetchone()
        if row:
            # Update hash and metadata
            cursor.execute("UPDATE assets SET md5_hash = ? WHERE id = ?", (md5, row["id"]))
            conn.commit()
            return row["id"]

        # 3. Probe the file
        asset_info = probe_media(path)
        if asset_info.error:
            # Failed to probe
            return None

        # 4. Create new asset record
        asset_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO assets (
                id, path, filename, media_type, duration_us,
                width, height, fps, tags, category_name, md5_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                str(path),
                path.name,
                asset_info.media_type,
                asset_info.duration_us,
                asset_info.width,
                asset_info.height,
                asset_info.fps,
                tags,
                category_name,
                md5
            )
        )
        conn.commit()
        return asset_id

    @staticmethod
    def get_asset(asset_id: str) -> dict | None:
        """
        Retrieves a single asset by its ID.
        """
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
        return _row_to_dict(cursor.fetchone())

    @staticmethod
    def list_assets(category_name: str = None, search_query: str = None) -> list[dict]:
        """
        Lists assets with optional filtering by category and fuzzy query matching.
        """
        conn = Database.get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM assets"
        conditions = []
        params = []

        if category_name and category_name.lower() != "all":
            conditions.append("category_name = ?")
            params.append(category_name)

        if search_query:
            conditions.append("(filename LIKE ? OR tags LIKE ?)")
            fuzzy = f"%{search_query}%"
            params.append(fuzzy)
            params.append(fuzzy)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY filename ASC"
        cursor.execute(query, tuple(params))
        return [_row_to_dict(r) for r in cursor.fetchall()]

    @staticmethod
    def delete_asset(asset_id: str) -> bool:
        """
        Deletes an asset from the library database.
        """
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def update_asset_metadata(asset_id: str, tags: str = None, category_name: str = None) -> bool:
        """
        Updates tags and category configuration for an asset.
        """
        conn = Database.get_connection()
        cursor = conn.cursor()

        fields = []
        params = []

        if tags is not None:
            fields.append("tags = ?")
            params.append(tags)

        if category_name is not None:
            fields.append("category_name = ?")
            params.append(category_name)

        if not fields:
            return False

        params.append(asset_id)
        query = f"UPDATE assets SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        conn.commit()
        return cursor.rowcount > 0
