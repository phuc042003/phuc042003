# CHECKLIST LÀM VIỆC – Bản vẽ lắp ráp khung sofa (vòng 5)

Quy tắc: làm xong + tự kiểm 1 bước mới đánh dấu [x] và sang bước sau.

| # | Bước | Trạng thái | Kiểm chứng |
|---|---|---|---|
| B1 | Phân tích yêu cầu, lập checklist | [x] | File này |
| B2 | Mô hình hình học lăng trụ: thanh LVL vát đầu 41°, ke góc tam giác 45°, pát L nhiều khối | [x] | geom.py; 56 chi tiết, check_overlaps (SAT) = 0 |
| B3 | Ván ép 9/12/15/18 trong mô hình (ván hông tay 15, ván lưng 9, khung ngồi 18) + pát nối tựa–tay | [x] | material_of → Ván ép 9/15/18, LVL |
| B4 | Quy tắc phụ kiện: lỗ Ø10 → ốc 4 chấu M8, lỗ Ø8 → ốc cấy M6; bulông dài theo ván 9→12, 12→16, 15→18, 18→21 | [x] | BOLT_LEN: P8×21 (8), P6×21 (8), P8×12 (4) |
| B5 | Lỗ khoan trên mặt bất kỳ (kể cả mặt vát) + tách biến thể cùng KT khác lỗ | [x] | holes.py: 0 điểm lỗi; 6A/6B, 12A–D, 14A/B, 19A–C |
| B6 | Engine vẽ: khử nét khuất cho đa diện lồi; hình chiếu lắp KHÔNG nét khuất; tự thêm hướng nhìn phụ khi chi tiết bị che | [x] | render.py: visibility() + best_aux(); trang 01 có hướng nhìn sau |
| B7 | Trang cụm: 1 cụm = 1 trang A4 duy nhất (hình bung lớn, KT bao, bảng kê, phụ kiện kèm chiều dài bulông) | [x] | trang 09–14 |
| B8 | Trang chi tiết: dim tổng L×W×T, dim vị trí lỗ, Ø lỗ, góc vát, đánh số phân biệt biến thể; KHÔNG xuất chi tiết pát | [x] | trang 15–40; VT16 góc 41°/139° |
| B9 | Trang tổng: hình chiếu không nét khuất + hướng nhìn phụ, bước lắp, BOM, phụ kiện + bảng quy tắc | [x] | trang 01–08 |
| B10 | Tự kiểm tra tự động + chấm điểm /10, sửa đến ≥ 9/10 | [x] | selfcheck.py: lần 1 = 9.55 → lần 2 = 9.9 → lần 3 = **10.0/10** (output/TU-KIEM-TRA.md) |
| B11 | Xem ảnh từng trang, commit + push, báo cáo | [x] | Chấm trực quan ≈ 9.3/10: thanh 1870 vẽ 1:20; vài nhãn lỗ sát nhau ở ván lưng/đà đáy (vẫn đọc được) |

## Vòng 6 – Khoanh vùng pát sắt + hình chi tiết phóng to

| # | Bước | Trạng thái | Kiểm chứng |
|---|---|---|---|
| C1 | Cắt vùng 3D quanh pát (clip lăng trụ theo hộp) để vẽ riêng phần gỗ gần pát | [x] | clip_part() trong make_a4.py |
| C2 | Khoanh vùng (vòng tròn đỏ + ký hiệu A/B/C) trên trang tổng hình bung, trang cụm M2/M5, bước lắp 3/4 | [x] | trang 02, 03–04, 13, 16 |
| C3 | Trang "Vị trí pát sắt": hình tổng có khoanh vùng mọi vị trí + bảng chi tiết | [x] | trang 08: 4×A, 2×B, 2×C |
| C4 | Mỗi chi tiết A/B/C 1 trang: 2 hình chiếu phóng to + hình trục đo, dim định vị pát & lỗ, chỉ chỗ bắn bulông/vít, ghi chú | [x] | trang 09–11, tỉ lệ 1:2; A: hạ 10 mm, lỗ 17.5/20/12.5 |
| C5 | Tự kiểm tra (thêm tiêu chí khoanh vùng + chi tiết pát) ≥ 9/10, xem ảnh, commit | [x] | 11 tiêu chí: 9.96 → **10.0/10**; đã xem ảnh trang 08–11 |

## Vòng 7 – Gọn còn 5 trang A4

| # | Bước | Trạng thái | Kiểm chứng |
|---|---|---|---|
| D1 | Trang 1 Tổng thể: hình chiếu KT bao, hình bung nhãn cụm + khoanh pát, trình tự lắp, tổng phụ kiện | [x] | SF-01 |
| D2 | Trang 2 Gác tay (trái + phải), Trang 3 Tựa lưng (+ chi tiết pát B), Trang 4 Khung ngồi (+ chi tiết A, C), Trang 5 Khung đáy (+ chân) | [x] | SF-02…05 |
| D3 | Mỗi trang cụm: hình bung lớn, KT bao, bảng kê (vật liệu, khác lỗ, vát 41°), phụ kiện + chiều dài bulông | [x] | bảng kê ghi 'khác lỗ', 'vát 41°/139°', 'vát 45°' |
| D4 | Tự kiểm tra cho chế độ 5 trang ≥ 9/10, xem ảnh, commit | [x] | 11 tiêu chí = 10.0/10; xem ảnh sửa thêm 5 lỗi (KT bao tay đè bảng, chú thích tràn, mất dim hạ 10 mm…) |

## Vòng 8 – 1 cụm = 1 trang chứa TOÀN BỘ (lắp ráp + bảng + chi tiết gia công)

| # | Bước | Trạng thái | Kiểm chứng |
|---|---|---|---|
| E1 | Ô chi tiết gia công thu gọn: biên dạng, dim tổng, dim vị trí lỗ, lỗ mặt/cạnh/đầu, góc vát, mã biến thể | [x] | compact.part_cell() |
| E2 | Bố cục trang cụm: hình bung + bảng kê/phụ kiện + lưới ô chi tiết + ô chi tiết pát | [x] | SF-02…05 |
| E3 | Tự kiểm tra thêm tiêu chí "mọi chi tiết gỗ có ô gia công trên trang cụm" ≥ 9/10, xem ảnh, commit | [x] | 12 tiêu chí: 9.33 (lỗ mặt B nét đứt) → 10.0/10; xem ảnh: giãn dim chuỗi thanh dài |
