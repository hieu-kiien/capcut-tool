"""
Công cụ tự động hóa tạo CapCut Draft hàng loạt cho series video kể chuyện dài.
Chuẩn hóa 100% theo khuôn mẫu 'ngủ 27':
- 5 Track chuẩn: Ảnh nền (Track 0), Sương mù (Track 1), Tia lửa 1 (Track 2), Watermark (Track 3), Voice 120% (Track 4).
- Tự động chia đều ảnh theo thời lượng audio.
- 5 Presets keyframe xen kẽ (Zoom In, Zoom Out, Pan L-R, Pan R-L, Pan Dưới-Trên).
- 100% Transition "Kết hợp" giữa các phân đoạn ảnh.
- Tự sinh draft_cover.jpg và cập nhật root_meta_info.json để hiển thị trên CapCut PC.
"""

import copy
import json
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Root paths
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from media_probe import probe_media

DRAFT_ROOT = Path(r"C:\Users\hieuk\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft")
TEMPLATE_DRAFT = DRAFT_ROOT / "ngủ 29"
VOICE_DIR = Path(r"D:\2. Media\Voice")
IMAGE_BASE_DIR = Path(r"D:\2. Media\Ảnh")

KEYFRAME_PADDING_OFFSET_US = 300_000  # 0.3s offset from clip boundaries to prevent transition jitter

def gen_uuid() -> str:
    return str(uuid.uuid4()).upper()

def get_channel_info(name: str):
    if "bình yên" in name.lower():
        return "Lịch Sử Bình Yên", "Lịch Sử Bình Yên"
    return "Giấc Ngủ Lịch Sử", "Giấc Ngủ Lịch Sử"

def make_keyframe(prop_type: str, v_start: float, v_end: float, duration_us: int) -> dict:
    pad = KEYFRAME_PADDING_OFFSET_US if duration_us > KEYFRAME_PADDING_OFFSET_US * 2 else 0
    t_start = pad
    t_end = duration_us - pad
    return {
        "id": gen_uuid(),
        "property_type": prop_type,
        "material_id": "",
        "keyframe_list": [
            {
                "id": gen_uuid(),
                "time_offset": t_start,
                "values": [v_start],
                "curveType": "Line",
                "graphID": "",
                "left_control": {"x": 0.0, "y": 0.0},
                "right_control": {"x": 0.0, "y": 0.0},
                "string_value": ""
            },
            {
                "id": gen_uuid(),
                "time_offset": t_end,
                "values": [v_end],
                "curveType": "Line",
                "graphID": "",
                "left_control": {"x": 0.0, "y": 0.0},
                "right_control": {"x": 0.0, "y": 0.0},
                "string_value": ""
            }
        ]
    }

def get_keyframes_for_segment(pattern_idx: int, duration_us: int) -> list:
    mode = pattern_idx % 5
    if mode == 0:
        return [
            make_keyframe("KFTypeScaleX", 1.20, 1.08, duration_us),
            make_keyframe("KFTypeScaleY", 1.20, 1.08, duration_us),
        ]
    elif mode == 1:
        return [
            make_keyframe("KFTypeScaleX", 1.04, 1.18, duration_us),
            make_keyframe("KFTypeScaleY", 1.04, 1.18, duration_us),
        ]
    elif mode == 2:
        return [
            make_keyframe("KFTypeScaleX", 1.18, 1.18, duration_us),
            make_keyframe("KFTypeScaleY", 1.18, 1.18, duration_us),
            make_keyframe("KFTypePositionX", -0.10052083333333334, 0.10052083333333334, duration_us),
            make_keyframe("KFTypePositionY", 0.0, 0.0, duration_us),
        ]
    elif mode == 3:
        return [
            make_keyframe("KFTypeScaleX", 1.16, 1.16, duration_us),
            make_keyframe("KFTypeScaleY", 1.16, 1.16, duration_us),
            make_keyframe("KFTypePositionX", 0.10052083333333334, -0.10052083333333334, duration_us),
            make_keyframe("KFTypePositionY", 0.0, 0.0, duration_us),
        ]
    else:
        return [
            make_keyframe("KFTypeScaleX", 1.18, 1.18, duration_us),
            make_keyframe("KFTypeScaleY", 1.18, 1.18, duration_us),
            make_keyframe("KFTypePositionX", 0.0, 0.0, duration_us),
            make_keyframe("KFTypePositionY", -0.09722222222222222, 0.09722222222222222, duration_us),
        ]

