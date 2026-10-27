# Review Status Current

Tai lieu nay la trang thai review hien tai. Cac handoff/backlog cu da duoc dua vao `docs/archive/` de tranh AI doc nham task cu la task dang mo.

## Da xac minh on dinh

### 1. Draft folder path safety

- File chinh: `pyJianYingDraft/draft_folder.py`, `core/path_validation.py`.
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

- File chinh: `core/downloader/downloader.py` (908 dong). **Luu y:** `app/downloader.py` chi la shim 31 dong re-export, khong con logic. Truoc 2026-08-07 muc nay ghi sai file, nen ket luan bao mat da tung duoc xac minh tren file khong co code.
- Xac minh lai tren file that ngay 2026-08-07:
  - Khong co `shell=True`, `os.system`, `os.popen`. Ca 3 cho spawn process deu dung argv list.
  - `_validate_url` chan ky tu dieu khien, metachar `;` `|` `` ` `` `$`, va chi cho `http`/`https` co netloc.
  - Moi duong vao URL deu di qua no: `parse_url_list`, `build_ytdlp_command`, `build_gallerydl_command`, `YtDlpDownloadRunner.run`, va `ydl.download` o library mode.
  - Cookie/archive path qua `_validate_optional_file` (resolve + bat buoc ton tai). Output dir qua `_prepare_output_dir`.
  - Khong log nao dump argv, nen duong dan cookie khong lo ra progress hay job history.
- Da sua trong dot audit: `build_gallerydl_command` append `url` tho trong khi `build_ytdlp_command` append `_validate_url(url)`. Khong khai thac duoc (runner da validate ca list o `:278` truoc khi goi builder o `:514`), nhung la bat doi xung phong thu. Gio ca hai builder deu validate tai cho.

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
- Xac minh 2026-08-07: `98/98` test pass trong 11.95s, `compileall` pass, `main.py --diagnose-json` bao `ok: true`.

### 9. Queue mutex deadlock (fix 2026-08-07)

- File chinh: `app/queue_manager.py :: BatchQueueManager`.
- `_finish_current_job()` goi tiep `_run_next_job()` de chay job ke tiep, nhung `_run_next_job()` lay `QMutexLocker(self._mutex)`. `QMutex` khong reentrant, nen khi mot job ket thuc dong bo tren cung thread thi khoa bi vao lai va treo vinh vien.
- Trieu chung: `python -m pytest -q tests` treo vo han (khong output). Test lo ra loi nay la `tests/test_build_queue.py::test_queue_run_next_logic`, vi no mock `QThread.start` de chay dong bo.
- Fix: doi sang `QRecursiveMutex`. Them `timeout = 120` vao `pytest.ini` de mot deadlock khong the treo ca suite.
- Anh huong that: bug nay khong chi o test. Bat ky job nao that bai/hoan thanh dong bo trong queue that cung se treo queue.

## Ket qua xac minh moi nhat

- **Manual UI smoke**: Pass phần lớn, ngoại trừ lỗi zombie process (A4). Đã fix bằng cách force terminate QThread khi đóng ứng dụng. Hiện tại PASS toàn bộ.
- **Pipeline success nho**: Tao draft qua Python PASS, parse JSON thanh cong.
- **CapCut compact compatibility**: BLOCKED_EXTERNAL (Da copy JSON vao `Projects` nhung can CapCut PC that de mo va xac minh).
- **Real ffprobe benchmark**: BLOCKED_EXTERNAL (Thieu 5-10 media hop le tu nguoi dung).
- **Regression suite**: 98/98 PASS trong 11.95s, compileall OK (xac minh 2026-08-07). Truoc do full suite khong the chay den cuoi vi deadlock o muc 9.

## Viec con nen lam (De dat 10/10)

1. **Mo CapCut PC That**
   - Kiem tra lai 2 file draft (pretty va compact) trong UI CapCut de xem media, subtitle, transition co duoc render dung khong.

2. **Cung cap Media that cho Benchmark**
   - Dat `CAPCUT_BENCHMARK_MEDIA_DIR` toi thu muc 5-10 media hop le (khong phai file tu tao) va chay lai `scratch\benchmark_perf_baseline.py`.

3. **Docs hygiene**
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
