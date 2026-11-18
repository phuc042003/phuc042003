# Bóc tách lắp ráp khung sofa – bản vẽ bung thông minh (Smart exploded assembly drawing)

Sinh **một bản vẽ A1 (DXF)** cho khung sofa, nhìn vào là hiểu cách lắp:

| Vùng bản vẽ | Nội dung |
|---|---|
| Trái trên | 3 hình chiếu vuông góc 1:10 (đứng / bằng / cạnh), **có nét khuất**, kích thước bao |
| Phải trên | **Hình bung trục đo tổng thể** – màu theo cụm, số vị trí bám viền, đường bung (chấm gạch) chỉ vị trí phụ kiện, nhãn lục giác A..F |
| Dưới | **5 bước lắp** (khung đáy → gác tay → khung ngồi → tựa lưng → chân): cụm đã lắp màu xám, cụm mới màu + mũi tên chiều lắp + hướng dẫn |
| Phải dưới | Bảng kê chi tiết, bảng phụ kiện (số lượng tự đếm từ liên kết), ghi chú, khung tên, ký hiệu phép chiếu |

## Bộ bản vẽ xuất ra (mỗi cụm 1 bản vẽ)
| File | Nội dung |
|---|---|
| `SF-00_TONG-THE.dxf` (A1) | Tổng thể: hình chiếu, hình bung tổng, 5 bước lắp, BOM toàn bộ |
| `SF-01_M1_KHUNG-DAY.dxf` (A2) | Cụm khung đáy |
| `SF-02_M2_KHUNG-NGOI.dxf` (A2) | Cụm khung ngồi |
| `SF-03_M3_GAC-TAY-TRAI.dxf` (A2) | Cụm gác tay trái |
| `SF-04_M4_GAC-TAY-PHAI.dxf` (A2) | Cụm gác tay phải |
| `SF-05_M5_TUA-LUNG.dxf` (A2) | Cụm tựa lưng |
| `SF-06_M6_CHAN.dxf` (A2) | Cụm chân (+ chi tiết chân 1:2) |
| `SF_BO-BAN-VE.pdf` | Gộp 7 tờ để in / gửi |
| `SF_BOM.xlsx` | BOM VN/EN/CN + phụ kiện + tham số |

Mỗi bản vẽ cụm: 3 hình chiếu 1:10 có nét khuất + kích thước bao + kích thước chuỗi vị trí thanh;
hình bung cụm (số vị trí đồng bộ với SF-00, đường bung, nhãn phụ kiện); sơ đồ vị trí cụm trong sofa;
bảng kê chi tiết cụm; bảng phụ kiện ghi rõ *nội bộ cụm* hay *liên kết với cụm nào*; hướng dẫn lắp; khung tên.

## Chạy
```bash
pip install ezdxf shapely openpyxl matplotlib
python make_sheets.py                        # xuất cả bộ 7 tờ, tham số mẫu, góc chiếu 1 (TCVN/ISO-E)
python make_sheets.py --params my_sofa.json  # kích thước thật của bạn
python make_sheets.py --projection third     # phép chiếu góc 3
```
Kết quả trong `output/` (xem bảng trên), kèm ảnh `_preview.png` từng tờ.

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
- `make_sheets.py` – **lệnh chính**: xuất tờ tổng + từng tờ cụm, PDF gộp, BOM.
- `make_drawing.py` – tờ tổng thể; khử nét khuất (sắp độ sâu theo tia + trừ vùng che), đặt số vị trí, vẽ bảng, khung tên, xuất DXF/Excel/preview.

## Layer trong DXF
`1-NET-THAY`, `2-NET-KHUAT` (HIDDEN), `3-KICH-THUOC`, `4-DUONG-BUNG` (DASHDOT), `5-SO-VI-TRI`, `8-CUM-DA-LAP`, `9-MUI-TEN`, `10-PHU-KIEN`, `M-M1..M6-*` (màu theo cụm).
Khổ giấy vẽ trong Model ở tỉ lệ 1:10 (khung A1 phóng ×10, LTSCALE=10, DIMSCALE=10). Chữ dùng style `VN` (Arial – Unicode tiếng Việt).

> ⚠️ Kích thước mặc định là **mẫu minh hoạ**, không lấy từ bản vẽ thật. Đối chiếu mẫu sofa trước khi sản xuất.
