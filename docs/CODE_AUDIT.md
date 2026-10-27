# CODE AUDIT: CapCut Long Story Studio

This document contains the structural code audit of the CapCut Long Story Studio project. Issues are ranked by priority (**Critical / High / Medium / Low**) and mapped to specific files and paths.

---

## 1. Error-Prone Files

> **Citation convention.** Findings cite `file :: symbol`, not line numbers. Line numbers drift with every edit; several citations in earlier revisions of this document pointed past the end of their file. If a symbol is renamed, update the citation.

### A. Monolithic UI & Thread Management [Rank: High]
*   **Target**: `app/gui.py :: MainWindow.closeEvent`
*   **Issue**: The GUI module is ~2,240 lines of mixed concerns. On shutdown, if background media scanning or download processes are still active, they may not receive termination signals cleanly — leaving orphaned subprocesses or crashing on Windows.
*   **Partial mitigation**: the close path now requests interruption and waits on scan, import, download and cutter workers, refusing to close while a worker is still running (see `REVIEW_STATUS_CURRENT.md` §8). The breadth of worker types makes this worth re-checking whenever a new worker is added.

### B. Dict Key Keyframe Timeline Injection [Rank: High]
*   **Target**: `capcut_keyframe_tool.py :: PROPERTY_MAP` and its consumers
*   **Issue**: Injects keyframe parameters straight into CapCut's draft JSON, relying on hardcoded key names (`KFTypeScaleUniform`, `KFTypePositionX`, …) and assumed list lengths. Any schema change in a future CapCut PC release causes parse failures or corrupted project files.
*   **Note**: this is inherent to writing an undocumented third-party format. The mitigation is backup-before-write plus `draft_doctor.py`, not schema stability.

### C. Chroma-Key Processing & Subprocess Lifecycles [Rank: High]
*   **Target**: `capcut_draft_creator.py` — the `_partial_` folder rename in the draft-write wrapper; `core/chroma.py :: remove_solid_bg_from_video`
*   **Issue**: Spawns FFmpeg for green/blue/white/black-screen chroma-keying. If a process is halted or a file handle stays locked, the copy or delete step — especially renaming `_partial_` folders — fails with `PermissionError` on Windows.

---

## 2. Security Issues

### A. Directory Traversal Vulnerability [Rank: Medium]
*   **Target**: `core/path_validation.py :: validate_project_name`
*   **Issue**: Folders are created and deleted inside the CapCut draft root based on user-supplied project names. Accepting a name containing traversal patterns (`../../`, an absolute path, a drive letter) would let the app write outside the draft root.
*   **Status**: **Mitigated**. The validator rejects traversal patterns and Windows device names, and confirms the resolved path with `is_relative_to()`. Enforced at `pyJianYingDraft/draft_folder.py :: DraftFolder._resolve_draft_path`, so it covers the vendored library's draft operations too. Tests cover `remove("../outside")` and `duplicate_as_template("template", "../outside")`.

