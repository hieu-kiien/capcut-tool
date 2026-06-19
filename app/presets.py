# app/presets.py

KEYFRAME_PRESETS = [
    # ─── Zoom ───────────────────────────────────────────────────────────────
    {
        "id": "zoom_in_slow",
        "name": "Phóng to chậm (Zoom In Slow) – 100% → 112%",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 100.0, "to": 112.0, "unit": "pct_base"}
        ]
    },
    {
        "id": "zoom_out_slow",
        "name": "Thu nhỏ chậm (Zoom Out Slow) – 112% → 100%",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 112.0, "to": 100.0, "unit": "pct_base"}
        ]
    },
    {
        "id": "zoom_in_fast",
        "name": "Phóng to nhanh (Quick Zoom In) – 100% → 125%",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 100.0, "to": 125.0, "unit": "pct_base"}
        ]
    },
    {
        "id": "zoom_out_fast",
        "name": "Thu nhỏ nhanh (Quick Zoom Out) – 125% → 100%",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 125.0, "to": 100.0, "unit": "pct_base"}
        ]
    },
    {
        "id": "zoom_bounce",
        "name": "Zoom nảy (Zoom Bounce) – 100% → 118% → 108%",
        "segment": "media",
        "operations": [
            {
                "property": "scale_uniform",
                "keyframes": [
                    {"at": 0.0,  "value": 100.0},
                    {"at": 0.6,  "value": 118.0},
                    {"at": 1.0,  "value": 108.0},
                ],
                "unit": "pct_base"
            }
        ]
    },
    # ─── Pan Ngang ───────────────────────────────────────────────────────────
    {
        "id": "pan_left_right",
        "name": "Trượt Trái → Phải (Pan L-to-R)",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 115.0, "to": 115.0, "unit": "pct_base"},
            {"property": "pos_x", "from": -0.07, "to": 0.07}
        ]
    },
    {
        "id": "pan_right_left",
        "name": "Trượt Phải → Trái (Pan R-to-L)",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 115.0, "to": 115.0, "unit": "pct_base"},
            {"property": "pos_x", "from": 0.07, "to": -0.07}
        ]
    },
    # ─── Pan Dọc ─────────────────────────────────────────────────────────────
    {
        "id": "pan_up_down",
        "name": "Trượt Trên → Dưới (Pan Up-to-Down)",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 115.0, "to": 115.0, "unit": "pct_base"},
            {"property": "pos_y", "from": -0.07, "to": 0.07}
        ]
    },
    {
        "id": "pan_down_up",
        "name": "Trượt Dưới → Trên (Pan Down-to-Up)",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 115.0, "to": 115.0, "unit": "pct_base"},
            {"property": "pos_y", "from": 0.07, "to": -0.07}
        ]
    },
    # ─── Zoom + Pan kết hợp ──────────────────────────────────────────────────
    {
        "id": "zoom_in_pan_left",
        "name": "Phóng to + Trượt Trái (Zoom In + Pan Left)",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 100.0, "to": 115.0, "unit": "pct_base"},
            {"property": "pos_x", "from": 0.0, "to": -0.06}
        ]
    },
    {
        "id": "zoom_in_pan_right",
        "name": "Phóng to + Trượt Phải (Zoom In + Pan Right)",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 100.0, "to": 115.0, "unit": "pct_base"},
            {"property": "pos_x", "from": 0.0, "to": 0.06}
        ]
    },
    {
        "id": "zoom_in_pan_up",
        "name": "Phóng to + Trượt Lên (Zoom In + Pan Up)",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 100.0, "to": 115.0, "unit": "pct_base"},
            {"property": "pos_y", "from": 0.0, "to": -0.06}
        ]
    },
    {
        "id": "zoom_out_pan_down",
        "name": "Thu nhỏ + Trượt Xuống (Zoom Out + Pan Down)",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 115.0, "to": 100.0, "unit": "pct_base"},
            {"property": "pos_y", "from": -0.06, "to": 0.0}
        ]
    },
    # ─── Xoay ────────────────────────────────────────────────────────────────
    {
        "id": "subtle_rotate_cw",
        "name": "Xoay nhẹ thuận chiều kim đồng hồ",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 105.0, "to": 105.0, "unit": "pct_base"},
            {"property": "rotation", "from": -1.5, "to": 1.5}
        ]
    },
    {
        "id": "subtle_rotate_ccw",
        "name": "Xoay nhẹ ngược chiều kim đồng hồ",
        "segment": "media",
        "operations": [
            {"property": "scale_uniform", "from": 105.0, "to": 105.0, "unit": "pct_base"},
            {"property": "rotation", "from": 1.5, "to": -1.5}
        ]
    },
    # ─── Fade (Alpha) ────────────────────────────────────────────────────────
    {
        "id": "fade_in",
        "name": "Hiện dần (Fade In) – Alpha 0 → 1",
        "segment": "media",
        "operations": [
            {"property": "alpha", "from": 0.0, "to": 1.0}
        ]
    },
    {
        "id": "fade_out",
        "name": "Ẩn dần (Fade Out) – Alpha 1 → 0",
        "segment": "media",
        "operations": [
            {"property": "alpha", "from": 1.0, "to": 0.0}
        ]
    },
    {
        "id": "fade_in_out",
        "name": "Hiện → Ẩn (Fade In-Out) – Alpha 0 → 1 → 0",
        "segment": "media",
        "operations": [
            {
                "property": "alpha",
                "keyframes": [
                    {"at": 0.0,  "value": 0.0},
                    {"at": 0.15, "value": 1.0},
                    {"at": 0.85, "value": 1.0},
                    {"at": 1.0,  "value": 0.0},
                ]
            }
        ]
    },
]

