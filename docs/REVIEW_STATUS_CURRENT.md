# Review Status Current

Tai lieu nay la trang thai review hien tai. Cac handoff/backlog cu da duoc dua vao `docs/archive/` de tranh AI doc nham task cu la task dang mo.

## Da xac minh on dinh

### 1. Draft folder path safety

- File chinh: `pyJianYingDraft/draft_folder.py`, `app/path_validation.py`.
- Cac thao tac draft quan trong da di qua helper validate project/draft name.
- `remove("../outside")` va `duplicate_as_template("template", "../outside")` duoc test de dam bao khong thao tac ngoai draft root.

### 2. Media probe timeout

- File chinh: `media_probe.py`.
- Khi ffprobe bi timeout, `probe_media()` tra ve loi timeout tu source `ffprobe` va khong fallback sang `pymediainfo`.
- Muc tieu la tranh treo app tren file loi, file khoa, hoac media nam tren storage cham.

### 3. Transition targeting

- File chinh: `capcut_keyframe_tool.py`.
- Mac dinh chi target track video ten `long_story_background`.
- Fallback sang primary video track chi chay khi co flag opt-in `transition_allow_primary_fallback=True`.
- Muc tieu la khong chen transition vao logo/overlay/animation track.

### 4. Downloader validation

- File chinh: `app/downloader.py`.
- URL input chi nhan `http`/`https`.
- Command cho `yt-dlp`/`gallery-dl` duoc build bang argv list, khong shell string.
- History/log can tiep tuc tranh luu ro URL/cookie nhay cam khi thay doi downloader.

### 5. Pipeline smoke

- `tests/test_pipeline.py` da chay duoc success path nho tao draft CapCut bang input tam.
- `tests/test_new_features.py` bao phu path traversal, media timeout, transition targeting, downloader validation, history va lock logic.

### 6. Media probe cache va concurrency

- File chinh: `media_probe.py`, `tests/test_media_probe.py`.
- Cache gioi han 1000 entry, invalidation khi size/mtime thay doi va khong luu timeout/loi tam thoi.
- Cac thread probe cung mot path chia se ket qua in-flight, tranh spawn ffprobe trung lap.
- API resize tu choi gia tri 0, am, bool va kieu khong phai so nguyen.

### 7. Compact JSON an toan

- File chinh: `pyJianYingDraft/script_file.py`, `capcut_draft_creator.py`, `tests/test_compact_json.py`.
- Pretty JSON van la mac dinh; compact chi bat bang tham so `compact=True`.
- Da test Unicode, dual-file, override, round-trip va mac dinh cua hai draft creator.
- Chua coi round-trip noi bo la bang chung CapCut that da tuong thich.

### 8. Worker shutdown va benchmark

- `ScanWorker` kiem tra ca cancel flag va `QThread.requestInterruption()`.
- Main window chi dong khi pipeline, scan va media-studio worker da dung trong timeout.
- Benchmark dung warm-up + 5 vong, bao median/min/max va tach mock call count khoi ffprobe that.
- Xac minh 2026-06-19: `85/85` test pass va `compileall` pass.

## Viec con nen lam

1. **Manual UI smoke**
   - Launch `python main.py`.
   - Kiem tra text tieng Viet, layout chinh, media scan, downloader recoverable failure, cancel/close worker, pipeline success nho.
   - Khong can package EXE cho den khi user can artifact.

2. **CapCut compact compatibility**
   - Tao cung mot draft o pretty va compact mode.
   - Mo trong CapCut, kiem tra media, voice, subtitle, transition va save lai.
   - Chi can nhac bat compact mac dinh sau khi smoke nay pass.

3. **Real ffprobe benchmark**
   - Dat `CAPCUT_BENCHMARK_MEDIA_DIR` toi thu muc 5-10 media hop le.
   - Khong suy dien CPU that tu benchmark subprocess mock.

4. **Docs hygiene**
   - Giu trang thai hien tai trong file nay va `PROJECT_CONTEXT.md`.
   - Neu tao handoff/review moi, dat vao `docs/archive/` khi khong con la nguon su that hien tai.

## Verification nen chay

```powershell
python tests\test_new_features.py
python tests\test_pipeline.py
python -m compileall app pyJianYingDraft capcut_draft_creator.py capcut_keyframe_tool.py media_probe.py tests -q
python scratch\benchmark_perf_baseline.py
```

Neu sua UI/worker:

```powershell
python main.py
```

Sau do test manual it nhat mot success path va mot recoverable failure path lien quan den thay doi.
