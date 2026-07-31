import os
import sys
import subprocess
from pathlib import Path

def run_tests():
    project_root = Path(__file__).resolve().parent.parent
    tests_dir = project_root / "tests"
    
    # Find all test files matching test_*.py
    test_files = sorted([f for f in tests_dir.glob("test_*.py")])
    
    print(f"Found {len(test_files)} test files to execute sequentially.")
    print("-" * 60)
    
    failed_tests = []
    total_passed = 0
    total_failed = 0
    
    for test_file in test_files:
        relative_path = test_file.relative_to(project_root)
        print(f"Running: {relative_path}...")
        
        # Run pytest as a separate subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-q"],
            cwd=str(project_root)
        )
        
        if result.returncode == 0:
            print(f"[SUCCESS] {relative_path}")
            total_passed += 1
        else:
            print(f"[FAILURE] {relative_path} (exit code: {result.returncode})")
            failed_tests.append(str(relative_path))
            total_failed += 1
        print("-" * 60)
        
    print("\n=== TEST EXECUTION SUMMARY ===")
    print(f"Total Test Modules Run: {len(test_files)}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    
    if failed_tests:
        print("\nFailed Modules:")
        for failed in failed_tests:
            print(f" - {failed}")
        sys.exit(1)
    else:
        print("\nAll test modules passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
