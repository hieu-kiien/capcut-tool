# Remaining Review Tasks - CapCut Long Story Studio

## Scope

This handoff covers only the issues still open after reviewing Gemini's latest changes.

Work in:

- `app/path_validation.py`
- `pyJianYingDraft/draft_folder.py`
- `media_probe.py`
- `capcut_keyframe_tool.py`
- `app/gui.py`
- `tests/test_new_features.py`
- `tests/test_pipeline.py` if needed

Do not work in generated/package folders:

- `build/`
- `dist/`
- `obfuscated/`
- `tools/`
- `__pycache__/`

## Current Verification State

`pytest` is not installed in the current Python environment.

These commands passed when run directly:

```powershell
python tests\test_new_features.py
python tests\test_pipeline.py
python -m compileall app pyJianYingDraft capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py tests -q
```

## Priority 1 - Fully Close Core Draft Path Traversal

### Problem

`DraftFolder.create_draft()` now has a path-safety guard, but other core methods still join user-controlled draft names directly:

- `pyJianYingDraft/draft_folder.py:51` `remove()`
- `pyJianYingDraft/draft_folder.py:233` `inspect_material()`
- `pyJianYingDraft/draft_folder.py:249` `load_template()`
- `pyJianYingDraft/draft_folder.py:270` `duplicate_as_template()`

Confirmed failing behavior:

```python
df.remove("../outside_victim")
```

This can delete a folder outside the draft root.

### Implementation

1. Add a private helper in `DraftFolder`, for example `_resolve_draft_path(draft_name: str) -> str`.

2. The helper must:
   - reject empty/whitespace names
   - reject absolute paths
   - reject names containing path separators `/` or `\`
   - reject Windows-invalid path chars `: * ? " < > |`
   - reject `..`
   - resolve `folder_path / draft_name`
   - ensure the resolved path is strictly inside the resolved draft root

3. Prefer reusing `app.path_validation.validate_project_name()` if import layering is acceptable. If avoiding app-to-library coupling, duplicate a small local guard in `draft_folder.py`.

4. Replace all direct path joins for draft names with the helper:
   - `remove()`
   - `create_draft()`
   - `inspect_material()`
   - `load_template()`
   - `duplicate_as_template()` for both `template_name` and `new_draft_name`

5. In `duplicate_as_template()`:
   - validate both source and destination names before any file operation
   - if `new_draft_path` exists and `allow_replace=True`, make sure replacement remains inside root
   - do not create partial outside folders when loading the copied template fails

### Acceptance Criteria

- `create_draft("../x", ...)` raises `ValueError`.
- `remove("../x")` raises `ValueError` and does not delete outside folders.
- `load_template("../x")` raises `ValueError`.
- `duplicate_as_template("template", "../outside")` raises `ValueError` and does not create `outside`.
- Valid names still work.

### Suggested Tests

Add tests to `tests/test_new_features.py`:

- temp draft root with an outside sibling folder
- call `DraftFolder.remove("../outside")`
- assert outside folder still exists
- call `duplicate_as_template("template", "../outside_copy")`
- assert outside copy was not created
- call valid `create_draft("Safe_Project", ...)` if the fixture can satisfy the draft template requirements

## Priority 2 - Make Media Probe Timeout Truly Non-Hanging

### Problem

`ffprobe` now has a 15s timeout, but `probe_media()` falls back to `_probe_with_pymediainfo()` after any ffprobe error, including timeout:

- `media_probe.py:127`
- `media_probe.py:133`
- `media_probe.py:217`

`pymediainfo.MediaInfo.parse()` has no current timeout in this code path. A corrupt, locked, slow, or network-backed file can still hang.

### Implementation

1. Decide fallback policy:
   - recommended: if ffprobe exists and times out, return the ffprobe timeout error directly and do not fallback to MediaInfo
   - fallback to MediaInfo only when ffprobe is unavailable, or when ffprobe returns a normal parse error and MediaInfo is explicitly desired

2. Update `_probe_with_ffprobe()` to set a recognizable timeout error.
   - example: `error=f"ffprobe timed out after {timeout_sec}s"`
   - optionally add a helper `_is_timeout_error(asset)`.

3. Update `probe_media()`:
   - if ffprobe returns success, return it
   - if ffprobe returns timeout, return it immediately
   - if ffprobe returns non-timeout error, either return it or fallback to MediaInfo based on the chosen policy

4. Add cancellation support between files is already present in `scan_media_folder()`. Keep it.

5. Optional stronger fix:
   - run MediaInfo in a separate process with timeout if MediaInfo fallback must remain
   - do not use a thread-only timeout for MediaInfo because a hung native call may not stop cleanly

### Acceptance Criteria

- A mocked `subprocess.run(... timeout=...)` raising `TimeoutExpired` returns a `MediaAsset` from source `ffprobe`.
- Timeout case does not call `_probe_with_pymediainfo()`.
- Scan cancellation between files still stops scanning early.
- Valid media probing still works.

### Suggested Tests

In `tests/test_new_features.py`:

- monkeypatch or temporarily replace:
  - `media_probe.resolve_ffprobe`
  - `media_probe.subprocess.run`
  - `media_probe._probe_with_pymediainfo`
- raise `subprocess.TimeoutExpired`
- assert `_probe_with_pymediainfo` was not called
- assert returned asset has `error` containing `timed out`

For cancellation:

- create two fake media files
- monkeypatch `probe_media()` to record calls
- use `cancel_check` that returns `False` once, then `True`
- assert only one file was probed

