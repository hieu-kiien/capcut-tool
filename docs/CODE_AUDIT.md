# CODE AUDIT: CapCut Long Story Studio

This document contains the structural code audit of the CapCut Long Story Studio project. Issues are ranked by priority (**Critical / High / Medium / Low**) and mapped to specific files and paths.

---

## 1. Error-Prone Files

### A. Monolithic UI & Thread Management [Rank: High]
*   **Target File**: [app/gui.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/gui.py)
*   **Issue**: The GUI script contains over 2500 lines of mixed code. During application shutdown (`closeEvent`), if background media scanning or downloading processes are still active, they might not receive termination signals cleanly. This can leave subprocesses hanging in the background or cause application crashes on Windows.
*   **Code Reference**: [gui.py:L2454-2464](file:///D:/1.%20LapTrinh/capcut%20tool/app/gui.py#L2454-L2464) (closeEvent does not wait or signal ScanWorkers).

### B. Dict Key Keyframe Timeline Injection [Rank: High]
*   **Target File**: [capcut_keyframe_tool.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_keyframe_tool.py)
*   **Issue**: Modifies CapCut's internal timeline by injecting keyframe parameters directly into the JSON content. This script assumes hardcoded key values (`KFTypeScaleUniform`, `KFTypePositionX`) and list lengths. Any minor schema changes in future versions of CapCut PC will cause immediate parsing failures or project file corruption.
*   **Code Reference**: [capcut_keyframe_tool.py:L15-23](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_keyframe_tool.py#L15-L23) (hardcoded property mapping).

### C. Chroma-Key Processing & Subprocess Lifecycles [Rank: High]
*   **Target File**: [capcut_draft_creator.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_draft_creator.py)
*   **Issue**: Spawns external FFmpeg processes for background green/blue/white/black screen chroma-keying. If the process is halted or if a file handle remains locked by an active process, file copy or deletion commands (especially when renaming `_partial_` folders) will fail with `PermissionError` on Windows.
*   **Code Reference**: [capcut_draft_creator.py:L95-103](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_draft_creator.py#L95-L103) (moving folder on failure).

---

## 2. Security Issues

### A. Directory Traversal Vulnerability [Rank: Medium]
*   **Target File**: [app/path_validation.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/path_validation.py)
*   **Issue**: Arbitrary folder creation/deletion inside CapCut draft root directories based on project names. If names containing traversal patterns (like `../../` or absolute drives) were accepted, it would overwrite critical system files.
*   **Status**: **Mitigated**. Path validation enforces strict rules (excluding device names and checking with `is_relative_to()`).
*   **Code Reference**: [path_validation.py:L30-90](file:///D:/1.%20LapTrinh/capcut%20tool/app/path_validation.py#L30-L90).

### B. Shell Command Injection via URL Downloads [Rank: Medium]
*   **Target File**: [app/downloader.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/downloader.py)
*   **Issue**: Calling external downloaders (`yt-dlp`, `gallery-dl`) with user-provided URL lists opens possibilities for shell injection if inputs are evaluated inside a shell.
*   **Status**: **Mitigated**. Executions consistently avoid `shell=True` and urls are validated to reject characters like `;`, `|`, `` ` ``, `$`.
*   **Code Reference**: [downloader.py:L78-88](file:///D:/1.%20LapTrinh/capcut%20tool/app/downloader.py#L78-L88).

---

## 3. Performance Issues

### A. Sequential Subprocess Spawning (ffprobe) [Rank: High]
*   **Target File**: [media_probe.py](file:///D:/1.%20LapTrinh/capcut%20tool/media_probe.py)
*   **Issue**: The media folder scanner (`scan_media_folder()`) probes every visual media file sequentially. Because spawning a subprocess (`ffprobe.exe`) has a high startup overhead on Windows, scanning directories with hundreds of clips takes a very long time.
*   **Code Reference**: [media_probe.py:L100-116](file:///D:/1.%20LapTrinh/capcut%20tool/media_probe.py#L100-L116) (sequential loop over files).

### B. Redundant JSON Parse-Write Disk Cycles [Rank: Medium]
*   **Target File**: [capcut_keyframe_tool.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_keyframe_tool.py)
*   **Issue**: The tool loads the draft JSON, performs modifications, and writes it back to disk for individual operations (e.g. applying keyframes, then applying transitions). For large project timelines, this causes duplicate parsing and serializing cycles.
*   **Code Reference**: [capcut_keyframe_tool.py:L73-88](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_keyframe_tool.py#L73-L88) (separate `_load_draft()` calls).

---

## 4. Dead Code

### A. Unused pillow Dependency [Rank: Low]
*   **Target File**: [requirements.txt](file:///D:/1.%20LapTrinh/capcut%20tool/requirements.txt) & [scripts/build_exe.py](file:///D:/1.%20LapTrinh/capcut%20tool/scripts/build_exe.py)
*   **Issue**: `pillow>=10.0.0` is specified as a project dependency and collected by PyInstaller packaging. However, a codebase search shows that the application never imports PIL or uses image manipulation from pillow.
*   **Code Reference**: [requirements.txt:L6](file:///D:/1.%20LapTrinh/capcut%20tool/requirements.txt#L6) and [build_exe.py:L222](file:///D:/1.%20LapTrinh/capcut%20tool/scripts/build_exe.py#L222).

### B. pyJianYingDraft Template Mode [Rank: Low]
*   **Target File**: [pyJianYingDraft/template_mode.py](file:///D:/1.%20LapTrinh/capcut%20tool/pyJianYingDraft/template_mode.py)
*   **Issue**: The entire `template_mode.py` file is unused. It defines methods to load an existing CapCut draft, parse its tracks, and replace material segments. The main pipeline builds drafts from scratch templates, making this module entirely redundant.
*   **Code Reference**: [pyJianYingDraft/template_mode.py](file:///D:/1.%20LapTrinh/capcut%20tool/pyJianYingDraft/template_mode.py).

### C. Unused Imports and Helper Methods [Rank: Low]
*   **Target File**: [pyJianYingDraft/script_file.py](file:///D:/1.%20LapTrinh/capcut%20tool/pyJianYingDraft/script_file.py)
*   **Issue**: Contains imports of template mode classes and definitions of template editing functions like `import_track()` and `replace_material_by_seg()` that are never invoked.
*   **Code Reference**: [script_file.py:L12](file:///D:/1.%20LapTrinh/capcut%20tool/pyJianYingDraft/script_file.py#L12) and [script_file.py:L559-565](file:///D:/1.%20LapTrinh/capcut%20tool/pyJianYingDraft/script_file.py#L559-L565).

---

## 5. Technical Debt

### A. Monolithic GUI Script [Rank: High]
*   **Target File**: [app/gui.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/gui.py)
*   **Issue**: The UI file is a massive monolith containing parameter builders, custom layouts, history table controls, threading workers, and configurations file serialization logic. This violates single responsibility principles.
*   **Code Reference**: [app/gui.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/gui.py).

### B. Circular Dependency Resolved via Inline Imports [Rank: Medium]
*   **Target File**: [pyJianYingDraft/draft_folder.py](file:///D:/1.%20LapTrinh/capcut%20tool/pyJianYingDraft/draft_folder.py)
*   **Issue**: The library wrapper `pyJianYingDraft` imports from the parent application module `app/path_validation.py` to check project path security, creating a circular reference. This is resolved at runtime using inline imports.
*   **Code Reference**: [draft_folder.py:L35-39](file:///D:/1.%20LapTrinh/capcut%20tool/pyJianYingDraft/draft_folder.py#L35-L39).

### C. Console stdout Prints [Rank: Medium]
*   **Target File**: Throughout the codebase
*   **Issue**: The codebase relies heavily on standard print statement console logs rather than Python's standard `logging` library.
*   **Code Reference**: Multiple print statements in [capcut_draft_creator.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_draft_creator.py) and [capcut_keyframe_tool.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_keyframe_tool.py).
