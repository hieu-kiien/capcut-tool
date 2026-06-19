import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import capcut_draft_creator
import media_probe
import pyJianYingDraft as draft
import video_mixer


ITERATIONS = max(1, int(os.environ.get("CAPCUT_BENCHMARK_ITERATIONS", "5")))
WARMUPS = max(0, int(os.environ.get("CAPCUT_BENCHMARK_WARMUPS", "1")))
REAL_MEDIA_DIR = os.environ.get("CAPCUT_BENCHMARK_MEDIA_DIR", "").strip()
_REAL_SUBPROCESS_RUN = subprocess.run
_counter_lock = threading.Lock()
ffprobe_call_count = 0
ffprobe_called_paths: list[str] = []
captured_script = None


def _reset_probe_counter() -> None:
    global ffprobe_call_count, ffprobe_called_paths
    with _counter_lock:
        ffprobe_call_count = 0
        ffprobe_called_paths = []


def _mock_subprocess_run(cmd, *args, **kwargs):
    global ffprobe_call_count
    if any("ffprobe" in str(arg).lower() for arg in cmd):
        file_path = str(cmd[-1])
        with _counter_lock:
            ffprobe_call_count += 1
            ffprobe_called_paths.append(file_path)

        path = Path(file_path)
        duration = "18000.0" if path.suffix.lower() == ".mp3" else "10.0"
        codec_type = "audio" if path.suffix.lower() == ".mp3" else "video"
        stream = {"codec_type": codec_type, "duration": duration}
        if codec_type == "video":
            stream.update({"width": 1920, "height": 1080, "avg_frame_rate": "30/1"})
        response = MagicMock()
        response.returncode = 0
        response.stdout = json.dumps({"streams": [stream], "format": {"duration": duration}})
        response.stderr = ""
        return response
    return _REAL_SUBPROCESS_RUN(cmd, *args, **kwargs)


def _measure(fn, *, iterations: int = ITERATIONS, warmups: int = WARMUPS):
    for index in range(warmups):
        fn(-(index + 1))
    samples = []
    results = []
    for index in range(iterations):
        started = time.perf_counter()
        results.append(fn(index))
        samples.append(time.perf_counter() - started)
    stats = {
        "median": statistics.median(samples),
        "min": min(samples),
        "max": max(samples),
    }
    return results[-1], stats, results


def _format_stats(stats: dict, scale: float = 1.0, unit: str = "s") -> str:
    return (
        f"median={stats['median'] * scale:.3f} {unit}, "
        f"min={stats['min'] * scale:.3f}, max={stats['max'] * scale:.3f}"
    )


def _serialize(content: dict, output_path: Path, *, compact: bool):
    tracemalloc.start()
    try:
        if compact:
            payload = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        else:
            payload = json.dumps(content, ensure_ascii=False, indent=4)
        output_path.write_text(payload, encoding="utf-8")
        _, peak = tracemalloc.get_traced_memory()
        return {"peak": peak, "size": output_path.stat().st_size}
    finally:
        tracemalloc.stop()


def _run_real_ffprobe_benchmark() -> str:
    if not REAL_MEDIA_DIR:
        return "SKIPPED: set CAPCUT_BENCHMARK_MEDIA_DIR to a folder with valid media"
    root = Path(REAL_MEDIA_DIR).expanduser().resolve()
    if not root.is_dir():
        return f"SKIPPED: media directory not found: {root}"
    files = list(media_probe.iter_media_files(root))[:10]
    if not files:
        return f"SKIPPED: no supported visual media in {root}"

    def probe_sample(_index):
        media_probe.clear_media_probe_cache()
        return [media_probe.probe_media(path) for path in files]

    assets, stats, _ = _measure(probe_sample)
    errors = sum(1 for asset in assets if asset.error)
    return f"{len(files)} files, {errors} errors, {_format_stats(stats)}"


