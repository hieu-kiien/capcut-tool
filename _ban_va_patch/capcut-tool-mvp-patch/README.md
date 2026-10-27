# CapCut Tool MVP Patch Kit

Gói này nâng cấp repository `hieu-kiien/capcut-tool` theo hướng MVP ổn định cho Windows, giữ backend Python/PySide6 hiện có và không phát hành phần Tauri prototype.

## Cách áp dụng

1. Tải hoặc clone repository gốc.
2. Giải nén gói patch này ở một thư mục riêng.
3. Mở PowerShell tại thư mục patch và chạy:

```powershell
python .\apply_mvp_patch.py "D:\duong-dan\capcut-tool" --test
```

Script sẽ kiểm tra đúng repository, tạo backup trong `.mvp-backup`, chép các file MVP, vá preflight/pipeline và chạy compile/test. Có thể xem trước bằng `--dry-run`.

## Thay đổi quan trọng

- Preflight nhanh: chỉ đếm file media; metadata được probe trong bước scan có progress riêng.
- Không còn yêu cầu quyền ghi vào thư mục media nguồn.
- Chống mở hai app cùng lúc.
- Log xoay vòng, crash report, chẩn đoán môi trường.
- CI và build EXE có thể lặp lại.

## Khôi phục

```powershell
python .\apply_mvp_patch.py "D:\duong-dan\capcut-tool" --restore-latest
```

Luôn thử trên bản sao repository và bản sao thư mục draft trước khi dùng với dự án quan trọng.

## Tài liệu kỹ thuật

- `overlay/docs/MVP_RESEARCH_REPORT.md`: quyết định kiến trúc, lỗi đã vá và giới hạn kiểm chứng.
- `overlay/docs/MVP_RELEASE_GUIDE.md`: checklist để build và xác nhận bằng CapCut PC thật.
