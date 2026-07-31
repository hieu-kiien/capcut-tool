# Project Context Quick Start

## Muc tieu

Repo nay la app desktop PySide6 de tao draft CapCut cho video ke chuyen dai. App khong render video cuoi; no chuan bi draft gom voice, phu de SRT, media nen, logo/overlay, keyframe, transition va cac buoc repair/preflight de nguoi dung mo CapCut kiem tra va render.

## Diem vao chinh

- `main.py`: chay ung dung PySide6.
- `app/gui.py`: giao dien, worker thread, nut chay pipeline, log/progress.
- `app/pipeline.py`: wrapper quy trinh tao draft.
- `app/presets.py`: preset keyframe/transition va cau hinh mac dinh.
- `app/path_validation.py`: validate ten project/path de tranh path traversal.

## Backend quan trong

- `capcut_draft_creator.py`: tao draft CapCut tu input media/audio/subtitle.
- `pyJianYingDraft/draft_folder.py`: thao tac thu muc draft/template.
- `capcut_keyframe_tool.py`: chen keyframe, speed, scale, transition vao JSON draft.
- `media_probe.py`: do duration/resolution media bang ffprobe hoac fallback.
- `video_mixer.py`: lap plan media nen theo do dai voice/SRT.
- `draft_doctor.py`: kiem tra va sua loi draft.
- `runtime_tools.py`: dinh vi FFmpeg/FFprobe portable.

## Trang thai hien tai

Da xac minh trong code/test gan day:

- `DraftFolder` da dung helper validate path cho cac thao tac draft quan trong, giam rui ro path traversal.
- `media_probe.py` tra loi timeout ffprobe truc tiep va khong fallback sang `pymediainfo` trong case timeout.
- `capcut_keyframe_tool.py` mac dinh chi chen transition vao track `long_story_background`; fallback primary track la opt-in.
- Downloader dung URL validation va command argv list.
- Media probe cache co gioi han, invalidation theo path/size/mtime, validate kich thuoc va chia se mot probe dang chay giua cac thread cung doc mot file.
- Export compact JSON la opt-in; luong tao draft mac dinh van ghi pretty JSON de giu tuong thich nguoc.
- `ScanWorker` nhan interruption; close flow doi scan/import/download/cutter worker dung sach va tu choi dong neu worker chua dung.
- Full suite `90/90` test va `compileall` da pass ngay 2026-06-22 (trong 10.34s).
- Benchmark 5 gio/600 media/3600 segment da co warm-up va 5 vong do: draft cached median 3.847 giay, uncached 4.210 giay; compact serialization median 0.776 giay, pretty 0.905 giay.

Con nen lam truoc khi goi la 10/10:

1. **Mo CapCut PC That**: Mo thu draft compact va pretty trong CapCut that (B3, B4). UI smoke test via Python da PASS hoan toan nhung thieu xac minh truc quan.
2. **Benchmark ffprobe that**: Cung cap 5-10 media hop le qua `CAPCUT_BENCHMARK_MEDIA_DIR` de do CPU that (Hien dang BLOCKED_EXTERNAL).
3. Chi package EXE khi user yeu cau artifact phan phoi.

*Ghi chu: Regression test 86/86 PASS. UI Smoke phát hiện một lỗi zombie process khi đóng app có worker nền (A4), đã được fix bằng cách force terminate QThread. Các case khác (A1-A3, A5) PASS.*

## Kiem tra nhanh

Chay cac lenh nho truoc khi nghi den build/package:

```powershell
python tests\test_new_features.py
python tests\test_pipeline.py
python -m compileall app pyJianYingDraft capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py tests -q
```

Neu `pytest` co san:

```powershell
python -m pytest -q tests
```

Benchmark lap lai:

```powershell
python scratch\benchmark_perf_baseline.py
$env:CAPCUT_BENCHMARK_MEDIA_DIR = "D:\media-mau"
python scratch\benchmark_perf_baseline.py
```

## Nguyen tac doc repo

- Khong quet toan repo khi chi can mot tac vu cu the.
- Bat dau tu file trong muc "Diem vao chinh", "Backend quan trong", hoac file user nhac ten.
- Loai tru `build`, `dist`, `obfuscated`, `tools`, `output`, `downloads`, cache va virtualenv khi search.
- Full packaging chi nen chay khi user can EXE/distributable.
- Cac file trong `docs/archive/` la lich su; khong doc mac dinh va khong coi la trang thai hien tai.
