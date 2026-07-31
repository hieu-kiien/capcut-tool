# Báo cáo Phân tích & Kế hoạch Nâng cấp (Vortex Studio / CapCut Tool)

Tài liệu này ghi nhận kết quả khảo sát chi tiết và phân rã các module chức năng của ứng dụng để nâng cấp giao diện, trải nghiệm người dùng (UI/UX) và tính năng dựa trên dự án mẫu (Vortex Studio).

---

## 0. Chuẩn bị chung: Scope & Mapping

Dưới đây là bảng ánh xạ (mapping) chi tiết giữa các tệp nguồn, ảnh chụp màn hình dự án mẫu (reference screenshots) và vai trò chức năng trong hệ thống.

| Subtask / Agent | Tệp Nguồn Phân Tích | Ảnh Giao Diện Tham Chiếu | Chức Năng Chính & Vai Trò |
| :--- | :--- | :--- | :--- |
| **0. Chuẩn bị chung** | `prompt.md` | Toàn bộ 12 ảnh trong `image/` | Xác định phạm vi dự án, luật context và ánh xạ tổng quan. |
| **1. Agent A — Dashboard + Setup** | `app/widgets/dashboard_widget.py`<br>`app/widgets/setup_widget.py` | `001 - Bảng điều khiển.png`<br>`002 - Thiết lập dự án.png` | Hiển thị KPI, lối tắt nhanh (shortcuts) và biểu đồ; Cấu hình tham số đầu vào dự án (tên, thư mục lưu, tỷ lệ khung hình, v.v.). |
| **2. Agent B — Media Studio** | `app/widgets/media_studio_widget.py` | `003, 008, 009, 010 - Xưởng media.png` | Nhập tệp phương tiện (import), hiển thị danh sách, phân loại tag, hiển thị duration/resolution, lọc và tìm kiếm nhanh. |
| **3. Agent C — Effects + Keyframe** | `app/widgets/effects_widget.py` | `004, 011, 012 - Hiệu ứng & Thương hiệu.png` | Điều chỉnh thương hiệu (logo/overlay), cấu hình keyframe, chèn transition, áp dụng hiệu ứng chuyển động. |
| **4. Agent D — History / Undo / Redo** | `app/widgets/history_widget.py` | `006, 013 - Lịch sử & Phục hồi.png` | Ghi nhận lịch sử công việc, danh sách dự án cũ, sao lưu dự án (backups), và khôi phục trạng thái (undo/redo). |
| **5. Agent E — Build / Export** | `app/widgets/build_widget.py`<br>`core/downloader/downloader.py`<br>`core/cutter/cutter.py` | `005 - Trung tâm dựng.png` | Quản lý hàng đợi build (build queue), tải xuống tài nguyên nền (yt-dlp), cắt ghép video/audio (cutter). |
| **6. Agent F — Theme / Visual System** | `app/theme.py` | Toàn bộ 12 ảnh trong `image/` | Định nghĩa phong cách trực quan (QSS rules, dark/light modes, typography, icons, card layouts). |
| **7. Agent G — Core Data / Validation** | `core/db.py`<br>`core/path_validation.py` | Không có | Cơ sở dữ liệu SQLite cục bộ (draft_studio.db), kiểm tra an toàn đường dẫn tránh Path Traversal. |
| **8. Agent H — Tests / Coverage** | `tests/test_new_features.py`<br>`tests/test_profile_system.py` | Không có | Kiểm thử tự động (Unit test, Integration test), đảm bảo không gây lỗi hồi quy (regression) khi thay đổi UI/logic. |
| **9. Agent I — Orchestration & Sync** | `app/gui.py`<br>`app/pipeline.py`<br>`app/preflight.py`<br>`app/queue_manager.py` | Không có | Kết nối, điều phối luồng xử lý chính giữa các tab UI và các luồng xử lý nền (worker threads). |
| **10. Agent J — Tổng hợp / Kế hoạch cuối** | Toàn bộ báo cáo từ A đến I | Không có | Tổng hợp kiến trúc, lập danh sách đầu việc chi tiết và đề xuất phương án thi công tối ưu. |

---

## Chi tiết Phân tích từ các Agent

### 1. Agent A — Dashboard + Setup
- **Tệp nguồn đã phân tích**:
  - `app/widgets/dashboard_widget.py` (Dòng 1 đến 649)
  - `app/widgets/setup_widget.py` (Dòng 1 đến 1277)
  - `app/controllers/profile_controller.py` (Dòng 1 đến 513)
  - `app/gui.py` (Dòng 720 đến 900)
- **Nhiệm vụ chính**: 
  - `DashboardWidget`: Quản lý trung tâm điều khiển (KPIs, live logs, checklists và timeline preview).
  - `SetupWidget`: Thiết lập tham số dự án, chỉnh sửa phụ đề (SRT), kết xuất waveform âm thanh qua FFmpeg, và xem trước font/style phụ đề.
