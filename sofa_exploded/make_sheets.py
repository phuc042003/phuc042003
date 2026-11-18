# -*- coding: utf-8 -*-
"""
XUẤT BỘ BẢN VẼ: 1 BẢN TỔNG THỂ + MỖI CỤM (MODULE) 1 BẢN VẼ RIÊNG
=================================================================
    SF-00  Tổng thể (A1)      : hình chiếu, hình bung tổng, các bước lắp, BOM
    SF-01..06  Từng cụm (A2)  : M1 Khung đáy, M2 Khung ngồi, M3 Gác tay trái,
                                M4 Gác tay phải, M5 Tựa lưng, M6 Chân
Mỗi bản vẽ cụm gồm:
    - 3 hình chiếu vuông góc của cụm (nét khuất), tỉ lệ chuẩn tự chọn (1:2/1:5/1:10/1:20),
      kích thước bao + kích thước chuỗi vị trí các thanh
    - Hình bung trục đo của cụm: số vị trí (đồng bộ với bản tổng), đường bung, nhãn phụ kiện
    - Sơ đồ vị trí cụm trong sofa (cụm tô màu, phần còn lại xám)
    - Bảng kê chi tiết của cụm, bảng phụ kiện (nội bộ cụm / liên kết với cụm khác),
      hướng dẫn lắp, khung tên

Chạy:
    python make_sheets.py                    # tham số mẫu
    python make_sheets.py --params my.json   # tham số thật
    python make_sheets.py --projection third
Kết quả: output/SF-00_TONG-THE.dxf, output/SF-01_M1_KHUNG-DAY.dxf, ...,
         output/SF_BO-BAN-VE.pdf (gộp tất cả), output/SF_BOM.xlsx, preview PNG từng bản
"""
import argparse
import json
import math
import os
import unicodedata
from collections import Counter, OrderedDict

from ezdxf.enums import TextEntityAlignment

import make_drawing as md
from make_drawing import (S, View, balloon, corners, fit_view, hw_tag, mod_layer, mtext,
                          part_numbers, place_balloons, projection_symbol, render_boxes,
                          setup_doc, sheet_outline, shift, table, text)
from sofa_model import (HARDWARE, LEG_MODULE, MODULES, PART_TYPES, STEP_MODULES, build,
                        check_overlaps, solo_offset)

A2 = (594 * S, 420 * S)
SCALES = [(5, "1:2"), (2, "1:5"), (1, "1:10"), (0.5, "1:20")]   # hệ số view (giấy ×10)


