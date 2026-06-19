import os
import pytest
from unittest.mock import patch
from pathlib import Path
import threading
import time

from media_probe import (
    probe_media,
    clear_media_probe_cache,
    set_media_probe_cache_max_size,
    MediaAsset,
    _MEDIA_PROBE_CACHE
)

@pytest.fixture(autouse=True)
def clean_cache():
    clear_media_probe_cache()
    set_media_probe_cache_max_size(1000)
    yield
    clear_media_probe_cache()


def test_cache_hit_and_miss(tmp_path):
    file_path = tmp_path / "test.mp4"
    file_path.write_bytes(b"dummy video content")

    mock_asset = MediaAsset(
        path=str(file_path.resolve()),
        media_type="video",
        duration_us=1000000,
        width=1920,
        height=1080,
        fps=30.0,
        source="ffprobe"
    )

    with patch("media_probe._probe_with_ffprobe", return_value=mock_asset) as mock_ffprobe:
        # First call: cache miss, probes the file
        asset1 = probe_media(file_path)
        assert asset1.path == str(file_path.resolve())
        assert asset1.media_type == "video"
        mock_ffprobe.assert_called_once()

        # Second call: cache hit, should not call ffprobe again
        mock_ffprobe.reset_mock()
        asset2 = probe_media(file_path)
        assert asset2.path == str(file_path.resolve())
        assert asset2.media_type == "video"
        mock_ffprobe.assert_not_called()


def test_cache_invalidation_on_size_change(tmp_path):
    file_path = tmp_path / "test.mp4"
    file_path.write_bytes(b"dummy")

    mock_asset1 = MediaAsset(str(file_path.resolve()), "video", 1000000, source="ffprobe")
    mock_asset2 = MediaAsset(str(file_path.resolve()), "video", 2000000, source="ffprobe")

    with patch("media_probe._probe_with_ffprobe") as mock_ffprobe:
        mock_ffprobe.side_effect = [mock_asset1, mock_asset2]

        # First call: cache miss
        asset1 = probe_media(file_path)
        assert asset1.duration_us == 1000000

        # Change size
        file_path.write_bytes(b"dummy modified size")

        # Second call: size changed, cache should invalidate, cache miss, probes again
        asset2 = probe_media(file_path)
        assert asset2.duration_us == 2000000
        assert mock_ffprobe.call_count == 2


def test_cache_invalidation_on_mtime_change(tmp_path):
    file_path = tmp_path / "test.mp4"
    file_path.write_bytes(b"dummy")

    mock_asset1 = MediaAsset(str(file_path.resolve()), "video", 1000000, source="ffprobe")
    mock_asset2 = MediaAsset(str(file_path.resolve()), "video", 3000000, source="ffprobe")

    with patch("media_probe._probe_with_ffprobe") as mock_ffprobe:
        mock_ffprobe.side_effect = [mock_asset1, mock_asset2]

        # First call: cache miss
        asset1 = probe_media(file_path)
        assert asset1.duration_us == 1000000

        # Change modification time
        stat = file_path.stat()
        # Set modification time ahead by 5 seconds
        new_mtime = stat.st_mtime + 5.0
        os.utime(file_path, (stat.st_atime, new_mtime))

        # Second call: mtime changed, cache miss, probes again
        asset2 = probe_media(file_path)
        assert asset2.duration_us == 3000000
        assert mock_ffprobe.call_count == 2


def test_cache_invalidation_on_deletion(tmp_path):
    file_path = tmp_path / "test.mp4"
    file_path.write_bytes(b"dummy")

    mock_asset = MediaAsset(str(file_path.resolve()), "video", 1000000, source="ffprobe")

    with patch("media_probe._probe_with_ffprobe", return_value=mock_asset) as mock_ffprobe:
        asset1 = probe_media(file_path)
        assert asset1.duration_us == 1000000

        # Delete file
        file_path.unlink()

        # Next probe should return file not found error and should not hit cache
        asset2 = probe_media(file_path)
        assert asset2.error == "file not found"
        mock_ffprobe.assert_called_once()  # should not call ffprobe again since file doesn't exist


def test_error_not_cached(tmp_path):
    file_path = tmp_path / "test.mp4"
    file_path.write_bytes(b"dummy")

    mock_asset_error = MediaAsset(str(file_path.resolve()), "unknown", 0, error="ffprobe timed out", source="ffprobe")
    mock_asset_success = MediaAsset(str(file_path.resolve()), "video", 1000000, source="ffprobe")

    with patch("media_probe._probe_with_ffprobe") as mock_ffprobe:
        mock_ffprobe.side_effect = [mock_asset_error, mock_asset_success]

        # First call: returns error
        asset1 = probe_media(file_path)
        assert asset1.error == "ffprobe timed out"

        # Second call: since error is transient/not cached, it should call ffprobe again and succeed
        asset2 = probe_media(file_path)
        assert asset2.error == ""
        assert asset2.duration_us == 1000000
        assert mock_ffprobe.call_count == 2


