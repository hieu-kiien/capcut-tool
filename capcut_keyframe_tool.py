import argparse
import json
import os
import random
import shutil
import subprocess
import psutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
import time
from core.logger import logger

DEFAULT_ROOT = Path(r'C:\Users\Admin\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft')

KEYFRAME_PADDING_OFFSET_US = 300_000  # 0.3 seconds offset from clip boundaries to prevent transition jitter

PROPERTY_MAP = {
    'rotation': 'KFTypeRotation',
    'scale_x': 'KFTypeScaleX',
    'scale_y': 'KFTypeScaleY',
    'scale_uniform': 'KFTypeScaleUniform',
    'pos_x': 'KFTypePositionX',
    'pos_y': 'KFTypePositionY',
    'alpha': 'KFTypeAlpha'
}

def detect_capcut_draft_root():
    candidates = []
    local_appdata = os.environ.get('LOCALAPPDATA')
    if local_appdata:
        candidates.append(Path(local_appdata) / 'CapCut' / 'User Data' / 'Projects' / 'com.lveditor.draft')
    candidates.append(DEFAULT_ROOT)
    for p in candidates:
        try:
            if p.exists() and p.is_dir():
                return p
        except Exception:
            pass
    return DEFAULT_ROOT

def parse_args():
    p = argparse.ArgumentParser(description='Quick keyframe tool for CapCut draft_content.json')
    p.add_argument('--root', type=Path, default=DEFAULT_ROOT, help='CapCut draft root folder')
    p.add_argument('--project', default='*', help='Project folder name, or * for all')
    p.add_argument('--property', choices=list(PROPERTY_MAP.keys()), required=True)
    p.add_argument('--from-value', type=float, required=True)
    p.add_argument('--to-value', type=float, required=True)
    p.add_argument('--segment-type', choices=['video', 'image', 'media', 'text', 'all'], default='video')
    p.add_argument('--mode', choices=['replace', 'append'], default='replace')
    p.add_argument('--dry-run', action='store_true')
    return p.parse_args()

def make_keyframe(time_offset, value):
    return {
        'curveType': 'Line',
        'graphID': '',
        'id': str(uuid.uuid4()).upper(),
        'left_control': {'x': 0.0, 'y': 0.0},
        'right_control': {'x': 0.0, 'y': 0.0},
        'string_value': '',
        'time_offset': int(time_offset),
        'values': [float(value)]
    }

def segment_duration(seg):
    src = (seg.get('source_timerange') or {}).get('duration', 0)
    tgt = (seg.get('target_timerange') or {}).get('duration', 0)
    d = src or tgt or 0
    if d and d > 0:
        return int(d)
    return 1

# ─── Draft I/O Helpers ───────────────────────────────────────────────────────

def _load_draft(path):
    """Load draft_content.json và trả về (data, material_sets)."""
    try:
        import orjson
        with open(path, 'rb') as f:
            data = orjson.loads(f.read())
    except Exception:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    mats = data.get('materials') or {}
    images = mats.get('images') or []
    videos = mats.get('videos') or []
    image_ids = {m.get('id') for m in images if m.get('id')}
    video_ids  = {m.get('id') for m in videos  if m.get('id')}
    video_meta = {m.get('id'): m for m in videos if m.get('id')}
    photo_ids  = {
        m.get('id')
        for m in videos
        if m.get('id') and str(m.get('type', '')).lower() in {'image', 'photo', 'picture'}
    }
    return data, image_ids, video_ids, video_meta, photo_ids

MAX_BACKUPS = 10


def _get_project_dir(draft_path):
    draft_path = Path(draft_path).resolve()
    if "Timelines" in draft_path.parts:
        idx = draft_path.parts.index("Timelines")
        return Path(*draft_path.parts[:idx])
    return draft_path.parent


def _add_backup_record(project_dir, backup_path, note=""):
    from core.db import Database
    try:
        import uuid
        conn = Database.get_connection()
        cursor = conn.cursor()
        backup_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT INTO backups (id, project_dir, backup_path, timestamp, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (backup_id, str(project_dir), str(backup_path), timestamp, note)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"[KEYFRAME TOOL] Error adding backup record to SQLite: {e}")


