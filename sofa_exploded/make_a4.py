# -*- coding: utf-8 -*-
"""
XUẤT TOÀN BỘ BẢN VẼ KHỔ A4 (ngang 297×210) – BÓC TÁCH LẮP RÁP KHUNG SOFA
==========================================================================
Thứ tự trang:
  1. Tổng thể – 3 hình chiếu
  2. Tổng thể – hình bung trục đo (nhãn cụm M1..M6, chi tiết sắt tô đỏ)
  3–4. Các bước lắp ráp
  5+. Bảng kê chi tiết (BOM) theo mã biến thể
  .   Phụ kiện + tổng hợp vật liệu + bảng ký hiệu lỗ
  .   CHI TIẾT SẮT: pát L + thanh gia cố – hình chiếu + hướng dẫn lắp
  .   Mỗi cụm 2 trang: (a) hình chiếu, (b) hình bung + bảng kê + phụ kiện
  .   Mỗi biến thể chi tiết gỗ 1 trang gia công: hình chiếu, lỗ khoan, bảng toạ độ lỗ

Quy tắc vật liệu: dày 3–18 mm = VÁN ÉP; dày ≥ 20 mm = LVL (sofa_model.material_of).
Chi tiết cùng kích thước nhưng khác lỗ: mã có hậu tố chữ (6A, 6B...), số vị trí khung
VUÔNG thay vì tròn, ghi chú "cùng KT – khác lỗ" trong BOM và trang gia công.

Chạy:
    pip install ezdxf shapely openpyxl matplotlib
    python make_a4.py [--params my.json] [--projection third]
Kết quả: output/A4/*.dxf (mỗi trang 1 file), output/SF_A4_BO-BAN-VE.pdf, output/SF_BOM.xlsx
"""
import argparse
import json
import math
import os
import re
import shutil
import unicodedata
from collections import Counter, OrderedDict

from ezdxf.enums import TextEntityAlignment as TA

import make_drawing as md
from holes import FACE_DESC, hole_desc, hole_rows, variants
from make_drawing import View, corners, fit_view, place_balloons, render_boxes, shift
from sofa_model import (HARDWARE, HOLE_SPEC, LEG_MODULE, METAL_TYPES, MODULES, PART_TYPES,
                        STEP_MODULES, build, check_overlaps, explode_offset, loc_name,
                        material_of, solo_offset)

S = md.S
PW, PH = 297 * S, 210 * S
TB_W, TB_H = 1500, 280                  # khung tên 150 × 28 mm
SCALES = [(20, "2:1"), (10, "1:1"), (5, "1:2"), (2, "1:5"), (1, "1:10"), (0.5, "1:20"), (0.2, "1:50")]
METAL_LAYER = "11-SAT"

STEPS_A4 = [
    ("LẮP KHUNG ĐÁY (M1)",
     "Ghép giằng {base_end}, {base_mid} vào đà đáy {base_front} và {base_back} bằng chốt B + keo; "
     "vít C ở 2 giằng đầu. Bắt ke góc {block} bằng vít E. Đo chéo kiểm tra vuông (lệch ≤ 2 mm)."),
    ("LẮP GÁC TAY (M3, M4)",
     "Ghép trụ {arm_post}, giằng {arm_bot}, {arm_mid} và thanh {arm_top} bằng chốt B + keo. "
     "Áp gác tay vào 2 đầu khung đáy, bắt bulông A (6 bộ/bên)."),
    ("LẮP KHUNG NGỒI (M2) + SẮT",
     "Ghép thanh {seat_fb}, {seat_side} bằng chốt B. Bắt 4 pát L {pat_L} ở 4 góc trong (vít G). "
     "Đặt thanh gia cố {steel_bar}, bắt bulông H qua thanh hông. Bắt nan {seat_slat}: vít C ở 2 đầu, "
     "vít tự khoan K xuống thanh sắt. Đặt lên khung đáy, vít F; bulông A qua trụ gác tay trước."),
    ("LẮP TỰA LƯNG (M5)",
     "Ghép thanh đứng {back_stile} với thanh {back_bot}, {back_top} bằng chốt B + keo. Đặt lên đà đáy "
     "sau {base_back}, bulông A vào trụ gác tay sau (2 bộ/bên), vít C xuống đà đáy sau."),
    ("LẮP CHÂN (M6)",
     "Lật úp sofa lên mặt phẳng có lót, vặn 6 chân {leg} bằng bulông treo D vào tán cấy. "
     "Lật lại, kiểm tra cân bằng, siết lại toàn bộ bulông A."),
]


def ascii_name(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").upper()


# ================================================================== tiện ích vẽ
def setup():
    doc = md.setup_doc()
    doc.layers.add(METAL_LAYER, color=1, lineweight=35)
    ds = doc.dimstyles.new("A4")
    for k, v in dict(dimscale=S, dimtxt=1.8, dimasz=1.6, dimexe=1.0, dimexo=0.8, dimgap=0.5,
                     dimdec=1, dimzin=8, dimtad=1, dimtxsty="VN", dimclrd=1, dimclre=1,
                     dimclrt=7).items():
        ds.dxf.set(k, v)
    return doc


def T(msp, s, pos, h=2.0, align=TA.LEFT, layer="6-CHU", color=None):
    md.text(msp, s, pos, h=h, layer=layer, align=align, color=color)


def MT(msp, s, pos, h=1.9, width=None, layer="6-CHU"):
    return md.mtext(msp, s, pos, h=h, width=width, layer=layer)


def dim(msp, base, p1, p2, k, angle=0):
    msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="A4",
                       override={"dimlfac": 1.0 / k},
                       dxfattribs={"layer": "3-KICH-THUOC"}).render()


def rect(msp, x0, y0, x1, y1, layer="1-NET-THAY", **kw):
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                       dxfattribs=dict(layer=layer, **kw))


def tbl(msp, x0, y_top, cols, rows, rh=55, title=None, h=1.7):
    width = sum(w for _, w in cols)
    if title:
        T(msp, title, (x0, y_top + 22), h=2.2, layer="7-BANG-KE")
    y = y_top
    for ri, r in enumerate([[c for c, _ in cols]] + rows):
        x = x0
        for (_, w), cell in zip(cols, r):
            rect(msp, x, y - rh, x + w, y, layer="7-BANG-KE")
            T(msp, str(cell), (x + 12, y - rh / 2), h=h, layer="7-BANG-KE", align=TA.MIDDLE_LEFT)
            x += w
        y -= rh
    rect(msp, x0, y, x0 + width, y_top, layer="0-KHUNG-BANVE")
    return y