- **Các Symbol / Chức năng quan trọng**:
  - `TimelineWidget` (`dashboard_widget.py`): Vẽ timeline gồm 3 phần (Intro, Media, Outro) dùng `QPainter`.
  - `SubtitlePreviewLabel` (`setup_widget.py`): Vẽ text layout tùy biến màu, stroke outline, shadow offset.
  - `AudioWaveformLoader` (`setup_widget.py`): Khởi chạy `QThread` gọi FFmpeg downsample lấy dữ liệu PCM vẽ waveform.
  - `AudioWaveformWidget` (`setup_widget.py`): Vẽ thanh waveform và nhận tương tác tua âm thanh.
  - `ProfileController` (`profile_controller.py`): Đồng bộ các widget settings với SQLite.
- **Data Flow**: Các thiết lập trong UI được ProfileController lưu trữ. `app/gui.py` điều phối chính, khi cài đặt thay đổi sẽ chạy `_update_dashboard_summary()` để cập nhật các thẻ trạng thái (Voice, Subtitle, Logo...), liệt kê cảnh báo/lỗi và kích hoạt/vô hiệu nút Dựng draft.
- **Rủi ro & Ràng buộc**: Phụ thuộc vào file thực thi FFmpeg và thư viện MediaInfo cục bộ để tính duration; Intro/Outro asset dropdown trống nếu cache DB bị cũ; chỉnh sửa SRT trực tiếp sử dụng split chuỗi thô sơ có thể gây lỗi nếu format không chuẩn.
- **Khuyến nghị nâng cấp giao diện**:
  - **Dashboard**: Tổ chức lại lưới Tóm tắt dự án thành 2 hàng x 4 cột; Đổi checklist trạng thái sang dạng thẻ (Card grid) nằm ngang; Đổi các nút chức năng thành các thẻ click lớn có mô tả; Mở rộng log console toàn màn hình ở dưới cùng.
  - **Setup**: Thêm nút Lưu preset/Nhân bản/Xuất/Nhập lên header; Chia phần âm thanh thành 2 thanh waveform song song (Giọng đọc và Nhạc nền); Thêm nút kiểm tra thời gian và hiển thị tóm tắt lỗi phụ đề dưới bảng SRT.

### 2. Agent B — Media Studio
- **Tệp nguồn đã phân tích**:
  - `app/widgets/media_studio_widget.py` (Dòng 1 đến 1411)
  - `media_probe.py` (Dòng 1 đến 200)
  - `assets/manager.py` (Dòng 1 đến 200)
  - `core/db.py` (Dòng 1 đến 150)
  - `app/theme.py` (Dòng 1 đến 200)
- **Nhiệm vụ chính**: Quản lý thư viện tài nguyên (import, gắn tag category, trích xuất thumbnail qua FFmpeg, validate kích thước/FPS), download media từ URL (yt-dlp/gallery-dl) và cắt video không mất dữ liệu (lossless cutter).
- **Các Symbol / Chức năng quan trọng**:
  - `MediaStudioWidget`: Bộ điều khiển trung tâm quản lý tab thư viện, download và cắt video.
  - `ImportWorker` & `DownloadThread`: Quản lý import và download chạy trên QThread để tránh giật lag UI.
  - `CutterWorker`: Thực hiện lệnh cắt FFmpeg losslessly (`ffmpeg -ss ... -i ... -t ... -c copy`).
  - `AssetManager`: Xử lý CRUD tài nguyên, băm MD5 để check trùng lặp và dump frame thumbnail ở giây thứ 1.0.
  - `MediaProbeCache`: Cache LRU (tối đa 1000 phần tử) giúp bỏ qua probe FFmpeg nếu tệp không đổi size/mtime.
- **Data Flow**: User drag/browse file -> tag category -> ImportWorker -> AssetManager (MD5/Probe) -> lưu SQLite DB -> refresh_library() cập nhật grid. Tài nguyên được truy vấn qua `list_assets` để nạp vào video_mixer lập lịch.
- **Rủi ro & Ràng buộc**: 
  - Đóng app đột ngột khi đang download có thể tạo zombie process (yt-dlp).
  - Quét thư mục media quá lớn trên GUI thread có thể gây giật lag.
  - Cắt video hiển thị thanh tiến trình vô định (marquee) thay vì phần trăm thực tế.
  - Xem trước file (preview) gọi `QDesktopServices.openUrl` sẽ bị fail nếu máy client thiếu codec/default player.
- **Khuyến nghị nâng cấp giao diện**:
  - **Grid Card**: Thêm badge hiển thị thời lượng (ví dụ: `00:05`) ở góc dưới thẻ và thêm viền xanh Teal khi hover.
  - **Warnings Scan**: Chuyển logic quét thư mục trong `update_scan_warnings` sang QThread.
  - **Downloader**: Thay thế log phẳng bằng bảng `QTableWidget` hiển thị tiến độ và nút hủy riêng cho từng URL.
  - **Cutter**: Parse thẻ `time=` từ stdout của FFmpeg để hiển thị phần trăm cắt thực tế.
  - **Preview Player**: Tích hợp trình phát media gốc (`QMediaPlayer` + `QVideoWidget`) trực tiếp trong tab thay vì mở app ngoài.

