import json
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse


def safe_url_for_history(url: str) -> str:
    """
    Remove query strings, tokens, secrets, and fragments from URL.
    Returns only the scheme, netloc, and path.
    """
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme and parsed.netloc:
            # Reconstruct URL without query string/params or fragment
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        pass
    return ""


def safe_cookie_info(path: str) -> Dict[str, Any]:
    """
    Sanitize cookie file path to avoid storing absolute path info.
    """
    if not path:
        return {"cookies_used": False, "cookies_file_name": ""}
    return {
        "cookies_used": True,
        "cookies_file_name": Path(path).name
    }


def write_job_history(job_type: str, job_data: dict, root: Path) -> Path:
    """
    Write a job history JSON file. Avoids overwriting files with identical timestamps
    by appending a numeric suffix.
    """
    jobs_dir = root / ".capcut_tool_jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"job_{timestamp}_{job_type}.json"
    job_file = jobs_dir / filename

    counter = 1
    while job_file.exists():
        filename = f"job_{timestamp}_{counter}_{job_type}.json"
        job_file = jobs_dir / filename
        counter += 1

    # Ensure schema version and job_type are set
    job_data.setdefault("schema_version", 1)
    job_data.setdefault("job_type", job_type)

    job_file.write_text(json.dumps(job_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return job_file


def load_job_history(root: Path, limit: int = 100) -> List[dict]:
    """
    Load recent job history JSON files. Returns them sorted from newest to oldest.
    """
    jobs_dir = root / ".capcut_tool_jobs"
    if not jobs_dir.exists() or not jobs_dir.is_dir():
        return []

    job_files = []
    try:
        for f in jobs_dir.iterdir():
            if f.is_file() and f.name.startswith("job_") and f.suffix == ".json":
                job_files.append(f)
    except Exception:
        return []

    # Sort descending by filename which starts with timestamp
    job_files.sort(key=lambda x: x.name, reverse=True)

    history = []
    for f in job_files[:limit]:
        try:
            content = f.read_text(encoding="utf-8")
            data = json.loads(content)
            # Ensure basic fields exist for gui compatibility
            data.setdefault("schema_version", 1)
            data.setdefault("job_type", "unknown")
            data.setdefault("started_at", "N/A")
            data.setdefault("finished_at", "N/A")
            data.setdefault("status", "unknown")
            data.setdefault("inputs", {})
            data.setdefault("outputs", {})
            data.setdefault("error", "")
            # Inject filename for deletion/referencing
            data["_filename"] = f.name
            history.append(data)
        except Exception as e:
            # Report in console or ignore corrupt file
            print(f"Error reading job history file {f.name}: {e}")
            # Inject minimum data for list view to show error instead of crashing
            history.append({
                "schema_version": 1,
                "job_type": "unknown",
                "started_at": "Lỗi đọc file",
                "finished_at": "Lỗi đọc file",
                "status": "failed",
                "inputs": {},
                "outputs": {},
                "error": f"Lỗi đọc file {f.name}: {e}",
                "_filename": f.name
            })

    return history
