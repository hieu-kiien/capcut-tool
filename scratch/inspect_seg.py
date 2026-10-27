import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

p = Path(r"C:\Users\hieuk\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\ngủ 29\draft_content.json")
d = json.loads(p.read_text(encoding="utf-8"))

seg0 = d["tracks"][0]["segments"][0]
print("=== SEG 0 ===")
print(json.dumps(seg0, indent=2, ensure_ascii=False))

print("\n=== EXTRA MATERIAL REFS RESOLVED ===")
for ref in seg0.get("extra_material_refs", []):
    found = False
    for mat_cat, items in d.get("materials", {}).items():
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict) and it.get("id") == ref:
                    print(f"Ref {ref} -> in materials['{mat_cat}'], type={it.get('type')}, name={it.get('name')}")
                    found = True
                    break
        if found:
            break
