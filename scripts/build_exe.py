import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build CapCut Long Story Studio as a Windows EXE.")
    parser.add_argument("--check", action="store_true", help="Only check packaging prerequisites.")
    parser.add_argument("--name", default="CapCutLongStoryStudio")
    args = parser.parse_args(argv)

    issues = check_prerequisites()
    for severity, message in issues:
        print(f"[{severity.upper()}] {message}")
    if any(severity == "error" for severity, _ in issues):
        return 1
    if args.check:
        return 0

    # Automatically run project obfuscation
    print("[OBFUSCATE] Obfuscating source files...")
    try:
        # Dynamically import to ensure clean paths
        import sys
        if str(PROJECT_ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        import obfuscate_project
        obfuscate_project.main()
    except Exception as e:
        print(f"[ERROR] Obfuscation failed: {e}")
        return 1

    cmd = build_pyinstaller_command(args.name)
    print("[BUILD]", " ".join(cmd))
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=False)
    
    if result.returncode == 0:
        print("[BUILD] Build succeeded. Packaging release folder...")
        import datetime
        version = "1.0.0"
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        release_dir = PROJECT_ROOT / "release" / f"CapCutLongStoryStudio_{version}_{date_str}"
        dist_dir = PROJECT_ROOT / "dist" / args.name
        
        if release_dir.exists():
            shutil.rmtree(release_dir)
        release_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy dist content
        print(f"[RELEASE] Copying dist files to {release_dir}...")
        if dist_dir.exists():
            shutil.copytree(dist_dir, release_dir, dirs_exist_ok=True)
            
            # Write README_CHAY_APP.txt
            readme_path = release_dir / "README_CHAY_APP.txt"
            readme_content = """HƯỚNG DẪN CHẠY ỨNG DỤNG - CAPCUT LONG STORY STUDIO

1. Cách chạy ứng dụng:
   - Hãy chạy file "CapCutLongStoryStudio.exe" trực tiếp trong thư mục này.

2. Chọn thư mục lưu dự án CapCut ở đâu:
   - Trong giao diện ứng dụng, chọn mục "Tổng quan".
   - Bấm nút "Chọn" ở dòng "Thư mục lưu dự án CapCut" và dẫn tới thư mục CapCut đang lưu dự án.
     - Đường dẫn mặc định của CapCut trên Windows thường là:
       C:\\Users\\<Tên_User>\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft

3. Tải media hoạt động như thế nào:
   - Mục "Công cụ Media" dùng yt-dlp/gallery-dl để tải video hoặc âm thanh từ URL.
   - Có thể bật archive để tránh tải lại link đã tải trước đó.
   - Media tải xong nên được lưu vào thư mục media nền rồi chọn ở mục "Media nền".

4. Logo/animation có nền:
   - Mục "Hiệu ứng & Overlay" có tùy chọn xóa nền xanh lá, xanh dương, trắng hoặc đen.
   - Ứng dụng tạo file overlay đã xóa nền trong thư mục dự án, không sửa file gốc.

5. Lưu ý quan trọng khi sửa dự án CapCut:
   - Bạn CẦN ĐÓNG phần mềm CapCut hoặc ĐÓNG dự án tương ứng trước khi thực hiện chỉnh sửa chuyển động, chuyển cảnh hay sửa lỗi trên ứng dụng này để tránh bị xung đột ghi đè dữ liệu.

6. Nơi lưu trữ Log và Lịch sử (Job History):
   - Mọi thông tin về các tác vụ đã thực hiện thành công hay thất bại (tạo dự án CapCut, tải video, cắt video) được lưu tự động trong thư mục ".capcut_tool_jobs" nằm cùng cấp với tệp cấu hình ứng dụng.
   - Bạn có thể xem trực tiếp và quản lý lịch sử này qua mục "Tạo & Lịch sử" trên giao diện UI hoặc bấm nút "Mở Thư Mục Lịch Sử" để xem các file log chi tiết dạng JSON.
"""
            readme_path.write_text(readme_content, encoding="utf-8")
            print(f"[RELEASE] Created README_CHAY_APP.txt at {readme_path}")
            
            # Create a .zip release
            try:
                zip_name = PROJECT_ROOT / "release" / f"CapCutLongStoryStudio_{version}_{date_str}"
                print(f"[RELEASE] Creating zip archive at {zip_name}.zip ...")
                shutil.make_archive(str(zip_name), 'zip', release_dir)
                print("[RELEASE] Zip archive created successfully.")
            except Exception as e:
                print(f"[WARNING] Could not create zip archive: {e}")
        else:
            print(f"[ERROR] Dist directory {dist_dir} does not exist.")

    return result.returncode


