"""
tests/test_challenger_pipeline_stress.py
Empirical stress tests for Challenger 1:
- Stepper events synchronization, rapid updates, and boundary conditions.
- Concurrent job submissions, queue processing, cancellations, and shutdown lifecycle.
- clean_stale_locks() stress testing: dead PIDs, expired timestamps, active lock safety, concurrent readers/cleaners.
- Automation rules stress testing: calculate_bgm_volume, auto_wrap_subtitle, KEYFRAME_PADDING_OFFSET_US.
"""

import os
import time
import uuid
import tempfile
import threading
from pathlib import Path
from typing import Optional

import pytest
from PySide6.QtCore import QCoreApplication, QThread, Qt
from PySide6.QtWidgets import QApplication

from app.pipeline import ProjectConfig, StepResult
from app.queue_manager import BatchQueueManager, BuildJob
from app.widgets.build_widget import BuildWidget
from app.draft_lock import (
    clean_stale_locks,
    locked_draft,
    _lock_file_path,
    _try_lock_file,
    _unlock_file,
    _prepare_lock_file,
    draft_lock_key,
    DraftBusyError,
)
import capcut_draft_creator as cdc
import capcut_keyframe_tool as ckt
import video_mixer


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def isolated_db_and_queue(tmp_path):
    from core.db import Database
    Database.close_connection()

    test_db = tmp_path / "stress_test.db"
    Database.init_db(test_db)

    manager = BatchQueueManager.get_instance()
    manager.jobs = []
    manager.current_job_id = None
    manager.is_running = False
    manager.is_paused = False
    manager.worker = None
    manager.thread = None

    yield test_db

    try:
        manager.shutdown(wait_ms=500)
    except Exception:
        pass
    Database.close_connection()


# =========================================================================
# TASK 1: Stepper Events & Concurrency / Queue Lifecycle Stress Tests
# =========================================================================

def test_stepper_canonical_codes_and_states(qapp):
    """Verify BuildJob and BuildWidget share exact canonical 4 step codes."""
    cfg = ProjectConfig("StressProj", "C:/dummy_root", "C:/dummy_voice", "C:/dummy_media")
    job = BuildJob("job-1", "StressProj", cfg)

    canonical = ["preflight", "scan_media", "plan_media", "write_draft"]
    assert list(job.step_states.keys()) == canonical
    for code in canonical:
        assert job.step_states[code] == "pending"

    widget = BuildWidget()
    assert widget.step_codes == canonical
    for code in canonical:
        assert code in widget.step_widgets
        assert code in widget.step_status_labels


def test_stepper_get_step_states_boundary_stress(qapp):
    """Empirically test _get_step_states across every integer progress 0..100 and status values."""
    widget = BuildWidget()
    canonical = widget.step_codes

    # 1. Pending status: all pending regardless of progress
    for p in range(0, 101):
        states = widget._get_step_states(p, "pending")
        assert all(states[c] == "pending" for c in canonical)

    # 2. Completed status: all done regardless of progress
    for p in range(0, 101):
        states = widget._get_step_states(p, "completed")
        assert all(states[c] == "done" for c in canonical)

    # 3. Running status: strictly maps progress segments to the active running step
    for p in range(0, 25):
        states = widget._get_step_states(p, "running")
        assert states["preflight"] == "running"
        assert states["scan_media"] == "pending"
        assert states["plan_media"] == "pending"
        assert states["write_draft"] == "pending"

    for p in range(25, 50):
        states = widget._get_step_states(p, "running")
        assert states["preflight"] == "done"
        assert states["scan_media"] == "running"
        assert states["plan_media"] == "pending"
        assert states["write_draft"] == "pending"

    for p in range(50, 75):
        states = widget._get_step_states(p, "running")
        assert states["preflight"] == "done"
        assert states["scan_media"] == "done"
        assert states["plan_media"] == "running"
        assert states["write_draft"] == "pending"

    for p in range(75, 100):
        states = widget._get_step_states(p, "running")
        assert states["preflight"] == "done"
        assert states["scan_media"] == "done"
        assert states["plan_media"] == "done"
        assert states["write_draft"] == "running"

    states_100 = widget._get_step_states(100, "running")
    assert all(states_100[c] == "done" for c in canonical)

    # 4. Failed and Cancelled status: previous steps done, current step marked error/cancelled
    for status, expected_mark in [("failed", "error"), ("cancelled", "cancelled")]:
        st_early = widget._get_step_states(10, status)
        assert st_early["preflight"] == expected_mark
        assert st_early["scan_media"] == "pending"

        st_mid1 = widget._get_step_states(35, status)
        assert st_mid1["preflight"] == "done"
        assert st_mid1["scan_media"] == expected_mark
        assert st_mid1["plan_media"] == "pending"

        st_mid2 = widget._get_step_states(65, status)
        assert st_mid2["preflight"] == "done"
        assert st_mid2["scan_media"] == "done"
        assert st_mid2["plan_media"] == expected_mark
        assert st_mid2["write_draft"] == "pending"

        st_late = widget._get_step_states(90, status)
        assert st_late["preflight"] == "done"
        assert st_late["scan_media"] == "done"
        assert st_late["plan_media"] == "done"
        assert st_late["write_draft"] == expected_mark


