# Downloader Manual Test Notes - CapCut Long Story Studio

This file records the manual testing results performed using the updated downloader queue user interface.

## Test Cases & Results

### 1. Public YouTube Video (Short)
- **URL**: `https://www.youtube.com/watch?v=y3_P39P39PE` (or any short public URL)
- **Steps**:
  1. Dán URL vào hộp văn bản.
  2. Bấm nút **TẢI MEDIA BẰNG YT-DLP**.
- **Expected Behavior**:
  - Hàng đầu tiên trong bảng Queue hiển thị URL, trạng thái chuyển từ `Chờ tải` sang `Đang tải`.
  - Tiến độ tải hiển thị phần trăm tăng dần (ví dụ `10%`, `50%`, `100%`).
  - Thư mục output hiển thị đúng đường dẫn file lưu.
  - Khi hoàn thành, trạng thái đổi thành `Hoàn thành` (màu xanh lá).

### 2. Playlist with Limit (Max 2 Items)
- **URL**: `https://www.youtube.com/playlist?list=PL2fvyKa9DiGQ6o7d58Fk-T_s2sD-O-r-S`
- **Steps**:
  1. Dán link playlist vào ô nhập.
  2. Bật checkbox **Cho phép tải playlist/kênh**.
  3. Đặt **Giới hạn item playlist/kênh** thành `2`.
  4. Bấm **TẢI MEDIA BẰNG YT-DLP**.
- **Expected Behavior**:
  - Hàng chờ hiển thị URL của playlist.
  - yt-dlp bắt đầu phân tích và tải tối đa 2 video đầu tiên của playlist.
  - Tiến trình cập nhật riêng biệt cho từng item và chỉ giới hạn ở 2 tệp.

### 3. Invalid URL (Error Handling)
- **URL**: `https://invalid_url_for_testing`
- **Steps**:
  1. Dán URL lỗi vào ô nhập.
  2. Bấm **TẢI MEDIA BẰNG YT-DLP**.
- **Expected Behavior**:
  - Hàng chờ hiển thị URL lỗi.
  - Trạng thái chuyển sang `Lỗi` (màu đỏ) và hiển thị thông tin lỗi chi tiết ở cột `Lỗi`.
  - Toàn bộ giao diện UI của ứng dụng vẫn phản hồi tốt, không bị treo hoặc crash.
  - Người dùng có thể chỉnh sửa URL rồi bấm **Retry Lỗi** để chạy lại riêng URL này.

### 4. Cancel Mid-Download
- **Steps**:
  1. Dán 1 URL dài hoặc playlist nhiều tập để tải.
  2. Khi đang tải, bấm nút **HỦY TẢI MEDIA** (nút màu đỏ).
- **Expected Behavior**:
  - Tiến trình tải yt-dlp hiện tại bị dừng ngay lập tức.
  - Trạng thái của các dòng đang tải hoặc chờ tải trong Queue chuyển sang `Đã hủy` (màu cam).
  - Nút tải khôi phục lại trạng thái ban đầu (`TẢI MEDIA BẰNG YT-DLP`).
