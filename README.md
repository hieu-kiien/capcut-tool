# CapCut Long Story Studio

Ứng dụng desktop Windows tự động dựng timeline CapCut cho video kể chuyện dài.

Bạn đưa vào giọng đọc, phụ đề SRT và một thư mục media nền. App tạo ra một dự án nháp CapCut hoàn chỉnh — đã lắp voice, phụ đề, video nền phân bổ theo thời lượng, keyframe zoom/pan, chuyển cảnh, logo và nhạc nền — để bạn mở trực tiếp trong CapCut PC và render.

App **không render video**. Nó chỉ dựng draft, nên chạy nhanh và không tốn CPU/GPU cho encode.

## Dùng cho ai

Người làm video truyện dài (YouTube, TikTok, Shorts) đã có sẵn giọng đọc và phụ đề, muốn bỏ khâu lắp timeline thủ công cho dự án dài 1–3 tiếng.

## Yêu cầu

- Windows 10 hoặc mới hơn
- Python 3.11
- CapCut PC (JianyingPro) đã cài
- FFmpeg + FFprobe — đã kèm trong `tools/`, hoặc tự cài vào PATH

## Cài đặt

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Kiểm tra môi trường trước khi chạy:

```powershell
python main.py --diagnose
```

Lệnh này báo `RESULT: READY` nếu đủ điều kiện. Nếu thiếu FFmpeg hoặc thư mục dữ liệu không ghi được, nó nói rõ thiếu gì.

## Chạy

```powershell
python main.py
```

Các cờ dòng lệnh khác:

| Cờ | Tác dụng |
|---|---|
| `--diagnose` | Kiểm tra môi trường, in dạng người đọc |
| `--diagnose-json` | Kiểm tra môi trường, in JSON (dùng cho CI) |
| `--version` | In phiên bản |

App chỉ cho chạy một tiến trình tại một thời điểm, để hai bản không cùng sửa một draft.

## Quy trình dùng

Tab **Dựng Timeline Tự Động**:

1. Đặt tên dự án nháp và chọn Draft Root (thư mục dự án CapCut của bạn).
2. Chọn tệp giọng đọc, thư mục media nền. Nhạc nền và SRT là tùy chọn.
3. Chọn tỷ lệ khung hình (9:16 hoặc 16:9), độ dài clip nền, cách trộn.
4. Bật keyframe/chuyển cảnh tự động nếu muốn.
5. Chạy. Cột phải hiện tiến trình 4 bước và log chi tiết.

Tab **Keyframe & Chuyển Cảnh** dùng để biên tập hiệu ứng cho dự án đã có: preset zoom/pan, keyframe tự chọn, chuyển cảnh, đổi tốc độ, và sửa lỗi dự án tự động.

Mỗi lần ghi đè dự án đều tạo bản sao lưu `.bak` khôi phục được.

## Build EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\build_mvp.ps1
```

Kết quả ở `dist\CapCutLongStoryStudio\CapCutLongStoryStudio.exe`.

Script này tự tạo venv, cài dependency, chạy `--diagnose`, `compileall`, test suite, rồi đóng gói bằng `capcut_mvp.spec`. Thêm `-SkipTests` để bỏ bước test.

Quy trình phát hành đầy đủ, gồm cả kiểm thử thủ công bắt buộc, xem [`docs/MVP_RELEASE_GUIDE.md`](docs/MVP_RELEASE_GUIDE.md).

## Phát triển

```powershell
pip install -r requirements-dev.txt

python -m pytest -q tests
python -m compileall app core pyJianYingDraft mvp_runtime main.py capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py -q
```

Hiện: 98 test, chạy khoảng 12 giây.

### Kiến trúc

Bốn tầng, từ trên xuống:

| Tầng | Vị trí | Việc |
|---|---|---|
| Giao diện | `app/gui.py`, `app/widgets/` | PySide6, worker thread để UI không đóng băng |
| Điều phối | `app/pipeline.py`, `app/queue_manager.py` | Chạy tuần tự các bước, log, hủy giữa chừng |
| Nghiệp vụ | `core/`, `video_mixer.py`, `media_probe.py` | Quét media, phân bổ clip, chroma-key, tải media |
| Ghi draft | `pyJianYingDraft/`, `capcut_draft_creator.py` | Ghi JSON dự án CapCut |

Pipeline dựng draft chạy 4 bước: preflight → quét media → phân bổ clip → ghi draft, rồi tùy chọn chèn keyframe/transition.

Chi tiết module xem [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md).

### Tài liệu

| File | Nội dung |
|---|---|
| [`docs/README.md`](docs/README.md) | Chỉ mục tài liệu |
| [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) | Tóm tắt nhanh, điểm vào, trạng thái |
| [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) | Kiến trúc, module, luồng dữ liệu |
| [`docs/CODE_AUDIT.md`](docs/CODE_AUDIT.md) | Audit code theo mức nghiêm trọng |
| [`docs/BACKLOG.md`](docs/BACKLOG.md) | Việc còn mở |
| [`docs/MVP_RELEASE_GUIDE.md`](docs/MVP_RELEASE_GUIDE.md) | Quy trình phát hành |
| [`docs/AGENT_CONTEXT.md`](docs/AGENT_CONTEXT.md) | Hướng dẫn cho AI agent làm việc trên repo |

### Nhánh thử nghiệm Tauri/Rust

`src-tauri/` và `src/` là nhánh R&D, **không nằm trong bản phát hành**. Runtime phát hành là Python/PySide6. Trạng thái và điều kiện để nhánh này được cân nhắc phát hành: [`PROJECT.md`](PROJECT.md).

## Giấy phép

Dự án chưa chọn giấy phép.

Phần mềm bên thứ ba đi kèm được ghi trong [`NOTICE`](NOTICE):

- **pyJianYingDraft** (`pyJianYingDraft/`) — Apache-2.0, Copyright 2024 Gary Guan. Có sửa đổi cục bộ, ghi rõ trong `NOTICE`.
- **FFmpeg** (`tools/ffmpeg/`) — bản bundled là **GPL v3**. Việc này ràng buộc thật đến cách phân phối app; xem `NOTICE` và [`docs/OPEN_SOURCE_DECISIONS.md`](docs/OPEN_SOURCE_DECISIONS.md) trước khi phát hành.
