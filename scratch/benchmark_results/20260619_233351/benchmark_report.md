# Benchmark Report

**Status:** BLOCKED_EXTERNAL — need 5–10 valid local media

**Reason:** No real media files were found in the workspace or in `CAPCUT_BENCHMARK_MEDIA_DIR`. Synthetic files are strictly prohibited for this benchmark test.

## Regression Test Results

**Status:** PASSED

1. **Pytest (`python -m pytest -q tests`)**:
   - Result: 85 passed, 5 warnings in 8.35s
   - Notes: Successfully maintained the expected 85/85 passing tests.

2. **Compileall (`python -m compileall app pyJianYingDraft capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py tests -q`)**:
   - Result: Completed successfully with no syntax errors.