def _remove_backup_record(backup_path):
    from core.db import Database
    try:
        conn = Database.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM backups WHERE backup_path = ?", (str(backup_path),))
        conn.commit()
    except Exception as e:
        logger.error(f"[KEYFRAME TOOL] Error removing backup record from SQLite: {e}")


def _prune_backups(path, keep=MAX_BACKUPS):
    """Giữ lại tối đa `keep` file .bak mới nhất của `path`, xóa phần còn lại."""
    try:
        prefix = path.name + '.'
        backups = [
            f for f in path.parent.iterdir()
            if f.is_file() and f.name.startswith(prefix) and f.suffix == '.bak'
        ]
        if len(backups) <= keep:
            return
        backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        for old in backups[keep:]:
            try:
                old.unlink()
                # Xóa khỏi SQLite
                _remove_backup_record(old)
            except OSError:
                pass
    except OSError:
        pass


def _atomic_write_json(path, data):
    """Ghi JSON an toàn: ghi ra file tạm rồi os.replace (nguyên tử trên cùng ổ đĩa)."""
    tmp = path.with_suffix(path.suffix + '.tmp')
    try:
        try:
            import orjson
            payload = orjson.dumps(data)
            with tmp.open('wb') as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            with tmp.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
                f.flush()
                os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        # Dọn file tạm nếu ghi/replace thất bại để không để lại rác
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def _save_draft(path, data, note="Sao lưu tự động trước khi thay đổi (Keyframe)"):
    """Backup file hiện tại rồi ghi đè an toàn bằng data mới.

    Quy tắc an toàn: nếu KHÔNG sao lưu được file gốc (ví dụ CapCut đang mở và
    khóa file), thì hủy thao tác và báo lỗi rõ ràng — KHÔNG ghi đè file gốc khi
    chưa có bản sao lưu.
    """
    data['update_time'] = int(time.time() * 1000)
    ts  = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = path.with_suffix(path.suffix + f'.{ts}.bak')
    try:
        shutil.copy2(path, bak)
        # Ghi nhận SQLite
        proj_dir = _get_project_dir(path)
        _add_backup_record(proj_dir, bak, note)
    except Exception as exc:
        raise RuntimeError(
            f"Không thể tạo bản sao lưu cho '{path.name}' nên đã hủy để bảo vệ dữ liệu. "
            f"Vui lòng đóng CapCut rồi thử lại. Chi tiết: {exc}"
        ) from exc
    _atomic_write_json(path, data)
    _prune_backups(path)

def segment_matches(seg, track, kind, image_ids, video_ids, photo_ids, video_meta):
    if kind == 'all':
        return True
    if kind == 'media':
        return segment_matches(seg, track, 'video', image_ids, video_ids, photo_ids, video_meta) or \
               segment_matches(seg, track, 'image', image_ids, video_ids, photo_ids, video_meta)
    
    seg_type = seg.get('type')
    track_type = track.get('type')
    
    if kind in {'video', 'text'}:
        if kind == 'video' and seg.get('material_id') in photo_ids:
            return False
        if kind == 'video':
            v = video_meta.get(seg.get('material_id')) or {}
            if str(v.get('type', '')).lower() in {'image', 'photo', 'picture'}:
                return False
        return (seg_type == kind) or (track_type == kind)
        
    if kind == 'image':
        material_id = seg.get('material_id')
        if material_id in image_ids:
            return True
        if material_id in photo_ids:
            return True
        v = video_meta.get(material_id) or {}
        if str(v.get('type', '')).lower() in {'image', 'photo', 'picture'}:
            return True
        if material_id in video_ids:
            return False
        return False
        
    return False

def _pick_primary_video_track_indices(tracks):
    candidates = []
    for idx, t in enumerate(tracks or []):
        if str(t.get('type', '')).lower() != 'video':
            continue
        segs = t.get('segments') or []
        if not segs:
            continue
        candidates.append((idx, len(segs)))
        
    if not candidates:
        return set(range(len(tracks or [])))
        
    max_len = max(x[1] for x in candidates)
    return {idx for idx, ln in candidates if ln == max_len}

