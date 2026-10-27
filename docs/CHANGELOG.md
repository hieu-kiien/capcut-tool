# CHANGELOG: CapCut Long Story Studio

> **This is the technical history** — fixes, refactors and internal audits, including work that never reaches a release note. Release notes live in [`MVP_CHANGELOG.md`](MVP_CHANGELOG.md), which also defines the project version.
>
> Entries here are not versioned releases. `[1.0.0-docs]` below was a documentation milestone, not a product version.

---

## [Unreleased] - 2026-08-07

### Fixed
* Fixed a deadlock in `BatchQueueManager` that hung the build queue whenever a job finished or failed synchronously. `_finish_current_job()` chains into `_run_next_job()`, which acquires `self._mutex`; the mutex was a non-reentrant `QMutex`, so re-entry on the same thread blocked forever. Changed to `QRecursiveMutex`. This also unblocked the full test suite, which had been hanging indefinitely at `tests/test_build_queue.py::test_queue_run_next_logic`.
* Declared the missing `pillow` dependency. `core/chroma.py` imports `PIL.Image` to strip solid-color backgrounds from logo/overlay images, but `requirements.txt` never listed it, so a clean install failed at runtime with `RuntimeError: Thiếu Pillow để xóa nền ảnh logo`.
* Removed `sqlite3`, `imageio` and `imageio_ffmpeg` from the PyInstaller exclude list in `scripts/build_exe.py`. All three are imported by the application — `sqlite3` by `core/db.py` at startup, `imageio` by `pyJianYingDraft/local_materials.py` for GIF durations, `imageio_ffmpeg` by `runtime_tools.py` as the FFmpeg resolver fallback. Any EXE built by that script would have shipped broken.

### Added
* Added `pytest-timeout` with a 120s per-test ceiling in `pytest.ini`, so a deadlocked test can no longer hang the suite or consume the CI job's full time budget without output.

### Changed
* Relaxed the `pytest<9` pin in `requirements-dev.txt`; it conflicted with the pytest 9.x already used locally, meaning CI and developer machines ran different major versions.

### Documentation
* Corrected three inverted or stale claims in `CODE_AUDIT.md`, `PROJECT_MAP.md` and `BACKLOG.md`: pillow was described as an unused dependency to remove (it was used but undeclared); `pyJianYingDraft/template_mode.py` was described as entirely dead code slated for deletion (it is live on the draft-load path via `ScriptFile.load_template`); and the `pyJianYingDraft` → `app` circular dependency no longer exists.
* Corrected the path of the security validator across seven documents: `app/path_validation.py` → `core/path_validation.py`. The old path does not exist, while `AGENT_CONTEXT.md` mandated its use.
* Recorded verified test counts. The previous figures (`86/86`, `90/90`) disagreed with each other and with the suite, because the deadlock above made a full run impossible.
* Documented two previously unrecorded defects: the PyInstaller mis-exclusion (`CODE_AUDIT.md` §5A) and a `core` → `app` layering violation in `core/chroma.py` (§6C).

## [Superseded] - 2026-06-19

### Added
* Added bounded, thread-safe media probe caching with file-change invalidation and in-flight probe sharing.
* Added compact JSON export as an explicit opt-in while preserving pretty JSON defaults.
* Added repeatable performance benchmarks with warm-up, median/min/max reporting, and optional real ffprobe samples.
* Added focused tests for cache validation, concurrency, exceptions, JSON defaults, Unicode, dual-file output, and round trips.

### Changed
* Reduced media scan concurrency to a conservative maximum of four workers for lower-spec machines.
* Updated scan and media-studio shutdown paths to request interruption, wait with timeouts, and refuse unsafe close operations.
* Improved muted UI text contrast for dark backgrounds.

### Verified
* Full test suite: 86 passed on 2026-06-19.
* `compileall` passed for app, draft library, backend modules, tests, and benchmark script.
* Five-hour benchmark: 600 media, 3,600 segments, cached draft median 3.847s versus 4.210s uncached.
* Compact serialization median 0.776s versus 0.905s pretty serialization.

### Remaining
* Verify compact drafts in the installed CapCut application before considering compact output as the default.
* Run the optional real ffprobe benchmark with valid local media.

## [1.0.0-docs] - 2026-06-15

### Added
*   Created a restructured and consolidated documentation system in the `docs/` folder:
    *   [PROJECT_MAP.md](file:///D:/1.%20LapTrinh/capcut%20tool/docs/PROJECT_MAP.md): Restructured project scope, architecture, core modules list, directories map, dependencies checklist, and workflow data flows.
    *   [CODE_AUDIT.md](file:///D:/1.%20LapTrinh/capcut%20tool/docs/CODE_AUDIT.md): Logged system audit reports on error-prone logic, performance bottlenecks, security vectors, dead code, and technical debt, complete with issue priorities and code line paths.
    *   [BACKLOG.md](file:///D:/1.%20LapTrinh/capcut%20tool/docs/BACKLOG.md): Restructured backlog tasks (Critical, High, Medium, Low) for future development sprints.
    *   [AGENT_CONTEXT.md](file:///D:/1.%20LapTrinh/capcut%20tool/docs/AGENT_CONTEXT.md): Added a guide mapping onboarding constraints, development flows, and code safety guardrails for AI coding assistants.
    *   [CHANGELOG.md](file:///D:/1.%20LapTrinh/capcut%20tool/docs/CHANGELOG.md): Initialized this changelog file to keep track of all modifications.

### Cleaned
*   Pruned the previous temporary 12-file documentation structure to consolidate documentation layout and save context tokens.

---

## [1.0.0] - 2026-06-12

### Added
*   **CapCut PC Integration**: Core pipeline mapping voice tracks, SRT subtitles, BGM, and background directories directly to CapCut draft timelines.
*   **Path Validation Security**: Integrated strict traversal protections in [core/path_validation.py](file:///D:/1.%20LapTrinh/capcut%20tool/core/path_validation.py).
*   **Media Downloader Wrapper**: Implemented yt-dlp & gallery-dl UI wrapper with multi-threaded downloads, url validation, and cookies integration.
*   **Diagnostics & Recovery**: Integrated `Draft Doctor` for timeline self-healing and path recovery, and `app/draft_lock.py` for cross-process file lock safety.
*   **Subprocess Execution Safety**: Added execution timeout limits on all `ffprobe` and `ffmpeg` commands.
