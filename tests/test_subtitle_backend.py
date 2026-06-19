import tempfile
from pathlib import Path
from profiles.subtitle import parse_srt_file, validate_subtitles

def test_subtitle_parsing_and_validation():
    # 1. Prepare sample SRT content (one valid subtitle, one too short)
    srt_content = (
        "1\n"
        "00:00:01,000 --> 00:00:03,500\n"
        "Hello World!\n\n"
        "2\n"
        "00:00:04,000 --> 00:00:04,500\n"
        "Short sub\n\n"
    )
    
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w", encoding="utf-8") as f:
        f.write(srt_content)
        temp_srt_path = Path(f.name)
        
    try:
        # Test parsing
        subtitles = parse_srt_file(temp_srt_path)
        assert len(subtitles) == 2
        
        # Subtitle 1 check
        assert subtitles[0]["index"] == 1
        assert subtitles[0]["text"] == "Hello World!"
        assert subtitles[0]["duration"] == 2_500_000 # 2.5s in us
        
        # Subtitle 2 check
        assert subtitles[1]["index"] == 2
        assert subtitles[1]["text"] == "Short sub"
        assert subtitles[1]["duration"] == 500_000 # 0.5s in us
        
        # Test validation (default threshold 0.8s)
        issues = validate_subtitles(subtitles, min_duration_sec=0.8)
        assert len(issues) == 1
        assert issues[0]["index"] == 2
        assert issues[0]["type"] == "too_short"
        assert "0.50s < 0.8s" in issues[0]["message"]
        
    finally:
        try:
            temp_srt_path.unlink()
        except Exception:
            pass
