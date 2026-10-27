from __future__ import annotations

import os
import hashlib
import time
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator


DEFAULT_DRAFT_LOCK_TIMEOUT_SEC = 30.0


class DraftBusyError(RuntimeError):
    """Raised when another task is already writing the same draft project."""


_registry_lock = threading.Lock()
_locks: dict[str, threading.RLock] = {}
_thread_state = threading.local()


def draft_lock_key(project_path: str | Path) -> str:
    path = Path(project_path).expanduser().resolve(strict=False)
    return os.path.normcase(str(path))


def _get_lock(key: str) -> threading.RLock:
    with _registry_lock:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock


def _held_depths() -> dict[str, int]:
    depths = getattr(_thread_state, "draft_lock_depths", None)
    if depths is None:
        depths = {}
        _thread_state.draft_lock_depths = depths
    return depths


def _lock_file_path(project_path: str | Path, key: str) -> Path:
    project = Path(project_path).expanduser().resolve(strict=False)
    lock_dir = project.parent / ".capcut_tool_locks"
    lock_name = hashlib.sha256(key.encode("utf-8", errors="surrogatepass")).hexdigest()
    return lock_dir / f"{lock_name}.lock"


def _prepare_lock_file(lock_path: Path) -> BinaryIO:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(f"{os.getpid()}\n".encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    handle.seek(0)
    return handle


def _try_lock_file(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.lockf(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB, 1)


def _unlock_file(handle: BinaryIO) -> None:
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.lockf(handle.fileno(), fcntl.LOCK_UN, 1)
    finally:
        handle.close()


def _acquire_file_lock(project_path: str | Path, key: str, timeout_sec: float) -> BinaryIO:
    project_name = Path(project_path).name or str(project_path)
    lock_path = _lock_file_path(project_path, key)
    deadline = time.monotonic() + max(0.0, float(timeout_sec))

    while True:
        handle = None
        try:
            handle = _prepare_lock_file(lock_path)
            _try_lock_file(handle)
            return handle
        except OSError:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
            if time.monotonic() >= deadline:
                raise DraftBusyError(
                    f"Du an CapCut '{project_name}' dang duoc xu ly boi mot cua so/tien trinh khac. "
                    "Vui long doi tac vu hien tai hoan tat roi thu lai."
                )
            time.sleep(0.05)


@contextmanager
def locked_draft(
    project_path: str | Path,
    *,
    timeout_sec: float = DEFAULT_DRAFT_LOCK_TIMEOUT_SEC,
) -> Iterator[None]:
    key = draft_lock_key(project_path)
    lock = _get_lock(key)
    timeout = max(0.0, float(timeout_sec))
    deadline = time.monotonic() + timeout
    acquired = lock.acquire(timeout=timeout)
    if not acquired:
        project_name = Path(project_path).name or str(project_path)
        raise DraftBusyError(
            f"Du an CapCut '{project_name}' dang duoc xu ly boi tac vu khac. "
            "Vui long doi tac vu hien tai hoan tat roi thu lai."
        )
    depths = _held_depths()
    reentrant = depths.get(key, 0) > 0
    file_lock: BinaryIO | None = None
    registered = False
    try:
        if not reentrant:
            remaining = max(0.0, deadline - time.monotonic())
            file_lock = _acquire_file_lock(project_path, key, remaining)
        depths[key] = depths.get(key, 0) + 1
        registered = True
        yield
    finally:
        if registered:
            current_depth = depths.get(key, 0)
            if current_depth <= 1:
                depths.pop(key, None)
                if file_lock is not None:
                    _unlock_file(file_lock)
                    file_lock = None
            else:
                depths[key] = current_depth - 1
        elif file_lock is not None:
            _unlock_file(file_lock)
        lock.release()
        
        # Opportunistically clean stale locks in lock_dir
        try:
            lock_dir = Path(project_path).expanduser().resolve(strict=False).parent / ".capcut_tool_locks"
            if lock_dir.exists():
                clean_stale_locks(lock_dir, max_age_sec=3600.0)
        except Exception:
            pass


def clean_stale_locks(lock_dir: str | Path, max_age_sec: float = 3600.0) -> int:
    """
    Cleans up stale .lock files in the specified lock directory.
    A lock file is considered stale if:
    1. It is older than max_age_sec (default 1 hour) and no longer held by any process, OR
    2. The PID recorded in the file is no longer alive, and the file is not currently locked.

    Returns the number of removed lock files.
    """
    directory = Path(lock_dir).expanduser().resolve(strict=False)
    if not directory.exists() or not directory.is_dir():
        return 0

    removed_count = 0
    now = time.time()

    for lock_file in directory.glob("*.lock"):
        if not lock_file.is_file():
            continue
        try:
            mtime = lock_file.stat().st_mtime
            age = now - mtime
            is_stale = False
            recorded_pid: int | None = None

            try:
                raw_text = lock_file.read_text(encoding="utf-8", errors="ignore").strip()
                first_line = raw_text.splitlines()[0].strip() if raw_text else ""
                if first_line.isdigit():
                    recorded_pid = int(first_line)
            except Exception:
                pass

            if recorded_pid is not None:
                try:
                    import psutil
                    pid_alive = psutil.pid_exists(recorded_pid)
                except Exception:
                    try:
                        os.kill(recorded_pid, 0)
                        pid_alive = True
                    except OSError:
                        pid_alive = False

                if not pid_alive:
                    is_stale = True

            if age >= max_age_sec:
                is_stale = True

            if is_stale:
                handle = None
                try:
                    handle = lock_file.open("r+b")
                    _try_lock_file(handle)
                    _unlock_file(handle)
                    handle = None
                    lock_file.unlink()
                    removed_count += 1
                except (OSError, PermissionError):
                    pass
                finally:
                    if handle is not None:
                        try:
                            handle.close()
                        except Exception:
                            pass
        except Exception:
            pass

    return removed_count


prune_stale_locks = clean_stale_locks