### 3. Agent C — Effects + Keyframe
- **Tệp nguồn đã phân tích**:
  - `app/widgets/effects_widget.py` (Dòng 1 đến 907)
  - `app/gui.py` (Cấu hình ProjectConfig và chạy KeyframeWorker)
  - `app/pipeline.py` (Định nghĩa ProjectConfig và truyền params)
  - `capcut_draft_creator.py` (Dòng 170-250, 630-730)
  - `core/chroma.py` (Dòng 1 đến 122)
  - `capcut_keyframe_tool.py` (Dòng 1-200, 250-550, 840-880)
- **Nhiệm vụ chính**: Quản lý chèn logo và subscribe animation (định vị tọa độ, căn chỉnh thời điểm xuất hiện), xử lý tách nền phông xanh (chroma-key hình ảnh qua Pillow, video qua FFmpeg xuất MOV transparent), chèn keyframe chuyển động (Zoom, Pan, Rotate, Fade), và quản lý chèn các transition chuyển cảnh.
- **Các Symbol / Chức năng quan trọng**:
  - `EffectsWidget`: Widget UI chứa các thẻ cài đặt logo, animation, chroma key, và hiệu ứng chuyển động.
  - `KeyframeWorker`: QObject chạy trên QThread xử lý chèn keyframe và transition vào JSON nháp.
  - `prepare_overlay_asset()` (`core/chroma.py`): Xóa phông nền sử dụng Pillow (ảnh) và lệnh FFmpeg (video).
  - `apply_random_presets_to_file()` & `apply_random_transitions_to_file()`: Thao tác chỉnh sửa trực tiếp trường `common_keyframes` của segment trong JSON nháp.
- **Data Flow**: Settings UI -> đóng gói vào `ProjectConfig` -> `draft_creator` xử lý -> Gọi `core/chroma.py` tách nền và lưu overlay đã làm sạch -> `KeyframeWorker` gọi keyframe tool -> Đọc JSON nháp, chèn chuyển động/transition vào `common_keyframes` (tự động quy đổi đơn vị pixel/phần trăm sang không gian chuẩn hóa của CapCut) -> Lưu JSON và đồng bộ SQLite.
- **Rủi ro & Ràng buộc**:
  - Ghi file JSON trực tiếp giả định schema JSON CapCut cố định; nâng cấp CapCut PC có thể làm lỗi logic parse.
  - Xung đột ghi tệp nếu khôi phục hoặc chèn keyframe khi CapCut đang mở (CapCut tự động ghi đè hoặc giữ lock file).
  - Tách nền video phụ thuộc FFmpeg; luồng bị kill đột ngột có thể để lại file lock (`PermissionError` ở lần chạy sau).
- **Khuyến nghị nâng cấp**:
  - Gộp các thao tác chỉnh sửa JSON kế tiếp nhau (keyframes, transitions) thành một chu kỳ Đọc -> Sửa -> Ghi duy nhất để tối ưu I/O.
  - Đảm bảo kiểm soát và force-kill toàn bộ child process FFmpeg tách nền nếu worker bị hủy bởi user.
  - Đồng bộ typography và dùng chung `#configCard` từ `theme.py` để đồng nhất giao diện thẻ hiệu ứng.

### 4. Agent D — History / Undo / Redo
- **Tệp nguồn đã phân tích**:
  - `app/widgets/history_widget.py` (Dòng 1 đến 1041)
  - `app/history.py` (Dòng 1 đến 114)
  - `draft_doctor.py` (Dòng 1 đến 723)
  - `core/db.py` (Dòng 1 đến 242)
  - `app/workers.py` (Dòng 48 đến 200)
- **Nhiệm vụ chính**: Quản lý lịch sử tác vụ dựng dự án (đọc/ghi lịch sử từ tệp JSON), tự động sao lưu tệp nháp (`.bak`), quản lý khôi phục tệp nháp (phục hồi cả tệp chính và tệp gương), tự động sửa lỗi liên kết tệp tin và dọn dẹp các bản sao lưu cũ.
- **Các Symbol / Chức năng quan trọng**:
  - `HistoryWidget`: Quản lý hiển thị tab Lịch sử tác vụ và tab chẩn đoán lỗi Draft Doctor.
  - `LogViewerDialog`: Hộp thoại xem nhật ký chi tiết của tác vụ.
  - `check_draft_json()`, `repair_draft_project()`, `restore_draft_backup()`: Các hàm thực thi kiểm tra tính toàn vẹn, relink tài nguyên và ghi đè tệp nháp từ bản backup.
  - `KeyframeWorker`: Worker chạy ngầm phục vụ tác vụ khôi phục và sửa lỗi để tránh treo giao diện.
