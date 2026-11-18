# Bóc tách lắp ráp khung sofa – bộ bản vẽ A4 tự động

```bash
pip install ezdxf shapely openpyxl matplotlib
python make_a4.py                        # xuất toàn bộ + tự kiểm tra, chấm điểm
python make_a4.py --params my_sofa.json  # kích thước thật (chỉ ghi khoá cần đổi)
```
Kết quả: `output/A4/*.dxf` (mỗi trang 1 file A4), `output/SF_A4_BO-BAN-VE.pdf`, `output/SF_BOM.xlsx`,
`output/TU-KIEM-TRA.md` (điểm /10). Tiến độ làm việc: `CHECKLIST.md`.

## Bộ trang (43 trang với tham số mẫu)
| Trang | Nội dung |
|---|---|
| 01 | Tổng thể: 3 hình chiếu KHÔNG nét khuất + hướng nhìn phụ từ phía sau |
| 02 | Hình bung tổng (nhãn cụm, sắt đỏ); tự thêm hướng nhìn phụ nếu có cụm bị che |
| 03–04 | 5 bước lắp, mỗi bước kèm danh sách phụ kiện + chiều dài bulông |
| 05–06 | BOM theo mã (vật liệu theo quy tắc ván ép/LVL) |
| 07 | Phụ kiện, **quy tắc bulông theo ván**, tổng hợp vật liệu, ký hiệu lỗ |
| 08 | **Vị trí pát sắt – khoanh vùng** (vòng đỏ + ký hiệu A/B/C) |
| 09–11 | **Chi tiết A/B/C phóng to 1:2**: vùng gỗ quanh pát, dim định vị, đánh số chỗ bắn, bảng phụ kiện, cách lắp |
| 12–17 | **Mỗi cụm 1 trang** (có khoanh vùng pát): hình bung lớn, KT bao, bảng kê, phụ kiện, hướng dẫn |
| 18–43 | Mỗi chi tiết gỗ 1 trang: biên dạng, **góc vát**, dim tổng, dim vị trí lỗ, Ø, bảng toạ độ, ký hiệu biến thể |

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
