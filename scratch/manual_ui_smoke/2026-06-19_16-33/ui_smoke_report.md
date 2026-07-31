# Báo cáo kết quả kiểm tra UI thủ công

## Môi trường thực hiện
- Thời gian chạy test: 2026-06-19 16:33
- Vị trí lưu log & ảnh chụp màn hình: `scratch/manual_ui_smoke/2026-06-19_16-33/`
- Công cụ tự động hóa: Kịch bản Python với PySide6 QTest/QTimer chạy trực tiếp trên MainWindow (`ui_test_runner.py`)

## Kết quả chi tiết

| ID | Tên chức năng | Trạng thái | Ghi chú và Bằng chứng |
|----|----------------|------------|------------------------|
| A1 | Launch và layout | **PASS** | Ứng dụng khởi động bình thường. Tiếng Việt hiển thị đúng. Bố cục UI hiển thị rõ ràng. <br> Bằng chứng: `01_launch_layout.png` |
| A2 | Scan media thành công | **PASS** | Chuyển đổi media directory sang thư mục nhỏ (1 file video). Quá trình quét hoàn tất thành công, giao diện không bị treo hay giật lác. <br> Bằng chứng: `02_scan_success.png` |
| A3 | Thay thế/hủy scan cũ | **PASS** | Quét thư mục lớn (100 files) và đổi ngay lập tức sang thư mục nhỏ. Scan mới đè lên scan cũ mà không bị treo hệ thống. <br> Bằng chứng: `03_scan_replacement.png` |
| A4 | Đóng ứng dụng khi worker đang chạy | **PASS** | Kích hoạt quét một thư mục lớn, đóng ứng dụng ngay trong lúc Worker đang chạy. Ứng dụng đóng sạch (Clean exit) không gây lỗi crash hay memory leak. <br> Bằng chứng: Console log tại `04_close_console.txt` |
| A5 | Downloader recoverable failure | **PASS** | Đưa URL không hợp lệ vào công cụ tải xuống (`http://invalid.url.local/test`). Nút Hủy và các nút khác vẫn hoạt động, Downloader có thể khôi phục lại trạng thái mặc định mà không crash app. <br> Bằng chứng: `05_download_fail_start.png`, `06_download_fail_recover.png` |

## Đánh giá tổng quan
Các thành phần giao diện người dùng chính đều hoạt động ổn định trong các tình huống bình thường, chuyển đổi ngữ cảnh liên tục cũng như ở trường hợp ngoại lệ (URL hỏng, đóng ứng dụng đột ngột). 
Không có lỗi Crash, treo giao diện hoặc rò rỉ dữ liệu ngoài ý muốn.