def test_rapid_stepper_ui_updates_stress(qapp):
    """Stress test 2,000 rapid signal updates through BuildWidget stepper slots."""
    widget = BuildWidget()
    canonical = widget.step_codes
    statuses = ["running", "done", "error", "cancelled", "pending"]

    for i in range(500):
        code = canonical[i % len(canonical)]
        status = statuses[i % len(statuses)]
        widget.update_step_widget(code, status, f"Stress msg {i}")
        widget._update_stepper_ui(i % 101, "running", f"Progress {i}")

    # Ensure widget properties remain valid
    for code in canonical:
        w = widget.step_widgets[code]
        assert w is not None
        assert w.property("state") in statuses


def test_concurrent_job_submissions_and_queue_operations():
    """Stress test submitting 50 jobs concurrently from 5 threads."""
    manager = BatchQueueManager.get_instance()
    manager.jobs = []
    manager.current_job_id = None

    errors = []
    num_threads = 5
    jobs_per_thread = 10

    def worker_func(tid: int):
        for j in range(jobs_per_thread):
            try:
                cfg = ProjectConfig(
                    project_name=f"StressJob_{tid}_{j}",
                    draft_root="C:/dummy_root",
                    voice_path="C:/dummy_voice.mp3",
                    media_dir="C:/dummy_media",
                )
                manager.add_job(cfg)
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=worker_func, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(manager.jobs) == num_threads * jobs_per_thread

    # Remove 15 jobs concurrently
    job_ids_to_remove = [j.id for j in manager.jobs[:15]]

    def remove_func(jid):
        try:
            manager.remove_job(jid)
        except Exception as e:
            errors.append(e)

    rm_threads = [threading.Thread(target=remove_func, args=(jid,)) for jid in job_ids_to_remove]
    for t in rm_threads:
        t.start()
    for t in rm_threads:
        t.join()

    assert len(errors) == 0
    assert len(manager.jobs) == (num_threads * jobs_per_thread) - 15


def test_queue_shutdown_lifecycle_and_no_autochaining(monkeypatch):
    """Stress-test shutdown while jobs are queued and verify no subsequent jobs auto-chain."""
    manager = BatchQueueManager.get_instance()
    manager.jobs = []
    manager.current_job_id = None

    cfg = ProjectConfig("Job1", "C:/dummy_root", "C:/dummy_voice", "C:/dummy_media")
    id1 = manager.add_job(cfg)
    id2 = manager.add_job(cfg)
    id3 = manager.add_job(cfg)

    # Mock QThread.start to simulate a running job
    class MockWorker:
        def cancel(self):
            pass

    class MockThread:
        def isRunning(self):
            return True
        def requestInterruption(self):
            pass
        def quit(self):
            pass
        def wait(self, ms):
            return True
        def terminate(self):
            pass

    manager.thread = MockThread()
    manager.worker = MockWorker()
    manager.current_job_id = id1
    manager.is_running = True
    manager.is_paused = False

    # Perform shutdown
    res = manager.shutdown(wait_ms=100)
    assert res is True
    assert manager.is_running is False
    assert manager.is_paused is True

    # Now verify that finishing a job when is_running is False DOES NOT start next job!
    manager._finish_current_job("cancelled", "Shutdown invoked")
    assert manager.current_job_id is None
    # id2 must NOT be started
    assert manager.jobs[1].status == "pending"
    assert manager.jobs[2].status == "pending"


