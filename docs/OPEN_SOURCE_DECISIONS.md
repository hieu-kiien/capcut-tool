# Open Source Reference Decisions

## Pham vi dot trien khai nay

- Khong tich hop AI scene pipeline.
- Khong tich hop API/MCP hoac cong dieu khien ben ngoai.
- Khong lam sandbox so sanh `pyCapCut`.
- Khong thay loi draft hien tai.

## Quyet dinh ky thuat

App tiep tuc giu loi tao draft hien tai:

- `capcut_draft_creator.py`
- vendored `pyJianYingDraft`
- cac lop an toan quanh pipeline, keyframe, backup, cleanup va downloader

Nhung repo ngoai duoc neu trong trao doi chi dung lam nguon tham khao ve y tuong va hanh vi co the hoc hoi. Khong copy code tu repo co license/chinh sach chua ro, va khong dua chung thanh dependency runtime trong dot nay.

## Trang thai license (xac minh 2026-08-07)

Truoc ngay nay repo khong co `NOTICE` va khong ghi nguon cho code vendor. Da bo sung `NOTICE` o thu muc goc. Ket qua tra cuu:

### 1. pyJianYingDraft — Apache-2.0, khong co van de

- Upstream: https://github.com/GuanYixuan/pyJianYingDraft
- License: Apache License 2.0, `Copyright 2024 Gary Guan`.
- Apache-2.0 cho phep dung trong san pham thuong mai va khong doi hoi mo source phan con lai. Yeu cau la giu attribution va ghi ro cho da sua — ca hai da nam trong `NOTICE`.
- Con thieu: **khong ghi lai version/commit upstream luc vendor**. Hien khong the diff voi upstream, nen khong the ap security fix mot cach chac chan. Nen truy va ghi lai.
- Da sua cuc bo 2 cho: `draft_folder.py` (goi `core.path_validation`) va `script_file.py` (compact JSON opt-in).

### 2. FFmpeg bundled — GPL v3, CAN XU LY TRUOC KHI PHAT HANH

`tools/ffmpeg/ffmpeg-8.1.1-essentials_build/LICENSE` la **GPL v3**, khong phai LGPL. Ban "essentials" cua Gyan.dev duoc build voi `--enable-gpl`.

GPL v3 la copyleft manh. Dong goi binary GPL trong installer la mot hanh vi phan phoi binary do, keo theo nghia vu rieng — bao gom cung cap source tuong ung. App goi `ffmpeg.exe` nhu tien trinh rieng (`runtime_tools.py`) nen tinh huong nhe hon linking, nhung viec **bundle** van la van de can giai quyet.

Ba huong xu ly (chi tiet trong `NOTICE`):

1. Doi sang ban FFmpeg build theo LGPL; hoac
2. Khong bundle FFmpeg, de user tu cai — `runtime_tools.py` da ho tro resolve tu PATH san; hoac
3. Xin review phap ly va tuan thu yeu cau source-availability cua GPL v3.

Day khong phai tu van phap ly. Neu du an huong den phat hanh thuong mai, nen chon huong 1 hoac 2 vi ca hai tranh han van de.

### 3. LICENSE cua du an — chua chon

Repo chua co `LICENSE`. Apache-2.0 cua pyJianYingDraft khong rang buoc lua chon nay. Quyet dinh dang cho user.

## Ly do

Uu tien thuc te la on dinh app desktop dang co:

- tranh hai tac vu ghi cung mot draft cung luc;
- don backup/partial an toan trong draft root;
- giam rui ro downloader treo hoac tai file qua lon;
- giu lich su job khong lo URL day du hoac duong dan cookies.