def ascii_name(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.upper().replace(" ", "-")


# ------------------------------------------------------------------ khung + khung tên
def frame(msp, size, title_vn, title_en, dwg_no, scale_txt, info, proj, sheet_txt):
    W, H = size
    L = "0-KHUNG-BANVE"
    msp.add_lwpolyline([(0, 0), (W, 0), (W, H), (0, H)], close=True, dxfattribs={"layer": L})
    msp.add_lwpolyline([(200, 100), (W - 100, 100), (W - 100, H - 100), (200, H - 100)], close=True,
                       dxfattribs={"layer": L, "const_width": 7})
    x1, y0 = W - 100, 100
    x0, y1 = x1 - 1800, y0 + 560
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                       dxfattribs={"layer": L, "const_width": 5})
    for yy in (y0 + 140, y0 + 280, y0 + 420):
        msp.add_line((x0, yy), (x1, yy), dxfattribs={"layer": L})
    for xx in (x0 + 600, x0 + 1200):
        msp.add_line((xx, y0), (xx, y0 + 280), dxfattribs={"layer": L})
    text(msp, title_vn, (x0 + 40, y1 - 70), h=4.0)
    text(msp, title_en, (x0 + 40, y1 - 120), h=2.5)
    text(msp, info, (x0 + 40, y0 + 370), h=2.3)
    text(msp, "Phép chiếu góc thứ " + ("nhất (ISO-E / TCVN)" if proj == "first" else "ba (ISO-A)"),
         (x0 + 40, y0 + 305), h=2.3)
    projection_symbol(msp, (x0 + 1450, y0 + 350), proj, 0.75)
    cells = [("Tỉ lệ / Scale", scale_txt), ("Khổ / Size", f"A{'1' if W > 7000 else '2'}"),
             ("Tờ / Sheet", sheet_txt), ("Người vẽ / Drawn", ""), ("Ngày / Date", ""),
             ("Số BV / Dwg No.", dwg_no)]
    for i, (k, val) in enumerate(cells):
        cx = x0 + 600 * (i % 3) + 25
        cy = y0 + 280 - 140 * (i // 3)
        text(msp, k, (cx, cy - 40), h=2.0)
        text(msp, val, (cx, cy - 105), h=3.0)


# ------------------------------------------------------------------ hình chiếu cụm
def bbox(parts):
    return [min(q.box[k] for q in parts) for k in range(3)] + [max(q.box[k + 3] for q in parts) for k in range(3)]


def chain_edges(parts, axis, lo, hi):
    """Mép trái của từng thanh theo trục + điểm cuối -> kích thước chuỗi."""
    vals = sorted({round(q.box[axis], 1) for q in parts} | {round(lo, 1), round(hi, 1)})
    out = []
    for v in vals:
        if not out or v - out[-1] > 1:
            out.append(v)
    return out if 3 <= len(out) <= 16 else None


def dim(msp, base, p1, p2, k, angle=0):
    msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="SOFA_1-10",
                       override={"dimlfac": 1.0 / k},
                       dxfattribs={"layer": "3-KICH-THUOC"}).render()


def module_ortho(msp, parts, region, proj, kmax=10):
    """Vẽ 3 hình chiếu cụm trong vùng region. Trả về chuỗi tỉ lệ."""
    x0b, y0b, z0b, x1b, y1b, z1b = bbox(parts)
    dx, dy, dz = x1b - x0b, y1b - y0b, z1b - z0b
    rx0, ry0, rx1, ry1 = region
    g = 600                                 # khoảng hở cho kích thước + tên hình
    k, stxt = SCALES[-1]
    for kk, t in SCALES:
        if kk > kmax:
            continue
        if kk * (dx + dy) + g + 950 <= rx1 - rx0 and kk * (dz + dy) + g + 950 <= ry1 - ry0:
            k, stxt = kk, t
            break
    side = "left" if proj == "first" else "right"
    X0 = rx0 + 450
    if proj == "first":
        Yf = ry1 - 350 - k * dz            # hình đứng trên
        Yt = Yf - g - k * dy               # hình bằng dưới
    else:
        Yt = ry1 - 350 - k * dy
        Yf = Yt - g - k * dz
    Xs = X0 + k * dx + g
    fv = View("front", (X0 - k * x0b, Yf - k * z0b), k)
    tv = View("top", (X0 - k * x0b, Yt - k * y0b), k)
    sv = View(side, ((Xs + k * y1b) if side == "left" else (Xs - k * y0b), Yf - k * z0b), k)
    items = [(q.tag, q.box, "1-NET-THAY") for q in parts]
    for v in (fv, tv, sv):
        render_boxes(msp, v, items, hidden=True)
    o = 150
    # --- hình đứng: rộng (trên), cao (trái), chuỗi Z (phải)
    fl, fr, fb, ft = X0, X0 + k * dx, Yf, Yf + k * dz
    dim(msp, (fl, ft + o), (fl, ft), (fr, ft), k)
    dim(msp, (fl - o, fb), (fl, fb), (fl, ft), k, 90)
    ch = chain_edges(parts, 2, z0b, z1b)
    if ch and len(ch) > 2:
        for a, b in zip(ch, ch[1:]):
            dim(msp, (fr + o, 0), (fr, Yf + k * (a - z0b)), (fr, Yf + k * (b - z0b)), k, 90)
    # --- hình bằng: sâu (trái), chuỗi X + rộng (dưới)
    tl, tr, tb, tt = X0, X0 + k * dx, Yt, Yt + k * dy
    dim(msp, (tl - o, tb), (tl, tb), (tl, tt), k, 90)
    ch = chain_edges(parts, 0, x0b, x1b)
    off = o
    if ch:
        for a, b in zip(ch, ch[1:]):
            dim(msp, (0, tb - off), (X0 + k * (a - x0b), tb), (X0 + k * (b - x0b), tb), k)
        off += 150
    dim(msp, (0, tb - off), (tl, tb), (tr, tb), k)
    # --- hình cạnh: chuỗi Y + sâu (dưới), cao (phải)
    sl, sr = Xs, Xs + k * dy
    ch = chain_edges(parts, 1, y0b, y1b)
    off = o
    if ch:
        for a, b in zip(ch, ch[1:]):
            ua = (Xs + k * (y1b - a)) if side == "left" else (Xs + k * (a - y0b))
            ub = (Xs + k * (y1b - b)) if side == "left" else (Xs + k * (b - y0b))
            dim(msp, (0, fb - off), (ua, fb), (ub, fb), k)
        off += 150
    dim(msp, (0, fb - off), (sl, fb), (sr, fb), k)
    dim(msp, (sr + o, fb), (sr, fb), (sr, ft), k, 90)
    geo = dict(top_right=tr + 350, side_bottom=fb - 600, k=k)
    names = {"left": "HÌNH CHIẾU CẠNH TRÁI / LEFT VIEW", "right": "HÌNH CHIẾU CẠNH PHẢI / RIGHT VIEW"}
    text(msp, f"HÌNH CHIẾU ĐỨNG / FRONT VIEW  ({stxt})", (fl, fb - (420 if proj == "first" else 520)), h=3.2)
    text(msp, f"HÌNH CHIẾU BẰNG / TOP VIEW  ({stxt})", (tl, tb - 520), h=3.2)
    text(msp, f"{names[side]}  ({stxt})", (sl, fb - 520), h=3.2)
    return stxt, geo