def balloon(msp, c, label, anchor, r=36, square=False, h=1.9, layer="5-SO-VI-TRI"):
    if square:
        rect(msp, c[0] - r, c[1] - r, c[0] + r, c[1] + r, layer=layer)
    else:
        msp.add_circle(c, r, dxfattribs={"layer": layer})
    T(msp, label, c, h=h if len(label) < 3 else h * 0.85, align=TA.MIDDLE_CENTER, layer=layer)
    dx, dy = anchor[0] - c[0], anchor[1] - c[1]
    L = math.hypot(dx, dy)
    if L > r:
        msp.add_line((c[0] + dx / L * r, c[1] + dy / L * r), anchor, dxfattribs={"layer": layer})
        msp.add_circle(anchor, 5, dxfattribs={"layer": layer})


def hw_tag(msp, pos, code, a=24):
    pts = [(pos[0] + a * math.cos(math.radians(30 + 60 * i)), pos[1] + a * math.sin(math.radians(30 + 60 * i)))
           for i in range(6)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "10-PHU-KIEN"})
    T(msp, code, pos, h=1.8, align=TA.MIDDLE_CENTER, layer="10-PHU-KIEN")


def frame(msp, title_vn, title_en, dwg, scale, sheet, proj):
    L = "0-KHUNG-BANVE"
    rect(msp, 0, 0, PW, PH, layer=L)
    rect(msp, 200, 100, PW - 100, PH - 100, layer=L, const_width=5)
    x1, y0 = PW - 100, 100
    x0, y1 = x1 - TB_W, y0 + TB_H
    rect(msp, x0, y0, x1, y1, layer=L, const_width=4)
    msp.add_line((x0, y0 + 120), (x1, y0 + 120), dxfattribs={"layer": L})
    for i in range(1, 4):
        msp.add_line((x0 + 375 * i, y0), (x0 + 375 * i, y0 + 120), dxfattribs={"layer": L})
    T(msp, title_vn, (x0 + 25, y1 - 55), h=2.6)
    T(msp, title_en, (x0 + 25, y1 - 110), h=1.6)
    T(msp, "Góc chiếu " + ("1 (TCVN/ISO-E)" if proj == "first" else "3 (ISO-A)") + " – đơn vị mm",
          (x0 + 25, y0 + 132), h=1.5)
    md.projection_symbol(msp, (x1 - 230, y1 - 75), proj, 0.35)
    for i, (k, v) in enumerate([("Tỉ lệ", scale), ("Tờ", sheet), ("Số BV", dwg), ("Người vẽ / Ngày", "")]):
        T(msp, k, (x0 + 375 * i + 15, y0 + 95), h=1.4)
        T(msp, v, (x0 + 375 * i + 15, y0 + 35), h=2.0)


def layer_of(q, colored=True, gray=False):
    if gray:
        return "8-CUM-DA-LAP"
    if q.ptype in METAL_TYPES:
        return METAL_LAYER
    return md.mod_layer(q.module) if colored else "1-NET-THAY"


def items_of(parts, off=lambda q: (0, 0, 0), layer=lambda q: layer_of(q)):
    out = []
    for q in parts:
        o = off(q)
        for i, b in enumerate(q.boxes):
            out.append((f"{q.tag}#{i}", shift(b, o), layer(q)))
    return out


def vis_by_tag(vis):
    from shapely.ops import unary_union
    acc = {}
    for k, g in vis.items():
        acc.setdefault(k.split("#")[0], []).append(g)
    return {t: unary_union(gs) for t, gs in acc.items()}


def outline(v, vis):
    from shapely import affinity
    from shapely.ops import unary_union
    g = unary_union([x for x in vis.values() if not x.is_empty])
    g = affinity.scale(g, v.scale, v.scale, origin=(0, 0))
    return affinity.translate(g, v.origin[0], v.origin[1])


def bbox_parts(parts):
    bs = [b for q in parts for b in q.boxes]
    return [min(b[k] for b in bs) for k in range(3)] + [max(b[k + 3] for b in bs) for k in range(3)]


def anchor_of(v, vt, tags):
    best = max(tags, key=lambda t: vt[t].area if t in vt else -1)
    if best not in vt or vt[best].is_empty:
        return None
    rp = vt[best].representative_point()
    return v.sheet((rp.x, rp.y))


# ================================================================== hình chiếu vuông góc
def chain_edges(parts, axis, lo, hi, k=1.0, min_paper=70):
    """Kích thước chuỗi; bỏ mép tạo đoạn < 7 mm trên giấy để chữ không chồng."""
    vals = sorted({round(q.box[axis], 1) for q in parts} | {round(lo, 1), round(hi, 1)})
    gap = min_paper / k
    out = [vals[0]]
    for v in vals[1:-1]:
        if v - out[-1] >= gap and vals[-1] - v >= gap:
            out.append(v)
    out.append(vals[-1])
    return out if 3 <= len(out) <= 14 else None


