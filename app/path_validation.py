import os
import re
import unicodedata
from pathlib import Path

MAX_PROJECT_NAME_LENGTH = 120
INVALID_WINDOWS_CHARS = {'/', '\\', ':', '*', '?', '"', '<', '>', '|'}
WINDOWS_RESERVED_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CONIN$",
    "CONOUT$",
    "CLOCK$",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}


def _contains_control_character(value: str) -> bool:
    return any(ord(ch) == 127 or unicodedata.category(ch) == "Cc" for ch in value)


def _reserved_windows_device_name(value: str) -> str:
    base_name = value.split(".", 1)[0].rstrip(" .").upper()
    return base_name if base_name in WINDOWS_RESERVED_DEVICE_NAMES else ""


def validate_project_name(project_name: str, draft_root: Path | str) -> Path:
    """
    Validate project name for path safety and return the resolved path.
    Raises ValueError with a user-friendly message if the name is invalid.
    """
    if not isinstance(project_name, str):
        raise ValueError("Tên dự án phải là một chuỗi ký tự.")

    if _contains_control_character(project_name):
        raise ValueError("Tên dự án không được chứa các ký tự điều khiển (control characters).")

    if project_name.endswith(" ") or project_name.endswith("."):
        raise ValueError("Tên dự án không được kết thúc bằng dấu cách hoặc dấu chấm.")

    name_stripped = project_name.strip()
    if not name_stripped:
        raise ValueError("Tên dự án không được để trống hoặc chỉ chứa khoảng trắng.")
    
    if len(name_stripped) > MAX_PROJECT_NAME_LENGTH:
        raise ValueError("Tên dự án quá dài (tối đa 120 ký tự).")

    # Check prefix
    if name_stripped.startswith("_partial_"):
        raise ValueError("Tên dự án không được bắt đầu bằng prefix nội bộ '_partial_'.")

    # Check backup pattern
    if re.search(r"_bak_\d{8}_\d{6}", name_stripped):
        raise ValueError("Tên dự án không được chứa định dạng tên sao lưu '_bak_YYYYMMDD_HHMMSS'.")

    reserved_name = _reserved_windows_device_name(name_stripped)
    if reserved_name:
        raise ValueError(f"Tên dự án không được trùng với tên thiết bị hệ thống của Windows: {reserved_name}")

    for char in INVALID_WINDOWS_CHARS:
        if char in project_name:
            raise ValueError(f"Tên dự án không được chứa ký tự đường dẫn hoặc ký tự Windows không hợp lệ: {char}")
            
    if ".." in project_name:
        raise ValueError("Tên dự án không được chứa cụm ký tự chuyển thư mục '..'.")
        
    p = Path(project_name)
    if p.is_absolute():
        raise ValueError("Tên dự án không được là đường dẫn tuyệt đối.")
        
    try:
        resolved_root = Path(draft_root).resolve()
        resolved_proj = (resolved_root / name_stripped).resolve()
    except Exception as e:
        raise ValueError(f"Không thể định vị đường dẫn dự án CapCut: {e}")
        
    # Check if resolved_proj is strictly inside resolved_root
    try:
        is_inside = resolved_proj.is_relative_to(resolved_root)
    except AttributeError:
        # Fallback for Python versions < 3.9
        is_inside = resolved_root in resolved_proj.parents
        
    if not is_inside or resolved_proj == resolved_root:
        raise ValueError("Tên dự án không hợp lệ hoặc cố gắng truy cập ngoài thư mục lưu dự án CapCut.")
        
    return resolved_proj