# ------------------------------------------------------------------ hình bung cụm
def module_exploded(msp, p, parts, joints, nums, mod, region):
    by_tag = {q.tag: q for q in parts}
    mine = [q for q in parts if q.module == mod]
    context = mod == LEG_MODULE              # chân: vẽ sofa xám làm nền để thấy vị trí bắt
    offs = {}
    items = []
    for q in parts:
        if q.module == mod:
            offs[q.tag] = solo_offset(q)
            items.append((q.tag, shift(q.box, offs[q.tag]), mod_layer(mod)))
        elif context:
            offs[q.tag] = (0, 0, 0)
            items.append((q.tag, q.box, "8-CUM-DA-LAP"))
    v = fit_view("iso", [b for _, b, _ in items], region, margin=220)
    vis = render_boxes(msp, v, items)
    tags = []
    for j in joints:
        if j.a not in offs or j.b not in offs:
            continue
        if not context and (by_tag[j.a].module != mod or by_tag[j.b].module != mod):
            continue
        for kk, pt in enumerate(j.pts):
            a = v.P(tuple(pt[i] + offs[j.a][i] for i in range(3)))
            b = v.P(tuple(pt[i] + offs[j.b][i] for i in range(3)))
            if math.dist(a, b) > 15:
                msp.add_line(a, b, dxfattribs={"layer": "4-DUONG-BUNG"})
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if math.dist(a, b) > 140 and all(math.dist(m, t) > 160 for t in tags):
                    tags.append(m)
                    hw_tag(msp, m, j.hw)
    anchors = {}
    for ptype in nums:
        cands = [q for q in mine if q.ptype == ptype]
        if not cands:
            continue
        best = max(cands, key=lambda q: vis[q.tag].area)
        if vis[best.tag].is_empty:
            continue
        rp = vis[best.tag].representative_point()
        anchors[ptype] = v.sheet((rp.x, rp.y))
    out = sheet_outline(v, {t: vis[t] for t in vis if by_tag[t].module == mod})
    for ptype, c in place_balloons(anchors, out, 150, 45).items():
        balloon(msp, c, nums[ptype], anchors[ptype])