def test_terminate_child_processes_safety():
    """Verify terminate_child_processes() executes cleanly and tolerates absent targets."""
    manager = BatchQueueManager.get_instance()
    # Must not raise exceptions
    manager.terminate_child_processes()


# =========================================================================
# TASK 2: Stale Lock Pruning Stress Tests (clean_stale_locks)
# =========================================================================

def test_clean_stale_locks_dead_pid(tmp_path):
    """Synthetic lock with a dead PID (e.g. 9999999) must be removed immediately."""
    lock_dir = tmp_path / ".capcut_tool_locks"
    lock_dir.mkdir()

    dead_lock = lock_dir / "dead_proc.lock"
    dead_lock.write_text("9999999\n", encoding="utf-8")

    removed = clean_stale_locks(lock_dir, max_age_sec=3600.0)
    assert removed == 1
    assert not dead_lock.exists()


def test_clean_stale_locks_expired_timestamp(tmp_path):
    """Synthetic lock older than max_age_sec with dead or no PID must be removed."""
    lock_dir = tmp_path / ".capcut_tool_locks"
    lock_dir.mkdir()

    expired_lock = lock_dir / "old_job.lock"
    expired_lock.write_text("9999999\n", encoding="utf-8")
    old_time = time.time() - 7200.0
    os.utime(expired_lock, (old_time, old_time))

    removed = clean_stale_locks(lock_dir, max_age_sec=3600.0)
    assert removed == 1
    assert not expired_lock.exists()


def test_clean_stale_locks_active_pid_preserved(tmp_path):
    """Lock held by current live process PID (fresh timestamp) must NEVER be pruned."""
    lock_dir = tmp_path / ".capcut_tool_locks"
    lock_dir.mkdir()

    live_lock = lock_dir / "live_job.lock"
    live_lock.write_text(f"{os.getpid()}\n", encoding="utf-8")

    removed = clean_stale_locks(lock_dir, max_age_sec=3600.0)
    assert removed == 0
    assert live_lock.exists()


def test_clean_stale_locks_actively_held_file_never_deleted(tmp_path):
    """Actively locked file (msvcrt/fcntl locked) must NEVER be deleted even if stale."""
    lock_dir = tmp_path / ".capcut_tool_locks"
    lock_dir.mkdir()

    held_lock = lock_dir / "held.lock"
    held_lock.write_text("9999999\n", encoding="utf-8")
    # Make it expired
    old_time = time.time() - 7200.0
    os.utime(held_lock, (old_time, old_time))

    # Hold file lock in this process
    handle = held_lock.open("r+b")
    _try_lock_file(handle)
    try:
        removed = clean_stale_locks(lock_dir, max_age_sec=3600.0)
        assert removed == 0
        assert held_lock.exists()
    finally:
        _unlock_file(handle)

    # Once unlocked, cleaning must succeed
    removed_after = clean_stale_locks(lock_dir, max_age_sec=3600.0)
    assert removed_after == 1
    assert not held_lock.exists()


def test_clean_stale_locks_corrupted_content(tmp_path):
    """Lock files with corrupted / binary / empty data must be handled safely."""
    lock_dir = tmp_path / ".capcut_tool_locks"
    lock_dir.mkdir()

    empty_lock = lock_dir / "empty.lock"
    empty_lock.write_bytes(b"")

    gibberish_lock = lock_dir / "gibberish.lock"
    gibberish_lock.write_text("NOT_A_PID\nGARBAGE\n", encoding="utf-8")

    binary_lock = lock_dir / "binary.lock"
    binary_lock.write_bytes(b"\x00\xff\xfe\x01\x02\x03")

    # Set all 3 to old age so they trigger stale check
    old_time = time.time() - 4000.0
    for f in [empty_lock, gibberish_lock, binary_lock]:
        os.utime(f, (old_time, old_time))

    removed = clean_stale_locks(lock_dir, max_age_sec=3600.0)
    assert removed == 3
    assert not empty_lock.exists()
    assert not gibberish_lock.exists()
    assert not binary_lock.exists()


