# Checklist Tiến độ Kiểm tra và Nghiệm thu — Vortex Studio

Tất cả các giai đoạn kiểm tra và nghiệm thu đã hoàn tất thành công.

## Giai đoạn 1: Phân công Subagent
- [x] **Subagent A**: Qt offscreen và QApplication lifecycle (`test_setup_render.py` & `test_memory_leak.py`)
  - **Kết quả**: Đã refactor `test_setup_render.py` chạy test offscreen trong subprocess độc lập, bảo đảm không import PySide6 ở luồng cha. Đã cấu hình và kiểm chứng `test_memory_leak.py` dùng `QApplication.instance()` thích hợp.
  - **Đường dẫn**: [test_setup_render.py](tests/test_setup_render.py) | [test_memory_leak.py](tests/test_memory_leak.py)
- [x] **Subagent B**: Chroma logger và cp1252 strict (`test_advanced_features.py` & `chroma.py`)
  - **Kết quả**: Đã thay thế mock stream thủ công bằng cp1252 strict `logging.StreamHandler` thực thụ đính kèm vào logger chính. Đã cập nhật `core/chroma.py` đổi log tiếng Việt có dấu thành mã ASCII (`green`, `black`, `white`) giúp tránh hoàn toàn lỗi `UnicodeEncodeError`.
  - **Đường dẫn**: [test_advanced_features.py](tests/test_advanced_features.py) | [chroma.py](core/chroma.py)
- [x] **Subagent C**: Xác minh giao diện UI và cập nhật tài liệu
  - **Kết quả**: Đã đối chiếu thành công 12 màn hình thiết kế (FireShot) với ảnh thực tế (1920x1080). Đã cập nhật báo cáo `PROJECT_CONTEXT.md` nâng tỷ lệ test thành công từ 86/86 lên 90/90.
  - **Đường dẫn**: [PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) | [walkthrough.md](walkthrough.md)

## Giai đoạn 2: Git Hygiene
- [x] Stage chính xác hai tệp kiểm thử mới:
  - `git add -- tests/test_setup_render.py tests/test_memory_leak.py`
- [x] Xác minh trạng thái staged qua git diff (`git status --short` trả về trạng thái `A` cho hai tệp trên, các thay đổi khác trong worktree được giữ nguyên và bảo vệ hoàn toàn).

## Giai đoạn 3: Kiểm thử hồi quy và Hợp chuẩn
- [x] Chạy focused tests độc lập:
  - `python -m pytest -q tests/test_setup_render.py tests/test_memory_leak.py` (PASS)
  - `python -m pytest -q tests/test_advanced_features.py -k "chroma"` (PASS)
  - `python -m pytest -q tests/test_new_features.py -k "gui_splitter_widgets"` (PASS)
- [x] Chạy biên dịch toàn diện: `python -m compileall app core tests -q` (PASS, Exit code 0)
- [x] Chạy bộ test hồi quy đầy đủ: `python -X faulthandler -m pytest tests -q` (PASS, 90/90 passed)
- [x] Kiểm tra định dạng mã nguồn: `git diff --check` và `git diff --cached --check` (Sạch, không có khoảng trắng thừa)

## Giai đoạn 4: GitNexus và Báo cáo cuối
- [x] Chạy phân tích thay đổi GitNexus: `detect_changes` để kiểm soát vùng ảnh hưởng.
- [x] Xuất báo cáo walkthrough.md và task.md.
