# BACKLOG: CapCut Long Story Studio

This backlog details prioritized engineering tasks, bugs, and enhancements for CapCut Long Story Studio, ranked by priority (**Critical / High / Medium / Low**).

---

## 1. Critical Tasks

### A. Core Lockups & Thread Safety [Rank: Critical]
*   **Target File**: [app/gui.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/gui.py#L2454-L2464)
*   **Problem**: Closing the application during an active pipeline run or download task fails to terminate background workers gracefully. This can leave orphaned `ffmpeg.exe` or `yt-dlp.exe` processes running in the background and freeze the main desktop shell.
*   **Resolution Plan**: Update `closeEvent` to query active thread statuses, signal abort requests to all active processes, and wait synchronously for safe closures before allowing the window handle to destroy.

---

## 2. High-Priority Tasks

### A. Parallelize Media Metadata Probing [Rank: High]
*   **Target File**: [media_probe.py](file:///D:/1.%20LapTrinh/capcut%20tool/media_probe.py#L100-L116)
*   **Problem**: Sequential invocation of `ffprobe` as a subprocess for every media file is slow. Scanning a large background asset directory with hundreds of items takes a long time.
*   **Resolution Plan**: Refactor `scan_media_folder()` to execute concurrent runs via `ThreadPoolExecutor` or `ProcessPoolExecutor`.

### B. Stabilize CapCut Process Verification [Rank: High]
*   **Target File**: [capcut_keyframe_tool.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_keyframe_tool.py#L772-L785)
*   **Problem**: Verification of active CapCut processes parses standard command `tasklist /FI IMAGENAME eq CapCut.exe` output via CSV lists. This is prone to localization or permission issues on Windows.
*   **Resolution Plan**: Implement standard process checking using standard win32 APIs or `psutil` wrappers if available.

---

## 3. Medium-Priority Tasks

### A. Modularize the Monolithic GUI File [Rank: Medium]
*   **Target File**: [app/gui.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/gui.py)
*   **Problem**: Over 2500 lines of UI, event handlers, worker declarations, and configuration bindings are stored in one file.
*   **Resolution Plan**: Split `gui.py` into separate widget components (e.g. `ParamFrame`, `DownloadFrame`, `HistoryPanel`).

### B. Decouple Library Package References [Rank: Medium]
*   **Target File**: [pyJianYingDraft/draft_folder.py](file:///D:/1.%20LapTrinh/capcut%20tool/pyJianYingDraft/draft_folder.py#L35-L39)
*   **Problem**: Low-level library imports from parent application `app/path_validation.py` to check project directory paths.
*   **Resolution Plan**: Move validation functions to lower-level utility modules or expose them as callback hooks.

### C. Consolidate JSON Disk Access [Rank: Medium]
*   **Target File**: [capcut_keyframe_tool.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_keyframe_tool.py#L73-L88)
*   **Problem**: Repeatedly reading and writing the entire project `draft_content.json` file for every single transition and keyframe preset.
*   **Resolution Plan**: Batch modifications in memory and execute a single disk write at the end of the pipeline.

### D. Implement System-Wide Logging [Rank: Medium]
*   **Target File**: Throughout the codebase
*   **Problem**: Standard `print()` statements are scattered across the codebase, making it difficult to capture debugging histories or customize logging levels.
*   **Resolution Plan**: Implement the standard Python `logging` library.

---

## 4. Low-Priority Tasks

### A. Remove Unused pillow Dependency [Rank: Low]
*   **Target File**: [requirements.txt](file:///D:/1.%20LapTrinh/capcut%20tool/requirements.txt#L6) & [scripts/build_exe.py](file:///D:/1.%20LapTrinh/capcut%20tool/scripts/build_exe.py#L222)
*   **Problem**: Pillow is listed as a package dependency and collected by PyInstaller, but is never used.
*   **Resolution Plan**: Remove references to Pillow in requirements and packaging.

### B. Deprecate pyJianYingDraft Template Mode [Rank: Low]
*   **Target File**: [pyJianYingDraft/template_mode.py](file:///D:/1.%20LapTrinh/capcut%20tool/pyJianYingDraft/template_mode.py)
*   **Problem**: The entire module represents legacy template editing that is unused by the new generation pipeline.
*   **Resolution Plan**: Deprecate or remove the module to clean the low-level library folder.

### C. Subprocess Execution Timeout Settings [Rank: Low]
*   **Target File**: [capcut_draft_creator.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_draft_creator.py#L95-L100)
*   **Problem**: Asynchronous FFmpeg overlay processing commands run with hardcoded subprocess settings.
*   **Resolution Plan**: Expose execution timeouts as configurable variables in `profiles.json`.