def _is_intro_or_outro(seg, video_meta, base_args):
    intro_path = getattr(base_args, "intro_path", None)
    outro_path = getattr(base_args, "outro_path", None)
    if not intro_path and not outro_path:
        return False
    material_id = seg.get("material_id")
    if not material_id:
        return False
    v = video_meta.get(material_id)
    if not v or not v.get("path"):
        return False
    try:
        seg_path = Path(v.get("path")).resolve()
        if intro_path and Path(intro_path).resolve() == seg_path:
            return True
        if outro_path and Path(outro_path).resolve() == seg_path:
            return True
    except Exception:
        pass
    return False

def apply_to_file(path, args):
    data, image_ids, video_ids, video_meta, photo_ids = _load_draft(path)
    tracks = data.get('tracks') or []

    prop_type  = PROPERTY_MAP[args.property]
    prop_types = ['KFTypeScaleX', 'KFTypeScaleY'] if prop_type == 'KFTypeScaleUniform' else [prop_type]
    changed = 0

    for track in tracks:
        for seg in track.get('segments') or []:
            if not segment_matches(seg, track, args.segment_type, image_ids, video_ids, photo_ids, video_meta):
                continue
            if _is_intro_or_outro(seg, video_meta, args):
                continue
            ck = seg.setdefault('common_keyframes', [])
            if args.mode == 'replace':
                ck[:] = [x for x in ck if x.get('property_type') not in prop_types]
            dur = segment_duration(seg)
            padding_us = KEYFRAME_PADDING_OFFSET_US
            if dur > padding_us * 2:
                start_k_offset = padding_us
                end_k_offset = dur - padding_us
            else:
                start_k_offset = min(padding_us, int(dur * 0.1)) if dur > 0 else 0
                end_k_offset = max(dur - padding_us, int(dur * 0.9)) if dur > 0 else dur
            
            for ptype in prop_types:
                ck.append({
                    'id': str(uuid.uuid4()).upper(),
                    'keyframe_list': [
                        make_keyframe(start_k_offset, args.from_value),
                        make_keyframe(end_k_offset, args.to_value)
                    ],
                    'material_id': '',
                    'property_type': ptype
                })
            changed += 1

    if changed and not args.dry_run:
        _save_draft(path, data)
    return changed

def _expand_prop_types(prop_name):
    prop_type = PROPERTY_MAP[prop_name]
    if prop_type == 'KFTypeScaleUniform':
        return ['KFTypeScaleX', 'KFTypeScaleY']
    return [prop_type]

def _expand_ops_from_preset(preset):
    if preset.get('operations'):
        return preset['operations']
    op = {
        'property': preset['property'],
        'from': preset['from'],
        'to': preset['to']
    }
    if 'unit' in preset:
        op['unit'] = preset['unit']
    return [op]

def _convert_value_if_needed(op, raw_value, canvas_cfg, seg, property_type):
    unit = str(op.get('unit', '')).lower()
    prop = op.get('property')
    if unit != 'px':
        if unit in {'pct_base', 'percent_base'}:
            if property_type in {'KFTypeScaleX', 'KFTypeScaleY'}:
                clip = seg.get('clip') if seg else None
                scale = (clip or {}).get('scale') or {}
                base_x = float(scale.get('x', 1.0))
                base_y = float(scale.get('y', 1.0))
                base = base_x if property_type == 'KFTypeScaleX' else base_y
                return base * (raw_value / 100.0)
            return raw_value
        return raw_value
        
    width = float((canvas_cfg or {}).get('width') or 1920)
    height = float((canvas_cfg or {}).get('height') or 1080)
    if prop == 'pos_x':
        return raw_value / width
    if prop == 'pos_y':
        return raw_value / height
    return raw_value

def _build_keyframe_list_for_op(op, duration, canvas_cfg, seg, property_type, ops_ctx):
    # Keyframe Padding Offset (0.3s = 300,000 µs) to prevent transition jitter at boundaries
    padding_us = KEYFRAME_PADDING_OFFSET_US
    if duration > padding_us * 2:
        start_t = padding_us
        end_t = duration - padding_us
    else:
        start_t = 0
        end_t = duration

    kf_def = op.get('keyframes')
    if kf_def:
        out = []
        for item in kf_def:
            at = item.get('at', 0.0)
            if isinstance(at, str):
                a = at.strip().lower()
                if a in {'start', 'begin'}:
                    at = 0.0
                elif a in {'half', 'mid', 'middle'}:
                    at = 0.5
                elif a in {'finish', 'end'}:
                    at = 1.0
                else:
                    at = float(a)
            at = float(at)
            if at == 0.0:
                t = start_t
            elif at == 1.0:
                t = end_t
            else:
                t = int(duration * at)
            v = _convert_keyframe_item_value(op, item, canvas_cfg, seg, property_type, ops_ctx)
            out.append(make_keyframe(t, v))
        return out
    from_value = _convert_value_if_needed(op, float(op['from']), canvas_cfg, seg, property_type)
    to_value = _convert_value_if_needed(op, float(op['to']), canvas_cfg, seg, property_type)
    return [
        make_keyframe(start_t, from_value),
        make_keyframe(end_t, to_value)
    ]