def test_clear_cache_api(tmp_path):
    file_path = tmp_path / "test.mp4"
    file_path.write_bytes(b"dummy")

    mock_asset = MediaAsset(str(file_path.resolve()), "video", 1000000, source="ffprobe")

    with patch("media_probe._probe_with_ffprobe", return_value=mock_asset) as mock_ffprobe:
        probe_media(file_path)
        assert mock_ffprobe.call_count == 1

        clear_media_probe_cache()

        probe_media(file_path)
        assert mock_ffprobe.call_count == 2


def test_cache_lru_eviction(tmp_path):
    set_media_probe_cache_max_size(2)

    f1 = tmp_path / "f1.mp4"
    f1.write_bytes(b"1")
    f2 = tmp_path / "f2.mp4"
    f2.write_bytes(b"2")
    f3 = tmp_path / "f3.mp4"
    f3.write_bytes(b"3")

    mock_a1 = MediaAsset(str(f1.resolve()), "video", 1000, source="ffprobe")
    mock_a2 = MediaAsset(str(f2.resolve()), "video", 2000, source="ffprobe")
    mock_a3 = MediaAsset(str(f3.resolve()), "video", 3000, source="ffprobe")

    with patch("media_probe._probe_with_ffprobe") as mock_ffprobe:
        mock_ffprobe.side_effect = [mock_a1, mock_a2, mock_a3, mock_a1]

        probe_media(f1)
        probe_media(f2)
        assert mock_ffprobe.call_count == 2

        probe_media(f3)
        assert mock_ffprobe.call_count == 3

        probe_media(f2)
        assert mock_ffprobe.call_count == 3

        probe_media(f1)
        assert mock_ffprobe.call_count == 4


def test_cache_concurrency(tmp_path):
    f = tmp_path / "concurrent.mp4"
    f.write_bytes(b"content")

    mock_asset = MediaAsset(str(f.resolve()), "video", 1000, source="ffprobe")

    call_counter = 0
    lock = threading.Lock()
    probe_started = threading.Event()
    release_probe = threading.Event()
    
    def mock_probe(*args, **kwargs):
        nonlocal call_counter
        with lock:
            call_counter += 1
        probe_started.set()
        release_probe.wait(timeout=2)
        return mock_asset

    with patch("media_probe._probe_with_ffprobe", side_effect=mock_probe):
        threads = []
        for _ in range(10):
            t = threading.Thread(target=probe_media, args=(f,))
            threads.append(t)
            t.start()

        assert probe_started.wait(timeout=2)
        time.sleep(0.05)
        release_probe.set()

        for t in threads:
            t.join()

        cached = _MEDIA_PROBE_CACHE.get(f)
        assert cached is not None
        assert cached.duration_us == 1000
        assert call_counter == 1


@pytest.mark.parametrize("invalid_size", [0, -1, 1.5, "10", True, None])
def test_cache_rejects_invalid_max_size(invalid_size):
    with pytest.raises(ValueError, match="positive integer"):
        set_media_probe_cache_max_size(invalid_size)


def test_concurrent_probe_exception_releases_waiters(tmp_path):
    file_path = tmp_path / "failure.mp4"
    file_path.write_bytes(b"content")
    probe_started = threading.Event()
    release_probe = threading.Event()
    errors = []

    def failing_probe(*args, **kwargs):
        probe_started.set()
        release_probe.wait(timeout=2)
        raise RuntimeError("probe failed")

    def run_probe():
        try:
            probe_media(file_path)
        except RuntimeError as exc:
            errors.append(str(exc))

    with patch("media_probe._probe_with_ffprobe", side_effect=failing_probe) as mock_ffprobe:
        threads = [threading.Thread(target=run_probe) for _ in range(5)]
        for thread in threads:
            thread.start()
        assert probe_started.wait(timeout=2)
        time.sleep(0.05)
        release_probe.set()
        for thread in threads:
            thread.join(timeout=2)

        assert errors == ["probe failed"] * 5
        assert mock_ffprobe.call_count == 1

    success = MediaAsset(str(file_path.resolve()), "video", 1000, source="ffprobe")
    with patch("media_probe._probe_with_ffprobe", return_value=success) as mock_ffprobe:
        assert probe_media(file_path).duration_us == 1000
        mock_ffprobe.assert_called_once()
