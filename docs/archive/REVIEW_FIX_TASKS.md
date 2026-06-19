# Review Fix Tasks - CapCut Long Story Studio

## Scope

Fix the issues found in review for:

- `app/`
- root `*.py`
- `tests/`

Do not work inside:

- `dist/`
- `build/`
- `tools/`
- `obfuscated/pyJianYingDraft/metadata/`

## Priority Order

1. P1: Project name/path safety and draft overwrite protection.
2. P2: Transition application must target only the main video/background track.
3. P2: Media scan/probe must support cancellation and subprocess timeout.
4. P2: Lossless split must run outside the UI thread.

## Task 1 - Make Project Creation Path-Safe

### Problem

The UI only checks that `project_name` is non-empty. The pipeline then calls draft creation with `allow_replace=True`. The underlying draft creation joins `draft_root` and `project_name`, and deletes the existing folder before recreating it.

Risk:

- `..\some_folder` or names containing `/` or `\` can escape `draft_root`.
- A duplicate project name silently deletes the existing draft.

Relevant files:

- `app/gui.py`
- `app/pipeline.py`
- `capcut_draft_creator.py`
- `pyJianYingDraft/draft_folder.py`

### Implementation

1. Add a validation helper near pipeline or GUI code, for example:
   - reject empty names
   - reject `..`
   - reject `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`
   - reject absolute paths
   - resolve `draft_root / project_name` and ensure the resolved path is inside resolved `draft_root`

2. In `app/gui.py`, validate the project name before starting the pipeline.

3. In `app/pipeline.py` or `capcut_draft_creator.py`, validate again before writing. Do not rely only on UI validation.

4. Change overwrite behavior:
   - default should not silently replace existing draft
   - either set `allow_replace=False`, or add a clear UI confirmation before allowing replace
   - if overwrite is allowed, create a backup first or make the behavior explicit in the confirmation

### Acceptance Criteria

- Project name `My_Project` works.
- Project name `..\OtherFolder` is rejected before any file operation.
- Project name `abc/def` and `abc\def` are rejected.
- Existing project name does not get deleted silently.
- Error message tells the user what to fix.

### Suggested Tests

Add tests for:

- valid project name
- invalid path traversal name
- invalid separator name
- existing draft folder with replacement disabled

## Task 2 - Restrict Transitions To Main Video Track

### Problem

Keyframe application already chooses primary video tracks, but transition application loops over every track. Generated drafts can contain:

- background video track
- logo video overlay track
- animation video overlay track

Transitions should be applied only to the main background/video track, not logo or animation overlays.

Relevant files:

- `capcut_keyframe_tool.py`
- `app/pipeline.py`
- `app/gui.py`
- `capcut_draft_creator.py`

### Implementation

1. In `capcut_keyframe_tool.apply_random_transitions_to_file`, reuse `_pick_primary_video_track_indices(tracks)`.

2. Iterate with `enumerate(data.get("tracks") or [])`.

3. Skip tracks whose index is not in `primary_track_indices`.

4. Preserve the existing `apply_all_cuts` behavior, but only inside the selected main track unless an explicit future option says "all tracks".

5. Consider naming-based targeting as a fallback:
   - prefer track named `long_story_background` when present
   - otherwise use `_pick_primary_video_track_indices`

### Acceptance Criteria

- A draft with background + logo + animation tracks gets transitions only on background cuts.
- Logo/animation track segments do not receive transition refs.
- Existing keyframe behavior remains unchanged.

### Suggested Tests

Create a small fake `draft_content.json` with:

- one background video track with 3 segments
- one logo video track with 1 segment
- one animation video track with 2 segments

Run `apply_random_transitions_to_file` and assert:

- background segments except last have transition refs
- logo/animation segments have no new transition refs

## Task 3 - Add Cancel And Timeout To Media Probing

### Problem

Pipeline cancellation is checked only before and after large steps. During media scan, each file is probed with `ffprobe`, and `ffprobe` currently has no timeout. A corrupt, locked, slow, or network-backed file can make the worker hang. Closing the app can also freeze because the GUI waits for the worker thread.

Relevant files:

- `app/pipeline.py`
- `media_probe.py`
- `video_mixer.py`
- `app/gui.py`

### Implementation

1. Add a `timeout_sec` argument to `media_probe.probe_media`, default around 15 seconds.

2. Pass that timeout into `_probe_with_ffprobe`.

3. Add `timeout=timeout_sec` to `subprocess.run` in `_probe_with_ffprobe`.

4. Handle `subprocess.TimeoutExpired` and return a `MediaAsset` with:
   - `media_type="unknown"` or best-known type
   - `duration_us=0`
   - `source="ffprobe"`
   - `error="ffprobe timed out after Ns"`

5. Add optional `cancel_check` to scan flow:
   - `PipelineRunner.scan_media`
   - `video_mixer.scan_media_folder` or `media_probe.scan_media_folder`
   - check cancellation between files

6. Do not call `thread.wait()` forever on close. If needed, use a bounded wait and show/allow graceful shutdown.

### Acceptance Criteria

- A hanging `ffprobe` cannot block longer than the configured timeout per file.
- Cancel during media scanning stops before scanning all files.
- Pipeline reports a clear cancellation message.
- Valid media scanning still works.

### Suggested Tests

- Monkeypatch `_probe_with_ffprobe` or `subprocess.run` to raise `TimeoutExpired`.
- Assert the returned asset has an error and scan continues/skips it.
- Add a cancel callback that returns true after the first file and assert the scan stops.

## Task 4 - Move Lossless Split To Worker Thread

### Problem

The lossless split button runs FFmpeg with `subprocess.run` directly in the UI click handler. Large videos block the whole app until FFmpeg exits.

Relevant file:

- `app/gui.py`

### Implementation

1. Create a `SplitWorker(QObject)` similar to `PipelineWorker` and `KeyframeWorker`.

2. Move FFmpeg split execution out of `_run_split_click` and into the worker.

3. Worker signals should include:
   - log messages
   - finished result with created file count and output directory
   - failed message

4. UI behavior:
   - disable split controls while running
   - keep the rest of the app responsive
   - show clear success/failure message
   - optionally support cancel by terminating the FFmpeg process

5. Avoid `QApplication.processEvents()` as the main responsiveness mechanism once the worker exists.

### Acceptance Criteria

- Clicking split starts a background worker.
- App remains responsive during FFmpeg execution.
- Button state is restored on success and failure.
- Failure output is shown in the log.

### Suggested Tests

Manual smoke test is acceptable:

1. Open the app.
2. Choose a long-ish local video.
3. Start split.
4. Verify window can still move/respond while FFmpeg runs.
5. Verify output files are created.

## Verification Commands

The current environment did not have `pytest` installed. Use one of these options.

Install pytest if allowed:

```powershell
python -m pip install pytest
python -m pytest -q tests
```

Without installing pytest, run the existing script-style tests:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python tests\test_new_features.py
python tests\test_pipeline.py
```

Also run a syntax/import smoke check:

```powershell
python -m py_compile app\gui.py app\pipeline.py app\presets.py main.py runtime_tools.py media_probe.py video_mixer.py capcut_draft_creator.py capcut_keyframe_tool.py draft_doctor.py
```

## Definition Of Done

- All four tasks are implemented.
- Existing tests pass.
- New tests cover project-name validation and transition track targeting.
- Manual smoke test confirms:
  - creating a draft still works
  - invalid project names are rejected
  - transition does not touch logo/animation tracks
  - split video no longer freezes the UI