def _scale_at_ratio(ops, ratio, fallback):
    scale_op = None
    for o in ops:
        if o.get('property') == 'scale_uniform':
            scale_op = o
            break
            
    if not scale_op:
        return fallback
        
    keyframes = scale_op.get('keyframes')
    if keyframes:
        pts = []
        for it in keyframes:
            at = it.get('at', 0.0)
            if isinstance(at, str):
                a = at.strip().lower()
                if a in {'start', 'begin'}:
                    at = 0.0
                elif a in {'middle', 'half', 'mid'}:
                    at = 0.5
                elif a in {'end', 'finish'}:
                    at = 1.0
                else:
                    at = float(a)
            pts.append((float(at), float(it.get('value', fallback))))
        pts.sort(key=lambda x: x[0])
        
        if ratio <= pts[0][0]:
            return pts[0][1]
        if ratio >= pts[-1][0]:
            return pts[-1][1]
            
        for i in range(1, len(pts)):
            t0, v0 = pts[i - 1]
            t1, v1 = pts[i]
            if t0 <= ratio <= t1:
                if t1 == t0:
                    return v1
                k = (ratio - t0) / (t1 - t0)
                return v0 + (v1 - v0) * k
                
    return float(scale_op.get('to', fallback))

def _clamp_position_norm_by_scale(value_norm, scale):
    limit = max(0.0, (float(scale) - 1.0) / 2.0)
    if value_norm > limit:
        return limit
    if value_norm < -limit:
        return -limit
    return value_norm

def _convert_keyframe_item_value(op, item, canvas_cfg, seg, property_type, ops_ctx):
    raw = float(item.get('value', 0.0))
    v = _convert_value_if_needed(op, raw, canvas_cfg, seg, property_type)
    if op.get('clamp_to_frame') and property_type in {'KFTypePositionX', 'KFTypePositionY'}:
        at = item.get('at', 0.0)
        if isinstance(at, str):
            a = at.strip().lower()
            if a in {'start', 'begin'}:
                at = 0.0
            elif a in {'half', 'mid', 'middle'}:
                at = 0.5
            elif a in {'finish', 'end'}:
                at = 1.0
            else:
                at = float(a)
        scale = _scale_at_ratio(ops_ctx, float(at), 1.0)
        v = _clamp_position_norm_by_scale(v, scale)
    return v

def apply_random_presets_to_draft_data(data, image_ids, video_ids, video_meta, photo_ids, base_args, presets, cancel_check=None):
    if not presets:
        return 0
    tracks     = data.get('tracks') or []
    canvas_cfg = data.get('canvas_config') or {}

    remove_types = set()
    for p in presets:
        for op in _expand_ops_from_preset(p):
            remove_types.update(_expand_prop_types(op['property']))

    primary_track_indices = _pick_primary_video_track_indices(tracks)
    changed = 0

    for ti, track in enumerate(tracks):
        if cancel_check and cancel_check():
            from app.job_control import JobCancelled
            raise JobCancelled("Quy trình áp dụng keyframe đã bị hủy bởi người dùng.")
        if ti not in primary_track_indices:
            continue
        for seg in track.get('segments') or []:
            if not segment_matches(seg, track, base_args.segment_type, image_ids, video_ids, photo_ids, video_meta):
                continue
            if _is_intro_or_outro(seg, video_meta, base_args):
                continue
            seg_is_image = segment_matches(seg, track, 'image', image_ids, video_ids, photo_ids, video_meta)
            seg_is_video = segment_matches(seg, track, 'video', image_ids, video_ids, photo_ids, video_meta)

            eligible = []
            for p in presets:
                pseg = str(p.get('segment', 'media')).lower()
                if pseg == 'image' and seg_is_image:
                    eligible.append(p)
                elif pseg == 'video' and seg_is_video:
                    eligible.append(p)
                elif pseg in {'all', 'media'} and (seg_is_image or seg_is_video):
                    eligible.append(p)
            if not eligible:
                continue

            picked = random.choice(eligible)
            ops    = _expand_ops_from_preset(picked)
            ck = seg.get('common_keyframes')
            if ck is None:
                ck = []
                seg['common_keyframes'] = ck
            if base_args.mode == 'replace':
                ck[:] = [x for x in ck if x.get('property_type') not in remove_types]

            dur = segment_duration(seg)
            for op in ops:
                prop_types = _expand_prop_types(op['property'])
                for ptype in prop_types:
                    kfl = _build_keyframe_list_for_op(op, dur, canvas_cfg, seg, ptype, ops)
                    ck.append({
                        'id': str(uuid.uuid4()).upper(),
                        'keyframe_list': kfl,
                        'material_id': '',
                        'property_type': ptype
                    })
            changed += 1
    return changed

