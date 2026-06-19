# profiles/subtitle.py
import re
from pathlib import Path
from typing import Dict, List, Optional

def parse_srt_file(srt_path: str | Path) -> List[Dict]:
    """
    Parses an SRT file and returns a list of dictionaries with:
      - 'index': 1-based index (int)
      - 'start': start time in microseconds (int)
      - 'end': end time in microseconds (int)
      - 'duration': duration in microseconds (int)
      - 'start_time_str': format HH:MM:SS,mmm
      - 'end_time_str': format HH:MM:SS,mmm
      - 'text': subtitle text (str)
    """
    path = Path(srt_path)
    if not path.exists():
        return []
        
    try:
        content = path.read_text(encoding="utf-8-sig")
    except Exception:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return []
            
    # Normalize line endings
    content = content.replace("\r\n", "\n")
    
    # Pattern to match srt blocks
    pattern = re.compile(
        r"(\d+)\s*\n"
        r"(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})\s*\n"
        r"([\s\S]*?)(?=\n\s*\n|\n\s*$|$)"
    )
    
    results = []
    for match in pattern.finditer(content):
        idx_str = match.group(1).strip()
        try:
            idx = int(idx_str)
        except ValueError:
            idx = len(results) + 1
            
        sh, sm, ss, sms = map(int, match.group(2, 3, 4, 5))
        eh, em, es, ems = map(int, match.group(6, 7, 8, 9))

        start_us = (((sh * 3600 + sm * 60 + ss) * 1000) + sms) * 1000
        end_us = (((eh * 3600 + em * 60 + es) * 1000) + ems) * 1000
        duration_us = end_us - start_us

        if duration_us <= 0:
            continue

        text = match.group(10).strip()
        if not text:
            continue
            
        start_time_str = f"{sh:02d}:{sm:02d}:{ss:02d},{sms:03d}"
        end_time_str = f"{eh:02d}:{em:02d}:{es:02d},{ems:03d}"
        
        results.append({
            "index": idx,
            "start": start_us,
            "end": end_us,
            "duration": duration_us,
            "start_time_str": start_time_str,
            "end_time_str": end_time_str,
            "text": text
        })
        
    # Sort by start time
    results.sort(key=lambda x: x["start"])
    return results

def validate_subtitles(subtitles: List[Dict], min_duration_sec: float = 0.8) -> List[Dict]:
    """
    Validates subtitles and flags issues like:
      - Duration too short (less than min_duration_sec)
    Returns a list of issue dictionaries:
      - 'index': subtitle index
      - 'type': 'too_short'
      - 'message': warning message
      - 'subtitle': reference to the subtitle dict
    """
    issues = []
    min_duration_us = int(min_duration_sec * 1_000_000)
    for sub in subtitles:
        if sub["duration"] < min_duration_us:
            duration_sec = sub["duration"] / 1_000_000.0
            issues.append({
                "index": sub["index"],
                "type": "too_short",
                "message": f"Thời lượng quá ngắn ({duration_sec:.2f}s < {min_duration_sec}s)",
                "subtitle": sub
            })
    return issues