def check_prerequisites() -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    try:
        import PyInstaller  # noqa: F401
        issues.append(("info", "PyInstaller is installed"))
    except Exception:
        issues.append(("error", "PyInstaller is not installed"))

    try:
        import PySide6  # noqa: F401
        issues.append(("info", "PySide6 is installed"))
    except Exception:
        issues.append(("error", "PySide6 is not installed"))

    try:
        import yt_dlp  # noqa: F401
        issues.append(("info", "yt-dlp Python package is installed"))
    except Exception:
        ytdlp_exe = shutil.which("yt-dlp") or shutil.which("yt_dlp")
        portable_ytdlp = _find_portable_ytdlp()
        if ytdlp_exe:
            issues.append(("info", f"yt-dlp executable found: {ytdlp_exe}"))
        elif portable_ytdlp:
            issues.append(("info", f"Portable yt-dlp found: {portable_ytdlp}"))
        else:
            issues.append(("warn", "yt-dlp not found; downloader tab will ask the user to install it"))

    try:
        import gallery_dl  # noqa: F401
        issues.append(("info", "gallery-dl Python package is installed"))
    except Exception:
        gallerydl_exe = shutil.which("gallery-dl") or shutil.which("gallery_dl")
        portable_gallerydl = _find_portable_gallerydl()
        if gallerydl_exe:
            issues.append(("info", f"gallery-dl executable found: {gallerydl_exe}"))
        elif portable_gallerydl:
            issues.append(("info", f"Portable gallery-dl found: {portable_gallerydl}"))
        else:
            issues.append(("warn", "gallery-dl not found; downloader tab will ask the user to install it"))

    ffmpeg_bin = PROJECT_ROOT / "tools" / "ffmpeg"
    ffmpeg = next(ffmpeg_bin.rglob("ffmpeg.exe"), None) if ffmpeg_bin.exists() else None
    ffprobe = next(ffmpeg_bin.rglob("ffprobe.exe"), None) if ffmpeg_bin.exists() else None
    if ffmpeg and ffprobe:
        issues.append(("info", f"Portable FFmpeg found: {ffmpeg.parent}"))
    else:
        issues.append(("warn", "Portable FFmpeg not found; media features may depend on system PATH"))

    assets = PROJECT_ROOT / "pyJianYingDraft" / "assets"
    if assets.exists():
        issues.append(("info", "pyJianYingDraft assets found"))
    else:
        issues.append(("error", "pyJianYingDraft assets folder is missing"))
    return issues


def build_pyinstaller_command(name: str) -> list[str]:
    script = PROJECT_ROOT / "obfuscated" / "main.py"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        name,
        "--add-data",
        f"{PROJECT_ROOT / 'obfuscated' / 'pyJianYingDraft' / 'assets'};pyJianYingDraft/assets",
    ]
    ffmpeg_bin = PROJECT_ROOT / "tools" / "ffmpeg" / "ffmpeg-8.1.1-essentials_build" / "bin"
    if ffmpeg_bin.exists():
        cmd.extend(["--add-data", f"{ffmpeg_bin};tools/ffmpeg/ffmpeg-8.1.1-essentials_build/bin"])

    ytdlp_dir = PROJECT_ROOT / "tools" / "yt-dlp"
    if ytdlp_dir.exists():
        cmd.extend(["--add-data", f"{ytdlp_dir};tools/yt-dlp"])
    ytdlp_exe = PROJECT_ROOT / "tools" / "yt-dlp.exe"
    if ytdlp_exe.exists():
        cmd.extend(["--add-data", f"{ytdlp_exe};tools"])

    try:
        import yt_dlp  # noqa: F401
        cmd.extend(["--collect-all", "yt_dlp"])
    except Exception:
        pass

    gallerydl_dir = PROJECT_ROOT / "tools" / "gallery-dl"
    if gallerydl_dir.exists():
        cmd.extend(["--add-data", f"{gallerydl_dir};tools/gallery-dl"])
    gallerydl_exe = PROJECT_ROOT / "tools" / "gallery-dl.exe"
    if gallerydl_exe.exists():
        cmd.extend(["--add-data", f"{gallerydl_exe};tools"])

    try:
        import gallery_dl  # noqa: F401
        cmd.extend(["--collect-all", "gallery_dl"])
    except Exception:
        pass

    for module in [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ]:
        cmd.extend(["--hidden-import", module])
    for module in [
        "ctranslate2",
        "scenedetect",
        "cv2",
        "numpy",
        "pandas",
        "matplotlib",
        "torch",
        "triton",
        "imageio",
        "imageio_ffmpeg",
        "av",
        "sqlite3",
        "tkinter",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.QtPdf",
        "PySide6.QtNetwork",
        "PySide6.QtSql",
        "PySide6.QtSvg",
        "PySide6.QtXml",
        "PySide6.QtBluetooth",
        "PySide6.QtDBus",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
        "PySide6.QtMultimedia",
        "PySide6.QtNfc",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtSpatialAudio",
        "PySide6.QtTest",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
    ]:
        cmd.extend(["--exclude-module", module])
    cmd.append(str(script))
    return cmd


def _find_portable_ytdlp() -> Path | None:
    roots = [
        PROJECT_ROOT / "tools",
        PROJECT_ROOT / "tools" / "yt-dlp",
        PROJECT_ROOT / "tools" / "ytdlp",
    ]
    names = ["yt-dlp.exe", "yt_dlp.exe", "yt-dlp", "yt_dlp"]
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate
    return None


def _find_portable_gallerydl() -> Path | None:
    roots = [
        PROJECT_ROOT / "tools",
        PROJECT_ROOT / "tools" / "gallery-dl",
        PROJECT_ROOT / "tools" / "gallerydl",
    ]
    names = ["gallery-dl.exe", "gallery_dl.exe", "gallery-dl", "gallery_dl"]
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