def apply_random_presets_to_file(path, base_args, presets, cancel_check=None):
    if not presets:
        return 0
    data, image_ids, video_ids, video_meta, photo_ids = _load_draft(path)
    changed = apply_random_presets_to_draft_data(
        data, image_ids, video_ids, video_meta, photo_ids, base_args, presets, cancel_check=cancel_check
    )
    if changed and not getattr(base_args, 'dry_run', False):
        _save_draft(path, data)
    return changed

def _new_transition_material(template, preset, duration_us):
    """Tạo transition material. Nếu có template thì clone, nếu không thì tạo từ built-in IDs."""
    tid = str(uuid.uuid4()).upper()
    duration = int(duration_us if duration_us is not None else preset.get('duration', 400000))
    name = preset.get('name', '')

    if template:
        base = dict(template)
        base['id'] = tid
        base['duration'] = duration
        if name:
            base['name'] = name
        return base

    # Fallback: tạo từ TransitionType built-in IDs
    from_type = _builtin_transition_by_name(name)
    if from_type is None:
        return None
    meta = from_type.value
    return {
        "category_id": "",
        "category_name": "",
        "duration": duration,
        "effect_id": meta.effect_id,
        "id": tid,
        "is_overlap": getattr(meta, 'is_overlap', True),
        "name": meta.name if hasattr(meta, 'name') else name,
        "platform": "all",
        "resource_id": meta.resource_id,
        "type": "transition"
    }


def _builtin_transition_by_name(name):
    """Tìm TransitionType enum member tương ứng với tên preset (fuzzy match)."""
    try:
        from pyJianYingDraft.metadata import TransitionType
    except ImportError:
        return None

    norm = _normalize_transition_name(name)
    aliases = _transition_aliases(name)

    # Map tên thường dùng → tên trong enum
    _COMMON_MAP = {
        'mix': '叠化', 'dissolve': '叠化', 'crossfade': '叠化',
        'fade': '叠化', 'mixdissolve': '叠化',
        'slideup': '上移', 'slidedown': '下移',
        'slideleft': '向左滑动', 'slideright': '向右滑动',
        'zoomin': '放大', 'zoomout': '缩小',
        'flash': '闪白', 'whiteflash': '闪白',
        'blur': '模糊放大', 'warp': '漩涡扭曲',
        'spin': '旋转模糊', 'rotate': '旋转模糊',
    }
    chinese = _COMMON_MAP.get(norm)

    for member in TransitionType:
        member_name = member.name  # Chinese name of the enum member
        member_norm = _normalize_transition_name(member_name)
        if chinese and chinese in member_name:
            return member
        if member_norm and (member_norm in aliases or norm in member_norm or any(a in member_norm for a in aliases)):
            return member

    # Last resort: return 叠化 (dissolve/mix) as universal fallback
    for member in TransitionType:
        if '叠化' in member.name:
            return member
    return None


def _normalize_transition_name(name):
    s = str(name or '').lower()
    return ''.join(ch for ch in s if ch.isalnum())


