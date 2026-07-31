import time
import gc
import sys
import psutil
import os
from PySide6.QtWidgets import QApplication

# Prevent QApplication from failing if multiple instances are created
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from app.workers import KeyframeWorker, PipelineWorker
from app.pipeline import ProjectConfig

def print_memory():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    print(f"Memory Usage: {mem_info.rss / 1024 / 1024:.2f} MB")

def test_memory_leak():
    print("Initial Memory:")
    print_memory()

    # Create and destroy workers in a loop
    for i in range(100):
        worker1 = KeyframeWorker("dummy_proj", "dummy_preset", {})

        config = ProjectConfig(
            project_name="dummy",
            draft_root="dummy_root",
            voice_path="dummy.mp3",
            media_dir="dummy_dir"
        )
        worker2 = PipelineWorker(config)

        # Simulate connecting and disconnecting signals if needed
        # but just creating and letting them go out of scope is a good test

        del worker1
        del worker2

        if i % 20 == 0:
            gc.collect()
            print(f"Memory at iteration {i}:")
            print_memory()

    gc.collect()
    print("Final Memory:")
    print_memory()

if __name__ == "__main__":
    test_memory_leak()
