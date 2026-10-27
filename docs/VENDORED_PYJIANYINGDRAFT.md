# Quản Trị Mã Nguồn Nhúng `pyJianYingDraft` (Vendored Code Governance)

Tài liệu này ghi nhận nguồn gốc xuất xứ, danh sách bản vá (patchset) và quy trình duy trì thư viện `pyJianYingDraft` được nhúng trực tiếp trong dự án **CapCut Long Story Studio**.

---

## 1. Nguồn Gốc Xuất Xứ (Upstream Provenance)

*   **Tên dự án gốc:** `pyJianYingDraft`
*   **Tác giả:** Gary Guan (Guan Yixuan)
*   **Kho mã nguồn upstream:** [https://github.com/GuanYixuan/pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft)
*   **Giấy phép bản quyền:** **Apache License 2.0** (cho phép nhúng, phân phối và sửa đổi mã nguồn kèm điều kiện ghi nhận thay đổi theo Điều 4(b)).
*   **Phiên bản mốc (Baseline Version):** Nhánh **v0.2.x** (~tháng 06/2024).
*   **Quy mô mã nguồn:** ~20.200 dòng mã Python (bao gồm metadata, animation, keyframe, và các template JSON).

---

## 2. Danh Sách Bản Vá Cục Bộ (Local Patchset)

Dự án đã áp dụng 4 bản vá kỹ thuật cục bộ nhằm tối ưu hiệu năng, bảo mật và tương thích với CapCut Long Story Studio:

### Patch 1: Bảo vệ chống Path Traversal (`pyJianYingDraft/draft_folder.py`)
*   **Mục tiêu:** Ngăn chặn lỗ hổng Directory Traversal khi người dùng đặt tên dự án chứa ký tự đặc biệt (ví dụ: `../../system32`).
*   **Thực thi:** Gọi hàm thẩm định `core.path_validation.validate_project_name()` trước khi resolve đường dẫn tệp nháp.
*   **Trạng thái:** Đã dọn dẹp import lên module scope theo chuẩn PEP 8.

### Patch 2: Tối ưu hóa tuần tự hóa JSON và tra cứu Material (`pyJianYingDraft/script_file.py`)
*   **Mục tiêu:** Giảm thời gian serialize timeline từ hàng chục giây xuống dưới 1 giây.
*   **Thực thi:**
    1. Tích hợp thư viện siêu tốc `orjson` (Rust C-binding) với cơ chế fallback an toàn sang `json` tiêu chuẩn.
    2. Chuyển đổi cơ chế kiểm tra trùng lặp material từ danh sách tuyến tính $O(N)$ sang tập hợp `set` $O(1)$.
    3. Loại bỏ bước mã hóa kép không cần thiết trong phương thức `save()`.

### Patch 3: Thuật toán thêm phân đoạn Fast-Path $O(1)$ (`pyJianYingDraft/track.py`)
*   **Mục tiêu:** Tránh việc duyệt toàn bộ mảng track segments $O(N)$ mỗi khi thêm clip mới trong quy trình dựng video dài (> 3.000 clip).
*   **Thực thi:** Kiểm tra thời điểm bắt đầu của segment mới. Nếu lớn hơn hoặc bằng phân đoạn cuối cùng (`start >= last_segment.target_timerange.start`), chèn trực tiếp vào đuôi danh sách với độ phức tạp $O(1)$.

### Patch 4: Khử phụ thuộc vòng (Decoupling)
*   **Mục tiêu:** Loại bỏ các import tréo giữa `pyJianYingDraft` và tầng giao diện `app`.
*   **Thực thi:** Toàn bộ phụ thuộc chỉ hướng về `core.path_validation` (stdlib-only).

---

## 3. Quy Trình Ứng Phó Khi CapCut Desktop Cập Nhật (Schema Drift Strategy)

Khi ByteDance phát hành phiên bản CapCut mới (ví dụ v5.x hoặc v6.x) làm thay đổi cấu trúc `draft_content.json`:

1. **Kiểm tra tương thích ngược:**
   - Tạo một dự án mẫu bằng CapCut mới.
   - So sánh file `draft_content.json` mới với template tại `pyJianYingDraft/assets/draft_content_template.json`.
2. **Theo dõi Upstream:**
   - Kiểm tra các bản phát hành mới tại [GuanYixuan/pyJianYingDraft Releases](https://github.com/GuanYixuan/pyJianYingDraft/releases).
   - Bản v0.3.0 của upstream dự kiến sẽ hỗ trợ định dạng nháp phi JSON (non-JSON draft format) và cấu trúc track mới.
3. **Quy trình hòa nhập (Merge/Rebase):**
   - Không ghi đè trực tiếp toàn bộ thư mục.
   - Áp dụng lại 4 bản vá (Patch 1, 2, 3, 4) vào mã nguồn mới của upstream.
   - Chạy toàn bộ bộ test `python -m pytest -q tests` để đảm bảo không gãy pipeline.
