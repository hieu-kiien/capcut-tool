from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("patcher", Path(__file__).parents[1] / "apply_mvp_patch.py")
patcher = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = patcher
SPEC.loader.exec_module(patcher)


class PatchKitTests(unittest.TestCase):
    def test_patch_text_replaces_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.py"
            path.write_text("a\nreport = run_preflight(self.config)\nb\n", encoding="utf-8")
            changed = patcher.patch_text(path, patcher.PIPELINE_OLD, patcher.PIPELINE_NEW, dry_run=False)
            self.assertTrue(changed)
            self.assertIn(patcher.PIPELINE_NEW, path.read_text(encoding="utf-8"))

    def test_patch_text_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.py"
            path.write_text(patcher.PIPELINE_NEW, encoding="utf-8")
            changed = patcher.patch_text(path, patcher.PIPELINE_OLD, patcher.PIPELINE_NEW, dry_run=False)
            self.assertFalse(changed)

    def test_fast_preflight_still_validates_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preflight.py"
            path.write_text(patcher.VOICE_FAST_OLD, encoding="utf-8")
            patcher.patch_text(path, patcher.VOICE_FAST_OLD, patcher.VOICE_FAST_NEW, dry_run=False)
            text = path.read_text(encoding="utf-8")
            self.assertIn("voice_asset = media_probe.probe_media", text)
            self.assertNotIn("voice_duration_sec = 0.0", text)

    def test_preflight_patch_removes_write_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preflight.py"
            path.write_text(patcher.PREFLIGHT_OLD, encoding="utf-8")
            patcher.patch_text(path, patcher.PREFLIGHT_OLD, patcher.PREFLIGHT_NEW, dry_run=False)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(".write_test_", text)
            self.assertIn("media_ok = True", text)


if __name__ == "__main__":
    unittest.main()
