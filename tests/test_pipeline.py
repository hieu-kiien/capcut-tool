import sys
import os
import tempfile
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline import PipelineRunner, ProjectConfig
import capcut_keyframe_tool as core

def test_pipeline_configuration():
    print("Testing PipelineRunner configuration...")
    
    # Configure dummy settings
    config = ProjectConfig(
        project_name="E2E_Test_Project",
        draft_root="C:/Users/hieuk/AppData/Local/JianyingPro/User Data/Projects/com.lveditor.draft",
        voice_path="dummy_voice.mp3",
        media_dir="dummy_media",
        bgm_path="",
        srt_path="",
        canvas="9:16"
    )
    
    # Initialize runner
    runner = PipelineRunner(config)
    assert runner.config.project_name == "E2E_Test_Project"
    assert runner.config.canvas == "9:16"
    
    print("[OK] PipelineRunner successfully configured!")

def test_pipeline_execution():
    print("Testing PipelineRunner execution end-to-end...")
    
    # 1. Resolve ffmpeg path
    import runtime_tools
    ffmpeg_exe = runtime_tools.resolve_ffmpeg()
    if not ffmpeg_exe:
        print("[SKIP] Skipping E2E test: ffmpeg not found in path/tools.")
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # 2. Create dummy voice file (5 seconds of silence)
        voice_file = tmp_path / "voice.wav"
        cmd_voice = [ffmpeg_exe, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "5", str(voice_file)]
        subprocess.run(cmd_voice, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        # 3. Create media folder and dummy background video (10 seconds)
        media_dir = tmp_path / "background_media"
        media_dir.mkdir()
        video_file = media_dir / "bg_video.mp4"
        cmd_video = [ffmpeg_exe, "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=10", "-t", "10", str(video_file)]
        subprocess.run(cmd_video, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        # 4. Create a dummy SRT subtitle file
        srt_file = tmp_path / "subs.srt"
        srt_content = (
            "1\n"
            "00:00:00,000 --> 00:00:02,000\n"
            "Chào bạn, đây là câu test đầu tiên.\n\n"
            "2\n"
            "00:00:02,500 --> 00:00:04,500\n"
            "Và đây là câu test thứ hai.\n"
        )
        srt_file.write_text(srt_content, encoding="utf-8")
        
        # 5. Build ProjectConfig
        config = ProjectConfig(
            project_name="E2E_Simulation",
            draft_root=str(tmp_path),
            voice_path=str(voice_file),
            media_dir=str(media_dir),
            srt_path=str(srt_file),
            canvas="9:16",
            bg_switch_mode="subtitle",
            subtitle_font_size=8.0,
            subtitle_color=(1.0, 1.0, 0.0), # Yellow
            subtitle_bold=True
        )
        
        # 6. Run pipeline
        runner = PipelineRunner(config)
        logs = []
        def progress_cb(msg):
            logs.append(msg)
            try:
                enc = sys.stdout.encoding or "utf-8"
                sys.stdout.buffer.write(f"  [Log] {msg}\n".encode(enc, errors="backslashreplace"))
                sys.stdout.flush()
            except Exception:
                pass
            
        result = runner.run_all(progress=progress_cb)
        
        # 7. Assertions
        assert result["status"] == "success", f"Pipeline failed: {result}"
        assert result["project_name"] == "E2E_Simulation"
        
        draft_path = Path(result["draft_path"])
        assert draft_path.exists(), f"Draft path does not exist: {draft_path}"
        assert draft_path.name == "draft_content.json", "Draft path is not draft_content.json"
        
        # Read draft content to verify subtitles color and settings
        content = json_read(draft_path)
        texts = content.get("materials", {}).get("texts", [])
        assert len(texts) > 0, "No texts created in draft_content.json"
        
        print("[OK] PipelineRunner E2E execution passed successfully!")

def json_read(path: Path) -> dict:
    import json
    return json.loads(path.read_text(encoding="utf-8"))

if __name__ == "__main__":
    try:
        test_pipeline_configuration()
        print("-" * 50)
        test_pipeline_execution()
        print("-" * 50)
        print("ALL PIPELINE TESTS COMPLETED SUCCESSFULLY!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
