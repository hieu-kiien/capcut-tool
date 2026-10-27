# MVP Changelog

> **Đây là changelog bản phát hành.** Phiên bản dự án được định nghĩa tại `mvp_runtime/__init__.py :: APP_VERSION` — đó là giá trị `main.py --version` in ra và là nguồn sự thật duy nhất.
>
> Lịch sử kỹ thuật chi tiết (fix, refactor, audit nội bộ) nằm ở [`CHANGELOG.md`](CHANGELOG.md).
>
> `package.json` và `src-tauri/Cargo.toml` mang version riêng ở `0.0.1-experimental`; đó là nhánh R&D Tauri, không phải version dự án — xem [`../PROJECT.md`](../PROJECT.md).

## 0.1.0-mvp

- Giữ Python/PySide6 làm runtime phát hành chính.
- Bổ sung khóa single-instance để tránh hai tiến trình cùng sửa draft.
- Bổ sung log xoay vòng và crash report trong dữ liệu người dùng.
- Bổ sung chế độ `--diagnose`, `--diagnose-json` và `--version`.
- Tối ưu preflight để không probe toàn bộ kho media hai lần.
- Cho phép dùng thư mục media chỉ đọc; ứng dụng chỉ kiểm tra khả năng đọc/quét.
- Bổ sung CI Windows, test runtime và cấu hình PyInstaller.
- Tách rõ Tauri/Rust là phần thử nghiệm, chưa đưa vào bản phát hành.