def generate_episode(draft_name: str, voice_file: Path, images_dir: Path, volume: float = 1.2):
    print(f"\n==========================================")
    print(f"🎬 Bắt đầu tạo draft: '{draft_name}'")
    print(f"🎤 Voice: {voice_file.name}")
    print(f"🖼️ Ảnh: {images_dir}")

    if not voice_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file voice: {voice_file}")
    if not images_dir.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục ảnh: {images_dir}")

    # 1. Đo thời lượng voice
    voice_asset = probe_media(voice_file)
    total_duration_us = voice_asset.duration_us
    print(f"⏱️ Thời lượng voice: {total_duration_us / 1e6:.2f}s ({total_duration_us / 1e6 / 60:.2f} phút)")

    # 2. Lấy danh sách ảnh
    image_files = sorted(list(images_dir.glob("*.png")), key=lambda p: p.name)
    num_images = len(image_files)
    print(f"📸 Số lượng ảnh: {num_images}")
    if num_images == 0:
        raise ValueError(f"Không có ảnh nào trong {images_dir}")

    # 3. Phân bổ thời lượng đều khít microsecond
    base_dur = total_duration_us // num_images
    remainder = total_duration_us % num_images
    segment_durations = [base_dur + (1 if i < remainder else 0) for i in range(num_images)]

    # 4. Đọc template mẫu
    with open(TEMPLATE_DRAFT / "draft_content.json", "r", encoding="utf-8") as f:
        tpl_data = json.load(f)

    new_draft_id = gen_uuid()
    now_sec = int(time.time())
    now_us = int(time.time() * 1_000_000)

    draft_content = copy.deepcopy(tpl_data)
    draft_content["id"] = new_draft_id
    draft_content["name"] = draft_name
    draft_content["duration"] = total_duration_us
    draft_content["create_time"] = now_sec
    draft_content["update_time"] = now_sec

    mat_videos = []
    mat_transitions = []
    mat_canvases = []
    mat_animations = []
    mat_speeds = []

    tpl_trans = tpl_data["materials"]["transitions"][0]

    # Track 0: Photos
    t0_segments = []
    curr_start = 0

    for idx, img_path in enumerate(image_files):
        dur = segment_durations[idx]
        v_id = gen_uuid()
        mat_videos.append({
            "id": v_id,
            "unique_id": "",
            "type": "photo",
            "duration": 10800000000,
            "path": str(img_path).replace("\\", "/"),
            "media_path": "",
            "local_id": "",
            "has_audio": False,
            "reverse_path": "",
            "intensifies_path": "",
            "reverse_intensifies_path": "",
            "intensifies_audio_path": "",
            "cartoon_path": "",
            "width": 1376,
            "height": 768,
            "category_id": "",
            "category_name": "local",
            "material_id": "",
            "material_name": img_path.name,
            "material_url": "",
            "crop": {
                "upper_left_x": 0.0, "upper_left_y": 0.0,
                "upper_right_x": 1.0, "upper_right_y": 0.0,
                "lower_left_x": 0.0, "lower_left_y": 1.0,
                "lower_right_x": 1.0, "lower_right_y": 1.0
            },
            "crop_ratio": "free",
            "audio_fade": None,
            "crop_scale": 1.0,
            "extra_type_option": 0,
            "stable": {"stable_level": 0, "matrix_path": "", "time_range": {"start": 0, "duration": 0}},
            "matting": {
                "flag": 0, "path": "", "interactiveTime": [], "has_use_quick_brush": False,
                "strokes": [], "has_use_quick_eraser": False, "expansion": 0, "feather": 0,
                "reverse": False, "custom_matting_id": "", "enable_matting_stroke": False,
                "is_clould": False, "mask_video_path": "", "cloud_product_fps": 0.0
            },
            "source": 0,
            "source_platform": 0,
            "formula_id": "",
            "check_flag": 62978047,
            "video_algorithm": {
                "algorithms": [], "time_range": None, "path": "", "gameplay_configs": [],
                "ai_in_painting_config": [], "complement_frame_config": None, "motion_blur_config": None,
                "deflicker": None, "noise_reduction": None, "quality_enhance": None,
                "super_resolution": None, "ai_background_configs": [], "smart_complement_frame": None,
                "aigc_generate": None, "aigc_generate_list": [], "mouth_shape_driver": None,
                "ai_expression_driven": None, "ai_motion_driven": None, "image_interpretation": None,
                "story_video_modify_video_config": {
                    "task_id": "", "is_overwrite_last_video": False,
                    "tracker_task_id": "", "generate_id": "", "generate_card_id": ""
                },
                "skip_algorithm_index": []
            },
            "is_unified_beauty_mode": False,
            "is_set_beauty_mode": False,
            "object_locked": None,
            "smart_motion": None,
            "multi_camera_info": None,
            "freeze": None,
            "picture_from": "none",
            "picture_set_category_id": "",
            "picture_set_category_name": "",
            "team_id": "",
            "local_material_id": "",
            "origin_material_id": "",
            "request_id": "",
            "has_sound_separated": False,
            "is_text_edit_overdub": False,
            "is_ai_generate_content": False,
            "aigc_type": "none",
            "is_copyright": False,
            "aigc_history_id": "",
            "aigc_item_id": "",
            "local_material_from": "",
            "smart_match_info": None,
            "beauty_face_preset_infos": [],
            "beauty_body_preset_id": "",
            "beauty_face_auto_preset": {"preset_id": "", "name": "", "rate_map": "", "scene": ""},
            "beauty_face_auto_preset_infos": [],
            "beauty_body_auto_preset": None,
            "live_photo_timestamp": -1,
            "live_photo_cover_path": "",
            "content_feature_info": None,
            "corner_pin": None,
            "surface_trackings": [],
            "video_mask_stroke": {
                "resource_id": "", "path": "", "type": "", "color": "",
                "size": 0.0, "alpha": 0.0, "distance": 0.0, "texture": 0.0,
                "horizontal_shift": 0.0, "vertical_shift": 0.0
            },
            "video_mask_shadow": {
                "resource_id": "", "path": "", "color": "", "alpha": 0.0,
                "blur": 0.0, "distance": 0.0, "angle": 0.0
            },
            "pre_applied_vip_materials": [],
            "workflow_node_id": ""
        })

        speed_id = gen_uuid()
        mat_speeds.append({"id": speed_id, "type": "speed", "mode": 0, "speed": 1.0, "curve_speed": None})

        canvas_id = gen_uuid()
        mat_canvases.append({
            "id": canvas_id, "type": "canvas_color", "color": "", "blur": 0.0,
            "image": "", "album_image": "", "image_id": "", "image_name": "",
            "source_platform": 0, "team_id": ""
        })

        extra_refs = [speed_id, canvas_id]
        if idx < num_images - 1:
            trans_id = gen_uuid()
            new_trans = copy.deepcopy(tpl_trans)
            new_trans["id"] = trans_id
            mat_transitions.append(new_trans)
            extra_refs.append(trans_id)

        seg_kfs = get_keyframes_for_segment(idx, dur)

        seg = {
            "id": gen_uuid(),
            "source_timerange": {"start": 0, "duration": dur},
            "target_timerange": {"start": curr_start, "duration": dur},
            "render_timerange": {"start": 0, "duration": 0},
            "desc": "",
            "state": 0,
            "speed": 1.0,
            "is_loop": False,
            "is_tone_modify": False,
            "reverse": False,
            "intensifies_audio": False,
            "cartoon": False,
            "volume": 1.0,
            "last_nonzero_volume": 1.0,
            "clip": {
                "scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
                "transform": {"x": 0.0, "y": 0.0},
                "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0
            },
            "uniform_scale": {"on": True, "value": 1.0},
            "material_id": v_id,
            "extra_material_refs": extra_refs,
            "render_index": 0,
            "keyframe_refs": [],
            "enable_lut": True,
            "enable_adjust": True,
            "enable_hsl": False,
            "visible": True,
            "group_id": "",
            "enable_color_curves": True,
            "enable_hsl_curves": True,
            "track_render_index": 0,
            "hdr_settings": {"mode": 1, "intensity": 1.0, "nits": 1000},
            "enable_color_wheels": True,
            "track_attribute": 0,
            "is_placeholder": False,
            "template_id": "",
            "enable_smart_color_adjust": False,
            "template_scene": "default",
            "common_keyframes": seg_kfs,
            "caption_info": None,
            "responsive_layout": {
                "enable": False, "target_follow": "", "size_layout": 0,
                "horizontal_pos_layout": 0, "vertical_pos_layout": 0
            },
            "enable_color_match_adjust": False,
            "enable_color_correct_adjust": False,
            "enable_adjust_mask": False,
            "raw_segment_id": "",
            "lyric_keyframes": None,
            "enable_video_mask": True,
            "digital_human_template_group_id": "",
            "color_correct_alg_result": "",
            "source": "segmentsourcenormal",
            "enable_mask_stroke": False,
            "enable_mask_shadow": False,
            "enable_color_adjust_pro": False,
            "segment_color_tag": ""
        }
        t0_segments.append(seg)
        curr_start += dur

    track_0 = {
        "id": gen_uuid(),
        "type": "video",
        "segments": t0_segments,
        "flag": 0,
        "attribute": 0,
        "name": "",
        "is_default_name": True
    }

    # Track 1: Sương mù
    eff1_mat = copy.deepcopy(tpl_data["materials"]["video_effects"][0])
    eff1_mat_id = gen_uuid()
    eff1_mat["id"] = eff1_mat_id

    t1_seg = copy.deepcopy(tpl_data["tracks"][1]["segments"][0])
    t1_seg["id"] = gen_uuid()
    t1_seg["material_id"] = eff1_mat_id
    t1_seg["target_timerange"] = {"start": 0, "duration": total_duration_us}

    track_1 = {
        "id": gen_uuid(), "type": "effect", "segments": [t1_seg],
        "flag": 0, "attribute": 0, "name": "", "is_default_name": True
    }

    # Track 2: Tia lửa 1
    eff2_mat = copy.deepcopy(tpl_data["materials"]["video_effects"][1])
    eff2_mat_id = gen_uuid()
    eff2_mat["id"] = eff2_mat_id

    t2_seg = copy.deepcopy(tpl_data["tracks"][2]["segments"][0])
    t2_seg["id"] = gen_uuid()
    t2_seg["material_id"] = eff2_mat_id
    t2_seg["target_timerange"] = {"start": 0, "duration": total_duration_us}

    track_2 = {
        "id": gen_uuid(), "type": "effect", "segments": [t2_seg],
        "flag": 0, "attribute": 0, "name": "", "is_default_name": True
    }

    # Track 3: Watermark Text
    text_mat = copy.deepcopy(tpl_data["materials"]["texts"][0])
    text_mat_id = gen_uuid()
    text_mat["id"] = text_mat_id

    channel_name, watermark_text = get_channel_info(draft_name)
    try:
        content_obj = json.loads(text_mat.get("content", "{}"))
        content_obj["text"] = watermark_text
        if content_obj.get("styles") and len(content_obj["styles"]) > 0:
            content_obj["styles"][0]["range"] = [0, len(watermark_text)]
        text_mat["content"] = json.dumps(content_obj, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Cảnh báo cập nhật watermark text: {e}")

    text_anim = copy.deepcopy(tpl_data["materials"]["material_animations"][0])
    mat_animations.insert(0, text_anim)

    t3_seg = copy.deepcopy(tpl_data["tracks"][3]["segments"][0])
    t3_seg["id"] = gen_uuid()
    t3_seg["material_id"] = text_mat_id
    t3_seg["target_timerange"] = {"start": 0, "duration": total_duration_us}
    t3_seg["extra_material_refs"] = [text_anim["id"]]

    track_3 = {
        "id": gen_uuid(), "type": "text", "segments": [t3_seg],
        "flag": 0, "attribute": 0, "name": "", "is_default_name": True
    }

    # Track 4: Voice
    audio_mat_id = gen_uuid()
    audio_mat = {
        "id": audio_mat_id,
        "unique_id": gen_uuid().lower().replace("-", ""),
        "type": "extract_music",
        "name": voice_file.name,
        "duration": total_duration_us,
        "path": str(voice_file).replace("\\", "/"),
        "category_name": "local",
        "wave_points": [],
        "music_id": str(uuid.uuid4()),
        "app_id": 0, "text_id": "", "tone_type": "", "source_platform": 0,
        "video_id": "", "effect_id": "", "resource_id": "", "third_resource_id": "",
        "category_id": "", "intensifies_path": "", "formula_id": "", "check_flag": 1,
        "team_id": "", "local_material_id": str(uuid.uuid4()), "tone_speaker": "",
        "mock_tone_speaker": "", "tone_effect_id": "", "tone_effect_name": "",
        "tone_platform": "", "cloned_model_type": "", "tone_category_id": "",
        "tone_category_name": "", "tone_second_category_id": "", "tone_second_category_name": "",
        "tone_emotion_name_key": "", "tone_emotion_style": "", "tone_emotion_role": "",
        "tone_emotion_selection": "", "tone_emotion_scale": 0.0, "moyin_emotion": "",
        "request_id": "", "query": "", "search_id": "", "sound_separate_type": "",
        "is_text_edit_overdub": False, "is_ugc": False, "is_ai_clone_tone": False,
        "is_ai_clone_tone_post": False, "source_from": "", "copyright_limit_type": "none",
        "aigc_history_id": "", "aigc_item_id": "", "music_source": "", "pgc_id": "",
        "pgc_name": "", "similiar_music_info": {"original_song_id": "", "original_song_name": ""},
        "ai_music_type": 0, "ai_music_enter_from": "", "lyric_type": 0, "tts_task_id": "",
        "tts_generate_scene": "", "ai_music_generate_scene": 0,
        "tts_benefit_info": {"benefit_type": "none", "benefit_log_id": "", "benefit_log_extra": "", "benefit_amount": -1}
    }

    aud_speed_id = gen_uuid()
    mat_speeds.append({"id": aud_speed_id, "type": "speed", "mode": 0, "speed": 1.0, "curve_speed": None})
    aud_beat_id = gen_uuid()
    beat_item = copy.deepcopy(tpl_data["materials"]["beats"][0])
    beat_item["id"] = aud_beat_id

    t4_seg = copy.deepcopy(tpl_data["tracks"][4]["segments"][0])
    t4_seg["id"] = gen_uuid()
    t4_seg["material_id"] = audio_mat_id
    t4_seg["source_timerange"] = {"start": 0, "duration": total_duration_us}
    t4_seg["target_timerange"] = {"start": 0, "duration": total_duration_us}
    t4_seg["volume"] = volume
    t4_seg["last_nonzero_volume"] = volume
    t4_seg["extra_material_refs"] = [
        aud_speed_id,
        aud_beat_id
    ]

    track_4 = {
        "id": gen_uuid(), "type": "audio", "segments": [t4_seg],
        "flag": 0, "attribute": 0, "name": "", "is_default_name": True
    }

    draft_content["tracks"] = [track_0, track_1, track_2, track_3, track_4]

    # Preserve all material category keys from template for C++ parser compatibility
    new_materials = copy.deepcopy(tpl_data["materials"])
    for k in new_materials.keys():
        new_materials[k] = []

    new_materials["videos"] = mat_videos
    new_materials["audios"] = [audio_mat]
    new_materials["texts"] = [text_mat]
    new_materials["video_effects"] = [eff1_mat, eff2_mat]
    new_materials["transitions"] = mat_transitions
    new_materials["canvases"] = mat_canvases
    new_materials["material_animations"] = mat_animations
    new_materials["speeds"] = mat_speeds
    new_materials["beats"] = [beat_item]

    draft_content["materials"] = new_materials

    # Clean existing draft directory completely to eliminate ghost media and stale cache
    target_draft_dir = DRAFT_ROOT / draft_name
    if target_draft_dir.exists():
        shutil.rmtree(target_draft_dir, ignore_errors=True)
    target_draft_dir.mkdir(parents=True, exist_ok=True)

    out_content_path = target_draft_dir / "draft_content.json"
    with open(out_content_path, "w", encoding="utf-8") as f:
        json.dump(draft_content, f, ensure_ascii=False, indent=2)

    tpl_meta_path = TEMPLATE_DRAFT / "draft_meta_info.json"
    meta_data = json.load(open(tpl_meta_path, "r", encoding="utf-8")) if tpl_meta_path.exists() else {}
    meta_data.update({
        "draft_id": new_draft_id,
        "draft_name": draft_name,
        "draft_fold_path": str(target_draft_dir).replace("\\", "/"),
        "draft_root_path": str(DRAFT_ROOT).replace("\\", "/"),
        "draft_json_file": str(out_content_path).replace("\\", "/"),
        "draft_cover": "draft_cover.jpg",
        "tm_duration": total_duration_us,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_removed": 0
    })
    # Reset draft_materials so CapCut does NOT look for old missing files from the template project!
    meta_data["draft_materials"] = [
        {"type": 0, "value": []},
        {"type": 1, "value": []},
        {"type": 2, "value": []},
        {"type": 3, "value": []},
        {"type": 6, "value": []},
        {"type": 7, "value": []},
        {"type": 8, "value": []}
    ]

    out_meta_path = target_draft_dir / "draft_meta_info.json"
    with open(out_meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_data, f, ensure_ascii=False, indent=2)

    cover_dst = target_draft_dir / "draft_cover.jpg"
    try:
        with Image.open(image_files[0]) as im:
            im.convert("RGB").save(cover_dst, "JPEG", quality=85)
    except Exception:
        pass

    register_in_root_meta(draft_name, new_draft_id, target_draft_dir, out_content_path, cover_dst, total_duration_us, now_us)
    print(f"✅ Hoàn thành tạo dự án: '{draft_name}'")


def register_in_root_meta(draft_name: str, draft_id: str, draft_dir: Path, content_path: Path, cover_path: Path, duration_us: int, now_us: int):
    root_meta_file = DRAFT_ROOT / "root_meta_info.json"
    if not root_meta_file.exists():
        return

    with open(root_meta_file, "r", encoding="utf-8") as f:
        root_data = json.load(f)

    store = root_data.get("all_draft_store", [])
    store = [item for item in store if item.get("draft_name") != draft_name]

    new_entry = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": str(cover_path).replace("/", "\\"),
        "draft_fold_path": str(draft_dir).replace("\\", "/"),
        "draft_id": draft_id,
        "draft_is_ai_shorts": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_infinite_canvas_draft": False,
        "draft_is_invisible": False,
        "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_json_file": str(content_path).replace("/", "\\"),
        "draft_name": draft_name,
        "draft_new_version": "",
        "draft_root_path": str(DRAFT_ROOT).replace("\\", "/"),
        "draft_timeline_materials_size": 800000000,
        "draft_type": "",
        "draft_web_article_video_enter_from": "",
        "pippit_avatar_url": "",
        "pippit_extra_info": "",
        "pippit_id": "",
        "pippit_user_name": "",
        "streaming_edit_draft_ready": True,
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_entry_id": -1,
        "tm_draft_cloud_modified": 0,
        "tm_draft_cloud_parent_entry_id": -1,
        "tm_draft_cloud_space_id": -1,
        "tm_draft_cloud_user_id": -1,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_removed": 0,
        "tm_duration": duration_us
    }

    store.insert(0, new_entry)
    root_data["all_draft_store"] = store
    root_data["draft_ids"] = len(store)

    bak_path = root_meta_file.with_suffix(".json.bak")
    with open(bak_path, "w", encoding="utf-8") as f:
        json.dump(root_data, f, ensure_ascii=False, indent=2)

    with open(root_meta_file, "w", encoding="utf-8") as f:
        json.dump(root_data, f, ensure_ascii=False, indent=2)


