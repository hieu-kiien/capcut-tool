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

## Ly do

Uu tien thuc te la on dinh app desktop dang co:

- tranh hai tac vu ghi cung mot draft cung luc;
- don backup/partial an toan trong draft root;
- giam rui ro downloader treo hoac tai file qua lon;
- giu lich su job khong lo URL day du hoac duong dan cookies.

