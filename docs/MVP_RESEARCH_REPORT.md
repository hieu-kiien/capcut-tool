# MVP Research & Engineering Report

## Quyết định kiến trúc

Bản phát hành MVP dùng Python/PySide6 làm runtime chính. Đây là nhánh đang có pipeline tạo draft thực, preflight, media probe, mixer, keyframe, transition, backup và test. Phần React/Tauri/Rust chỉ nên giữ ở trạng thái thử nghiệm cho đến khi Rust backend ghi được timeline CapCut thật và đạt functional parity.

MVP không cố trở thành trình dựng video thay thế CapCut. Sản phẩm tập trung vào một luồng rõ ràng: voice + SRT + kho media + preset → draft CapCut có thể mở và tiếp tục chỉnh sửa.

## Phát hiện kỹ thuật chính

### 1. Preflight bị lặp công việc

`PipelineRunner.preflight()` gọi preflight đầy đủ. Preflight probe từng media trong kho, sau đó bước `scan_media` lại quét/probe kho media. Với hàng trăm file, người dùng phải chờ lâu ngay ở bước đầu và khó hiểu ứng dụng đang làm gì.

Bản vá dùng fast preflight cho kho media: chỉ kiểm tra đường dẫn và đếm extension. File voice vẫn được probe để lỗi audio và cảnh báo SRT không bị sai. Metadata kho media được đọc đúng một lần ở bước scan có log/progress riêng.

### 2. Thư mục media bị yêu cầu quyền ghi không cần thiết

Media là đầu vào chỉ đọc, nhưng preflight tạo `.write_test_*` trong thư mục nguồn. Điều này làm thất bại với thư viện read-only, NAS, ổ chia sẻ hoặc thư mục do tài khoản khác quản lý; đồng thời để lại rác nếu tiến trình bị dừng đúng thời điểm.

Bản vá bỏ thao tác ghi thử. Lỗi đọc/liệt kê vẫn được phát hiện trong khối scan và vẫn chặn chạy.

### 3. Runtime thiếu lớp bảo vệ phát hành

Entry point cũ khởi tạo app trực tiếp, chưa có single-instance, log xoay vòng, crash report hoặc chẩn đoán môi trường. Hai tiến trình cùng mở có thể làm tăng nguy cơ cùng sửa một draft hoặc database.

Bản vá bổ sung:

- `QLockFile` để chỉ chạy một instance.
- Log 5 MB × 5 bản trong thư mục dữ liệu người dùng.
- Crash report riêng cho exception ngoài dự kiến.
- `--diagnose`, `--diagnose-json`, `--version`.
- Metadata ứng dụng và đường dẫn app-data ổn định.

### 4. Quy trình build chưa tái lập

Bản vá bổ sung requirements dev, CI Windows, compileall, pytest, chẩn đoán và PyInstaller spec. Gói EXE không đưa mã Tauri, screenshot, scratch hay dependency AI nặng vào bản phát hành.

## Những gì đã kiểm chứng trong gói patch

- Python compile thành công cho toàn bộ file mới.
- 4 unit test của patcher chạy thành công.
- Apply trên repository mô phỏng có đúng các đoạn mã upstream: thành công.
- Compile sau apply: thành công.
- Restore latest: khôi phục file cũ và xóa file mới thành công.
- ZIP không chứa `__pycache__` hoặc `.pyc`.

## Những gì chưa thể khẳng định

- Chưa chạy toàn bộ test suite trên checkout đầy đủ của repository trong môi trường này.
- Chưa build EXE thật trên Windows.
- Chưa mở draft bằng CapCut PC thật.
- Chưa benchmark với 500+ media thật hoặc video 1–3 giờ.

Do đó đây là bản **MVP hardening patch có kiểm thử**, chưa phải chứng nhận production. Chỉ gọi bản phát hành ổn định sau khi hoàn tất checklist thủ công trong `MVP_RELEASE_GUIDE.md`.

## Tiêu chí “MVP hoàn hảo” thực tế

Một bản MVP tốt không cần nhiều tính năng nhất. Nó cần:

1. Một kiến trúc phát hành duy nhất.
2. Không làm hỏng hoặc ghi nhầm dữ liệu nguồn.
3. Tạo draft thành công lặp lại trên ba kích thước dự án.
4. Hiển thị tiến trình và lỗi có thể hành động.
5. Có backup, rollback, log và chẩn đoán.
6. Có build/test tái lập.
7. Được xác minh bằng CapCut PC thật trước khi phân phối.
