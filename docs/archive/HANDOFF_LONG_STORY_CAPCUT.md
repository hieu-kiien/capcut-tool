# Bàn giao dự án: CapCut Long Story Automation (Updated)

## Mục tiêu

Xây dựng công cụ tự động tạo dòng thời gian (timeline) dự án CapCut cho video kể chuyện dài từ 30 phút đến hơn 3 tiếng, kết hợp bộ công cụ biên tập Keyframe chuyển động và chèn Transition hàng loạt.

Công cụ không render video cuối. Nó chỉ chuẩn bị timeline trong CapCut: voice chính, phụ đề srt, video/ảnh nền, nhạc nền, keyframe chuyển động, hiệu ứng chuyển cảnh. Người dùng mở CapCut để kiểm duyệt và render bước cuối.

## Định vị sản phẩm

Ứng dụng là máy dựng bản nháp và biên tập hiệu ứng tự động cho video dài:

- Chọn file giọng đọc (voice) có sẵn (.mp3, .wav).
- Chọn file phụ đề (srt) có sẵn để căn thời gian hình ảnh.
- Chọn thư mục video/ảnh nền để tự động phân bổ và lấp đầy dòng thời gian.
- Thêm logo và video hoạt ảnh overlay (Subscribe/Like).
- Biên tập hiệu ứng keyframe chuyển động (zoom, pan, trượt hình) và transition chuyển cảnh hàng loạt.
- Tự động kiểm tra lỗi và sửa đường dẫn dự án nháp CapCut (Draft Doctor).

## Code hiện tại

Thư mục dự án:

`C:\Users\hieuk\Desktop\capcut tool`

File chính:

- `main.py`: Điểm khởi chạy giao diện PySide6.
- `runtime_tools.py`: Cấu hình môi trường và định vị FFmpeg portable.
- `media_probe.py`: Đo đạc độ dài và phân giải của các file media.
- `video_mixer.py`: Lập kế hoạch cắt ghép và trộn ngẫu nhiên clip nền lấp đầy timeline.
- `capcut_draft_creator.py`: Tạo project thô của CapCut bằng thư viện `pyJianYingDraft`.
- `capcut_keyframe_tool.py`: Chèn keyframe chuyển động, speed, scale, và chèn transition giữa các điểm cắt.
- `draft_doctor.py`: Tự động chẩn đoán và sửa lỗi tệp nháp (Platform mismatch, missing files).
- `app/`: Thư mục giao diện PySide6 và pipeline chính.

## Điểm đã có sẵn

- Tạo dự án CapCut mới trực tiếp từ file JSON.
- Phân bổ hình ảnh/video nền tự động dựa theo thời lượng của file voice.
- Căn chỉnh khớp các phân đoạn media khớp với từng đoạn timing của file SRT.
- Chèn logo và clip hoạt ảnh overlay (chọn vị trí, tỷ lệ zoom, thời điểm lặp lại).
- Tự động chèn Keyframe chuyển động (zoom chậm/nhanh, pan trượt dọc/ngang, xoay, fade alpha) dựa trên các preset thiết lập sẵn hoặc tự chọn.
- Chèn Transition chuyển cảnh (Mix, Central Fade, Checker Fade, Slide, Zoom, Flash...) hàng loạt.
- Tính năng backup dự án trước khi áp dụng hiệu ứng và khôi phục khi cần.
- Tính năng tự động sửa lỗi dự án (Auto Repair) để chuyển đổi dự án nháp giữa các máy tính khác nhau dễ dàng.

## Cach lam nen uu tiên

Không nên viết lại toàn bộ app. Hãy giữ code hiện tại hoạt động ổn định trên Windows.
Mọi tính năng mới nên được viết thành module độc lập, kiểm thử kỹ bằng test scripts trước khi tích hợp vào giao diện PySide6.
