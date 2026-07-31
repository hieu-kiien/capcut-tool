# CHANGELOG: CapCut Long Story Studio

All notable changes to the CapCut Long Story Studio project will be documented in this file.

---

## [Unreleased] - 2026-06-19

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
*   **Path Validation Security**: Integrated strict traversal protections in [app/path_validation.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/path_validation.py).
*   **Media Downloader Wrapper**: Implemented yt-dlp & gallery-dl UI wrapper with multi-threaded downloads, url validation, and cookies integration.
*   **Diagnostics & Recovery**: Integrated `Draft Doctor` for timeline self-healing and path recovery, and `app/draft_lock.py` for cross-process file lock safety.
*   **Subprocess Execution Safety**: Added execution timeout limits on all `ffprobe` and `ffmpeg` commands.
