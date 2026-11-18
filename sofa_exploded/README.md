# Bóc tách lắp ráp khung sofa – bản vẽ bung thông minh (Smart exploded assembly drawing)

Sinh **một bản vẽ A1 (DXF)** cho khung sofa, nhìn vào là hiểu cách lắp:

| Vùng bản vẽ | Nội dung |
|---|---|
| Trái trên | 3 hình chiếu vuông góc 1:10 (đứng / bằng / cạnh), **có nét khuất**, kích thước bao |
| Phải trên | **Hình bung trục đo tổng thể** – màu theo cụm, số vị trí bám viền, đường bung (chấm gạch) chỉ vị trí phụ kiện, nhãn lục giác A..F |
| Dưới | **5 bước lắp** (khung đáy → gác tay → khung ngồi → tựa lưng → chân): cụm đã lắp màu xám, cụm mới màu + mũi tên chiều lắp + hướng dẫn |
| Phải dưới | Bảng kê chi tiết, bảng phụ kiện (số lượng tự đếm từ liên kết), ghi chú, khung tên, ký hiệu phép chiếu |

## Chạy
```bash
pip install ezdxf shapely openpyxl matplotlib
python make_drawing.py                       # tham số mẫu, phép chiếu góc 1 (TCVN/ISO-E)
python make_drawing.py --params my_sofa.json # kích thước thật của bạn
python make_drawing.py --projection third    # phép chiếu góc 3
```
Kết quả trong `output/`: `sofa_frame_exploded.dxf` (mở bằng AutoCAD), `_BOM.xlsx` (VN/EN/CN, có công thức thể tích), `_preview.png/.pdf`.

`my_sofa.json` chỉ cần ghi các khoá muốn đổi, ví dụ: `{"W": 2200, "D": 950, "H_back": 850, "n_mid_rails": 4}`.
Toàn bộ khoá xem `PARAMS` trong `sofa_model.py`.

## Cấu tạo sofa (6 cụm)
| Cụm | Tên | Chi tiết |
|---|---|---|
| M1 | Khung đáy / Base frame | đà đáy trước, sau, giằng đầu, giằng giữa, ke góc |
| M2 | Khung ngồi / Seat frame | thanh trước/sau, thanh hông, nan ngồi — đặt trên khung đáy |
| M3, M4 | Gác tay trái/phải / Arms | trụ, thanh trên, giằng dưới, giằng giữa — bulông KD vào khung đáy |
| M5 | Tựa lưng / Back frame | thanh dưới, trên, thanh đứng — bulông vào trụ gác tay sau |
| M6 | Chân / Legs | 6 chân, bulông treo |

Trình tự lắp sửa trong `STEP_MODULES` (sofa_model.py).

## Cấu trúc
- `sofa_model.py` – mô hình tham số: chi tiết (hộp 3D), module M1..M5, liên kết + phụ kiện, vector bung, kiểm tra chồng chi tiết (interference).
- `make_drawing.py` – khử nét khuất (sắp độ sâu theo tia + trừ vùng che), đặt số vị trí, vẽ bảng, khung tên, xuất DXF/Excel/preview.

## Layer trong DXF
`1-NET-THAY`, `2-NET-KHUAT` (HIDDEN), `3-KICH-THUOC`, `4-DUONG-BUNG` (DASHDOT), `5-SO-VI-TRI`, `8-CUM-DA-LAP`, `9-MUI-TEN`, `10-PHU-KIEN`, `M-M1..M6-*` (màu theo cụm).
Khổ giấy vẽ trong Model ở tỉ lệ 1:10 (khung A1 phóng ×10, LTSCALE=10, DIMSCALE=10). Chữ dùng style `VN` (Arial – Unicode tiếng Việt).

> ⚠️ Kích thước mặc định là **mẫu minh hoạ**, không lấy từ bản vẽ thật. Đối chiếu mẫu sofa trước khi sản xuất.