def ortho(msp, parts, region, proj, kmax=10, colored=False, chain=True):
    x0b, y0b, z0b, x1b, y1b, z1b = bbox_parts(parts)
    dx, dy, dz = x1b - x0b, y1b - y0b, z1b - z0b
    rx0, ry0, rx1, ry1 = region
    g, top, bot, side_m = 320, 150, 290, 300
    k, stxt = SCALES[-1]
    for kk, t in SCALES:
        if kk <= kmax and kk * (dx + dy) + g + 2 * side_m <= rx1 - rx0 and \
                kk * (dz + dy) + g + top + bot <= ry1 - ry0:
            k, stxt = kk, t
            break
    side = "left" if proj == "first" else "right"
    X0 = rx0 + side_m
    if proj == "first":
        Yf = ry1 - top - k * dz
        Yt = Yf - g - k * dy
    else:
        Yt = ry1 - top - k * dy
        Yf = Yt - g - k * dz
    Xs = X0 + k * dx + g
    fv = View("front", (X0 - k * x0b, Yf - k * z0b), k)
    tv = View("top", (X0 - k * x0b, Yt - k * y0b), k)
    sv = View(side, ((Xs + k * y1b) if side == "left" else (Xs - k * y0b), Yf - k * z0b), k)
    it = items_of(parts, layer=lambda q: layer_of(q, colored=colored))
    for v in (fv, tv, sv):
        render_boxes(msp, v, it, hidden=True)
    o, oc = 70, 75
    fl, fr, fb, ft = X0, X0 + k * dx, Yf, Yf + k * dz
    dim(msp, (fl, ft + o), (fl, ft), (fr, ft), k)
    dim(msp, (fl - o, fb), (fl, fb), (fl, ft), k, 90)
    ch = chain and chain_edges(parts, 2, z0b, z1b, k)
    if ch:
        for a, b in zip(ch, ch[1:]):
            dim(msp, (fr + o, 0), (fr, Yf + k * (a - z0b)), (fr, Yf + k * (b - z0b)), k, 90)
    tl, tr, tb, tt = X0, X0 + k * dx, Yt, Yt + k * dy
    dim(msp, (tl - o, tb), (tl, tb), (tl, tt), k, 90)
    off = o
    ch = chain and chain_edges(parts, 0, x0b, x1b, k)
    if ch:
        for a, b in zip(ch, ch[1:]):
            dim(msp, (0, tb - off), (X0 + k * (a - x0b), tb), (X0 + k * (b - x0b), tb), k)
        off += oc
    dim(msp, (0, tb - off), (tl, tb), (tr, tb), k)
    sl, sr = Xs, Xs + k * dy
    soff = o
    ch = chain and chain_edges(parts, 1, y0b, y1b, k)
    if ch:
        for a, b in zip(ch, ch[1:]):
            ua = (Xs + k * (y1b - a)) if side == "left" else (Xs + k * (a - y0b))
            ub = (Xs + k * (y1b - b)) if side == "left" else (Xs + k * (b - y0b))
            dim(msp, (0, fb - soff), (ua, fb), (ub, fb), k)
        soff += oc
    dim(msp, (0, fb - soff), (sl, fb), (sr, fb), k)
    dim(msp, (sr + o, fb), (sr, fb), (sr, ft), k, 90)
    nm = {"left": "HÌNH CHIẾU CẠNH TRÁI", "right": "HÌNH CHIẾU CẠNH PHẢI"}
    T(msp, f"HÌNH CHIẾU ĐỨNG ({stxt})", (fl, fb - 140 if proj == "first" else fb - 230), h=2.0)
    T(msp, f"HÌNH CHIẾU BẰNG ({stxt})", (tl, tb - off - 130), h=2.0)
    T(msp, f"{nm[side]} ({stxt})", (sl, fb - soff - 130), h=2.0)
    return stxt


# ================================================================== hình trục đo
def exploded(msp, parts, joints, offs, region, labels, square=(), gray=(), margin=170,
             joint_filter=None, r=36, label_gap=110):
    """offs: tag->offset; labels: {label: [tags]} -> 1 số vị trí / nhãn."""
    by = {q.tag: q for q in parts}
    shown = [q for q in parts if q.tag in offs]
    it = items_of(shown, off=lambda q: offs[q.tag], layer=lambda q: layer_of(q, gray=q.tag in gray))
    v = fit_view("iso", [b for _, b, _ in it], region, margin=margin)
    vis = render_boxes(msp, v, it)
    vt = vis_by_tag(vis)
    tags_pos = []
    for j in joints:
        if j.a not in offs or j.b not in offs or (joint_filter and not joint_filter(j)):
            continue
        for pt in j.pts:
            a = v.P(tuple(pt[i] + offs[j.a][i] for i in range(3)))
            b = v.P(tuple(pt[i] + offs[j.b][i] for i in range(3)))
            d = math.dist(a, b)
            if d > 12:
                msp.add_line(a, b, dxfattribs={"layer": "4-DUONG-BUNG"})
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if d > 110 and all(math.dist(m, t) > 120 for t in tags_pos):
                    tags_pos.append(m)
                    hw_tag(msp, m, j.hw)
    anchors = {}
    for lab, tags in labels.items():
        a = anchor_of(v, vt, tags)
        if a:
            anchors[lab] = a
    ol = outline(v, {k: g for k, g in vis.items() if k.split("#")[0] not in gray})
    if anchors:
        for lab, c in place_balloons(anchors, ol, label_gap, r).items():
            balloon(msp, c, lab, anchors[lab], r=r, square=lab in square)
    return v


def location_key(msp, parts, mods, region):
    it = items_of(parts, layer=lambda q: layer_of(q) if q.module in mods else "8-CUM-DA-LAP")
    v = fit_view("iso", [b for _, b, _ in it], region, margin=30)
    render_boxes(msp, v, it)


# ================================================================== ngữ cảnh
class Ctx:
    def __init__(self, params, proj):
        self.p, self.parts, self.joints = build(params)
        bad = check_overlaps(self.parts)
        if bad:
            raise SystemExit(f"Lỗi chồng chi tiết: {bad}")
        self.proj = proj
        self.by = {q.tag: q for q in self.parts}
        self.nums = md.part_numbers(self.parts)
        self.var, self.t2c, self.problems = variants(self.parts, self.joints, self.nums)

    def codes_of(self, ptype):
        cs = [c for c, g in self.var.items() if g["ptype"] == ptype]
        return "/".join(cs)

    def step_text(self, i):
        title, txt = STEPS_A4[i]
        return title, txt.format(**{pt: self.codes_of(pt) for pt in PART_TYPES})

    def labels_for(self, tags):
        lab = OrderedDict()
        for t in tags:
            lab.setdefault(self.t2c[t], []).append(t)
        return lab

    def square_set(self):
        return {c for c, g in self.var.items() if g["siblings"]}

    def material(self, code):
        g = self.var[code]
        return material_of(g["ptype"], g["dims"], self.p)


# ================================================================== các trang
def pg_overview_views(c, msp):
    s = ortho(msp, c.parts, (250, 300, PW - 150, PH - 150), c.proj, kmax=1, chain=False)
    T(msp, "Nét đỏ = chi tiết sắt. Kích thước là tham số MẪU.", (250, 140), h=1.6)
    return "TỔNG THỂ – HÌNH CHIẾU", "OVERALL – ORTHOGRAPHIC VIEWS", s