- **Data Flow**: Khi có sự kiện thay đổi nháp -> Tạo tệp `.bak` và ghi nhận vào SQLite `backups`. Khi khôi phục -> Khóa UI -> Khởi chạy KeyframeWorker chạy ngầm -> Ghi đè file nháp chính -> Ghi đè toàn bộ các file nháp gương (mirrors) để đồng bộ -> Lưu lịch sử -> Mở khóa UI và chạy lại chẩn đoán.
- **Rủi ro & Ràng buộc**: Xung đột ghi đè nếu khôi phục khi CapCut đang chạy (đã có cảnh báo bằng chữ vàng); Lỗi OSError nếu tệp sao lưu `.bak` bị tiến trình khác khóa khi dọn dẹp; SQLite DB lock nếu luồng ghi đụng độ (đã dùng WAL mode).
- **Khuyến nghị nâng cấp giao diện**:
  - **Lịch sử**: Đổi tiêu đề tab thành "Lịch sử" và đổi nhãn các cột sang: `NGÀY`, `LOẠI`, `DỰ ÁN`, `TRẠNG THÁI`, `THỜI LƯỢNG`. Đổi style nút thao tác (Tải lại, Xem log...) thành link text thanh thoát.
  - **Sao lưu**: Tái cấu trúc bảng sao lưu thành dạng List row phẳng: `<Tên dự án> · <Thời gian>` kèm nút phục hồi và nút xóa. Bổ sung tính năng xóa backup đơn lẻ (Trash icon) cập nhật đồng thời file vật lý và SQLite.
  - **Bác sĩ Draft**: Thêm badge đếm lỗi động cạnh tiêu đề (ví dụ: `4 VẤN ĐỀ`). Tái cấu trúc danh sách lỗi thành dạng List widget kèm nút bấm "Sửa" trực tiếp. Nhóm nút đáy đổi thành: `Quét draft`, `Sửa tự động`, `Báo cáo`.

### 5. Agent E — Build / Export
- **Tệp nguồn đã phân tích**:
  - `app/widgets/build_widget.py` (Dòng 1 đến 847)
  - `app/queue_manager.py` (Dòng 1 đến 639)
  - `app/pipeline.py` (Dòng 1 đến 446)
  - `core/downloader/downloader.py` (Dòng 1 đến 909)
  - `core/cutter/cutter.py` (Dòng 1 đến 124)
- **Nhiệm vụ chính**: Quản lý hàng đợi dựng dự án (Batch Build Queue), tải tài nguyên đa phương tiện song song (yt-dlp/gallery-dl) và cắt ghép video losslessly qua FFmpeg.
- **Các Symbol / Chức năng quan trọng**:
  - `BuildWidget`: Widget giao diện hiển thị danh sách hàng đợi, trạng thái stepper và nhật ký ghi.
  - `BatchQueueManager`: Quản lý trung tâm của hàng đợi dựng, lưu trữ trạng thái SQLite.
  - `QueuePipelineWorker` & `PipelineRunner`: QRunnable chạy ngầm gọi pipeline xử lý các bước dựng dự án.
  - `YtDlpDownloadRunner`: Engine tải tài nguyên sử dụng ThreadPoolExecutor hỗ trợ timeout và kiểm tra dung lượng ổ đĩa.
  - `lossless_cut_video()` & `CutterWorker`: Thao tác cắt video qua command line FFmpeg với cơ chế parse progress từ stderr.
- **Data Flow**: Thêm cấu hình vào hàng đợi -> Tạo `BuildJob` (status `pending`) -> Chạy hàng đợi -> `PipelineRunner` chạy qua 5 bước (preflight -> scan -> plan -> write -> apply_effects) -> Tạo thư mục draft CapCut hoàn chỉnh.
- **Rủi ro & Ràng buộc**: Subprocess (yt-dlp, FFmpeg) có thể bị treo hoặc tạo zombie process (đã giải quyết bằng psutil khi đóng app); Thiếu dung lượng ổ đĩa khi ghi tệp tin lớn; Lỗi nếu FFmpeg/FFprobe cầm tay bị mất đường dẫn.
- **Khuyến nghị nâng cấp**:
  - Thêm nút "Thử lại" trực tiếp trên giao diện hàng đợi cho các job bị lỗi.
  - Thêm hiển thị dung lượng ổ đĩa còn lại trên giao diện BuildWidget để cảnh báo nếu dưới 2GB.
  - Đồng bộ format log của Cutter/Downloader để đồng nhất màu hiển thị trong Build console.

### 6. Agent F — Theme / Visual System
- **Tệp nguồn đã phân tích**:
  - `app/theme.py` (Dòng 1 đến 486)
  - `app/gui.py` (Các phần styling)
  - `app/widgets/dashboard_widget.py` (Các màu vẽ và stylesheets cục bộ)
  - Thư mục `image/` (Chứa 12 hình ảnh giao diện tham chiếu)
- **Nhiệm vụ chính**: Định nghĩa và quản lý stylesheet toàn cục (QSS), bảng màu chủ đạo (Zinc base kết hợp neon Teal accent), cấu hình typography và các style chunks dùng chung cho các widget UI.
- **Các Symbol / Chức năng quan trọng**:
  - `COLOR_TEAL` (`#0dd3ba`): Màu accent chính của ứng dụng.
  - `COLOR_DARK_ZINC` (`#0d0e12`) & `COLOR_CARD_BG` (`#18181b`): Màu nền ứng dụng và nền thẻ.
  - `QSS_CARD`, `QSS_BUTTON`, `QSS_LINEEDIT`: Các chuỗi CSS định dạng cho các widget cơ bản.
  - `get_application_stylesheet()`: Tổng hợp tất cả định nghĩa QSS thành một stylesheet lớn để nạp vào ứng dụng.
