# BACKLOG: CapCut Long Story Studio

Open engineering tasks, ranked **Critical / High / Medium / Low**.

**Citation convention**: tasks cite `file :: symbol`, not line numbers. Line numbers drift with every edit, and several citations in earlier revisions pointed past the end of their file.

**Scope**: this file lists work that is *open*. Completed work belongs in `CHANGELOG.md`. Findings that are documented facts rather than tasks belong in `CODE_AUDIT.md`. Last reconciled against the code on 2026-08-07.

---

## 1. Critical Tasks

None open.

---

## 2. High-Priority Tasks

### A. Verify the Rust draft engine before trusting the Tauri branch [Rank: High]
*   **Target**: `src-tauri/src/engine/draft.rs :: export_draft`
*   **Problem**: The function writes `draft_content.json` and `draft_meta_info.json` but emits `audios`, `texts`, `transitions` and `keyframes` as empty arrays — none of the content the Python pipeline produces. `PROJECT.md` previously marked this milestone DONE. There are zero Rust tests in `src-tauri/`.
*   **Resolution Plan**: Either bring it to parity with `capcut_draft_creator.py` and add tests, or state plainly in `PROJECT.md` that the branch is a prototype. Exit criteria are listed in `PROJECT.md`.
*   **Note**: not release-blocking — the Tauri branch is excluded from the EXE. It is High because the documentation previously overstated its readiness.

### B. Resolve the bundled FFmpeg licence question [Rank: High]
*   **Target**: `tools/ffmpeg/`, `capcut_mvp.spec`
*   **Problem**: The bundled FFmpeg build is **GPL v3**, not LGPL. Shipping it inside a distributable bundle carries copyleft obligations, including source availability.
*   **Resolution Plan**: Pick one — swap to an LGPL build; stop bundling and let `runtime_tools.py` resolve FFmpeg from PATH (already supported); or obtain legal review and comply. See `NOTICE` and `OPEN_SOURCE_DECISIONS.md`.
*   **Note**: only blocking if the app is distributed. Not a code defect.

---

## 3. Medium-Priority Tasks

### A. Record the vendored `pyJianYingDraft` version [Rank: Medium]
*   **Target**: `pyJianYingDraft/`, `NOTICE`
*   **Problem**: The upstream commit or release this ~20,200-line copy came from was never recorded, so it cannot be diffed against upstream. Upstream security fixes cannot be applied with confidence, because vendored-and-modified code cannot be told apart from vendored-and-unchanged code.
*   **Resolution Plan**: Identify the matching upstream version, record it in `NOTICE`, and keep the two local modifications as a reviewable patch set.

### B. Modularize the remaining GUI monolith [Rank: Medium]
*   **Target**: `app/gui.py`
*   **Problem**: ~2,240 lines of window setup, settings persistence, worker wiring and event handlers in one module.
*   **Progress**: per-tab UI has already moved to `app/widgets/` (7 modules, ~6,900 LOC) and profile logic to `app/controllers/`. What remains is the window shell and worker orchestration.
*   **Resolution Plan**: Extract settings persistence and worker lifecycle management into their own modules.

---

## 4. Low-Priority Tasks

None open.

---

## Resolved Tasks

Reconciled and resolved against the codebase. Detail in `CHANGELOG.md`.

| Task | Outcome |
|---|---|
| Core Lockups & Thread Safety *(was Critical)* | Done. `app/gui.py :: MainWindow._request_worker_shutdown` requests interruption, waits with a timeout, force-terminates, and refuses to close while a worker runs. |
| Parallelize Media Metadata Probing *(was High)* | Done. `scan_media_folder` uses `ThreadPoolExecutor`; `probe_media` adds a bounded cache and in-flight sharing. |
| Stabilize CapCut Process Verification *(was High)* | Done. `capcut_keyframe_tool.py` uses `psutil.process_iter` instead of parsing `tasklist` CSV. |
| Fix `core` → `app` layering violation *(was §3C)* | Done. Created `core/job_control.py` (`JobCancelled`, `raise_if_cancelled`); `app/job_control.py` re-exports; `core/chroma.py` imports from `core.job_control`. |
| Consolidate JSON disk access *(was §3D)* | Done. `capcut_keyframe_tool.py :: apply_batch_effects_to_file` batches keyframes & transitions in RAM with single read/write. |
| Replace `print()` with shared logger *(was §3E)* | Done. Routed `capcut_draft_creator.py`, `capcut_keyframe_tool.py`, and `app/queue_manager.py` through `core.logger`. |
| Retire legacy build path *(was §4A)* | Done. Deprecated `scripts/build_exe.py` with explicit notice pointing to `build_mvp.ps1` (`capcut_mvp.spec`). |
| Subprocess timeout settings *(was §4B)* | Done. Added `timeout_sec` guard to `core/chroma.py :: remove_solid_bg_from_video` and exposed in `capcut_draft_creator.py`. |
| Hoist function-local import *(was §4C)* | Done. Moved `core.path_validation` import in `pyJianYingDraft/draft_folder.py` to module scope. |
| Remove Unused pillow Dependency *(was Low)* | Void — the claim was inverted. pillow was used but undeclared; it is now declared. |
| Deprecate pyJianYingDraft Template Mode *(was Low)* | Void — the module is live on the draft-load path. |
| Decouple Library Package References *(was Medium)* | Void — replaced by §3C above. |