def pg_overview_exploded(c, msp):
    offs = {q.tag: explode_offset(q, c.p, "full") for q in c.parts}
    labels = OrderedDict()
    for m in MODULES:
        labels[m] = [q.tag for q in c.parts if q.module == m and q.ptype not in METAL_TYPES]
    for code, g in c.var.items():
        if g["metal"]:
            labels[code] = g["tags"]
    exploded(msp, c.parts, c.joints, offs, (250, 420, 2150, PH - 150), labels, r=40, label_gap=120)
    rows = [[m, f"{i['vn']} / {i['en']}"] for m, i in MODULES.items()]
    rows += [[code, f"{PART_TYPES[g['ptype']][0]} (sắt, nét đỏ)"] for code, g in c.var.items() if g["metal"]]
    y = tbl(msp, 2200, PH - 200, [("Nhãn", 150), ("Cụm / chi tiết", 520)], rows, 55, "CHÚ GIẢI")
    MT(msp, "Nhãn lục giác A..K = phụ kiện (xem trang Phụ kiện).\\PNét chấm gạch = đường bung "
            "(vị trí, phương lắp).\\PMàu theo cụm; sắt màu đỏ.", (2200, y - 50), h=1.7, width=650)
    return "TỔNG THỂ – HÌNH BUNG", "OVERALL – EXPLODED ISOMETRIC", "không TL"


def draw_step(c, msp, step, region):
    mods_upto, acc = {}, set()
    for i, (mods, _) in enumerate(STEP_MODULES):
        acc |= set(mods)
        mods_upto[i + 1] = set(acc)
    new = set(STEP_MODULES[step - 1][0])
    level = STEP_MODULES[step - 1][1]
    offs, gray = {}, set()
    for q in c.parts:
        if q.module not in mods_upto[step]:
            continue
        if q.module in new:
            o = explode_offset(q, c.p, level)
            if q.module == LEG_MODULE:
                o = (0, 0, -c.p["ex_leg"] * 0.8)
            if q.ptype in METAL_TYPES:          # sắt: thêm bung riêng để thấy rõ
                o = tuple(a + b for a, b in zip(o, q.part_off))
            offs[q.tag] = o
        else:
            offs[q.tag] = (0, 0, 0)
            gray.add(q.tag)
    newtags = [q.tag for q in c.parts if q.module in new]
    exploded(msp, c.parts, c.joints, offs, region, c.labels_for(newtags), square=c.square_set(),
             gray=gray, margin=120, joint_filter=lambda j: j.step == step, r=32, label_gap=80)


def pg_steps(c, msp, steps):
    n = 3
    w = (PW - 100 - 250) / n
    for i, st in enumerate(steps):
        x = 250 + i * w
        draw_step(c, msp, st, (x + 10, 720, x + w - 10, PH - 170))
        title, txt = c.step_text(st - 1)
        msp.add_circle((x + 45, 650), 40, dxfattribs={"layer": "6-CHU", "color": 1})
        T(msp, str(st), (x + 45, 650), h=3.5, align=TA.MIDDLE_CENTER, color=1)
        T(msp, title, (x + 105, 640), h=2.1)
        MT(msp, txt, (x + 10, 575), h=1.7, width=w - 40)
        if i:
            msp.add_line((x, 120), (x, PH - 120), dxfattribs={"layer": "0-KHUNG-BANVE"})
    if len(steps) < n:
        x = 250 + len(steps) * w
        MT(msp, "GHI CHÚ CHUNG:\\P1. Kích thước là tham số MẪU – đối chiếu mẫu thật trước khi sản xuất.\\P"
                "2. Chốt B bôi keo PVA, kẹp ép ≥ 30 phút.\\P3. Bulông A chỉ siết chặt sau khi lắp đủ cụm.\\P"
                "4. Số vị trí khung VUÔNG = chi tiết cùng kích thước nhưng KHÁC LỖ – kiểm tra mã trước khi lắp.\\P"
                "5. Màu xám = phần đã lắp ở bước trước.", (x + 20, PH - 250), h=1.8, width=w - 60)
        msp.add_line((x, 120), (x, PH - 120), dxfattribs={"layer": "0-KHUNG-BANVE"})
    return (f"CÁC BƯỚC LẮP {steps[0]}–{steps[-1]}", "ASSEMBLY SEQUENCE", "không TL")


def bom_rows(c, codes=None):
    rows = []
    for code, g in c.var.items():
        if codes is not None and code not in codes:
            continue
        L, W, Tt = g["dims"]
        note = ("Cùng KT – KHÁC LỖ: " + "/".join(g["siblings"])) if g["siblings"] else ""
        if g["metal"]:
            note = "Xem trang Chi tiết sắt"
        rows.append(dict(code=code, name=PART_TYPES[g["ptype"]][0], en=PART_TYPES[g["ptype"]][1],
                         cn=PART_TYPES[g["ptype"]][2], mod=g["module"], qty=len(g["tags"]),
                         size=f"{L:g}×{W:g}×{Tt:g}", mat=c.material(code), note=note,
                         L=L, W=W, T=Tt, metal=g["metal"], used=", ".join(loc_name(t) for t in g["tags"])))
    return rows


def pg_bom(c, msp, rows, part, parts_total):
    cols = [("VT", 130), ("Tên chi tiết", 560), ("Cụm", 140), ("SL", 100), ("L×W×T (mm)", 400),
            ("Vật liệu", 640), ("Ghi chú", 600)]
    tbl(msp, 250, PH - 200, cols, [[r["code"], r["name"], r["mod"], r["qty"], r["size"], r["mat"], r["note"]]
                                   for r in rows], 58, f"BẢNG KÊ CHI TIẾT / PARTS LIST ({part}/{parts_total})")
    T(msp, "Quy tắc vật liệu: dày 3–18 mm = VÁN ÉP; dày ≥ 20 mm = LVL. VT có chữ (6A, 6B) = cùng kích "
           "thước, khác lỗ khoan.", (250, 410), h=1.7)
    return "BẢNG KÊ CHI TIẾT", "BILL OF MATERIALS", "—"


def pg_hardware(c, msp):
    hc = Counter(j.hw for j in c.joints for _ in j.pts)
    rows = [[k, HARDWARE[k][0].replace("Ø", "%%c"), ", ".join(map(str, sorted({j.step for j in c.joints if j.hw == k}))),
             hc[k]] for k in HARDWARE if hc[k]]
    y = tbl(msp, 250, PH - 200, [("Mã", 110), ("Phụ kiện", 830), ("Bước", 200), ("SL", 110)], rows, 58,
            "PHỤ KIỆN / HARDWARE")
    # tổng hợp vật liệu
    lvl = ply = 0.0
    nmet = Counter()
    for r in bom_rows(c):
        v = r["L"] * r["W"] * r["T"] / 1e9 * r["qty"]
        if r["metal"]:
            nmet[r["name"]] += r["qty"]
        elif r["mat"].startswith("LVL"):
            lvl += v
        elif r["mat"].startswith("Ván ép"):
            ply += v
    mrows = [["LVL (dày ≥ 20)", f"{lvl:.4f} m³"], ["Ván ép (dày 3–18)", f"{ply:.4f} m³"]]
    mrows += [[k, f"{n} cái"] for k, n in nmet.items()]
    tbl(msp, 250, y - 120, [("Vật liệu", 600), ("Khối lượng tinh", 650)], mrows, 58, "TỔNG HỢP VẬT LIỆU")
    hrows, seen = [], set()
    for (hw, role), (code, desc, dia, dep) in HOLE_SPEC.items():
        if code in seen:
            continue
        seen.add(code)
        hrows.append([code, desc.replace("Ø", "%%c"), f"{dia:g}" if dia else "-", dep])
    tbl(msp, 1600, PH - 200, [("Mã lỗ", 140), ("Mô tả lỗ khoan", 820), ("%%c", 110), ("Sâu", 150)], hrows, 52,
        "KÝ HIỆU LỖ KHOAN / HOLE LEGEND", h=1.55)
    return "PHỤ KIỆN – VẬT LIỆU – KÝ HIỆU LỖ", "HARDWARE / MATERIALS / HOLE LEGEND", "—"