def location_key(msp, parts, mod, region):
    items = [(q.tag, q.box, mod_layer(mod) if q.module == mod else "8-CUM-DA-LAP") for q in parts]
    v = fit_view("iso", [b for _, b, _ in items], region, margin=60)
    render_boxes(msp, v, items)


def leg_detail(msp, p, origin):
    """Chi tiết 1 chân tỉ lệ 1:2: hình đứng + nhìn từ trên, bulông treo M8 (nét khuất)."""
    k = 5                                       # 1:2 trên giấy ×10
    lg, hl = p["leg"], p["H_leg"]
    x0, y0 = origin
    L1, LH, LC = "1-NET-THAY", "2-NET-KHUAT", "4-DUONG-BUNG"
    w, h = lg * k, hl * k
    msp.add_lwpolyline([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)], close=True,
                       dxfattribs={"layer": L1})
    cx = x0 + w / 2
    r8, dep, pro = 4 * k, 40 * k, 40 * k        # M8, sâu ren 40, nhô 40 (tham số mẫu)
    for xx in (cx - r8, cx + r8):
        msp.add_line((xx, y0 + h - dep), (xx, y0 + h), dxfattribs={"layer": LH})
    msp.add_line((cx - r8, y0 + h - dep), (cx + r8, y0 + h - dep), dxfattribs={"layer": LH})
    msp.add_lwpolyline([(cx - r8, y0 + h), (cx - r8, y0 + h + pro), (cx + r8, y0 + h + pro),
                        (cx + r8, y0 + h)], dxfattribs={"layer": L1})
    msp.add_line((cx, y0 - 60), (cx, y0 + h + pro + 60), dxfattribs={"layer": LC})
    dim(msp, (x0 - 130, y0), (x0, y0), (x0, y0 + h), k, 90)
    dim(msp, (x0 + w + 130, y0), (x0 + w, y0 + h), (x0 + w, y0 + h + pro), k, 90)
    dim(msp, (x0, y0 - 130), (x0, y0), (x0 + w, y0), k)
    tx = x0 + w + 450                            # nhìn từ trên (hướng A)
    msp.add_lwpolyline([(tx, y0), (tx + w, y0), (tx + w, y0 + w), (tx, y0 + w)], close=True,
                       dxfattribs={"layer": L1})
    msp.add_circle((tx + w / 2, y0 + w / 2), r8, dxfattribs={"layer": L1})
    msp.add_line((tx + w / 2, y0 - 50), (tx + w / 2, y0 + w + 50), dxfattribs={"layer": LC})
    msp.add_line((tx - 50, y0 + w / 2), (tx + w + 50, y0 + w / 2), dxfattribs={"layer": LC})
    dim(msp, (tx, y0 - 130), (tx, y0), (tx + w, y0), k)
    text(msp, "CHI TIẾT CHÂN 16 / LEG DETAIL (1:2)", (x0 - 150, y0 + h + pro + 120), h=3.0)
    text(msp, "Nhìn từ trên", (tx, y0 + w + 60), h=2.2)
    text(msp, "Bulông treo M8, ren gỗ sâu 40, nhô 40 (mẫu)", (tx - 50, y0 + w + 250), h=2.0)


