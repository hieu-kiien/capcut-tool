import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

draft_dir = Path(r"C:\Users\hieuk\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft")

for project_name in ["ngủ 29", "ngủ 28", "truyện ngủ"]:
    p = draft_dir / project_name / "draft_content.json"
    if not p.exists():
        print(f"Project {project_name} not found.")
        continue
    
    print(f"\n==========================================")
    print(f"PROJECT: {project_name}")
    print(f"==========================================")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("Canvas config:", data.get("canvas_config"))
    print("Duration:", data.get("duration"), "us (~", round(data.get("duration", 0)/1_000_000, 2), "s)")
    print("FPS:", data.get("fps"))

    tracks = data.get("tracks", [])
    print(f"Total tracks: {len(tracks)}")
    for i, t in enumerate(tracks):
        t_type = t.get("type")
        segments = t.get("segments", [])
        print(f"\n--- Track {i}: type={t_type}, count={len(segments)} ---")
        if segments:
            s0 = segments[0]
            print(f"  Sample Seg 0: target={s0.get('target_timerange')}, source={s0.get('source_timerange')}")
            # check keyframes
            if "keyframe_refs" in s0:
                print(f"  Keyframe refs in seg 0: {s0.get('keyframe_refs')}")
            if "extra_material_refs" in s0:
                print(f"  Extra refs in seg 0: {s0.get('extra_material_refs')}")

    # Inspect materials
    materials = data.get("materials", {})
    for mat_type, mat_list in materials.items():
        if mat_list:
            print(f"Material {mat_type}: {len(mat_list)} items")
            if mat_type in ["videos", "audios", "transitions", "keyframes", "texts", "material_animations"]:
                sample = mat_list[0]
                if mat_type == "videos":
                    print(f"  Sample video/img path: {sample.get('path')} (type: {sample.get('type')}, size: {sample.get('width')}x{sample.get('height')})")
                elif mat_type == "audios":
                    print(f"  Sample audio path: {sample.get('path')}")
                elif mat_type == "transitions":
                    print(f"  Sample transition: name={sample.get('name')}, duration={sample.get('duration')}")
                elif mat_type == "keyframes":
                    print(f"  Sample keyframe: property_type={sample.get('property_type')}, time={sample.get('time_offset')}, values={sample.get('values')}")
