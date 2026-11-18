# Bóc tách lắp ráp khung sofa – bộ bản vẽ A4 tự động

Sinh **toàn bộ bản vẽ khổ A4 ngang (297×210)**, mỗi trang 1 file DXF + 1 PDF gộp + BOM Excel.

## Chạy
```bash
pip install ezdxf shapely openpyxl matplotlib
python make_a4.py                        # tham số mẫu, góc chiếu 1 (TCVN/ISO-E)
python make_a4.py --params my_sofa.json  # kích thước thật (chỉ ghi khoá cần đổi)
python make_a4.py --projection third     # góc chiếu 3
```
Kết quả: `output/A4/SF-A4-xx_*.dxf`, `output/SF_A4_BO-BAN-VE.pdf`, `output/SF_BOM.xlsx`.

## Danh mục trang (39 trang với tham số mẫu)
| Trang | Nội dung |
|---|---|
| 01 | Tổng thể – 3 hình chiếu |
| 02 | Tổng thể – hình bung trục đo, nhãn cụm M1..M6, sắt tô đỏ |
| 03–04 | 5 bước lắp (cụm cũ xám, cụm mới màu, đường bung, phụ kiện) |
| 05 | Bảng kê chi tiết theo mã biến thể + vật liệu theo quy tắc |
| 06 | Phụ kiện, tổng hợp vật liệu (m³ LVL / ván ép, số chi tiết sắt), bảng ký hiệu lỗ |
| 07 | **Chi tiết sắt**: vị trí lắp trong khung ngồi, hình chiếu pát L & thanh gia cố, hướng dẫn lắp |
| 08–19 | Mỗi cụm 2 trang: hình chiếu (kích thước chuỗi) / hình bung + bảng kê + phụ kiện + vị trí cụm |
| 20–39 | Mỗi **biến thể chi tiết gỗ** 1 trang gia công: mặt A, cạnh C, 2 đầu E/F, ký hiệu lỗ, bảng toạ độ lỗ |

## Quy tắc
- **Vật liệu** (`sofa_model.material_of`): dày 3–18 mm = **ván ép**; dày ≥ 20 mm = **LVL**.
  Dày ngoài khoảng (vd 19 mm) ghi *CHƯA XÁC ĐỊNH*. Ngoại lệ khai trong `MATERIAL_OVERRIDE` (hiện: chân).
- **Biến thể** (`holes.py`): lỗ tính từ các điểm liên kết. Chi tiết cùng kích thước được xem là giống nhau
  khi mẫu lỗ trùng sau khi lật đầu/lật mặt (không tính đối xứng gương; lỗ xuyên không phân biệt mặt vào).
  Khác lỗ → mã có hậu tố **6A, 6B…**, số vị trí khung **vuông**, ghi chú *"cùng KT – khác lỗ"* ở BOM,
  tam giác cảnh báo đỏ + yêu cầu ghi mã lên mặt B ở trang gia công.
- **Hệ toạ độ lỗ**: X dọc chiều dài L, Y dọc rộng W, Z dọc dày T; gốc O góc dưới-trái mặt A.
  Mặt A/B = 2 mặt lớn, cạnh C/D, đầu E (X=0) / F (X=L).

## Cấu trúc code
- `sofa_model.py` – tham số, chi tiết (kể cả sắt nhiều khối), liên kết + phụ kiện, `HOLE_SPEC`, quy tắc vật liệu.
- `holes.py` – trích lỗ khoan, hệ toạ độ riêng chi tiết, tách biến thể.
- `make_a4.py` – **lệnh chính**, dựng tất cả trang A4, PDF, Excel.
- `make_drawing.py` – thư viện vẽ (khử nét khuất, đặt số vị trí, DXF setup).

> ⚠️ Kích thước, vị trí sắt và phụ kiện là **tham số mẫu** – đối chiếu mẫu thật trước khi sản xuất.