- **Data Flow**: Khi khởi chạy app, `MainWindow` gọi `_apply_style()` để nạp stylesheet toàn cục. Các widget động thay đổi thuộc tính CSS bằng cách gọi `unpolish` / `polish`. Các canvas vẽ tự do (như timeline hay preview) tự vẽ bằng `QPainter` kết hợp các `QColor` tĩnh.
- **Rủi ro & Ràng buộc**: 
  - **Hardcoded màu sắc chéo tệp (Technical Debt)**: Màu neon Teal và các màu Zinc được hardcode trực tiếp trong các widget UI thay vì import từ `theme.py`. Nếu đổi theme trong `theme.py`, giao diện sẽ không đồng nhất.
  - **Typography phân tán**: Cỡ chữ (`font-size: 11px`, `9px`...) được code trực tiếp trong QSS cục bộ thay vì dùng scale chung.
  - **Lỗi hiển thị nguyên bản (Native conflicts)**: Việc override toàn bộ Scrollbar, Combobox có thể gây lỗi hiển thị trên một số phiên bản Windows.
- **Khuyến nghị nâng cấp giao diện (Giả lập Glassmorphism)**:
  - Chuyển `theme.py` thành một bộ quản lý tập trung cung cấp cả chuỗi QSS lẫn đối tượng `QColor` / `QFont` cho `QPainter`.
  - Thay thế toàn bộ hex màu hardcode bằng cách tham chiếu đến biến của `theme.py`.
  - Thiết kế giả lập Glassmorphism bằng cách giảm opacity của Card background (vd: `rgba(25, 25, 30, 0.7)`) kết hợp viền mờ `1px solid rgba(255, 255, 255, 0.08)` và hiệu ứng đổ bóng mềm `QGraphicsDropShadowEffect`.
  - Thiết lập font scale chuẩn hóa (`FONT_SIZE_XS`, `SM`, `MD`, `LG`, `XL`).

### 7. Agent G — Core Data / Validation
- **Tệp nguồn đã phân tích**:
  - `core/db.py` (Dòng 1 đến 242)
  - `core/path_validation.py` (Dòng 1 đến 91)
  - `app/presets.py` (Dòng 1 đến 259)
  - `profiles/manager.py` (Dòng 1 đến 354)
  - `app/draft_lock.py` (Dòng 1 đến 154)
  - `app/preflight.py` (Dòng 70 đến 120)
- **Nhiệm vụ chính**: Khởi tạo SQLite DB, quản lý các bảng preset/history, validate an toàn tên dự án/đường dẫn (tránh Path Traversal), quản lý CRUD profile/versioning cấu hình, và lock/unlock ghi đè tệp tin chéo tiến trình.
- **Các Symbol / Chức năng quan trọng**:
  - `Database.get_connection(db_path)`: Singleton trả về connection dùng chung, cấu hình `WAL` mode và `foreign_keys=ON`.
  - `validate_project_name(project_name, draft_root)`: Xác thực chuỗi tên dự án hợp lệ, chặn traversal (`..`), tên thiết bị dành riêng của Windows (`CON`, `PRN`), và trả về resolved path.
  - `ProfileManager.rollback_profile()`: Hoàn tác trạng thái cấu hình dựa trên Snapshot đã lưu trong `profile_versions`.
  - `locked_draft(project_path)`: Context manager bảo vệ chống ghi đè đồng thời trên tệp draft (sử dụng file lock qua `msvcrt` trên Windows hoặc `fcntl` trên Unix).
- **Data Flow**:
  1. Người dùng nhập tên dự án -> `validate_project_name` thực hiện kiểm tra độ an toàn.
  2. Bất kỳ lỗi nào (ValueError) -> Giao diện UI lập tiếp chặn tiến trình xây dựng (Preflight check).
  3. Cập nhật profile -> Sao lưu Snapshot cấu hình JSON cũ vào `profile_versions`, sau đó cập nhật thông tin mới vào bảng `profiles` và tăng số version.
  4. Preset được gộp từ các presets mặc định tĩnh (`KEYFRAME_PRESETS` trong `presets.py`) và preset tùy biến động lưu trong DB.
- **Rủi ro & Ràng buộc**:
  - **Shared Connection Race Conditions**: Connection SQLite được chia sẻ toàn cục thông qua Singleton giữa các Thread khác nhau (ScanWorker, BuildWorker, v.v.). SQLite không hoàn toàn an toàn khi nhiều thread cùng chạy query cursors đồng thời trên 1 connection duy nhất, dễ gây ra lỗi "database is locked" hoặc sai lệch trạng thái cursor.
  - **Lỗi case-sensitivity trên Windows**: Kiểm tra folder cha (`resolved_root in resolved_proj.parents`) có thể trả về sai nếu viết hoa/thường không đồng bộ trên Windows (vd: `d:\Drafts` vs `D:\Drafts`), dẫn tới block sai các dự án hợp lệ.
  - **Thiếu Busy Timeout**: Khi khởi tạo sqlite3.connect, không truyền tham số `timeout`. Tác vụ ghi của thread này có thể lập tức quăng Exception nếu thread khác đang khóa ghi, thay vì chờ đợi ngắn.