def run_benchmark() -> None:
    global captured_script
    print("=== CapCut Tool Performance Benchmark ===")
    print(f"Warm-ups: {WARMUPS}; measured iterations: {ITERATIONS}")

    with tempfile.TemporaryDirectory() as temp_name:
        temp_path = Path(temp_name)
        for index in range(600):
            (temp_path / f"video_{index}.mp4").touch()
        voice_path = temp_path / "voice.mp3"
        voice_path.touch()
        draft_root = temp_path / "drafts"
        draft_root.mkdir()

        with patch("subprocess.run", side_effect=_mock_subprocess_run), patch(
            "media_probe.resolve_ffprobe", return_value="mock_ffprobe"
        ):
            discovered, discovery_stats, _ = _measure(
                lambda _index: list(media_probe.iter_media_files(temp_path))
            )
            print(f"Discovery: {len(discovered)} files; {_format_stats(discovery_stats, 1000, 'ms')}")

            def scan_once(_index):
                media_probe.clear_media_probe_cache()
                _reset_probe_counter()
                return media_probe.scan_media_folder(temp_path)

            assets, scan_stats, _ = _measure(scan_once)
            scan_calls = ffprobe_call_count
            print(f"Mock scan: {len(assets)} assets, {scan_calls} calls; {_format_stats(scan_stats)}")

            total_duration_us = 5 * 3600 * 1_000_000
            config = video_mixer.VideoMixerConfig(
                mode=video_mixer.MODE_EVERY_X_SECONDS,
                fixed_clip_sec=5.0,
                seed=42,
            )
            segments, plan_stats, _ = _measure(
                lambda _index: video_mixer.plan_background_segments(
                    assets, total_duration_us, config=config
                )
            )
            print(f"Timeline: {len(segments)} segments; {_format_stats(plan_stats)}")

            def capture_save(script, *args, **kwargs):
                global captured_script
                captured_script = script

            def create_draft(index, *, clear_cache: bool, prefix: str):
                if clear_cache:
                    media_probe.clear_media_probe_cache()
                return capcut_draft_creator.create_draft_from_files(
                    draft_root=draft_root,
                    project_name=f"{prefix}_{index}",
                    voice_path=voice_path,
                    background_segments=segments,
                    allow_replace=True,
                )

            with patch.object(draft.ScriptFile, "save", capture_save):
                media_probe.clear_media_probe_cache()
                media_probe.scan_media_folder(temp_path)
                _reset_probe_counter()
                create_draft(9999, clear_cache=False, prefix="count_cached")
                cached_calls = ffprobe_call_count

                _, cached_stats, _ = _measure(
                    lambda index: create_draft(index, clear_cache=False, prefix="cached")
                )

                _reset_probe_counter()
                create_draft(9999, clear_cache=True, prefix="count_uncached")
                uncached_calls = ffprobe_call_count
                uncached_paths = list(ffprobe_called_paths)

                _, uncached_stats, _ = _measure(
                    lambda index: create_draft(index, clear_cache=True, prefix="uncached")
                )

            print(f"Draft cached: {cached_calls} first-run calls; {_format_stats(cached_stats)}")
            print(f"Draft uncached: {uncached_calls} calls; {_format_stats(uncached_stats)}")

            if captured_script is None:
                raise RuntimeError("Unable to capture ScriptFile during draft creation")
            captured_script.dumps(compact=False)
            content = captured_script.content
            pretty_path = temp_path / "pretty.json"
            compact_path = temp_path / "compact.json"
            pretty, pretty_stats, pretty_results = _measure(
                lambda _index: _serialize(content, pretty_path, compact=False)
            )
            compact, compact_stats, compact_results = _measure(
                lambda _index: _serialize(content, compact_path, compact=True)
            )

        real_probe_result = _run_real_ffprobe_benchmark()
        unique_uncached = len(set(uncached_paths))
        pretty_peak = statistics.median(item["peak"] for item in pretty_results)
        compact_peak = statistics.median(item["peak"] for item in compact_results)
        size_change = (compact["size"] - pretty["size"]) / pretty["size"] * 100
        peak_change = (compact_peak - pretty_peak) / pretty_peak * 100

        report = f"""# Performance Benchmark Report

## Configuration
- Warm-ups: {WARMUPS}
- Measured iterations: {ITERATIONS}
- Mock media: 600 videos, 1 voice file
- Timeline: 5 hours, {len(segments)} segments

## Repeated Measurements
| Phase | Median | Min | Max |
| :--- | ---: | ---: | ---: |
| Discovery | {discovery_stats['median']:.6f}s | {discovery_stats['min']:.6f}s | {discovery_stats['max']:.6f}s |
| Mock scan/probe | {scan_stats['median']:.6f}s | {scan_stats['min']:.6f}s | {scan_stats['max']:.6f}s |
| Timeline planning | {plan_stats['median']:.6f}s | {plan_stats['min']:.6f}s | {plan_stats['max']:.6f}s |
| Draft creation, cached | {cached_stats['median']:.6f}s | {cached_stats['min']:.6f}s | {cached_stats['max']:.6f}s |
| Draft creation, uncached | {uncached_stats['median']:.6f}s | {uncached_stats['min']:.6f}s | {uncached_stats['max']:.6f}s |
| Pretty serialization | {pretty_stats['median']:.6f}s | {pretty_stats['min']:.6f}s | {pretty_stats['max']:.6f}s |
| Compact serialization | {compact_stats['median']:.6f}s | {compact_stats['min']:.6f}s | {compact_stats['max']:.6f}s |

## Probe Calls
- Mock scan: {scan_calls}
- First cached draft: {cached_calls}
- Uncached draft: {uncached_calls} calls across {unique_uncached} unique paths
- Real ffprobe: {real_probe_result}

## Serialization
- Pretty size: {pretty['size'] / 1024 / 1024:.2f} MB
- Compact size: {compact['size'] / 1024 / 1024:.2f} MB ({size_change:+.1f}%)
- Pretty median peak RAM: {pretty_peak / 1024 / 1024:.2f} MB
- Compact median peak RAM: {compact_peak / 1024 / 1024:.2f} MB ({peak_change:+.1f}%)

Mock timings validate Python call paths only. They do not measure real ffprobe CPU usage.
"""
        report_path = PROJECT_ROOT / "scratch" / "performance_baseline.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"Pretty serialization: {_format_stats(pretty_stats)}")
        print(f"Compact serialization: {_format_stats(compact_stats)}")
        print(f"Real ffprobe: {real_probe_result}")
        print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    run_benchmark()