# ------------------------------------------------------------------ bảng cụm
def module_tables(msp, parts, joints, nums, mod, x0, y_top, rh=55):
    mine = [q for q in parts if q.module == mod]
    cnt = Counter(q.ptype for q in mine)
    cols = [("VT", 90), ("Tên chi tiết / Part name", 760), ("SL", 100),
            ("Kích thước L×W×T (mm)", 450), ("Vật liệu", 400)]
    rows = []
    for ptype, n in nums.items():
        if ptype not in cnt:
            continue
        L, Wd, T = next(q for q in mine if q.ptype == ptype).size
        rows.append([str(n), f"{PART_TYPES[ptype][0]} / {PART_TYPES[ptype][1]}", str(cnt[ptype]),
                     f"{L:g}×{Wd:g}×{T:g}", PART_TYPES[ptype][3]])
    y = table(msp, x0, y_top, cols, rows, rh, f"BẢNG KÊ CHI TIẾT CỤM {mod} / PARTS LIST")
    by_tag = {q.tag: q for q in parts}
    grp = OrderedDict()
    for j in joints:
        ma, mb = by_tag[j.a].module, by_tag[j.b].module
        if mod not in (ma, mb):
            continue
        other = mb if ma == mod else ma
        where = "Nội bộ cụm" if other == mod else f"Với {other} {MODULES[other]['vn']}"
        grp[(j.hw, where)] = grp.get((j.hw, where), 0) + len(j.pts)
    cols2 = [("Mã", 90), ("Phụ kiện / Hardware", 1010), ("Liên kết", 600), ("SL", 100)]
    rows2 = [[hw, f"{HARDWARE[hw][0]} / {HARDWARE[hw][1]}".replace("Ø", "%%c"), where, str(n)]
             for (hw, where), n in sorted(grp.items())]
    y = table(msp, x0, y - 90, cols2, rows2, rh, "PHỤ KIỆN / HARDWARE")
    return y


# ------------------------------------------------------------------ bản vẽ cụm
def module_sheet(p, parts, joints, nums, mod, idx, total, proj, outdir):
    doc = setup_doc()
    msp = doc.modelspace()
    W, H = A2
    mine = [q for q in parts if q.module == mod]
    info = MODULES[mod]
    x0b, y0b, z0b, x1b, y1b, z1b = bbox(mine)
    dx, dy = x1b - x0b, y1b - y0b
    title_x = f"HÌNH BUNG CỤM {mod} – {info['vn'].upper()} / EXPLODED VIEW (không TL)"
    # chiều cao bảng (để xếp bảng sát khung tên, nhường chỗ cho hình bung)
    by_tag = {q.tag: q for q in parts}
    n_hw = len({(j.hw, by_tag[j.b].module if by_tag[j.a].module == mod else by_tag[j.a].module)
                for j in joints if mod in (by_tag[j.a].module, by_tag[j.b].module)})
    n_pt = len({q.ptype for q in mine})
    tab_h = (n_pt + n_hw + 2) * 55 + 90
    tab_top_auto = 660 + 120 + tab_h
    if dx > 1.5 * dy:
        # CỤM DÀI: hình chiếu chiếm dải trên toàn khổ; hình bung bên phải hình bằng
        stxt, geo = module_ortho(msp, mine, (250, 1150, W - 150, H - 150), proj, kmax=1)
        key, note = (250, 150, 1550, 1100), (1650, 1050)
        tab_top = tab_top_auto
        ex = (max(geo["top_right"], 2400), tab_top + 150, W - 150, min(geo["side_bottom"] - 120, H - 400))
        text(msp, title_x, (ex[0] + 50, ex[3] + 40), h=3.2)
        module_exploded(msp, p, parts, joints, nums, mod, (ex[0], ex[1], ex[2], ex[3] - 60))
    else:
        # CỤM HẸP (gác tay): hình chiếu bên trái; hình bung + bảng bên phải
        stxt, geo = module_ortho(msp, mine, (250, 700, 3300, H - 150), proj)
        key, note = (1500, 1300, 3250, 2450), (250, 620)
        text(msp, title_x, (3350, H - 230), h=3.5)
        tab_top = tab_top_auto
        module_exploded(msp, p, parts, joints, nums, mod, (3300, tab_top + 150, W - 150, H - 280))
    # sơ đồ vị trí
    kx0, ky0, kx1, ky1 = key
    text(msp, "VỊ TRÍ CỤM TRONG SOFA / LOCATION", (kx0 + 50, ky1 - 70), h=3.0)
    msp.add_lwpolyline([(kx0, ky0), (kx1, ky0), (kx1, ky1), (kx0, ky1)], close=True,
                       dxfattribs={"layer": "7-BANG-KE"})
    location_key(msp, parts, mod, (kx0 + 10, ky0 + 10, kx1 - 10, ky1 - 110))
    # hướng dẫn lắp
    si = next(i for i, (mods, _) in enumerate(STEP_MODULES) if mod in mods)
    title, lines = md.STEPS[si]
    hint = (f"HƯỚNG DẪN LẮP – BƯỚC {si + 1}/{len(STEP_MODULES)} TRONG BẢN TỔNG SF-00:\\P"
            + "\\P".join(lines)
            + "\\P\\PGhi chú: số vị trí đồng bộ với bản vẽ tổng SF-00. Kích thước là tham số MẪU.")
    if mod == LEG_MODULE:
        hint += "\\PHình bung: sofa vẽ xám làm nền để thấy điểm bắt chân."
        leg_detail(msp, p, (2900, 230))
    mtext(msp, hint, note, h=2.4,
          width=(950 if mod == LEG_MODULE else 1550) if note[0] > 1000 else 3000)
    # bảng
    module_tables(msp, parts, joints, nums, mod, W - 100 - 1900, tab_top)
    dwg = f"SF-KHUNG-{idx:02d}"
    frame(msp, A2, f"CỤM {mod}: {info['vn'].upper()}", f"{info['en'].upper()} – SOFA FRAME MODULE",
          dwg, f"{stxt} (3D: không TL)",
          f"Bao cụm: {x1b - x0b:g} × {y1b - y0b:g} × {z1b - z0b:g} mm (L×W×H, tham số mẫu)",
          proj, f"{idx + 1}/{total}")
    name = f"SF-{idx:02d}_{mod}_{ascii_name(info['vn'])}.dxf"
    path = os.path.join(outdir, name)
    doc.saveas(path)
    return doc, path