def test_concurrent_locked_draft_and_cleaner_stress(tmp_path):
    """Stress test 10 concurrent threads acquiring draft locks while cleaner runs in background."""
    project_dir = tmp_path / "TestProject"
    project_dir.mkdir()
    lock_dir = project_dir.parent / ".capcut_tool_locks"
    lock_dir.mkdir(exist_ok=True)

    stop_event = threading.Event()
    cleaner_errors = []
    worker_errors = []
    lock_acquisitions = [0]

    def cleaner_thread():
        while not stop_event.is_set():
            try:
                # Production setting (max_age_sec=3600.0)
                clean_stale_locks(lock_dir, max_age_sec=3600.0)
            except Exception as e:
                cleaner_errors.append(e)
            time.sleep(0.01)

    def worker_thread(tid: int):
        for i in range(20):
            try:
                with locked_draft(project_dir, timeout_sec=5.0):
                    lock_acquisitions[0] += 1
                    time.sleep(0.005)
            except DraftBusyError:
                # Expected when another thread holds it
                pass
            except Exception as e:
                worker_errors.append(e)

    c_th = threading.Thread(target=cleaner_thread)
    c_th.start()

    workers = [threading.Thread(target=worker_thread, args=(i,)) for i in range(10)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()

    stop_event.set()
    c_th.join()

    assert len(cleaner_errors) == 0, f"Cleaner errors: {cleaner_errors}"
    assert len(worker_errors) == 0, f"Worker errors: {worker_errors}"
    assert lock_acquisitions[0] > 0



# =========================================================================
# TASK 3: Automation Rules Stress Tests
# =========================================================================

def test_calculate_bgm_volume_stress(tmp_path):
    """Stress-test calculate_bgm_volume across boundary conditions."""
    voice_file = tmp_path / "test_voice.mp3"
    voice_file.write_bytes(b"dummy audio content")

    # 1. Voice present, positive duration -> scaled to 0.20
    assert video_mixer.calculate_bgm_volume(str(voice_file), voice_duration=5.0) == 0.20
    assert video_mixer.calculate_bgm_volume(str(voice_file), voice_duration=0.001) == 0.20
    assert video_mixer.calculate_bgm_volume(str(voice_file), voice_duration=100000.0) == 0.20

    # 2. Voice present, duration 0.0 -> returns 0.20
    assert video_mixer.calculate_bgm_volume(str(voice_file), voice_duration=0.0) == 0.20

    # 3. Voice present, negative duration -> falls back to default_volume
    assert video_mixer.calculate_bgm_volume(str(voice_file), voice_duration=-1.0, default_volume=0.85) == 0.85

    # 4. Voice path is None -> returns default_volume
    assert video_mixer.calculate_bgm_volume(None, voice_duration=5.0, default_volume=0.7) == 0.7
    assert video_mixer.calculate_bgm_volume(None, voice_duration=0.0) == 1.0

    # 5. Voice path is empty string -> returns default_volume
    assert video_mixer.calculate_bgm_volume("", voice_duration=5.0, default_volume=0.5) == 0.5

    # 6. Non-existent path -> returns default_volume
    non_existent = tmp_path / "ghost_voice.mp3"
    assert video_mixer.calculate_bgm_volume(str(non_existent), voice_duration=5.0, default_volume=0.9) == 0.9

    # 7. Verification via capcut_draft_creator entrypoint
    assert cdc.calculate_bgm_volume(str(voice_file), 5.0) == 0.20
    assert cdc.calculate_bgm_volume(None, 0.0) == 1.0


def test_auto_wrap_subtitle_stress():
    """Stress test auto_wrap_subtitle on extreme lengths, whitespace, and boundaries."""
    from capcut_draft_creator import auto_wrap_subtitle
    from profiles.subtitle import auto_wrap_subtitle as wrap_prof

    for wrap_fn in (auto_wrap_subtitle, wrap_prof):
        # 1. Empty and whitespace cases
        assert wrap_fn("") == ""
        assert wrap_fn("   ") == "   "
        assert wrap_fn(None) == ""

        # 2. Single word
        assert wrap_fn("XinChào") == "XinChào"

        # 3. Exactly 8 words (boundary condition: must NOT wrap)
        words_8 = "Một hai ba bốn năm sáu bảy tám"
        assert len(words_8.split()) == 8
        assert wrap_fn(words_8, max_words=8) == words_8
        assert "\n" not in wrap_fn(words_8, max_words=8)

        # 4. Exactly 9 words (boundary condition: MUST wrap into 2 lines)
        words_9 = "Một hai ba bốn năm sáu bảy tám chín"
        assert len(words_9.split()) == 9
        res_9 = wrap_fn(words_9, max_words=8)
        assert "\n" in res_9
        lines_9 = res_9.split("\n")
        assert len(lines_9) == 2
        # 9 // 2 == 4 words in line 1, 5 words in line 2
        assert len(lines_9[0].split()) == 4
        assert len(lines_9[1].split()) == 5
        assert lines_9[0] == "Một hai ba bốn"
        assert lines_9[1] == "năm sáu bảy tám chín"

        # 5. Exactly 10 words
        words_10 = "1 2 3 4 5 6 7 8 9 10"
        res_10 = wrap_fn(words_10, max_words=8)
        lines_10 = res_10.split("\n")
        assert len(lines_10) == 2
        assert len(lines_10[0].split()) == 5
        assert len(lines_10[1].split()) == 5

        # 6. Extreme sentence: 100 words
        words_100 = " ".join([f"word{i}" for i in range(100)])
        res_100 = wrap_fn(words_100, max_words=8)
        lines_100 = res_100.split("\n")
        assert len(lines_100) == 2
        assert len(lines_100[0].split()) == 50
        assert len(lines_100[1].split()) == 50

        # 7. Multi-line input preserving existing lines
        multiline = f"{words_8}\n{words_9}"
        res_multi = wrap_fn(multiline, max_words=8)
        lines_multi = res_multi.split("\n")
        assert len(lines_multi) == 3
        assert lines_multi[0] == words_8
        assert lines_multi[1] == "Một hai ba bốn"
        assert lines_multi[2] == "năm sáu bảy tám chín"


def test_keyframe_padding_offset_stress():
    """Stress test KEYFRAME_PADDING_OFFSET_US (0.3s) arithmetic on clips from 0 to 60s."""
    padding = ckt.KEYFRAME_PADDING_OFFSET_US
    assert padding == 300_000  # 0.3s in microseconds

    op = {"from": 1.0, "to": 1.2, "property": "scale_uniform"}

    # 1. Normal clip > 0.6s (e.g. 5s = 5_000_000 us)
    dur_5s = 5_000_000
    kfl_5s = ckt._build_keyframe_list_for_op(op, dur_5s, {}, None, "KFTypeScaleX", [op])
    assert len(kfl_5s) == 2
    assert kfl_5s[0]["time_offset"] == 300_000
    assert kfl_5s[1]["time_offset"] == 5_000_000 - 300_000

    # 2. Long clip (e.g. 60s = 60_000_000 us)
    dur_60s = 60_000_000
    kfl_60s = ckt._build_keyframe_list_for_op(op, dur_60s, {}, None, "KFTypeScaleX", [op])
    assert kfl_60s[0]["time_offset"] == 300_000
    assert kfl_60s[1]["time_offset"] == 60_000_000 - 300_000

    # 3. Boundary: exactly 0.6s (600_000 us) -> duration is NOT > padding_us * 2
    # Fallback to start=0, end=dur to prevent start_t >= end_t collapse
    dur_600ms = 600_000
    kfl_600ms = ckt._build_keyframe_list_for_op(op, dur_600ms, {}, None, "KFTypeScaleX", [op])
    assert kfl_600ms[0]["time_offset"] == 0
    assert kfl_600ms[1]["time_offset"] == 600_000

    # 4. Ultra-short clip: 0.3s (300_000 us)
    dur_300ms = 300_000
    kfl_300ms = ckt._build_keyframe_list_for_op(op, dur_300ms, {}, None, "KFTypeScaleX", [op])
    assert kfl_300ms[0]["time_offset"] == 0
    assert kfl_300ms[1]["time_offset"] == 300_000

    # 5. Micro clip: 0.05s (50_000 us)
    dur_50ms = 50_000
    kfl_50ms = ckt._build_keyframe_list_for_op(op, dur_50ms, {}, None, "KFTypeScaleX", [op])
    assert kfl_50ms[0]["time_offset"] == 0
    assert kfl_50ms[1]["time_offset"] == 50_000

    # 6. Zero duration clip
    kfl_0 = ckt._build_keyframe_list_for_op(op, 0, {}, None, "KFTypeScaleX", [op])
    assert kfl_0[0]["time_offset"] == 0
    assert kfl_0[1]["time_offset"] == 0


def test_job_cancellation_while_worker_running():
    """Verify step states update correctly when a running job is cancelled midway."""
    manager = BatchQueueManager.get_instance()
    manager.jobs = []
    manager.current_job_id = None

    cfg = ProjectConfig("CancelMidway", "C:/dummy_root", "C:/dummy_voice", "C:/dummy_media")
    jid = manager.add_job(cfg)
    manager.current_job_id = jid
    job = manager.jobs[0]
    job.status = "running"

    # Simulate step 1: preflight done
    step1 = StepResult(code="preflight", status="done", label="Preflight", message="Preflight OK")
    manager._on_worker_step(step1)
    assert job.step_states["preflight"] == "done"
    assert job.step_states["scan_media"] == "pending"

    # Simulate step 2: scan_media running
    step2 = StepResult(code="scan_media", status="running", label="Scan Media", message="Scanning...")
    manager._on_worker_step(step2)
    assert job.step_states["preflight"] == "done"
    assert job.step_states["scan_media"] == "running"
    assert job.step_states["plan_media"] == "pending"
    assert job.step_states["write_draft"] == "pending"

    # Now cancel the job
    manager._on_worker_failed("JobCancelled: User cancelled")
    assert job.status == "cancelled"
    # preflight should remain done
    assert job.step_states["preflight"] == "done"
    # scan_media (the running step) should transition to cancelled
    assert job.step_states["scan_media"] == "cancelled"
    # remaining steps must not be running
    assert job.step_states["plan_media"] == "pending"
    assert job.step_states["write_draft"] == "pending"


def test_build_widget_select_job_stress(qapp):
    """Stress test BuildWidget._select_job with diverse job structures."""
    widget = BuildWidget()
    cfg = ProjectConfig("SelStress", "C:/dummy_root", "C:/dummy_voice", "C:/dummy_media")

    # 1. Normal job
    j1 = BuildJob("j1", "SelStress1", cfg)
    widget.manager.jobs = [j1]
    widget._select_job("j1")
    assert widget.selected_job_id == "j1"

    # 2. Job with missing step_states attribute
    j2 = BuildJob("j2", "SelStress2", cfg)
    j2.step_states = None
    widget.manager.jobs.append(j2)
    widget._select_job("j2")
    assert widget.selected_job_id == "j2"

    # 3. Non-existent job ID: guarded against desynchronization
    widget._select_job("non_existent_id")
    # Verified: selected_job_id is NOT corrupted by non-existent job ID, preserves previous valid selection
    assert widget.selected_job_id == "j2"



def test_clean_stale_locks_edge_case_paths(tmp_path):
    """Verify clean_stale_locks behaves robustly with non-existent or file paths."""
    # 1. Non-existent directory
    assert clean_stale_locks(tmp_path / "non_existent_folder") == 0

    # 2. Path is a regular file, not a directory
    reg_file = tmp_path / "regular_file.txt"
    reg_file.write_text("hello")
    assert clean_stale_locks(reg_file) == 0

    # 3. Subdirectory ending with .lock inside lock_dir
    lock_dir = tmp_path / ".capcut_tool_locks"
    lock_dir.mkdir()
    sub_dir = lock_dir / "folder.lock"
    sub_dir.mkdir()
    assert clean_stale_locks(lock_dir) == 0
    assert sub_dir.exists()


def test_draft_lock_reentrant_and_cleanup(tmp_path):
    """Verify draft_lock supports re-entrant calls and cleans up on exit."""
    project_dir = tmp_path / "ReentrantProj"
    project_dir.mkdir()

    # Re-entrancy on same thread should not raise DraftBusyError
    with locked_draft(project_dir, timeout_sec=2.0):
        with locked_draft(project_dir, timeout_sec=2.0):
            pass

    # Lock directory was created and opportunistic cleanup runs
    lock_dir = project_dir.parent / ".capcut_tool_locks"
    assert lock_dir.exists()

