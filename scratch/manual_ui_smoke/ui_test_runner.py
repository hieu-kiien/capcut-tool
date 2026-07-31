import sys
import os
import time
from pathlib import Path

# Adjust paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
OUT_DIR = Path(__file__).resolve().parent / "2026-06-19_16-33"

import runtime_tools
runtime_tools.configure_environment()

from PySide6.QtCore import Qt, QTimer, QCoreApplication
from PySide6.QtWidgets import QApplication
from app.gui import MainWindow
from core.db import Database

class TestRunner:
    def __init__(self, window: MainWindow):
        self.window = window
        self.step = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.run_next_step)
        
        self.small_dir = PROJECT_ROOT / "tests" / "mock_assets"
        self.small_dir.mkdir(parents=True, exist_ok=True)
        (self.small_dir / "small.mp4").touch()
        
        self.large_dir = PROJECT_ROOT / "tests" / "mock_large"
        self.large_dir.mkdir(parents=True, exist_ok=True)
        for i in range(100):
            (self.large_dir / f"large_{i}.mp4").touch()
            
    def run_next_step(self):
        try:
            if self.step == 0:
                print("Step 0: A1. Launch and layout")
                # Need to allow some event loop cycles for layout to settle
                QCoreApplication.processEvents()
                self.window.grab().save(str(OUT_DIR / "01_launch_layout.png"))
                print("A1 Done")
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 1:
                print("Step 1: A2. Scan media (success)")
                self.window.setup_widget.media_dir.setText(str(self.small_dir))
                QCoreApplication.processEvents()
                # Assuming scan auto-starts when media_dir changes
                self.window.grab().save(str(OUT_DIR / "02_scan_success.png"))
                print("A2 Done")
                self.step += 1
                self.timer.start(1000)
                
            elif self.step == 2:
                print("Step 2: A3. Scan replacement")
                self.window.setup_widget.media_dir.setText(str(self.large_dir))
                QCoreApplication.processEvents()
                # Simulate replacement
                self.window.setup_widget.media_dir.setText(str(self.small_dir))
                QCoreApplication.processEvents()
                self.window.grab().save(str(OUT_DIR / "03_scan_replacement.png"))
                print("A3 Done")
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 3:
                print("Step 3: A5. Downloader failure start")
                self.window._switch_to_page("media_studio")
                QCoreApplication.processEvents()
                
                self.window.media_studio_widget.download_urls_edit.setPlainText("http://invalid.url.local/test")
                self.window.media_studio_widget.btn_run_download.click()
                QCoreApplication.processEvents()
                self.window.grab().save(str(OUT_DIR / "05_download_fail_start.png"))
                
                self.step += 1
                self.timer.start(2000) # wait for download to fail
                
            elif self.step == 4:
                print("Step 4: A5. Downloader recover")
                QCoreApplication.processEvents()
                self.window.grab().save(str(OUT_DIR / "06_download_fail_recover.png"))
                print("A5 Done")
                
                print("Step 5: A4. Close while worker running")
                self.window._switch_to_page("setup")
                self.window.setup_widget.media_dir.setText(str(self.large_dir))
                QCoreApplication.processEvents()
                
                print("Closing app now...")
                self.window.close()
                QApplication.quit()
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            QApplication.quit()

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    Database.init_db()
    
    window = MainWindow()
    window.show()
    
    runner = TestRunner(window)
    runner.timer.start(1000) # start first step after 1s
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