def _transition_aliases(name):
    n = _normalize_transition_name(name)
    aliases = {n}
    if 'mix' in n or 'dissolve' in n or 'crossfade' in n or 'fade' in n:
        aliases.update({'mix', 'dissolve', 'crossfade', 'fade', '叠化'})
    elif n in {'centralfade', 'centrefade', 'centerfade'}:
        aliases.update({'centralfade', 'centrefade', 'centerfade'})
    elif n in {'checkerfade', 'chessfade', 'chessboardfade'}:
        aliases.update({'checkerfade', 'chessfade', 'chessboardfade'})
    elif 'slide' in n:
        aliases.update({'slide', 'slideup', 'slidedown', 'slideleft', 'slideright'})
    return aliases


def _find_transition_template_in_root(root, target_name):
    """Tìm transition template từ các draft khác (optional)."""
    target_aliases = _transition_aliases(target_name)
    if not root or not root.exists():
        return None
    for p in root.iterdir():
        if p.is_dir() and p.name.startswith('.'):
            continue
        d = p / 'draft_content.json'
        if not d.exists():
            continue
        try:
            data = json.loads(d.read_text(encoding='utf-8'))
        except Exception:
            continue
        transitions = data.get('materials', {}).get('transitions') or []
        for t in transitions:
            tn = _normalize_transition_name(t.get('name', ''))
            if tn and (tn in target_aliases or any(a in tn for a in target_aliases)):
                return t
    return None


def apply_random_transitions_to_draft_data(data, image_ids, video_ids, video_meta, photo_ids, base_args, transition_presets, cancel_check=None):
    if not transition_presets:
        return 0
    mats        = data.setdefault('materials', {})
    transitions = mats.setdefault('transitions', [])
    trans_ids   = {t.get('id') for t in transitions if t.get('id')}

    def _find_template_for_name(name):
        target_norm = _normalize_transition_name(name)
        if not target_norm:
            return None
        wanted = _transition_aliases(name)
        for t in transitions:
            tn = _normalize_transition_name(t.get('name', ''))
            if not tn:
                continue
            if tn in wanted or target_norm in tn:
                return t
        return _find_transition_template_in_root(getattr(base_args, 'root', None), name)

    duration_override_us = None
    sec = getattr(base_args, 'transition_duration_sec', None)
    if sec is not None:
        try:
            sec = float(sec)
            if sec > 0:
                duration_override_us = int(sec * 1_000_000)
        except Exception:
            duration_override_us = None

    changed       = 0
    apply_all_cuts = bool(getattr(base_args, 'transition_apply_all', False))
    allow_fallback = bool(getattr(base_args, 'transition_allow_primary_fallback', False))

    tracks = data.get('tracks') or []
    primary_track_indices = set()
    for idx, t in enumerate(tracks):
        if str(t.get('type', '')).lower() == 'video' and t.get('name') == 'long_story_background':
            primary_track_indices.add(idx)
            break
            
    if not primary_track_indices and allow_fallback:
        primary_track_indices = _pick_primary_video_track_indices(tracks)

    if not primary_track_indices:
        return 0

    for ti, track in enumerate(tracks):
        if cancel_check and cancel_check():
            from app.job_control import JobCancelled
            raise JobCancelled("Quy trình chèn chuyển cảnh đã bị hủy bởi người dùng.")
        if ti not in primary_track_indices:
            continue
        segs = track.get('segments') or []
        if len(segs) < 2:
            continue
        for seg in segs[:-1]:
            if not apply_all_cuts and not segment_matches(
                seg, track, base_args.segment_type, image_ids, video_ids, photo_ids, video_meta
            ):
                continue
            if _is_intro_or_outro(seg, video_meta, base_args):
                continue
            refs = seg.setdefault('extra_material_refs', [])
            if base_args.mode == 'replace':
                refs[:] = [r for r in refs if r not in trans_ids]
            preset         = random.choice(transition_presets)
            picked_template = _find_template_for_name(preset.get('name'))
            tmat           = _new_transition_material(picked_template, preset, duration_override_us)
            if not tmat:
                continue
            transitions.append(tmat)
            refs.append(tmat['id'])
            trans_ids.add(tmat['id'])
            changed += 1

    return changed

