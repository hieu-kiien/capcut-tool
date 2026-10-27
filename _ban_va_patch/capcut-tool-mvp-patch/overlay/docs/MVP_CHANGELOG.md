# MVP Changelog

## 0.1.0-mvp

- Giữ Python/PySide6 làm runtime phát hành chính.
- Bổ sung khóa single-instance để tránh hai tiến trình cùng sửa draft.
- Bổ sung log xoay vòng và crash report trong dữ liệu người dùng.
- Bổ sung chế độ `--diagnose`, `--diagnose-json` và `--version`.
- Tối ưu preflight để không probe toàn bộ kho media hai lần.
- Cho phép dùng thư mục media chỉ đọc; ứng dụng chỉ kiểm tra khả năng đọc/quét.
- Bổ sung CI Windows, test runtime và cấu hình PyInstaller.
- Tách rõ Tauri/Rust là phần thử nghiệm, chưa đưa vào bản phát hành.
