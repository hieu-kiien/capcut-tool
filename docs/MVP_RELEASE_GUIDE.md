# MVP Release Guide

## Phạm vi bản MVP

Bản MVP ổn định lấy Python/PySide6 làm ứng dụng chính. Thư mục `src/` và `src-tauri/` được xem là nhánh thử nghiệm, không được đưa vào gói EXE cho đến khi backend Rust tạo draft thật và có kiểm thử tương thích CapCut.

Luồng phát hành tối thiểu:

1. Chạy `python main.py --diagnose`.
2. Chạy `python -m compileall app core pyJianYingDraft mvp_runtime main.py capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py -q`.
3. Chạy `python -m pytest -q tests`.
4. Tạo một draft mẫu trên bản sao dữ liệu.
5. Mở draft bằng CapCut PC thật và kiểm tra voice, nền, SRT, keyframe, transition, logo và BGM.
6. Chạy `powershell -ExecutionPolicy Bypass -File .\build_mvp.ps1`.

## Tiêu chí phát hành

- Không có test lỗi.
- Chẩn đoán báo `RESULT: READY`.
- Không ghi bất kỳ tệp thử nghiệm nào vào thư mục media nguồn.
- Khi ghi đè dự án, backup cũ phải tồn tại và mở được.
- Chỉ một phiên bản ứng dụng chạy tại một thời điểm.
- Lỗi ngoài dự kiến phải sinh báo cáo trong thư mục dữ liệu người dùng.

## Kiểm thử thủ công bắt buộc

Dùng ba bộ dữ liệu:

- Video ngắn 3-5 phút, 10-20 media.
- Video 30-60 phút, 100-300 media.
- Video 1-3 giờ, 500+ media và SRT dài.

Kiểm tra cả 9:16 và 16:9, đường dẫn có dấu tiếng Việt, khoảng trắng, media chỉ đọc, ổ đĩa gần đầy và thao tác hủy giữa chừng.
