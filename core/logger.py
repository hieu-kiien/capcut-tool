import logging
import sys
from pathlib import Path
from typing import Callable, List

# Create a logger
logger = logging.getLogger("CapCutDraftStudio")
logger.setLevel(logging.DEBUG)

# Register callbacks for UI updates or streaming
_callbacks: List[Callable[[str], None]] = []

class CallbackHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            for cb in _callbacks:
                try:
                    cb(msg)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

def add_log_callback(cb: Callable[[str], None]) -> None:
    if cb not in _callbacks:
        _callbacks.append(cb)

def remove_log_callback(cb: Callable[[str], None]) -> None:
    if cb in _callbacks:
        _callbacks.remove(cb)

# Formatting rules
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

# Stream handler for terminal/stderr
stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)

# Custom callback handler to forward logs to subscribers (e.g. GUI console)
callback_handler = CallbackHandler()
callback_handler.setFormatter(formatter)
callback_handler.setLevel(logging.DEBUG)
logger.addHandler(callback_handler)

# Central log file config
_file_handler: logging.FileHandler = None

def setup_file_logging(log_dir: Path) -> None:
    global _file_handler
    if _file_handler is not None:
        logger.removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None
        
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"
        _file_handler = logging.FileHandler(log_file, encoding="utf-8")
        _file_handler.setFormatter(formatter)
        _file_handler.setLevel(logging.DEBUG)
        logger.addHandler(_file_handler)
        logger.info(f"Khởi tạo ghi log vào tệp: {log_file}")
    except Exception as e:
        logger.error(f"Không thể khởi tạo tệp log: {e}")
