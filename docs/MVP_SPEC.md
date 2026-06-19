# CapCut Long Story Studio - MVP Spec (Updated)

## Mục tiêu

Tạo một phần mềm desktop EXE giúp biến giọng đọc (voice), phụ đề (srt) có sẵn, và folder media nền thành draft CapCut hoàn chỉnh. App phải dễ dùng, đẹp, rõ từng bước, chạy được dự án dài 1-3 tiếng và cho phép người dùng biên tập chuyển động (keyframe) và chuyển cảnh (transition) trực tiếp trên giao diện trước/sau khi tạo draft.

## Người dùng chính

Người làm video truyện dài cho YouTube, TikTok, Shorts hoặc các kênh nội dung dài đã chuẩn bị sẵn giọng đọc chính (voice) và phụ đề (SRT), mong muốn tự động hóa khâu lắp ráp timeline CapCut và chèn các hiệu ứng zoom, pan, trượt hình ảnh, chuyển cảnh hàng loạt mà không cần làm thủ công.

## Nguyên tắc thiết kế

- Màn hình chính là khu làm việc thật, chia làm 2 tab: Dựng Timeline Tự Động và Keyframe & Chuyển Cảnh.
- Luồng chính phải rõ: chọn nguyên liệu (voice, srt, media folder) -> cấu hình preset -> chạy tạo dự án.
- Mỗi bước có nút chạy riêng, trạng thái riêng, lỗi riêng và kết quả đầu ra riêng.
- Nguời dùng luôn thấy app đang làm gì, đang xử lý file nào, lỗi ở đâu qua bảng Stepper và Log Terminal trực quan.
- Preset dùng ngôn ngữ dễ hiểu, ví dụ `Dọc (9:16 Shorts/TikTok)`, `Ngang (16:9 YouTube)`.

## Cấu trúc màn hình

### 1. Dựng Timeline Tự Động (Tab 1)

Thiết lập nền tảng và nguyên liệu của dự án:

- **Tên dự án nháp:** Tên thư mục nháp của CapCut.
- **Thư mục lưu dự án nháp (Draft Root):** Thư mục chứa các dự án CapCut của người dùng.
- **Tệp giọng đọc chính (Voice Audio):** Tệp âm thanh đã thu âm hoặc xuất sẵn (.mp3, .wav).
- **Thư mục Video/Ảnh nền (Background Media):** Thư mục chứa kho nguyên liệu ảnh/video nền.
- **Tệp nhạc nền (BGM Audio - Tùy chọn):** Nhạc nền đi kèm.
- **Tệp phụ đề (SRT - Tùy chọn):** File phụ đề khớp với giọng đọc.

Cài đặt nâng cao:
- **Tỷ lệ khung hình:** `9:16` hoặc `16:9`.
- **Độ dài clip nền tối thiểu/tối đa:** Ví dụ từ 5 đến 9 giây.
- **Cách trộn video nền:** Trộn ngẫu nhiên (shuffle_bag), lần lượt (sequential), ngẫu nhiên hoàn toàn (random), v.v.
- **Xử lý video ngắn hơn voice:** Kéo giãn (stretch) hoặc lặp lại (loop).
- **Tự động thêm Keyframe / Chuyển cảnh:** Áp preset mẫu ngay khi chạy tạo draft.
- **Lớp phủ (Overlay):** Thêm Logo (chọn vị trí, tỷ lệ scale) hoặc Hoạt ảnh Subscribe/Like (chọn thời điểm xuất hiện đầu/giữa/cuối/lặp lại).

### 2. Keyframe & Chuyển Cảnh (Tab 2)

Khu vực biên tập hiệu ứng chuyên sâu cho dự án CapCut có sẵn hoặc vừa tạo:

- **Chọn dự án nháp:** Quét và liệt kê toàn bộ dự án hiện có tại Draft Root.
- **Biên tập hiệu ứng:**
  - **Preset Zoom/Pan có sẵn:** Chọn các mẫu chuyển động zoom chậm, zoom nhanh, xoay nhẹ, zoom nảy, trượt trái/phải/trên/dưới, fade alpha.
  - **Keyframe tự chọn:** Cho phép định nghĩa giá trị mốc đầu, mốc giữa, mốc cuối và đơn vị áp dụng (tỷ lệ, pixel) cho các thuộc tính Scale Uniform, Scale X/Y, Rotation, Position X/Y, Alpha.
  - **Hiệu ứng chuyển cảnh (Transitions):** Chèn các hiệu ứng Mix, Central Fade, Checker Fade, Slide, Zoom... vào giữa các clip, thiết lập thời lượng chuyển cảnh.
  - **Thay đổi tốc độ (Speed) & Thu phóng (Scale):** Tăng giảm tốc độ hoặc zoom scale hàng loạt cho các phân đoạn video nền.
- **Quản lý sao lưu & Hoàn tác:**
  - Danh sách bản sao lưu (.bak) của dự án.
  - Nút khôi phục (restore) về phiên bản cũ.
  - Tự động dọn dẹp backup cũ theo số ngày chỉ định.
- **Tự động sửa lỗi dự án (Auto Repair):** Gọi `draft_doctor` sửa lỗi đường dẫn tuyệt đối của file media và platform mismatch để dự án mở được bình thường trên CapCut mà không bị lỗi chấm than đỏ.

### 3. Tiến trình thực hiện & Live Logs (Cột Phải)

- **Stepper hiển thị trạng thái 4 bước:**
  1. Kiểm tra đầu vào (Preflight)
  2. Quét kho video nền (Scan Media)
  3. Phân bổ video nền (Plan Media)
  4. Tạo dự án nháp CapCut (Write Draft)
- **Log Terminal:** Hiển thị chi tiết từng hành động dưới dạng bảng màu console trực quan.

## Kiến trúc đề xuất

### UI

Tách biệt cấu trúc giao diện và nghiệp vụ:

- `main.py`: điểm chạy app và nạp font chữ.
- `app/gui.py`: màn hình, widget, style CSS và kết nối các Worker luồng phụ (QThread).
- `app/pipeline.py`: wrapper chạy quy trình dựng timeline tuần tự.
- `app/presets.py`: định nghĩa danh sách preset keyframe và transition.

### Backend

Các module nghiệp vụ độc lập:

- `video_mixer.py`: Lập kế hoạch phân bổ video nền theo thời lượng.
- `media_probe.py`: Đo thông tin duration/resolution của các file.
- `capcut_draft_creator.py`: Tạo project JSON thô của CapCut.
- `draft_doctor.py`: Chẩn đoán và vá lỗi tệp JSON.
- `capcut_keyframe_tool.py`: Chỉnh sửa keyframe/transition trong JSON.

## Đóng gói EXE

Mục tiêu đóng gói:
- Chạy ổn định trên Windows.
- Tự động giải nén và cấu hình FFmpeg/FFprobe portable đi kèm.
- Loại bỏ các thư viện nặng không cần thiết (PyTorch, SceneDetect, OpenCV...) để giảm dung lượng file EXE.