# ------------------------------------------------------------------ preview
def render(doc, size, ax):
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, lineweight_scaling=1.2)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace())
    ax.set_xlim(0, size[0]); ax.set_ylim(0, size[1]); ax.set_aspect("equal"); ax.axis("off")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params")
    ap.add_argument("--projection", choices=["first", "third"], default="first")
    ap.add_argument("--out", default="output")
    ap.add_argument("--no-preview", action="store_true")
    a = ap.parse_args()
    prm = json.load(open(a.params, encoding="utf-8")) if a.params else None
    os.makedirs(a.out, exist_ok=True)
    for f in os.listdir(a.out):                       # dọn file cũ của lần chạy trước
        if f.startswith(("SF-", "SF_", "sofa_frame_exploded")):
            os.remove(os.path.join(a.out, f))
    p, parts, joints = build(prm)
    if check_overlaps(parts):
        raise SystemExit(f"Lỗi chồng chi tiết: {check_overlaps(parts)}")
    nums = part_numbers(parts)
    mods = list(MODULES)
    total = len(mods) + 1
    sheets = []
    doc, path, *_ = md.make(prm, a.projection, a.out)
    new = os.path.join(a.out, "SF-00_TONG-THE.dxf")
    os.replace(path, new)
    sheets.append((doc, new, (md.SHEET_W, md.SHEET_H)))
    for i, m in enumerate(mods):
        d, pth = module_sheet(p, parts, joints, nums, m, i + 1, total, a.projection, a.out)
        sheets.append((d, pth, A2))
    md.export_bom(p, parts, joints, nums, os.path.join(a.out, "SF_BOM.xlsx"))
    if not a.no_preview:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        with PdfPages(os.path.join(a.out, "SF_BO-BAN-VE.pdf")) as pdf:
            for d, pth, size in sheets:
                fig = plt.figure(figsize=(size[0] / 254, size[1] / 254))
                render(d, size, fig.add_axes([0, 0, 1, 1]))
                pdf.savefig(fig)
                fig.savefig(os.path.splitext(pth)[0] + "_preview.png", dpi=110)
                plt.close(fig)
    for _, pth, _ in sheets:
        print("Đã tạo:", pth)
    print("Đã tạo:", os.path.join(a.out, "SF_BOM.xlsx"), os.path.join(a.out, "SF_BO-BAN-VE.pdf"))


if __name__ == "__main__":
    main()