def discover_all_episodes():
    """Tự động tìm kiếm và ghép đôi toàn bộ Voice và Thư mục ảnh theo 2 kênh."""
    episodes = []
    voice_files = sorted(list(VOICE_DIR.glob("*.mp3")))
    img_folders = [d for d in IMAGE_BASE_DIR.iterdir() if d.is_dir()]

    for vf in voice_files:
        stem = vf.stem.replace("_", " ").strip()
        channel, watermark = get_channel_info(stem)

        # Match image folder
        matched_img_dir = None
        for img_d in img_folders:
            clean_img = img_d.name.replace("ảnh -", "").strip()
            if stem.lower() in img_d.name.lower() or clean_img.lower() in stem.lower():
                matched_img_dir = img_d
                break
            # Fallback matching by numbers and channel
            m_voice = re.findall(r"\d+", stem)
            m_img = re.findall(r"\d+", img_d.name)
            if m_voice and m_img and m_voice[0] == m_img[0]:
                if ("bình yên" in stem.lower() and "bình yên" in img_d.name.lower()) or \
                   ("giấc ngủ" in stem.lower() and "giấc ngủ" in img_d.name.lower()):
                    matched_img_dir = img_d
                    break

        # Extract episode number
        m_num = re.search(r"(\d{2,3})", stem)
        ep_code = m_num.group(1) if m_num else ""

        draft_name = stem

        episodes.append({
            "ep_code": ep_code,
            "draft_name": draft_name,
            "voice_file": vf,
            "image_dir": matched_img_dir,
            "channel": channel,
            "watermark": watermark
        })
    return episodes