### B. Shell Command Injection via URL Downloads [Rank: Medium]
*   **Target File**: `core/downloader/downloader.py` — the real implementation, 908 lines.
*   **Issue**: Calling external downloaders (`yt-dlp`, `gallery-dl`) with user-provided URL lists opens possibilities for shell injection if inputs are evaluated inside a shell.
*   **Status**: **Mitigated** — re-verified against the real module on 2026-08-07.
    *   No `shell=True`, `os.system` or `os.popen` anywhere in the module. All three spawn sites (`get_ytdlp_version`, and the two `Popen` calls in the gallery-dl and yt-dlp run paths) pass an argv list.
    *   `_validate_url` rejects control characters, the metacharacters `;` `|` `` ` `` `$`, and any scheme other than `http`/`https`; it also requires a non-empty netloc.
    *   Every URL entry point routes through it: `parse_url_list`, `build_ytdlp_command`, `build_gallerydl_command`, `YtDlpDownloadRunner.run`, and the library-mode `ydl.download` call.
    *   Cookie and archive paths go through `_validate_optional_file`, which resolves and requires an existing file. Output directories go through `_prepare_output_dir`.
    *   No log statement dumps the assembled argv, so the cookie file path does not leak into progress output or job history.
*   **Fixed during this audit**: `build_gallerydl_command` appended the raw `url` while `build_ytdlp_command` appended `_validate_url(url)` at the equivalent site. Not exploitable — the only production caller (`YtDlpDownloadRunner.run`) validates the whole list up front — but the builder was unsafe for any caller that bypassed the runner, including tests. Both builders now validate at their own append site.
*   **Correction note**: this entry previously targeted `app/downloader.py` and cited `downloader.py:L78-88`. That file is now a 31-line re-export shim with no logic; the security conclusion had been recorded against the wrong file. `REVIEW_STATUS_CURRENT.md` §4 carried the same error.

---

## 3. Performance Issues

### A. ~~Sequential Subprocess Spawning (ffprobe)~~ — RESOLVED [Rank: High]
*   **Target**: `media_probe.py :: scan_media_folder`
*   **Original issue**: every visual media file was probed sequentially; `ffprobe.exe` startup overhead on Windows made large directories very slow.
*   **Status**: **Resolved**. `scan_media_folder` now uses `ThreadPoolExecutor` with `max_workers = min(4, os.cpu_count())` — capped deliberately to stay usable on low-spec machines. `probe_media` adds a bounded cache (1,000 entries, invalidated on size/mtime change) and shares in-flight probes between threads requesting the same path.
*   **Note**: `CHANGELOG.md` recorded this as done, but `BACKLOG.md` still listed it as an open High-priority task until 2026-08-07.

### B. Redundant JSON Parse-Write Disk Cycles [Rank: Medium]
*   **Target**: `capcut_keyframe_tool.py :: _load_draft` and its callers
*   **Issue**: Each operation loads the draft JSON, modifies it, and writes it back — so applying keyframes and then transitions parses and serializes the whole timeline twice. Costly on long projects.
*   **Resolution Plan**: Batch modifications in memory and write once at the end of the pipeline.

---

## 4. Dead Code

### A. ~~Unused pillow Dependency~~ — CLAIM WAS INVERTED [Rank: Low]
*   **Status**: **Corrected 2026-08-07**. The original entry claimed pillow was declared but never imported, and recommended removing it. The reverse was true: pillow was **used but undeclared**.
*   **Actual issue**: `core/chroma.py :: remove_solid_bg_from_image` imports `PIL.Image` to strip solid-color backgrounds from logo/overlay images. It is reached in production via `capcut_draft_creator.py :: prepare_overlay_asset`. `requirements.txt` did not list pillow, so a clean install raised `RuntimeError: Thiếu Pillow để xóa nền ảnh logo` at runtime.
*   **Resolution**: Added `pillow>=10.0.0` to `requirements.txt`.
*   **Note**: The original entry also cited `build_exe.py:L222` as collecting pillow. That line is the string `"av"` in the PyInstaller exclude list; neither build path ever referenced pillow.

### B. ~~pyJianYingDraft Template Mode~~ — NOT DEAD CODE [Rank: Low]
*   **Status**: **Corrected 2026-08-07**. The original entry claimed the entire module was unused and recommended deprecating or deleting it. It is live code on the draft-loading path.
*   **Actual usage**:
    *   `pyJianYingDraft/script_file.py` imports seven symbols from it: `ImportedTrack`, `EditableTrack`, `ImportedMediaTrack`, `ImportedTextTrack`, `ShrinkMode`, `ExtendMode`, `import_track`.
    *   `script_file.py :: ScriptFile.load_template` calls `import_track(track_data)` for every track when loading an existing draft.
    *   `pyJianYingDraft/__init__.py` re-exports `ShrinkMode` and `ExtendMode` as part of the package's public API.
*   **Warning**: Acting on the original recommendation would have broken draft loading. The corresponding BACKLOG task has been removed.

### C. Unused Public Methods in the Vendored Library [Rank: Low]
*   **Target**: `pyJianYingDraft/script_file.py :: ScriptFile.import_track`, `ScriptFile.replace_material_by_seg`
*   **Issue**: These two template-editing methods are never called by this application. Verified 2026-08-07: no call site for either exists outside their definitions.
*   **Recommendation**: **Leave them.** They are part of the upstream library's public API, not dead code this project introduced. Deleting them would create a gratuitous divergence from upstream and make future updates harder to merge. This entry documents the fact, not a task.
*   **Important**: do not confuse `ScriptFile.import_track` (the unused *method*) with the module-level `template_mode.import_track` *function*, which is live — see §4B.

---

## 5. Packaging Correctness

### A. PyInstaller excluded three modules the app actually imports [Rank: High]
*   **Target File**: `scripts/build_exe.py` (exclude list)
*   **Issue**: The exclude list named `imageio`, `imageio_ffmpeg` and `sqlite3`. All three are live dependencies:
    *   `imageio` — `pyJianYingDraft/local_materials.py` imports it to read GIF durations.
    *   `imageio_ffmpeg` — `runtime_tools.py` imports it as the FFmpeg resolver fallback.
    *   `sqlite3` — `core/db.py` and `assets/manager.py` import it; the profile and asset-library features are built on it.
*   **Impact**: Any EXE produced by this script would fail on GIF import, lose the FFmpeg fallback, and break the profile/asset database. Excluding `sqlite3` is the most severe: `core/db.py` is imported at startup.
*   **Status**: **Fixed 2026-08-07**. The three entries were removed from the exclude list. `av`, `torch`, `cv2`, `numpy` and the other heavy exclusions were left in place — none of them are imported.
*   **Note**: This defect was not previously documented. Two build paths exist with divergent exclude policies — see §5B.

### B. Two build paths with divergent policies [Rank: Medium]
*   **Target Files**: `capcut_mvp.spec` (via `build_mvp.ps1`) and `scripts/build_exe.py`
*   **Issue**: `docs/MVP_RELEASE_GUIDE.md` step 6 designates `build_mvp.ps1` → `capcut_mvp.spec` as the release path. That spec excludes only six heavy ML/plotting packages and uses `collect_submodules` for `app`, `core`, `pyJianYingDraft`. The older `scripts/build_exe.py` maintains a separate, much longer exclude list — the source of the §5A defect. Neither file references the other, and nothing marks `build_exe.py` as superseded.
*   **Resolution Plan**: Mark `scripts/build_exe.py` as legacy or delete it, so packaging policy lives in one place.

---

## 6. Technical Debt

### A. Monolithic GUI Script [Rank: High]
*   **Target File**: [app/gui.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/gui.py)
*   **Issue**: The UI file is a massive monolith containing parameter builders, custom layouts, history table controls, threading workers, and configurations file serialization logic. This violates single responsibility principles.
*   **Code Reference**: [app/gui.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/gui.py).

### B. ~~Circular Dependency Resolved via Inline Imports~~ — NO LONGER A CYCLE [Rank: Low]
*   **Target File**: `pyJianYingDraft/draft_folder.py :: DraftFolder._resolve_draft_path`
*   **Status**: **Corrected 2026-08-07**. The original entry described a circular reference caused by the library importing the parent `app` package. The validator now lives in `core/path_validation.py`, which imports only stdlib (`os`, `re`, `unicodedata`, `pathlib`) and has no dependency on `app` or `pyJianYingDraft`. There is no cycle.
*   **Remaining nit**: the import at `draft_folder.py :: _resolve_draft_path` is still function-local, which now serves no purpose. It can be hoisted to module scope. Cosmetic only.

### C. Layering violation: `core` imports from `app` [Rank: Medium]
*   **Target File**: `core/chroma.py :: remove_solid_bg_from_video`
*   **Issue**: `core/chroma.py` imports `from app.job_control import JobCancelled`. This inverts the intended layering — `core` is the lower tier and should not depend on the UI/orchestration tier. It is the only such edge; the rest of `core` is `app`-independent.
*   **Impact**: Low today (the import is function-local, so it does not break at import time), but it blocks reusing `core` without `app` and would surface if `core` is ever packaged separately.
*   **Resolution Plan**: Move `JobCancelled` into `core` (e.g. `core/job_control.py`) and have `app.job_control` re-export it for compatibility.
*   **Note**: Not previously documented.

### C. Console stdout Prints [Rank: Medium]
*   **Target File**: Throughout the codebase
*   **Issue**: The codebase relies heavily on standard print statement console logs rather than Python's standard `logging` library.
*   **Code Reference**: Multiple print statements in [capcut_draft_creator.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_draft_creator.py) and [capcut_keyframe_tool.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_keyframe_tool.py).