- **Khuyến nghị hành động tiếp theo**:
  - Chuyển đổi connection DB sang dạng Thread-Local (`threading.local()`) hoặc connection pool để mỗi Thread có connection SQLite riêng.
  - Thêm `timeout=30.0` khi khởi tạo sqlite3.connect.
  - Chuẩn hóa chữ hoa/thường cho đường dẫn trên Windows sử dụng `os.path.normcase()` trước khi đối chiếu.

### 8. Agent H — Tests / Coverage
- **Tệp nguồn đã phân tích**:
  - `tests/test_new_features.py` (Dòng 1 đến 1285)
  - `tests/test_profile_system.py` (Dòng 1 đến 247)
- **Nhiệm vụ chính**: Kiểm thử các tính năng mở rộng, giao diện PySide6, an toàn bảo mật, các logic tải xuống/cắt ghép và quản lý dữ liệu SQLite (CRUD, rollback, clone profile).
- **Các Symbol / Chức năng quan trọng**:
  - `test_video_mixer_ranges()`: Kiểm thử thuật toán phân bổ timeline của video mixer.
  - `test_project_name_validation()` & `test_windows_reserved_names()`: Kiểm tra regex loại bỏ path traversal và ký tự đặc biệt, kiểm tra reserved names của Windows (CON, PRN...).
  - `test_gui_splitter_widgets()`: Kiểm tra bindings của GUI cutter và worker thread `CutterWorker`.
  - `test_transition_track_targeting()`: Kiểm thử chèn transition ngẫu nhiên hoặc chỉ định cụ thể cho track draft JSON.
  - `test_draft_lock_blocks_*`: Kiểm thử an toàn luồng tránh ghi đè dữ liệu khi CapCut đang chạy.
  - `temp_db`: Fixture tạo SQLite database cô lập.
  - `test_profile_version_rollback()` & `test_profile_import_export()`: Quản lý version và khôi phục DB.
- **Data Flow**: Đầu vào được tạo giả lập (Mock/Environment), chạy qua các validation và ghi vào các SQLite DB/JSON tạm thời, sau đó xác nhận qua assert.
- **Rủi ro & Ràng buộc**:
  - **Coupling cao với PySide6 GUI**: Nhiều test suite yêu cầu khởi tạo `QApplication` và `MainWindow`. Sẽ bị treo/lỗi trên các môi trường CI/CD không có display/framebuffer ảo.
  - **Dễ bị lỗi khi đổi giao diện**: Assertions dạng `hasattr(studio, "cutter_source_edit")` sẽ fail ngay nếu tên widget thay đổi, làm tăng độ nhạy cảm của test suite với sự thay đổi giao diện thuần túy.
  - **Ràng buộc hệ điều hành**: Logic kiểm thử reserved names chỉ chạy đúng trên Windows, gây lỗi nếu test trên Unix.
- **Khuyến nghị hành động tiếp theo**:
  - Tách biệt kiểm thử logic nghiệp vụ (business/controller logic) khỏi component giao diện (GUI).
  - Gắn nhãn (pytest markers) như `@pytest.mark.gui` để dễ dàng bỏ qua các test liên quan tới UI khi chạy tự động trên CI/CD.
  - Thay đổi đường dẫn tuyệt đối tĩnh (ví dụ `C:/logos/logo.png`) bằng đường dẫn tương đối.

### 9. Agent I — Orchestration & Sync
- **Tệp nguồn đã phân tích**:
  - `app/gui.py` (Dòng 1 đến 2119)
  - `app/pipeline.py` (Dòng 1 đến 446)
  - `app/preflight.py` (Dòng 1 đến 350)
  - `app/queue_manager.py` (Dòng 1 đến 639)
  - `app/controllers/profile_controller.py` (Dòng 1 đến 300)
  - `profiles/manager.py` (Dòng 1 đến 200)
  - `core/db.py` (Dòng 30 đến 80)
- **Nhiệm vụ chính**: Phân tích luồng điều phối chính (Orchestration flow) thông qua mô hình MVC/MVVM của PySide6, đồng bộ hóa trạng thái SQLite database, quản lý lifecycle cấu hình giữa giao diện và các luồng Thread phụ.
- **Các Symbol / Chức năng quan trọng**:
  - `MainWindow` (`gui.py`): Điều phối chính, kết nối thay đổi cấu hình đầu vào, kích hoạt preflight check.
  - `PipelineRunner.run_all()`: Quản lý chạy pipeline qua 5 giai đoạn (preflight -> scan -> plan -> write -> apply_effects) trên thread pool.
  - `BatchQueueManager`: Quản lý danh sách hàng đợi build dưới SQLite DB, cập nhật tiến độ công việc qua tín hiệu Qt.