def apply_random_transitions_to_file(path, base_args, transition_presets, cancel_check=None):
    if not transition_presets:
        return 0
    data, image_ids, video_ids, video_meta, photo_ids = _load_draft(path)
    changed = apply_random_transitions_to_draft_data(
        data, image_ids, video_ids, video_meta, photo_ids, base_args, transition_presets, cancel_check=cancel_check
    )
    if changed and not getattr(base_args, 'dry_run', False):
        _save_draft(path, data)
    return changed

def apply_batch_effects_to_file(path, base_args, keyframe_presets=None, transition_presets=None, cancel_check=None):
    """Gom việc áp dụng keyframe và chuyển cảnh trong bộ nhớ, chỉ đọc và ghi file draft 1 lần duy nhất."""
    if not keyframe_presets and not transition_presets:
        return {"keyframes": 0, "transitions": 0}

    data, image_ids, video_ids, video_meta, photo_ids = _load_draft(path)
    kf_changed = 0
    trans_changed = 0

    if keyframe_presets:
        kf_changed = apply_random_presets_to_draft_data(
            data, image_ids, video_ids, video_meta, photo_ids, base_args, keyframe_presets, cancel_check=cancel_check
        )

    if transition_presets:
        trans_changed = apply_random_transitions_to_draft_data(
            data, image_ids, video_ids, video_meta, photo_ids, base_args, transition_presets, cancel_check=cancel_check
        )

    if (kf_changed or trans_changed) and not getattr(base_args, 'dry_run', False):
        _save_draft(path, data, note="Sao lưu tự động trước khi thay đổi (Gộp Keyframe & Transition)")

    return {"keyframes": kf_changed, "transitions": trans_changed}

def apply_video_speed_to_file(path, base_args):
    mode  = str(getattr(base_args, 'video_speed_mode', 'speed')).lower()
    value = getattr(base_args, 'video_speed_value', None)
    if value is None:
        return 0

    data, image_ids, video_ids, video_meta, photo_ids = _load_draft(path)
    tracks = data.get('tracks') or []
    primary_track_indices = _pick_primary_video_track_indices(tracks)
    changed = 0

    for ti, track in enumerate(tracks):
        if ti not in primary_track_indices:
            continue
        for seg in track.get('segments') or []:
            if not segment_matches(seg, track, 'video', image_ids, video_ids, photo_ids, video_meta):
                continue
            if _is_intro_or_outro(seg, video_meta, base_args):
                continue
            src     = (seg.get('source_timerange') or {}).get('duration', 0)
            tgt     = (seg.get('target_timerange') or {}).get('duration', 0)
            src_dur = int(src or tgt or 0)
            if src_dur <= 0:
                continue
            if mode == 'duration':
                new_tgt   = max(1, int(float(value) * 1_000_000))
                new_speed = max(0.01, min(100.0, float(src_dur) / float(new_tgt)))
                seg.setdefault('target_timerange', {})['duration'] = new_tgt
                seg['speed'] = float(new_speed)
            else:
                new_speed = max(0.01, min(100.0, float(value)))
                new_tgt   = max(1, int(float(src_dur) / new_speed))
                seg['speed'] = float(new_speed)
                seg.setdefault('target_timerange', {})['duration'] = new_tgt
            changed += 1

    if changed and not base_args.dry_run:
        _save_draft(path, data)
    return changed

def apply_video_scale_to_file(path, base_args):
    scale_pct = getattr(base_args, 'video_scale_percent', None)
    if scale_pct is None:
        return 0
    scale = float(scale_pct) / 100.0
    if scale <= 0:
        return 0

    data, image_ids, video_ids, video_meta, photo_ids = _load_draft(path)
    skip_first    = bool(getattr(base_args, 'skip_first_video_scale', False))
    first_skipped = False
    changed       = 0

    for track in data.get('tracks') or []:
        for seg in track.get('segments') or []:
            if not segment_matches(seg, track, 'video', image_ids, video_ids, photo_ids, video_meta):
                continue
            if _is_intro_or_outro(seg, video_meta, base_args):
                continue
            if skip_first and not first_skipped:
                first_skipped = True
                continue
            ck  = seg.setdefault('common_keyframes', [])
            dur = segment_duration(seg)
            for ptype in ('KFTypeScaleX', 'KFTypeScaleY'):
                ck[:] = [x for x in ck if x.get('property_type') != ptype]
                ck.append({
                    'id': str(uuid.uuid4()).upper(),
                    'keyframe_list': [
                        make_keyframe(0, scale),
                        make_keyframe(dur, scale)
                    ],
                    'material_id': '',
                    'property_type': ptype
                })
            changed += 1

    if changed and not base_args.dry_run:
        _save_draft(path, data)
    return changed