## Priority 3 - Make Transition Targeting Strict

### Problem

`apply_random_transitions_to_file()` prefers the track named `long_story_background`, but if that name is missing it falls back to `_pick_primary_video_track_indices()`.

For drafts outside the new pipeline, this can apply transitions to the wrong overlay track if the overlay has the most segments.

Relevant file:

- `capcut_keyframe_tool.py:583`

### Implementation

1. Replace the fallback behavior with stricter targeting.

2. Recommended behavior:
   - if a video track named `long_story_background` exists, use only that track
   - if no such track exists, do not apply transitions automatically
   - return `0`
   - optionally log/print a clear warning if this CLI-style tool already prints warnings elsewhere

3. If backwards compatibility is required:
   - add an explicit argument/param such as `transition_allow_primary_fallback`
   - default it to `False`
   - only use `_pick_primary_video_track_indices()` when the explicit flag is true

4. Keep `transition_apply_all` behavior scoped only inside the selected target track.

### Acceptance Criteria

- Draft with `long_story_background` gets transitions only on that track.
- Logo and animation tracks receive no transition refs.
- Draft without `long_story_background` receives no transitions by default.
- No fallback applies transitions to arbitrary overlay tracks unless explicitly enabled.

### Suggested Tests

Extend `test_transition_track_targeting()` or add a new test:

- mock draft with no `long_story_background`
- first video track has 2 overlay segments
- second video track has 1 background-looking segment under another name
- call `apply_random_transitions_to_file()`
- assert `changed == 0`
- assert all `extra_material_refs` remain empty

## Priority 4 - Safer App Shutdown For Worker Threads

### Problem

`MainWindow.closeEvent()` cancels workers, waits 2 seconds, then calls `QThread.terminate()`.

Relevant file:

- `app/gui.py:2614`

This can interrupt draft backup/write operations mid-flight. It is especially risky for:

- pipeline draft creation
- keyframe JSON writes
- backup restore/copy

### Implementation

1. Do not call `terminate()` for pipeline/keyframe threads that may write files.

2. On close:
   - call worker `cancel()` if available
   - call `thread.quit()`
   - wait briefly
   - if still running, either ignore close and show a message, or accept close only after worker finishes

3. Recommended UI behavior:
   - if pipeline/keyframe worker is running, show confirmation:
     - "A job is still running. Cancel and wait?"
   - if user chooses cancel, request cancel and keep app open until the thread finishes
   - if user chooses no, ignore close event

4. For `SplitWorker`, terminate the FFmpeg subprocess through `split_worker.cancel()` first. Avoid `QThread.terminate()` if possible.

5. Add a small helper to reduce duplicate close logic, for example:
   - `_request_worker_shutdown() -> bool`
   - returns `True` if safe to close, `False` if close should be ignored

### Acceptance Criteria

- Closing during media scan requests cancellation and does not hard-terminate the thread.
- Closing during draft write does not kill the thread mid-write.
- Split worker cancellation terminates FFmpeg process and then exits normally.
- App no longer waits forever on close.

### Suggested Manual Test

1. Start a long media scan.
2. Close the app.
3. Confirm cancellation.
4. App should either wait cleanly or stay open until worker exits.
5. No partial/corrupt draft writes caused by forced thread termination.

## Priority 5 - Encoding Cleanup For User-Facing Messages

### Problem

Several edited files display mojibake in the PowerShell output, for example Vietnamese text appears as `TÃªn dá»± Ã¡n`.

This may only be console codepage display, but verify actual UI strings.

### Implementation

1. Confirm files are saved as UTF-8.

2. Use Python to inspect strings with `unicode_escape` if needed.

3. If the actual file content is corrupted, rewrite affected user-facing strings in UTF-8.

4. Do not change Chinese comments from upstream unless necessary.

### Acceptance Criteria

- UI error dialogs display Vietnamese correctly.
- Python reads source files as UTF-8 without syntax or encoding errors.
- Existing tests and compileall still pass.

## Final Verification Commands

If installing pytest is allowed:

```powershell
python -m pip install pytest
python -m pytest -q tests
```

Without installing pytest:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python tests\test_new_features.py
python tests\test_pipeline.py
python -m compileall app pyJianYingDraft capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py tests -q
```

Run targeted manual checks:

1. Invalid project names are rejected before file operations.
2. Existing project overwrite prompts in GUI and old draft is backed up.
3. Transition does not touch logo/animation tracks.
4. Media scan can be cancelled.
5. Lossless split remains responsive and STOP terminates FFmpeg.

## Handoff Prompt For Another AI

Use this prompt:

```text
You are continuing work in the CapCut Long Story Studio repo.

Read docs/REVIEW_REMAINING_TASKS.md first. Implement the remaining tasks in priority order:

1. fully close DraftFolder path traversal across remove/load/inspect/duplicate/create
2. prevent ffprobe timeout from falling into a potentially hanging MediaInfo fallback
3. make transition targeting strict to long_story_background by default
4. remove unsafe QThread.terminate behavior from GUI shutdown
5. verify or fix mojibake in user-facing messages

Add focused tests in tests/test_new_features.py. Do not touch build/, dist/, obfuscated/, tools/, or __pycache__/.

After implementation, run:

python tests\test_new_features.py
python tests\test_pipeline.py
python -m compileall app pyJianYingDraft capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py tests -q

If pytest is available, also run python -m pytest -q tests.

Report changed files, test results, and any remaining manual checks.
```
