# AGENT CONTEXT: Guide for AI Coders

This document provides essential engineering context, execution guardrails, development workflows, and critical rules for AI Agents collaborating on this codebase.

---

## 1. Project Goal

The primary goal of CapCut Long Story Studio is to fully automate the timeline assembly of long storytelling videos directly into CapCut PC project drafts. The application acts as a middleman that processes audio assets, SRT subtitles, and background visual folders, generates a matching timeline JSON structure, and injects keyframes and transitions. This eliminates hours of manual visual sequencing, letting creators focus on voiceovers and final video review.

---

## 2. Important Files

Below is a curated index of critical entry points and core backend files that any developer or agent must review:

*   **[main.py](file:///D:/1.%20LapTrinh/capcut%20tool/main.py)**: The main entry point. Sets environment settings and font bindings before showing the UI.
*   **[app/gui.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/gui.py)**: The central GUI wrapper. Orchestrates user configurations and starts backend workers in background threads.
*   **[app/pipeline.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/pipeline.py)**: The orchestration pipeline. Directs preflight checks, folder scans, visual mixes, draft builds, and effect injection.
*   **[capcut_draft_creator.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_draft_creator.py)**: Core draft folder builder. Configures resource registries and overlay overlays.
*   **[capcut_keyframe_tool.py](file:///D:/1.%20LapTrinh/capcut%20tool/capcut_keyframe_tool.py)**: Core JSON timeline injector. Modifies keyframe coordinate tracks and transition segments.
*   **[core/path_validation.py](file:///D:/1.%20LapTrinh/capcut%20tool/core/path_validation.py)**: Essential security filter. Prevents directory traversal attacks in project directory parameters.
*   **[app/draft_lock.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/draft_lock.py)**: Essential file locker. Prevents concurrent processes from modifying CapCut JSON timelines simultaneously.

---

## 3. Development Workflow

AI Agents and developers must adhere to the following workflow sequence:

1.  **Read Context Files**: Start by checking `docs/PROJECT_MAP.md` and `docs/CODE_AUDIT.md`. Do not scan the entire codebase.
2.  **Run Local Checks**: Before compiling or committing code, run the local verification suite:
    *   **Unit Tests**:
        ```powershell
        python -m pytest -q tests
        ```
    *   **Compilation Check**:
        ```powershell
        python -m compileall app pyJianYingDraft capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py tests -q
        ```
3.  **Perform Smoke Tests**: Validate UI behaviors manually by running the Python main script directly:
    ```powershell
    python main.py
    ```
4.  **Avoid Repetitive Packaging**: Do **NOT** run the PyInstaller compilation command `python scripts\build_exe.py` unless the user explicitly requests a release build. This command is resource-heavy and takes several minutes.

---

## 4. Things Agents Must Know Before Editing

### A. Strict File Locking [Rank: Critical]
*   **Target File**: [app/draft_lock.py](file:///D:/1.%20LapTrinh/capcut%20tool/app/draft_lock.py)
*   **Context**: CapCut PC keeps project timeline files open. Any edits made without locking the folder path will be overwritten or corrupted by CapCut.
*   **Rule**: Always wrap operations modifying draft folders inside the `locked_draft()` context manager.

### B. Enforce Path Validation [Rank: High]
*   **Target File**: [core/path_validation.py](file:///D:/1.%20LapTrinh/capcut%20tool/core/path_validation.py)
*   **Context**: All project files are created relative to the user's CapCut draft directory.
*   **Rule**: Any new interface options or backend functions resolving user-provided project name inputs MUST validate them using `validate_project_name()`.

### C. Quota-Saver Command Limitations [Rank: High]
*   **Context**: Unbounded commands consume high resources and clutter execution contexts.
*   **Rule**: Keep terminal outputs clean. Limit lines shown. Exclude folders like `.git`, `__pycache__`, `venv`, and `tools/` from all folder search scripts.
