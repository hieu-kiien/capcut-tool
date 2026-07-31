# Compact Draft compatibility and Pipeline Test Report

## Bước 1: Pipeline success nhỏ
- Đã chuẩn bị script `test_drafts.py` chạy qua API.
- Tạo dummy media (video `dummy_bg.mp4` và audio `dummy_voice.m4a`) sử dụng `ffmpeg`.
- Đã sinh draft thành công. Thông tin lưu tại `draft_assertion.txt`.
- Ghi nhận chưa có GUI lease nên chưa mở UI để chụp ảnh màn hình (`01_pipeline_progress.png`, `02_pipeline_success.png`). Sẽ chụp sau khi có lease.

## Bước 2: Tạo pretty và compact draft
- Đã tạo 2 bản draft: `TestDraft_Normal` (compact=False) và `TestDraft_Compact` (compact=True).
- Kết quả kích thước file JSON (draft_content.json):
  - Normal: 10,455 bytes
  - Compact: 5,475 bytes
- Kích thước compact giảm gần một nửa. JSON parse không gặp lỗi.

## Bước 3: Kiểm tra bằng CapCut PC thật
- **Trạng thái**: BLOCKED_EXTERNAL — awaiting real CapCut open/save.
- Đã copy 2 draft (`TestDraft_Normal` và `TestDraft_Compact`) vào thư mục dự án của CapCut (`%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`).
- Vì giới hạn của AI không thể trực tiếp thao tác GUI và chụp ảnh màn hình CapCut, nhiệm vụ này cần được con người (hoặc tác vụ tự động hóa GUI) mở phần mềm, load từng draft, kiểm tra và chụp ảnh.

## Bước 4: Save và reopen
- **Trạng thái**: BLOCKED_EXTERNAL — awaiting real CapCut open/save.
- Tương tự B3, việc thay đổi, lưu và kiểm tra lại data cần thao tác thủ công trên phần mềm thật.