- **Data Flow**: Thay đổi cấu hình đầu vào -> Preflight check tự động (debounced) -> Người dùng bấm "Dựng" -> Thêm vào SQLite `build_jobs` (status `pending`) -> Thread pool chạy `PipelineRunner.run_all()` -> Gửi tín hiệu cập nhật trạng thái/tiến độ về UI -> Lưu lịch sử build.
- **Rủi ro & Các Lỗi Logic Nghiêm Trọng Phát Hiện**:
  - **Lỗi profile không bao giờ lưu vào DB**: Nút bấm `btn_save_profile` được dùng để chạy build chứ không phải lưu profile. Thay đổi cài đặt của người dùng trên UI chỉ lưu vào `config.json` tạm, khi đổi profile hoặc khởi động lại sẽ bị database ghi đè mất.
  - **Lỗi nhân bản profile (Clone)**: `ProfileManager.clone_profile` hoàn toàn bỏ sót các trường chroma (`logo_opacity`, `chroma_enabled`, `chroma_mode`, `chroma_threshold`, v.v.) và karaoke, khiến các cấu hình này bị đưa về giá trị mặc định khi clone profile.
  - **Lỗi khôi phục hàng đợi build**: `BatchQueueManager._load_jobs_from_db` bỏ quên các trường tùy biến phụ đề (font size, color, bold, outline, shadow) khi khôi phục `ProjectConfig` từ JSON trong SQLite DB.
  - **Lỗi chớp tắt nút (Flickering)**: Nút Dựng nhanh bị disable ngay khi người dùng nhấn phím và chỉ enable lại sau khi preflight check hoàn thành (500ms), gây cảm giác giật và chớp tắt khó chịu khi nhập liệu.
- **Khuyến nghị hành động**:
  - Tự động gọi `_save_current_profile()` trước khi tải profile mới hoặc bổ sung nút "Lưu cấu hình" rõ ràng.
  - Đồng bộ đầy đủ các cột chroma key và karaoke trong hàm `clone_profile()` của `ProfileManager`.
  - Bổ sung cấu hình style phụ đề đầy đủ khi dựng lại `ProjectConfig` từ hàng đợi cơ sở dữ liệu.
  - Không disable nút build khi đang gõ phím; thay vào đó hiển thị biểu tượng trạng thái "đang kiểm tra" và chỉ thực thi validate thật khi click nút.

---

### 10. Agent J — Tổng hợp & Kế hoạch cuối (Synthesis & Final Plan)
- **Bản đồ Module (Module Map)**:
  - **GUI / Presentation Layer**: `app/gui.py`, `app/widgets/*.py` (Dashboard, Setup, Media Studio, Effects, History, Build). Điều phối visual bởi `app/theme.py` (QSS).
  - **Orchestration / Pipeline Layer**: `app/pipeline.py` (`PipelineRunner`), `app/preflight.py` (`run_preflight`), `app/queue_manager.py` (`BatchQueueManager`).
  - **Controllers & Managers**: `app/controllers/profile_controller.py`, `profiles/manager.py`, `assets/manager.py`.
  - **Domain Logic / Engines**: `capcut_draft_creator.py`, `capcut_keyframe_tool.py`, `video_mixer.py`, `media_probe.py`, `draft_doctor.py`.
  - **Core Utilities**: `core/db.py`, `core/path_validation.py`, `core/chroma.py`, `core/downloader/downloader.py`, `core/cutter/cutter.py`, `app/draft_lock.py`, `app/draft_cleanup.py`.

- **Danh sách việc cần làm theo thứ tự ưu tiên (Prioritized Todo List)**:
  1. **[ƯU TIÊN CAO] Sửa Lỗi Đồng Bộ Trạng Thái & Khôi Phục (Bugs Giao Nhau từ Agent I)**:
     - Sửa lỗi profile không lưu: Thực hiện tự động gọi `_save_current_profile()` trước khi đổi profile hoặc thêm menu "Lưu profile".
     - Sửa lỗi `clone_profile()`: Bổ sung sao chép đầy đủ cấu hình chroma key và karaoke.
     - Sửa lỗi khôi phục Queue: Cập nhật `_load_jobs_from_db` để nạp đủ cấu hình font/style phụ đề.
     - Sửa lỗi chớp tắt nút build khi gõ phím (không disable nút, chỉ hiển thị loader).
  2. **[ƯU TIÊN CAO] Tái cấu trúc theme toàn cục và chuẩn hóa màu (Theme Alignment từ Agent F)**:
     - Chuyển `theme.py` thành Singleton/Manager cung cấp cả QSS và QColor/QFont cho QPainter.
     - Thay thế toàn bộ hex màu hardcode (`#0dd3ba` Teal, `#18181b` Zinc, v.v.) trong các file widgets bằng hằng số từ `theme.py`.
  3. **[ƯU TIÊN TRUNG BÌNH] Redesign giao diện chính (Widgets A, B, D, E)**:
     - **Dashboard**: Thiết kế dạng Card Grid nằm ngang, lưới tóm tắt 2x4, nút thao tác click lớn, logs console kéo rộng đáy.
     - **Setup**: Bổ sung nút lưu/clone trên header; hai waveform giọng đọc + nhạc nền song song; cảnh báo thời gian phụ đề ở footer.
     - **Media Studio**: Thiết kế grid card có badge thời lượng và viền xanh Teal khi hover. Chuyển quét directory sang QThread. Bảng downloader queue chia URL riêng lẻ kèm nút Hủy.
     - **History & Doctor**: Thay bảng table thô cứng bằng List row phẳng (dự án + thời gian) kèm icon phục hồi/thùng rác. Thêm badge vấn đề ở Doctor.
  4. **[ƯU TIÊN THẤP] Tích hợp tính năng & Cải thiện UX nâng cao**:
     - Embed video player nội bộ (`QMediaPlayer` + `QVideoWidget`) trong preview của Media Studio.
     - Hiển thị dung lượng đĩa còn lại trên Build Center.
     - Đồng nhất format log (Cutter/Downloader) trong Build console.
     - Thêm nút xóa backup đơn lẻ (đồng bộ ổ đĩa + SQLite).

