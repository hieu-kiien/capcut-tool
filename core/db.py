import sqlite3
from pathlib import Path

# DB file path in the project root
DB_PATH = Path(__file__).resolve().parents[1] / "draft_studio.db"

class Database:
    _conn = None

    @classmethod
    def get_connection(cls, db_path: str | Path = None) -> sqlite3.Connection:
        """
        Gets a connection to the SQLite database.
        Ensures foreign keys are enabled and journal mode is WAL.
        """
        if cls._conn is None:
            target_path = Path(db_path) if db_path else DB_PATH
            # Ensure parent directories exist
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Connect to database (check_same_thread=False allows multi-thread read/write safety under WAL)
            cls._conn = sqlite3.connect(str(target_path), check_same_thread=False)
            cls._conn.row_factory = sqlite3.Row
            
            # Configure database behavior
            cls._conn.execute("PRAGMA journal_mode=WAL;")
            cls._conn.execute("PRAGMA foreign_keys=ON;")
            
        return cls._conn

    @classmethod
    def init_db(cls, db_path: str | Path = None) -> None:
        """
        Initializes the SQLite database schema if tables do not exist.
        """
        conn = cls.get_connection(db_path)
        cursor = conn.cursor()
        
        # 1. profiles table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            canvas TEXT DEFAULT '9:16',
            clip_min_sec REAL DEFAULT 5.0,
            clip_max_sec REAL DEFAULT 9.0,
            selection_mode TEXT DEFAULT 'shuffle_bag',
            short_video_mode TEXT DEFAULT 'stretch',
            recursive_scan INTEGER DEFAULT 0,
            subtitle_style_json TEXT DEFAULT '{}',
            auto_keyframe TEXT DEFAULT 'none',
            auto_transition TEXT DEFAULT 'none',
            auto_transition_duration REAL DEFAULT 0.4,
            logo_path TEXT DEFAULT '',
            logo_position TEXT DEFAULT 'top_right',
            logo_scale REAL DEFAULT 15.0,
            logo_opacity REAL DEFAULT 1.0,
            anim_path TEXT DEFAULT '',
            anim_position TEXT DEFAULT 'bottom_center',
            anim_scale REAL DEFAULT 30.0,
            anim_timing TEXT DEFAULT 'end',
            bgm_path TEXT DEFAULT '',
            chroma_enabled INTEGER DEFAULT 0,
            chroma_mode TEXT DEFAULT 'green',
            chroma_threshold INTEGER DEFAULT 32,
            chroma_shadow INTEGER DEFAULT 2,
            subtitle_karaoke INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """)
        
        # 2. profile_versions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile_versions (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            profile_data_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            note TEXT,
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        );
        """)

        # 3. projects table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            draft_root TEXT NOT NULL,
            profile_id TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE SET NULL
        );
        """)

        # 4. templates table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            profile_id TEXT,
            assets_mapping_json TEXT DEFAULT '{}',
            version INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE SET NULL
        );
        """)

        # 5. assets table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            path TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            media_type TEXT NOT NULL,
            duration_us INTEGER DEFAULT 0,
            width INTEGER DEFAULT 0,
            height INTEGER DEFAULT 0,
            fps REAL DEFAULT 0.0,
            tags TEXT DEFAULT '',
            category_name TEXT DEFAULT 'overlay',
            md5_hash TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """)
        
        # Self-healing migration for assets table
        cursor.execute("PRAGMA table_info(assets);")
        columns = [row["name"] for row in cursor.fetchall()]
        if "category_name" not in columns:
            cursor.execute("ALTER TABLE assets ADD COLUMN category_name TEXT DEFAULT 'overlay';")
        if "md5_hash" not in columns:
            cursor.execute("ALTER TABLE assets ADD COLUMN md5_hash TEXT DEFAULT '';")

        # Self-healing migration for profiles table
        cursor.execute("PRAGMA table_info(profiles);")
        columns_profiles = [row["name"] for row in cursor.fetchall()]
        if "logo_opacity" not in columns_profiles:
            cursor.execute("ALTER TABLE profiles ADD COLUMN logo_opacity REAL DEFAULT 1.0;")
        if "chroma_enabled" not in columns_profiles:
            cursor.execute("ALTER TABLE profiles ADD COLUMN chroma_enabled INTEGER DEFAULT 0;")
        if "chroma_mode" not in columns_profiles:
            cursor.execute("ALTER TABLE profiles ADD COLUMN chroma_mode TEXT DEFAULT 'green';")
        if "chroma_threshold" not in columns_profiles:
            cursor.execute("ALTER TABLE profiles ADD COLUMN chroma_threshold INTEGER DEFAULT 32;")
        if "chroma_shadow" not in columns_profiles:
            cursor.execute("ALTER TABLE profiles ADD COLUMN chroma_shadow INTEGER DEFAULT 2;")
        if "subtitle_karaoke" not in columns_profiles:
            cursor.execute("ALTER TABLE profiles ADD COLUMN subtitle_karaoke INTEGER DEFAULT 0;")

        # 6. build_jobs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS build_jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            started_at TEXT,
            finished_at TEXT,
            error_message TEXT,
            project_name TEXT DEFAULT '',
            config_json TEXT DEFAULT '',
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)
        
        # Self-healing migration for build_jobs table
        cursor.execute("PRAGMA table_info(build_jobs);")
        columns_jobs = [row["name"] for row in cursor.fetchall()]
        if "project_name" not in columns_jobs:
            cursor.execute("ALTER TABLE build_jobs ADD COLUMN project_name TEXT DEFAULT '';")
        if "config_json" not in columns_jobs:
            cursor.execute("ALTER TABLE build_jobs ADD COLUMN config_json TEXT DEFAULT '';")

        # 7. history table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            duration_sec REAL DEFAULT 0.0,
            draft_path TEXT NOT NULL,
            video_segments_count INTEGER DEFAULT 0,
            voice_duration_sec REAL DEFAULT 0.0,
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """)

        # 8. backups table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS backups (
            id TEXT PRIMARY KEY,
            project_dir TEXT NOT NULL,
            backup_path TEXT NOT NULL,
            timestamp TEXT DEFAULT (datetime('now', 'localtime')),
            note TEXT
        );
        """)

        # 9. custom_presets table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_presets (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            segment_type TEXT DEFAULT 'media',
            operations_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """)
        
        # Ensure at least one default profile exists
        cursor.execute("SELECT COUNT(*) as count FROM profiles")
        row = cursor.fetchone()
        if row and row["count"] == 0:
            import uuid
            profile_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO profiles (
                    id, name, canvas, clip_min_sec, clip_max_sec, selection_mode,
                    short_video_mode, recursive_scan, version
                ) VALUES (?, 'Mặc định', '9:16', 5.0, 9.0, 'shuffle_bag', 'stretch', 0, 1)
                """,
                (profile_id,)
            )
            
        conn.commit()

    @classmethod
    def close_connection(cls) -> None:
        """
        Closes the active database connection.
        """
        if cls._conn is not None:
            cls._conn.close()
            cls._conn = None