def iter_projects(root, project_pattern):
    if project_pattern == '*':
        for p in root.iterdir():
            if p.is_dir() and not p.name.startswith('.'):
                yield p
    else:
        p = root / project_pattern
        if p.exists() and p.is_dir():
            yield p

def resolve_project_draft_paths(project_dir):
    """Return (primary_draft_path, mirror_paths[]) for a CapCut project.

    Newer CapCut builds may keep the effective timeline at:
      project/Timelines/<main_timeline_id>/draft_content.json
    while project/draft_content.json can become stale.
    """
    root_draft = project_dir / 'draft_content.json'
    timeline_draft = None
    pj = project_dir / 'Timelines' / 'project.json'
    
    if pj.exists():
        try:
            meta = json.loads(pj.read_text(encoding='utf-8'))
            mid = meta.get('main_timeline_id')
            if mid:
                cand = project_dir / 'Timelines' / str(mid) / 'draft_content.json'
                if cand.exists():
                    timeline_draft = cand
        except Exception:
            timeline_draft = None

    if timeline_draft:
        mirrors = [p for p in [root_draft] if p.exists() and p != timeline_draft]
        return timeline_draft, mirrors
    
    return root_draft, []

def mirror_draft_file(source, mirrors):
    """Sao chép file draft đã lưu sang các vị trí mirror một cách nguyên tử.

    Trả về danh sách lỗi (rỗng nếu thành công hết) để caller có thể báo cho người
    dùng thay vì âm thầm bỏ qua — nếu mirror thất bại, CapCut có thể nạp bản cũ.
    """
    errors = []
    source = Path(source)
    for m in mirrors:
        m = Path(m)
        if m == source:
            continue
        tmp = m.with_suffix(m.suffix + '.tmp')
        try:
            m.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, tmp)
            os.replace(tmp, m)
        except Exception as exc:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            errors.append(f"{m}: {exc}")
    if errors:
        try:
            sys.stderr.write("[CẢNH BÁO] Không thể đồng bộ mirror draft:\n  " + "\n  ".join(errors) + "\n")
        except Exception:
            pass
    return errors

def is_capcut_running():
    """Phát hiện CapCut đang chạy bằng psutil thay cho tasklist để tránh lỗi parsing CSV trên các ngôn ngữ Windows."""
    try:
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info.get('name')
                if name and name.lower() in ('capcut.exe', 'capcutpc.exe'):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass
    return False

def close_capcut(force):
    if not is_capcut_running():
        return True
    try:
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info.get('name')
                if name and name.lower() in ('capcut.exe', 'capcutpc.exe'):
                    if force:
                        proc.kill()
                    else:
                        proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Wait up to 3 seconds for processes to terminate
        import time
        for _ in range(15):
            if not is_capcut_running():
                return True
            time.sleep(0.2)
        return False
    except Exception:
        return not is_capcut_running()

def main():
    args = parse_args()
    root = args.root
    if not root.exists():
        print(f'[ERR] Root not found: {root}')
        return 1
    total_segments = 0
    touched_projects = 0
    
    for project in iter_projects(root, args.project):
        draft, mirrors = resolve_project_draft_paths(project)
        if not draft.exists():
            continue
        changed = apply_to_file(draft, args)
        if changed:
            if not args.dry_run and mirrors:
                mirror_draft_file(draft, mirrors)
            touched_projects += 1
            total_segments += changed
            pname = project.name
            try:
                print(f'[OK] {pname}: updated {changed} segments')
            except UnicodeEncodeError:
                safe = pname.encode('ascii', 'replace').decode('ascii')
                print(f'[OK] {safe}: updated {changed} segments')
                
    if touched_projects == 0:
        print('[INFO] No matching project/segment updated')
        return 0
        
    mode = 'DRY-RUN' if args.dry_run else 'DONE'
    print(f'[{mode}] Projects: {touched_projects}, Segments: {total_segments}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