- **Đề xuất Sub-task Triển khai Thật (Proposed Phases)**:
  - **Giai đoạn 1: Core Clean & Sync (2 ngày)**
    - Fix 4 bug logic của Agent I.
    - Tập trung dọn dẹp theme, chuyển hex màu về `theme.py`, hoàn thiện dynamic style manager.
  - **Giai đoạn 2: Trọng tâm UI/UX Redesign (3 ngày)**
    - Thay thế QTableWidget thành Custom List Rows cho Backup & Doctor.
    - Cập nhật layout Dashboard, Setup, Media Studio card grids.
    - Thiết kế giao diện Glassmorphism giả lập bằng QSS và DropShadows.
  - **Giai đoạn 3: Tính năng & Tối ưu (2 ngày)**
    - Chuyển logic quét warnings sang Thread phụ.
    - Tải/cắt tiến độ phần trăm chính xác.
    - Trình phát video preview nội bộ.

- **Bước kế tiếp cho Impact Analysis / Edit (Next Steps)**:
  - Trước khi sửa bất kỳ tệp tin nào (đặc biệt là `profiles/manager.py` hoặc `app/gui.py`), **BẮT BUỘC** chạy lệnh `impact({target: "symbolName", direction: "upstream"})` cho các symbol chính (ví dụ: `clone_profile`, `_load_jobs_from_db`, `_save_current_profile`) để xem tầm ảnh hưởng chéo.
  - Chạy test suite `pytest tests` để lấy baseline kiểm thử trước khi tiến hành code.

---

*Tài liệu này đã hoàn tất tổng hợp phân tích.*


Tôi đã hoàn tất việc chạy song song toàn bộ 10 subtask phân rã phân tích (chuẩn bị chung, các Agent từ A tới I và tổng hợp J).

Kết quả phân tích chi tiết của từng Agent bao gồm các tệp nguồn, trách nhiệm, data flow, rủi ro và các đề xuất chỉnh sửa cụ thể đã được tổng hợp đầy đủ thành một tài liệu báo cáo phân tích duy nhất tại: 👉 
analysis_report.md

Quyết định cần bạn xác nhận trước khi sửa code:
Dựa trên kết quả phân tích tổng hợp (đặc biệt là 4 lỗi logic đồng bộ nghiêm trọng phát hiện bởi Agent I và các đề xuất tối ưu từ Agent A, B, F), tôi đề xuất 2 phương án triển khai nâng cấp để bạn lựa chọn:

Phương án A: Thực hiện làm giống hệt giao diện và chức năng của dự án mẫu (Vortex Studio) mà không sửa đổi các cơ chế ngầm hiện có.
Phương án B (Khuyến nghị): Lấy dự án mẫu làm nền tảng trực quan (Redesign UI theo phong cách hiện đại/glassmorphism), đồng thời tiến hành tối ưu:
Sửa triệt để 4 lỗi logic đồng bộ: Lỗi không lưu Profile vào DB, lỗi mất trường chroma khi clone Profile, lỗi mất cấu hình phụ đề khi khôi phục Queue, và lỗi giật chớp nút Build khi gõ phím.
Tăng trải nghiệm phản hồi (UX): Chuyển toàn bộ các hàm quét thư mục đồng bộ đang gây đơ UI (ở tab Media Studio) sang luồng phụ (QThread).
Tách biệt thiết kế: Tái cấu trúc theme.py thành bộ quản lý tập trung và loại bỏ toàn bộ mã màu hardcode chéo tệp.
Bạn mong muốn chúng ta sẽ triển khai theo Phương án A hay Phương án B (Khuyến nghị)? Sau khi bạn xác nhận phương án và kế hoạch, tôi sẽ tạo tệp task.md và bắt đầu chỉnh sửa mã nguồn cho giai đoạn đầu tiên.