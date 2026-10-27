# Chỉ mục tài liệu

Thư mục này là bộ nhớ ngắn gọn cho AI agent và người mới vào repo. Không cần đọc hết mọi file trong mỗi lần làm việc.

Người dùng cuối nên bắt đầu từ [`../README.md`](../README.md) ở thư mục gốc.

## Nên đọc trước

| File | Nội dung |
|---|---|
| [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) | Tóm tắt mục tiêu, module chính, trạng thái hiện tại, lệnh kiểm tra |
| [`REVIEW_STATUS_CURRENT.md`](REVIEW_STATUS_CURRENT.md) | Các mục kỹ thuật đã xác minh và việc còn mở |
| [`AGENT_CONTEXT.md`](AGENT_CONTEXT.md) | Quy tắc và guardrail cho AI agent làm việc trên repo này |

## Kiến trúc và trạng thái code

| File | Nội dung |
|---|---|
| [`PROJECT_MAP.md`](PROJECT_MAP.md) | Kiến trúc 4 tầng, danh sách module kèm LOC, cây thư mục, luồng dữ liệu |
| [`CODE_AUDIT.md`](CODE_AUDIT.md) | Audit code xếp theo mức nghiêm trọng: lỗi tiềm ẩn, bảo mật, hiệu năng, packaging, nợ kỹ thuật |
| [`BACKLOG.md`](BACKLOG.md) | Việc còn mở, xếp hạng Critical/High/Medium/Low |
| [`VORTEX_FUNCTIONAL_PARITY.md`](VORTEX_FUNCTIONAL_PARITY.md) | Ma trận parity giữa mockup giao diện và backend thật (Existing/Partial/Missing) |

## Phạm vi sản phẩm

| File | Nội dung |
|---|---|
| [`MVP_SPEC.md`](MVP_SPEC.md) | Đặc tả sản phẩm: người dùng, luồng UI, cấu trúc màn hình. Đọc khi thay đổi phạm vi |
| [`MVP_RESEARCH_REPORT.md`](MVP_RESEARCH_REPORT.md) | Quyết định kiến trúc cho bản MVP và 4 phát hiện kỹ thuật kèm bản vá |
| [`QUY_TRINH_VA_PHAN_BO_THOI_GIAN.md`](QUY_TRINH_VA_PHAN_BO_THOI_GIAN.md) | SOP sản xuất video và phân bổ thời lượng nội dung |

## Phát hành

| File | Nội dung |
|---|---|
| [`MVP_RELEASE_GUIDE.md`](MVP_RELEASE_GUIDE.md) | Quy trình phát hành, tiêu chí, kiểm thử thủ công bắt buộc |
| [`MVP_CHANGELOG.md`](MVP_CHANGELOG.md) | **Changelog bản phát hành.** Định nghĩa phiên bản dự án |
| [`CHANGELOG.md`](CHANGELOG.md) | Lịch sử kỹ thuật: fix, refactor, audit nội bộ. Không phải release note |
| [`OPEN_SOURCE_DECISIONS.md`](OPEN_SOURCE_DECISIONS.md) | Quyết định về repo tham khảo bên ngoài, và trạng thái license của code vendor |

## Phiên bản

Nguồn sự thật duy nhất là `mvp_runtime/__init__.py :: APP_VERSION` — giá trị mà `main.py --version` in ra. Hiện tại: `0.1.0-mvp`.

`package.json`, `src-tauri/Cargo.toml` và `src-tauri/tauri.conf.json` mang version riêng `0.0.1-experimental`; đó là nhánh R&D Tauri, không phải version dự án. Xem [`../PROJECT.md`](../PROJECT.md).

## Archive

[`archive/`](archive/) chứa handoff, backlog, review task và test note cũ. Chỉ đọc khi cần truy vết lịch sử. **Không dùng các file này làm trạng thái hiện tại.**

Đã archive: `HANDOFF_LONG_STORY_CAPCUT.md`, `REVIEW_FIX_TASKS.md`, `REVIEW_REMAINING_TASKS.md`, `PHASE_7_BACKLOG.md`, `DOWNLOADER_TEST_NOTES.md`.

## Ghi chú cho AI

- Giữ `AGENTS.md` ở thư mục gốc để Codex tự nhận quy tắc làm việc.
- Cần ngữ cảnh nhanh thì đọc `PROJECT_CONTEXT.md` trước khi dùng `rg`.
- Tìm source thì bắt đầu từ các file nêu trong `PROJECT_MAP.md` thay vì quét toàn repo.
- Loại trừ `build`, `dist`, `tools`, `node_modules`, `.git`, `__pycache__`, `scratch`, `.agents` khi search.
- Không build hoặc package trừ khi user cần EXE hoặc artifact phân phối.

### Quy ước tài liệu

- **Ngôn ngữ:** tiếng Việt có dấu cho tài liệu mới. Một số file cũ còn tiếng Anh hoặc tiếng Việt không dấu; chuyển dần khi sửa nội dung, không đổi riêng để đổi.
- **Trích dẫn code:** dùng tên symbol (`gui.py :: closeEvent`), không dùng số dòng. Số dòng trôi sau mỗi lần sửa code và đã từng làm tài liệu trỏ sai chỗ.