# ---------------------------------------------------------------- trang chi tiết sắt
def pg_metal(c, msp):
    p = c.p
    pa, ph, pt = p["pat_a"], p["pat_h"], p["pat_t"]
    # (1) vị trí lắp: khung ngồi xám + sắt đỏ bung
    seat = [q for q in c.parts if q.module == "M2"]
    offs = {q.tag: ((0, 0, 0) if q.ptype not in METAL_TYPES else q.part_off) for q in seat}
    gray = {q.tag for q in seat if q.ptype not in METAL_TYPES}
    mt = [q.tag for q in seat if q.ptype in METAL_TYPES]
    seat_lab = c.labels_for(mt)
    for code in ("6A", "7A"):
        if code in c.var:
            seat_lab[code] = c.var[code]["tags"]
    exploded(msp, c.parts, c.joints, offs, (250, 1000, 1350, PH - 170), seat_lab, gray=gray, margin=120,
             joint_filter=lambda j: j.hw in "GHK", r=32, label_gap=80)
    T(msp, "VỊ TRÍ LẮP SẮT TRONG KHUNG NGỒI (M2)", (260, PH - 170), h=2.1)
    # (2) PÁT L – 3 hình chiếu 1:2 (k=5)
    k = 5
    code_p = c.t2c["pat_LF"]
    x0, y0 = 1600, 1630
    T(msp, f"PÁT L – VT {code_p} (1:2) – SL {len(c.var[code_p]['tags'])}", (1480, PH - 170), h=2.1)
    rect(msp, x0, y0, x0 + pa * k, y0 + ph * k, layer=METAL_LAYER)          # hình đứng: cánh 1
    msp.add_line((x0 + pt * k, y0), (x0 + pt * k, y0 + ph * k), dxfattribs={"layer": METAL_LAYER})
    hx = [pa * 0.3, pa * 0.75]
    for hxx in hx:
        msp.add_circle((x0 + hxx * k, y0 + ph / 2 * k), 2.5 * k, dxfattribs={"layer": METAL_LAYER})
    dim(msp, (x0, y0 + ph * k + 60), (x0, y0 + ph * k), (x0 + pa * k, y0 + ph * k), k)
    dim(msp, (x0 - 70, y0), (x0, y0), (x0, y0 + ph * k), k, 90)
    dim(msp, (x0, y0 - 60), (x0, y0 + ph * k / 2), (x0 + hx[0] * k, y0 + ph * k / 2), k)
    dim(msp, (x0, y0 - 120), (x0, y0 + ph * k / 2), (x0 + hx[1] * k, y0 + ph * k / 2), k)
    dim(msp, (x0 + pa * k + 60, y0), (x0 + pa * k, y0), (x0 + pa * k, y0 + ph * k / 2), k, 90)
    ty = y0 - 230 - pa * k                                                     # hình bằng: chữ L
    pts = [(x0, ty + pa * k), (x0 + pa * k, ty + pa * k), (x0 + pa * k, ty + (pa - pt) * k),
           (x0 + pt * k, ty + (pa - pt) * k), (x0 + pt * k, ty), (x0, ty)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": METAL_LAYER})
    dim(msp, (x0 - 70, ty), (x0, ty), (x0, ty + pa * k), k, 90)
    dim(msp, (x0 + pa * k + 60, ty), (x0 + pa * k, ty + (pa - pt) * k), (x0 + pa * k, ty + pa * k), k, 90)
    sx = x0 + pa * k + 260                                                     # hình cạnh: cánh 2
    rect(msp, sx, y0, sx + pa * k, y0 + ph * k, layer=METAL_LAYER)
    msp.add_line((sx + (pa - pt) * k, y0), (sx + (pa - pt) * k, y0 + ph * k), dxfattribs={"layer": METAL_LAYER})
    for hxx in hx:
        msp.add_circle((sx + (pa - hxx) * k, y0 + ph / 2 * k), 2.5 * k, dxfattribs={"layer": METAL_LAYER})
    MT(msp, f"Thép SS400 dày {pt:g}, chấn L 90°.\\P4 lỗ %%c5 đột sẵn (2 lỗ/cánh), tâm lỗ giữa chiều cao.\\P"
            "Gốc đo: góc trong pát.\\PSơn tĩnh điện đen.", (sx - 40, y0 - 120), h=1.6, width=760)
    # (3) THANH GIA CỐ – hình đứng + mặt cắt 1:2
    bar = c.by["steel_bar"]
    Lb = bar.box[3] - bar.box[0]
    bw, bh, wall = p["bar_w"], p["bar_h"], p["bar_wall"]
    code_b = c.t2c["steel_bar"]
    kb = 0.5
    bx, by_ = 1480, 760
    T(msp, f"THANH GIA CỐ – VT {code_b} (1:20) – SL 1 – thép hộp {bw:g}×{bh:g}×{wall:g}", (bx, 1080), h=2.0)
    hb = bh * kb * 2                                     # vẽ phóng 2× chiều cao
    rect(msp, bx, by_, bx + Lb * kb, by_ + hb, layer=METAL_LAYER)
    xs = sorted(j.pts[0][0] - bar.box[0] for j in c.joints if j.hw == "K")
    for xk in xs:
        msp.add_line((bx + xk * kb, by_ + hb), (bx + xk * kb, by_ + hb - 20), dxfattribs={"layer": METAL_LAYER})
    edges = [0] + xs + [Lb]
    for a_, b_ in zip(edges, edges[1:]):
        dim(msp, (0, by_ + hb + 60), (bx + a_ * kb, by_ + hb), (bx + b_ * kb, by_ + hb), kb)
    dim(msp, (0, by_ - 70), (bx, by_), (bx + Lb * kb, by_), kb)
    T(msp, "K = vị trí vít tự khoan (1 vít/nan, mặt trên); H = đai ốc hàn M6 ở 2 đầu, tâm tiết diện.",
      (bx, by_ - 190), h=1.55)
    T(msp, "(chiều cao vẽ phóng 2× cho dễ đọc)", (bx, by_ - 250), h=1.45)
    kc = 5
    cx, cyy = PW - 100 - 230, 700
    rect(msp, cx, cyy, cx + bw * kc, cyy + bh * kc, layer=METAL_LAYER)
    rect(msp, cx + wall * kc, cyy + wall * kc, cx + (bw - wall) * kc, cyy + (bh - wall) * kc, layer=METAL_LAYER)
    T(msp, "MẶT CẮT (1:2)", (cx - 60, cyy + bh * kc + 50), h=1.7)
    dim(msp, (cx, cyy - 60), (cx, cyy), (cx + bw * kc, cyy), kc)
    dim(msp, (cx - 60, cyy), (cx, cyy), (cx, cyy + bh * kc), kc, 90)
    # (4) hướng dẫn lắp
    yb = bar.box[1] + bw / 2
    MT(msp, "HƯỚNG DẪN LẮP SẮT (bước 3):\\P"
            f"1. Pát L {code_p}: đặt áp sát 4 góc trong khung ngồi sau khi ghép thanh "
            f"{c.codes_of('seat_fb')}/{c.codes_of('seat_side')}; mép trên thấp hơn mặt khung {p['pat_drop']:g} mm. "
            "Bắt 4 vít G 4×20 (2 vít/cánh) – khoan mồi %%c2.5.\\P"
            f"2. Thanh gia cố {code_b}: đặt mặt {bh:g} đứng, giữa chiều sâu khung (tâm cách mặt trong thanh "
            f"trước {yb - bar.box[1] + bar.box[1] - c.p['seat_t']:g} mm), mặt trên phẳng với đáy nan. "
            "Bắt 2 bulông H M6×70 xuyên thanh hông vào đai ốc hàn đầu thanh.\\P"
            f"3. Bắt nan {c.codes_of('seat_slat')} xong mới bắn vít tự khoan K xuống thanh sắt (1 vít/nan).\\P"
            "4. Sắt sơn tĩnh điện chống gỉ; không hàn tại chỗ.", (250, 940), h=1.7, width=1100)
    return "CHI TIẾT SẮT – PÁT L & THANH GIA CỐ", "STEEL PARTS – VIEWS & INSTALLATION", "ghi trên hình"


# ---------------------------------------------------------------- trang cụm
def pg_module_views(c, msp, m):
    mine = [q for q in c.parts if q.module == m]
    s = ortho(msp, mine, (250, 300, PW - 150, PH - 150), c.proj, kmax=2)
    T(msp, "Nét đỏ = chi tiết sắt. Kích thước là tham số MẪU.", (250, 140), h=1.6)
    i = MODULES[m]
    return f"CỤM {m} {i['vn'].upper()} – HÌNH CHIẾU", f"{i['en'].upper()} – VIEWS", s


def pg_module_exploded(c, msp, m):
    mine = [q for q in c.parts if q.module == m]
    ctx = m == LEG_MODULE
    offs = {q.tag: solo_offset(q) for q in mine}
    gray = set()
    if ctx:
        for q in c.parts:
            if q.module != m:
                offs[q.tag] = (0, 0, 0)
                gray.add(q.tag)
    jf = (lambda j: True) if ctx else (lambda j: c.by[j.a].module == m and c.by[j.b].module == m)
    exploded(msp, c.parts, c.joints, offs, (250, 640, 1650, PH - 150), c.labels_for([q.tag for q in mine]),
             square=c.square_set(), gray=gray, joint_filter=jf)
    codes = list(OrderedDict.fromkeys(c.t2c[q.tag] for q in mine))
    rows = [[r["code"], r["name"], sum(1 for q in mine if c.t2c[q.tag] == r["code"]), r["mat"]]
            for r in bom_rows(c, codes)]
    y = tbl(msp, 1700, PH - 200, [("VT", 120), ("Tên", 400), ("SL", 80), ("Vật liệu", 570)], rows, 52,
            f"CHI TIẾT CỤM {m}", h=1.55)
    grp = OrderedDict()
    for j in c.joints:
        ma, mb = c.by[j.a].module, c.by[j.b].module
        if m not in (ma, mb):
            continue
        other = mb if ma == m else ma
        grp[(j.hw, "Nội bộ" if other == m else f"Với {other}")] = grp.get((j.hw, "Nội bộ" if other == m else f"Với {other}"), 0) + len(j.pts)
    rows2 = [[hw, HARDWARE[hw][0].replace("Ø", "%%c"), w, n] for (hw, w), n in sorted(grp.items())]
    y = tbl(msp, 1700, y - 90, [("Mã", 90), ("Phụ kiện", 680), ("Liên kết", 300), ("SL", 100)], rows2, 52,
            "PHỤ KIỆN", h=1.5)
    ky = max(420, y - 520)
    if y - 80 - ky > 250:
        rect(msp, 1700, ky, 2870 - 100 - 0, y - 80, layer="7-BANG-KE")
        location_key(msp, c.parts, {m}, (1710, ky + 10, 2760, y - 130))
        T(msp, "Vị trí cụm trong sofa", (1720, y - 120), h=1.6)
    si = next(i for i, (mods, _) in enumerate(STEP_MODULES) if m in mods)
    title, txt = c.step_text(si)
    MT(msp, f"BƯỚC {si + 1}: {title}\\P{txt}\\PSố vị trí VUÔNG = cùng KT, khác lỗ.", (250, 600), h=1.65,
       width=1080)
    i = MODULES[m]
    return f"CỤM {m} {i['vn'].upper()} – HÌNH BUNG", f"{i['en'].upper()} – EXPLODED", "không TL"


# ---------------------------------------------------------------- trang gia công chi tiết
def hole_symbol(msp, pos, dia, k, code, through, hidden=False, label=None):
    r = max(dia * k / 2, 9)
    lay = "2-NET-KHUAT" if hidden else "1-NET-THAY"
    msp.add_circle(pos, r, dxfattribs={"layer": lay})
    if through and not hidden:
        msp.add_line((pos[0] - r, pos[1]), (pos[0] + r, pos[1]), dxfattribs={"layer": lay})
        msp.add_line((pos[0], pos[1] - r), (pos[0], pos[1] + r), dxfattribs={"layer": lay})
    elif not hidden:
        msp.add_circle(pos, 2, dxfattribs={"layer": lay})
    if label:
        T(msp, label, (pos[0] + r + 6, pos[1] + r + 4), h=1.4, layer="10-PHU-KIEN")


def pick_scale(limit_w, limit_h, w, h, kmax=10):
    for kk, t in SCALES:
        if kk <= kmax and kk * w <= limit_w and kk * h <= limit_h:
            return kk, t
    return SCALES[-1]


def pg_part(c, msp, code):
    g = c.var[code]
    L, W, Tt = g["dims"]
    holes = g["holes"]
    through = {cd for (cd, _d, _dia, dep) in HOLE_SPEC.values() if dep == "xuyên"}
    # --- tỉ lệ hình chính (mặt A + cạnh C), vùng x 450..2350, y 1110..1890
    k, stxt = pick_scale(1900, 340, L, W + Tt)
    fx, fy = 450, 1760 - k * W
    ty_top = fy - 160
    rect(msp, fx, fy, fx + k * L, fy + k * W)
    rect(msp, fx, ty_top - k * Tt, fx + k * L, ty_top)
    T(msp, f"MẶT A ({stxt})", (fx, fy + k * W + 125), h=1.8)
    T(msp, f"CẠNH C – nhìn từ trên ({stxt})", (fx, ty_top - k * Tt - 140), h=1.7)
    dim(msp, (fx, fy + k * W + 60), (fx, fy + k * W), (fx + k * L, fy + k * W), k)
    dim(msp, (fx - 80, fy), (fx, fy), (fx, fy + k * W), k, 90)
    dim(msp, (fx - 80, ty_top - k * Tt), (fx, ty_top - k * Tt), (fx, ty_top), k, 90)
    msp.add_circle((fx, fy), 14, dxfattribs={"layer": "10-PHU-KIEN"})
    T(msp, "O", (fx - 45, fy - 45), h=1.6, layer="10-PHU-KIEN")
    # --- chi tiết 2 đầu: vùng x 2430..2850
    ke, ste = pick_scale(150, 420, max(Tt, 1), W, kmax=20)
    ex0 = 2470
    ey0 = 1800 - ke * W
    fx0 = ex0 + ke * Tt + 130
    rect(msp, ex0, ey0, ex0 + ke * Tt, ey0 + ke * W)
    rect(msp, fx0, ey0, fx0 + ke * Tt, ey0 + ke * W)
    T(msp, f"ĐẦU E", (ex0, ey0 - 150), h=1.6)
    T(msp, f"ĐẦU F", (fx0, ey0 - 150), h=1.6)
    T(msp, f"({ste})", (ex0, ey0 - 210), h=1.5)
    dim(msp, (ex0, ey0 - 60), (ex0, ey0), (ex0 + ke * Tt, ey0), ke)
    dim(msp, (ex0 - 60, ey0), (ex0, ey0), (ex0, ey0 + ke * W), ke, 90)
    # --- vẽ lỗ
    labeled = set()
    for cd, li, sg, x, y, z in holes:
        th = cd in through
        lab = None
        key = (cd, li, sg)
        if key not in labeled:
            labeled.add(key)
            lab = cd
        if cd in ("K2", "H2"):
            continue
        dia = hole_desc(cd)[1]
        if li == 2:
            hole_symbol(msp, (fx + k * x, fy + k * y), dia, k, cd, th, hidden=sg < 0, label=lab)
        elif li == 1:
            hole_symbol(msp, (fx + k * x, ty_top - k * (Tt - z)), dia, k, cd, th, hidden=sg < 0, label=lab)
        elif sg < 0:
            hole_symbol(msp, (ex0 + ke * z, ey0 + ke * y), dia, ke, cd, th, label=lab)
        else:
            hole_symbol(msp, (fx0 + ke * (Tt - z), ey0 + ke * y), dia, ke, cd, th, label=lab)
    # --- bảng lỗ
    hr = hole_rows(holes)
    avail = 1060 - 420
    rh = max(40, min(54, avail / (len(hr) + 1.5)))
    rows = []
    for r in hr:
        desc, dia, dep = hole_desc(r["code"])
        vals = ", ".join(f"{v:g}" for v in r["vals"])
        rows.append([r["code"], desc.replace("Ø", "%%c"), FACE_DESC[r["face"]],
                     f"{r['fixed']};  {r['axis']} = {vals}", len(r["vals"])])
    if rows:
        tbl(msp, 250, 1060, [("Mã", 100), ("Mô tả lỗ", 900), ("Mặt", 470), ("Toạ độ từ gốc O (mm)", 1050),
                             ("SL", 90)], rows, rh, f"BẢNG LỖ KHOAN – VT {code} (tổng {len(holes)} lỗ)", h=1.45)
    else:
        T(msp, "Không có lỗ khoan.", (250, 1000), h=2)
    # --- nhận dạng biến thể
    name = PART_TYPES[g["ptype"]][0]
    if g["siblings"]:
        others = [s for s in g["siblings"] if s != code]
        x, y = 1500, 1180
        pts = [(x, y + 110), (x - 95, y - 55), (x + 95, y - 55)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "10-PHU-KIEN", "const_width": 5})
        T(msp, code, (x, y + 5), h=2.4, align=TA.MIDDLE_CENTER, layer="10-PHU-KIEN")
        T(msp, f"CÙNG KÍCH THƯỚC VỚI {', '.join(others)} – KHÁC LỖ KHOAN", (x + 140, y + 30), h=2.0, color=1)
        T(msp, f"Ghi mã {code} bằng bút lên mặt B trước khi lắp.", (x + 140, y - 40), h=1.7)
    MT(msp, f"{name} – SL {len(g['tags'])} – {c.material(code)}\\PDùng cho: "
            + ", ".join(loc_name(t) for t in g["tags"])
            + "\\PHệ toạ độ: X dọc chiều dài L, Y dọc rộng W, Z dọc dày T; gốc O góc dưới-trái mặt A. "
              "Ký hiệu: tròn có dấu + = lỗ xuyên; tròn có chấm = lỗ tịt; nét đứt = lỗ ở mặt khuất.",
       (250, 360), h=1.55, width=1080)
    return f"VT {code} – {name.upper()}", f"{PART_TYPES[g['ptype']][1].upper()} – MACHINING", stxt


