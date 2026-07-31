# app/utils.py
from typing import Tuple

def hex_to_rgb_tuple(hex_str: str) -> tuple[float, float, float]:
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) != 6:
        return (1.0, 1.0, 1.0)
    try:
        r = int(hex_str[0:2], 16) / 255.0
        g = int(hex_str[2:4], 16) / 255.0
        b = int(hex_str[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        return (1.0, 1.0, 1.0)

def rgb_tuple_to_hex(rgb: tuple[float, float, float]) -> str:
    if not isinstance(rgb, (list, tuple)) or len(rgb) < 3:
        return "#FFFFFF"
    r = int(max(0.0, min(1.0, rgb[0])) * 255)
    g = int(max(0.0, min(1.0, rgb[1])) * 255)
    b = int(max(0.0, min(1.0, rgb[2])) * 255)
    return f"#{r:02X}{g:02X}{b:02X}"
