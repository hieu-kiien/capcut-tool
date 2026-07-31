import sys
import time
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QCoreApplication
from PySide6.QtWidgets import QApplication

# Adjust paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import runtime_tools
runtime_tools.configure_environment()

from app.gui import MainWindow
from core.db import Database

class ScreenshotCapturer:
    def __init__(self, window: MainWindow):
        self.window = window
        self.window.resize(1920, 1080)
        self.window.show()
        self.step = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.run_next)
        
        self.out_dir = PROJECT_ROOT / "scratch" / "real_screenshots"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        
    def run_next(self):
        try:
            if self.step == 0:
                print("Capturing 1. Dashboard...")
                self.window._switch_to_page("dashboard")
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "01_dashboard.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 1:
                print("Capturing 2. Setup...")
                self.window._switch_to_page("project-setup")
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "02_setup.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 2:
                print("Capturing 3. Media Nen...")
                self.window._switch_to_page("media-studio")
                self.window.media_studio_widget.tab_widget.setCurrentIndex(0)
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "03_media_nen.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 3:
                print("Capturing 4. Downloader...")
                self.window._switch_to_page("media-studio")
                self.window.media_studio_widget.tab_widget.setCurrentIndex(1)
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "04_downloader.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 4:
                print("Capturing 5. Intro/Outro...")
                self.window._switch_to_page("media-studio")
                self.window.media_studio_widget.tab_widget.setCurrentIndex(0)
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "05_intro_outro.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 5:
                print("Capturing 6. Cutter...")
                self.window._switch_to_page("media-studio")
                self.window.media_studio_widget.tab_widget.setCurrentIndex(2)
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "06_cutter.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 6:
                print("Capturing 7. Branding...")
                self.window._switch_to_page("effects")
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "07_branding.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 7:
                print("Capturing 8. Hieu ung tu dong...")
                self.window._switch_to_page("effects")
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "08_auto_effects.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 8:
                print("Capturing 9. Trinh chinh hieu ung...")
                self.window._switch_to_page("effects")
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "09_effects_editor.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 9:
                print("Capturing 10. Build Center...")
                self.window._switch_to_page("build-center")
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "10_build_center.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 10:
                print("Capturing 11. History...")
                self.window._switch_to_page("history")
                self.window.history_widget.tabs.setCurrentIndex(0)
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "11_history.png"))
                self.step += 1
                self.timer.start(500)
                
            elif self.step == 11:
                print("Capturing 12. Draft Doctor...")
                self.window._switch_to_page("history")
                self.window.history_widget.tabs.setCurrentIndex(1)
                QCoreApplication.processEvents()
                time.sleep(0.5)
                self.window.grab().save(str(self.out_dir / "12_draft_doctor.png"))
                print("All screenshots captured!")
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
    window.resize(1920, 1080)
    window.show()
    
    capturer = ScreenshotCapturer(window)
    capturer.timer.start(1000)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