# ================================================================== lắp ráp bộ trang
def page_list(c):
    pages = [("TONG-THE_HINH-CHIEU", pg_overview_views, ()),
             ("TONG-THE_HINH-BUNG", pg_overview_exploded, ()),
             ("BUOC-LAP_1-3", pg_steps, ([1, 2, 3],)),
             ("BUOC-LAP_4-5", pg_steps, ([4, 5],))]
    rows = bom_rows(c)
    per = 22
    chunks = [rows[i:i + per] for i in range(0, len(rows), per)]
    for i, ch in enumerate(chunks):
        pages.append((f"BOM_{i + 1}", pg_bom, (ch, i + 1, len(chunks))))
    pages.append(("PHU-KIEN_VAT-LIEU", pg_hardware, ()))
    pages.append(("CHI-TIET-SAT", pg_metal, ()))
    for m in MODULES:
        nm = ascii_name(MODULES[m]["vn"])
        pages.append((f"{m}_{nm}_HINH-CHIEU", pg_module_views, (m,)))
        pages.append((f"{m}_{nm}_HINH-BUNG", pg_module_exploded, (m,)))
    for code, g in c.var.items():
        if not g["metal"]:
            pages.append((f"VT{code}_{ascii_name(PART_TYPES[g['ptype']][0])}", pg_part, (code,)))
    return pages


