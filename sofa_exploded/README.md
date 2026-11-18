# Bóc tách lắp ráp khung sofa – bộ bản vẽ A4 tự động

```bash
pip install ezdxf shapely openpyxl matplotlib
python make_a4.py                        # BỘ GỌN 5 trang A4 + tự kiểm tra
python make_a4.py --full                 # bộ đầy đủ (mỗi chi tiết 1 trang gia công)
python make_a4.py --params my_sofa.json  # kích thước thật
```
Kết quả: `output/A4/SF-01…05_*.dxf`, `output/SF_5TRANG_BAN-VE.pdf`, `output/SF_BOM.xlsx` (BOM + toạ độ lỗ khoan),
`output/TU-KIEM-TRA.md`.

## Bộ gọn 5 trang
| Trang | Nội dung |
|---|---|
| SF-01 Tổng thể | Hình chiếu KT bao, hình bung nhãn cụm + khoanh pát, trình tự lắp, tổng phụ kiện cả bộ |
| SF-02 Gác tay | Hình bung tay trái + phải, KT bao, bảng kê (vát 41°, khác lỗ), phụ kiện |
| SF-03 Tựa lưng | Hình bung + **chi tiết B** pát nối (khoanh vùng, dim, chỗ bắn) |
| SF-04 Khung ngồi | Hình bung + **chi tiết A** pát L góc + **chi tiết C** đầu thanh gia cố |
| SF-05 Khung đáy + chân | Hình bung, KT bao, bảng kê, phụ kiện |

## Quy tắc
- Vật liệu: dày 3–18 mm = ván ép, ≥ 20 mm = LVL.
- Bắt pát vào ván: lỗ Ø10 → ốc 4 chấu M8; lỗ Ø8 → ốc cấy M6; bulông dài theo ván 9→12, 12→16, 15→18, 18→21
  (`BOLT_LEN` trong `sofa_model.py`, tự tính theo độ dày ván nhận ốc).
- Chi tiết cùng kích thước khác lỗ → mã 6A/6B…, số vị trí khung vuông, tam giác đỏ + ghi khác biệt lỗ.

## Code
`geom.py` (lăng trụ, vát) · `sofa_model.py` (tham số, chi tiết, liên kết, quy tắc) · `holes.py` (lỗ, biến thể) ·
`render.py` (khử nét khuất, hướng nhìn phụ) · `make_a4.py` (dựng trang) · `selfcheck.py` (chấm điểm) ·
`make_drawing.py` (thư viện DXF).

> ⚠️ Kích thước, vị trí sắt, phụ kiện là **tham số mẫu** – đối chiếu mẫu thật trước khi sản xuất.