TRANSITION_PRESETS = [
    {"name": "Mix",          "label": "Hòa tan (Mix / Dissolve)",        "duration": 400000},
    {"name": "Central Fade", "label": "Mờ đen trung tâm (Central Fade)", "duration": 500000},
    {"name": "Checker Fade", "label": "Ô cờ (Checker Fade)",             "duration": 600000},
    {"name": "Slide Left",   "label": "Trượt sang trái (Slide Left)",    "duration": 400000},
    {"name": "Slide Right",  "label": "Trượt sang phải (Slide Right)",   "duration": 400000},
    {"name": "Slide Up",     "label": "Trượt lên trên (Slide Up)",       "duration": 400000},
    {"name": "Slide Down",   "label": "Trượt xuống dưới (Slide Down)",   "duration": 400000},
    {"name": "Zoom In",      "label": "Phóng to vào (Zoom In Trans.)",   "duration": 500000},
    {"name": "Zoom Out",     "label": "Thu nhỏ ra (Zoom Out Trans.)",    "duration": 500000},
    {"name": "Flash",        "label": "Nháy trắng (Flash)",              "duration": 300000},
]


def add_custom_preset(name: str, segment_type: str, operations: list) -> str:
    import uuid
    import json
    from core.db import Database
    try:
        conn = Database.get_connection()
        cursor = conn.cursor()
        preset_id = "custom_" + str(uuid.uuid4())
        ops_json = json.dumps(operations, ensure_ascii=False)
        cursor.execute(
            """
            INSERT INTO custom_presets (id, name, segment_type, operations_json)
            VALUES (?, ?, ?, ?)
            """,
            (preset_id, name, segment_type, ops_json)
        )
        conn.commit()
        return preset_id
    except Exception as e:
        print(f"Error adding custom preset: {e}")
        return ""


def delete_custom_preset(preset_id: str) -> bool:
    from core.db import Database
    try:
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_presets WHERE id = ?", (preset_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting custom preset: {e}")
        return False


def load_all_presets() -> list:
    import json
    from core.db import Database
    presets = list(KEYFRAME_PRESETS)
    try:
        conn = Database.get_connection()
        cursor = conn.cursor()
        # Kiểm tra nếu bảng chưa tồn tại
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='custom_presets'")
        if not cursor.fetchone():
            return presets
            
        cursor.execute("SELECT id, name, segment_type, operations_json FROM custom_presets ORDER BY name ASC")
        for row in cursor.fetchall():
            try:
                ops = json.loads(row["operations_json"])
                presets.append({
                    "id": row["id"],
                    "name": f"[Tự chế] {row['name']}",
                    "segment": row["segment_type"],
                    "operations": ops
                })
            except Exception:
                pass
    except Exception as e:
        print(f"Error loading custom presets: {e}")
    return presets