def export_excel(c, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook()
    thin = Side(style="thin")
    bd = Border(left=thin, right=thin, top=thin, bottom=thin)

    def style(ws, widths):
        for row in ws.iter_rows(min_row=1):
            for cl in row:
                cl.border = bd
                cl.alignment = Alignment(vertical="center", wrap_text=True)
        for cl in ws[1]:
            cl.font = Font(bold=True, color="FFFFFF")
            cl.fill = PatternFill("solid", fgColor="305496")
        for col, w in zip("ABCDEFGHIJKLMN", widths):
            ws.column_dimensions[col].width = w

    ws = wb.active
    ws.title = "BOM"
    ws.append(["VT", "Tên (VN)", "Part (EN)", "名称 (CN)", "Cụm", "SL", "Dài L", "Rộng W", "Dày T",
               "Vật liệu (quy tắc)", "Thể tích tinh (m³)", "Ghi chú", "Dùng cho"])
    for r in bom_rows(c):
        i = ws.max_row + 1
        ws.append([r["code"], r["name"], r["en"], r["cn"], r["mod"], r["qty"], r["L"], r["W"], r["T"], r["mat"],
                   "" if r["metal"] else f"=G{i}*H{i}*I{i}/1e9*F{i}", r["note"], r["used"]])
    n = ws.max_row
    ws.append(["", "TỔNG", "", "", "", f"=SUM(F2:F{n})", "", "", "", "", f"=SUM(K2:K{n})"])
    style(ws, [6, 20, 22, 14, 6, 5, 7, 7, 7, 26, 12, 24, 30])
    ws2 = wb.create_sheet("Lỗ khoan")
    ws2.append(["VT", "Mã lỗ", "Mô tả", "Ø", "Sâu", "Mặt", "X (mm)", "Y (mm)", "Z (mm)"])
    from holes import FACE_NAMES
    for code, g in c.var.items():
        for cd, li, sg, x, y, z in sorted(g["holes"], key=lambda h: (h[0], h[1], h[3])):
            desc, dia, dep = hole_desc(cd)
            ws2.append([code, cd, desc, dia, dep, FACE_NAMES[(li, sg)], round(x, 2), round(y, 2), round(z, 2)])
    style(ws2, [6, 7, 40, 6, 7, 6, 9, 9, 9])
    ws3 = wb.create_sheet("Phụ kiện")
    ws3.append(["Mã", "VN", "EN", "CN", "SL"])
    hc = Counter(j.hw for j in c.joints for _ in j.pts)
    for k, (vn, en, cn) in HARDWARE.items():
        ws3.append([k, vn, en, cn, hc[k]])
    style(ws3, [6, 32, 32, 22, 6])
    ws4 = wb.create_sheet("Tham số")
    ws4.append(["Tham số", "Giá trị"])
    for k, v in c.p.items():
        ws4.append([k, v])
    style(ws4, [16, 10])
    wb.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params")
    ap.add_argument("--projection", choices=["first", "third"], default="first")
    ap.add_argument("--out", default="output")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--png", help="thư mục lưu ảnh PNG từng trang (tuỳ chọn)")
    a = ap.parse_args()
    prm = json.load(open(a.params, encoding="utf-8")) if a.params else None
    c = Ctx(prm, a.projection)
    if c.problems:
        print("CẢNH BÁO – điểm liên kết không nằm trên mặt tiếp xúc:", c.problems)
    d4 = os.path.join(a.out, "A4")
    shutil.rmtree(d4, ignore_errors=True)
    os.makedirs(d4)
    pages = page_list(c)
    N = len(pages)
    docs = []
    for i, (name, fn, args) in enumerate(pages):
        doc = setup()
        msp = doc.modelspace()
        tv, te, sc = fn(c, msp, *args)
        dwg = f"SF-A4-{i + 1:02d}"
        frame(msp, tv, te, dwg, sc, f"{i + 1}/{N}", c.proj)
        path = os.path.join(d4, f"{dwg}_{name}.dxf")
        doc.saveas(path)
        docs.append((doc, path))
    export_excel(c, os.path.join(a.out, "SF_BOM.xlsx"))
    if not a.no_pdf:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        cfg = Configuration(background_policy=BackgroundPolicy.WHITE, lineweight_scaling=0.8)
        if a.png:
            os.makedirs(a.png, exist_ok=True)
        with PdfPages(os.path.join(a.out, "SF_A4_BO-BAN-VE.pdf")) as pdf:
            for doc, path in docs:
                fig = plt.figure(figsize=(11.69, 8.27))
                ax = fig.add_axes([0, 0, 1, 1])
                Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace())
                ax.set_xlim(0, PW); ax.set_ylim(0, PH); ax.set_aspect("equal"); ax.axis("off")
                pdf.savefig(fig)
                if a.png:
                    fig.savefig(os.path.join(a.png, os.path.basename(path)[:-4] + ".png"), dpi=150)
                plt.close(fig)
    print(f"Đã tạo {N} trang A4 trong {d4}, PDF gộp và SF_BOM.xlsx")
    for code, g in c.var.items():
        if g["siblings"]:
            print(f"  Biến thể {code}: {', '.join(g['tags'])}")


if __name__ == "__main__":
    main()
