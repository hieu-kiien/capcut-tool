import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from core.media import scan_media_directory, MediaProber
from core.cutter import lossless_cut_video, VideoCutterError

def test_media_prober_validation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Test HEIC format warning with existing file
        heic_file = tmp_path / "dummy_photo.heic"
        heic_file.write_text("dummy heic content")
        res = MediaProber.probe_file(heic_file)
        assert res["media_type"] == "image"
        assert "codec không hỗ trợ" in res["error"]

        # Test unsupported extension with existing file
        txt_file = tmp_path / "dummy_doc.txt"
        txt_file.write_text("dummy text")
        res = MediaProber.probe_file(txt_file)
        assert res["media_type"] == "unknown"
        assert "không được hỗ trợ" in res["error"]


@patch("core.media.resolve_ffprobe")
@patch("core.media.subprocess.run")
def test_parallel_media_directory_scanning(mock_run, mock_resolve_ffprobe):
    # Mock ffprobe path
    mock_resolve_ffprobe.return_value = "dummy_ffprobe"
    
    # Mock ffprobe output payload for a valid landscape video
    mock_payload = {
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "duration": "10.5",
                "avg_frame_rate": "30/1"
            }
        ],
        "format": {
            "duration": "10.5"
        }
    }
    
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    import json
    mock_proc.stdout = json.dumps(mock_payload)
    mock_run.return_value = mock_proc

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create a dummy mp4 file
        video_file = tmp_path / "test_video.mp4"
        video_file.write_text("dummy video content")
        
        # Scan with canvas ratio 9:16 (should produce warning for landscape video)
        res = scan_media_directory(tmp_dir, recursive=False, canvas_ratio="9:16")
        assert len(res["valid"]) == 1
        assert res["valid"][0]["filename"] == "test_video.mp4"
        assert res["valid"][0]["width"] == 1920
        assert res["valid"][0]["height"] == 1080
        
        # Ensure aspect ratio warning is captured
        assert len(res["warnings"]) == 1
        assert "sai tỉ lệ" in res["warnings"][0]["error"]
        assert "test_video.mp4" in res["warnings"][0]["filename"]


@patch("core.cutter.cutter.resolve_ffmpeg")
@patch("core.cutter.cutter.subprocess.Popen")
def test_lossless_video_cutter(mock_popen, mock_resolve_ffmpeg):
    mock_resolve_ffmpeg.return_value = "dummy_ffmpeg"
    
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    mock_proc.returncode = 0
    mock_popen.return_value = mock_proc

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        src_file = tmp_path / "src_video.mp4"
        src_file.write_text("source content")
        
        dest_file = tmp_path / "cut_video.mp4"
        
        # Call lossless cut
        log_msgs = []
        def log_cb(msg):
            log_msgs.append(msg)
            
        res = lossless_cut_video(src_file, dest_file, start_sec=2.5, duration_sec=5.0, log_callback=log_cb)
        
        assert res == dest_file
        assert any("lossless cut" in m for m in log_msgs)
        assert any("FFmpeg Command:" in m for m in log_msgs)
        
        # Check command execution
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "dummy_ffmpeg" in args
        assert "-ss" in args
        assert "2.500" in args
        assert "-t" in args
        assert "5.000" in args
        assert "-c" in args
        assert "copy" in args