def discover_and_build(target_episodes: list = None, volume: float = 1.2):
    all_eps = discover_all_episodes()
    print(f"🔍 Đã quét kho media: tìm thấy {len(all_eps)} tập truyện khớp cặp Voice + Ảnh:")
    for i, ep in enumerate(all_eps, 1):
        status = "✅ Sẵn sàng" if ep["image_dir"] else "❌ Thiếu ảnh"
        print(f"  {i}. [{ep['channel']}] Tập {ep['ep_code']}: {ep['draft_name'][:50]}... ({status})")

    to_build = []
    if target_episodes:
        targets_str = [str(t).lower() for t in target_episodes]
        for ep in all_eps:
            if "all" in targets_str:
                to_build.append(ep)
            else:
                for t in targets_str:
                    if ep["ep_code"] == t or ep["ep_code"].lstrip("0") == t.lstrip("0") or t in ep["draft_name"].lower():
                        to_build.append(ep)
                        break
    else:
        to_build = all_eps

    print(f"\n🚀 Sẽ tiến hành tạo {len(to_build)} dự án CapCut...")
    for ep in to_build:
        if not ep["image_dir"]:
            print(f"⚠️ Bỏ qua {ep['draft_name']} vì thiếu thư mục ảnh!")
            continue
        try:
            generate_episode(ep["draft_name"], ep["voice_file"], ep["image_dir"], volume=volume)
        except Exception as e:
            print(f"❌ Lỗi khi tạo {ep['draft_name']}: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tạo CapCut draft hàng loạt theo 2 kênh kể chuyện lịch sử")
    parser.add_argument("--episodes", nargs="*", type=str, help="Danh sách mã tập cần tạo (ví dụ: 010 011 hoặc all)")
    parser.add_argument("--volume", type=float, default=1.2, help="Âm lượng voice (mặc định 1.2 = 120%%)")
    args = parser.parse_args()

    if args.episodes:
        discover_and_build(args.episodes, volume=args.volume)
    else:
        print("💡 Hướng dẫn sử dụng:")
        print("  python scripts\\batch_story_creator.py --episodes 010")
        print("  python scripts\\batch_story_creator.py --episodes all")
