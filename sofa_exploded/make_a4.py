# -*- coding: utf-8 -*-
"""
XUẤT TOÀN BỘ BẢN VẼ A4 (ngang 297×210) – BÓC TÁCH LẮP RÁP KHUNG SOFA
=====================================================================
  01  Tổng thể – hình chiếu (KHÔNG nét khuất) + hướng nhìn phụ từ phía sau
  02  Tổng thể – hình bung (nhãn cụm), tự thêm hướng nhìn phụ nếu có cụm bị che
  03–04  Các bước lắp (kèm danh sách phụ kiện + chiều dài bulông từng bước)
  05+ BOM theo mã biến thể | Phụ kiện + quy tắc ván/bulông + ký hiệu lỗ | Lắp sắt
  Mỗi CỤM đúng 1 trang: hình bung lớn, hướng nhìn phụ (nếu cần), hình chiếu KT bao,
       bảng kê, phụ kiện (chiều dài bulông), hướng dẫn
  Mỗi BIẾN THỂ chi tiết gỗ 1 trang: biên dạng, góc vát, dim tổng, dim vị trí lỗ, Ø lỗ,
       bảng toạ độ, ký hiệu phân biệt biến thể. (Không xuất chi tiết pát sắt.)
Chạy:  python make_a4.py [--params my.json] [--projection third] [--png DIR]
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
import render as R
from geom import angle_deg
from holes import FACE_DESC, diff_holes, face_name, hole_desc, variants
from sofa_model import (BOLT_LEN, HOLE_SPEC, LEG_MODULE, METAL_TYPES, MODULES, PART_TYPES,
                        STEP_MODULES, build, check_overlaps, explode_offset, hw_name, loc_name,
                        material_of, solo_offset)

S = md.S
PW, PH = 297 * S, 210 * S
TB_W, TB_H = 1500, 280
SCALES = [(20, "2:1"), (10, "1:1"), (5, "1:2"), (2, "1:5"), (1, "1:10"), (0.5, "1:20"), (0.2, "1:50")]
METAL_LAYER = "11-SAT"
MAIN_ISO = (1, -1, 1)
AUX_CAND = [(-1, 1, 1), (1, 1, 1), (-1, -1, 1), (1, -1, -1), (-1, 1, -1)]

STEPS_A4 = [
    ("LẮP KHUNG ĐÁY (M1)",
     "Ghép giằng {base_end}, {base_mid} vào đà đáy {base_front}, {base_back} bằng chốt B + keo; vít C ở 2 giằng "
     "đầu. Bắt ke góc tam giác {block} bằng vít E. Đo chéo kiểm tra vuông (lệch ≤ 2 mm)."),
    ("LẮP GÁC TAY (M3, M4)",
     "Ghép trụ {arm_post}, giằng {arm_bot}, {arm_mid}, thanh chéo vát 41° {arm_brace} và thanh {arm_top} bằng chốt "
     "B + keo. Bắt ván hông {arm_panel} bằng vít C. Áp gác tay vào 2 đầu khung đáy, bắt bulông A."),
    ("LẮP KHUNG NGỒI (M2) + SẮT",
     "Ghép thanh {seat_fb}, {seat_side} bằng chốt B. Bắt 4 pát L {pat_L}: ốc 4 chấu M8 vào thanh trước/sau, ốc cấy "
     "M6 vào thanh hông. Đặt thanh gia cố {steel_bar}, bắt bulông H. Bắt nan {seat_slat} (vít C, vít tự khoan K). "
     "Đặt lên khung đáy, vít F; bulông A qua trụ gác tay trước."),
    ("LẮP TỰA LƯNG (M5)",
     "Ghép thanh đứng {back_stile} với thanh {back_bot}, {back_top} bằng chốt B + keo; bắt ván lưng {back_panel} "
     "bằng vít C. Đặt lên đà đáy sau {base_back}, bulông A vào trụ gác tay sau, vít C xuống đà đáy. "
     "Bắt pát nối {pat_flat}: vít G vào trụ, bulông + ốc 4 chấu vào ván lưng."),
    ("LẮP CHÂN (M6)",
     "Lật úp sofa lên mặt phẳng có lót, vặn 6 chân {leg} bằng bulông treo D vào tán cấy. Lật lại, kiểm tra cân "
     "bằng, siết lại toàn bộ bulông A."),
]


def ascii_name(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").upper()


# ================================================================== tiện ích vẽ
def setup():
    doc = md.setup_doc()
    doc.layers.add(METAL_LAYER, color=1, lineweight=35)
    doc.layers.add("12-GOC-VAT", color=1, lineweight=25)
    doc.layers.add("13-KHOANH-VUNG", color=1, lineweight=35, linetype="DASHED")
    ds = doc.dimstyles.new("A4")
    for k, v in dict(dimscale=S, dimtxt=1.6, dimasz=1.4, dimexe=1.0, dimexo=0.8, dimgap=0.5, dimdec=1,
                     dimzin=8, dimtad=1, dimtxsty="VN", dimclrd=1, dimclre=1, dimclrt=7).items():
        ds.dxf.set(k, v)
    return doc


def T(msp, s, pos, h=2.0, align=TA.LEFT, layer="6-CHU", color=None):
    md.text(msp, s, pos, h=h, layer=layer, align=align, color=color)


def MT(msp, s, pos, h=1.8, width=None, layer="6-CHU"):
    return md.mtext(msp, s, pos, h=h, width=width, layer=layer)


def dim(msp, base, p1, p2, k, angle=0):
    if math.dist(p1, p2) < 1:
        return
    msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="A4", override={"dimlfac": 1.0 / k},
                       dxfattribs={"layer": "3-KICH-THUOC"}).render()


def rect(msp, x0, y0, x1, y1, layer="1-NET-THAY", **kw):
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs=dict(layer=layer, **kw))


def tbl(msp, x0, y_top, cols, rows, rh=50, title=None, h=1.5):
    width = sum(w for _, w in cols)
    if title:
        T(msp, title, (x0, y_top + 20), h=2.0, layer="7-BANG-KE")
    y = y_top
    for r in [[c for c, _ in cols]] + rows:
        x = x0
        for (_, w), cell in zip(cols, r):
            rect(msp, x, y - rh, x + w, y, layer="7-BANG-KE")
            s = str(cell)
            maxc = int(w / (h * S * 0.8)) - 1
            if len(s) > maxc > 3:
                s = s[:maxc - 1] + "…"
            T(msp, s, (x + 10, y - rh / 2), h=h, layer="7-BANG-KE", align=TA.MIDDLE_LEFT)
            x += w
        y -= rh
    rect(msp, x0, y, x0 + width, y_top, layer="0-KHUNG-BANVE")
    return y


def balloon(msp, c, label, anchor, r=34, square=False, h=1.8, layer="5-SO-VI-TRI"):
    if square:
        rect(msp, c[0] - r, c[1] - r, c[0] + r, c[1] + r, layer=layer)
    else:
        msp.add_circle(c, r, dxfattribs={"layer": layer})
    T(msp, label, c, h=h if len(label) < 3 else h * 0.82, align=TA.MIDDLE_CENTER, layer=layer)
    dx, dy = anchor[0] - c[0], anchor[1] - c[1]
    L = math.hypot(dx, dy)
    if L > r:
        msp.add_line((c[0] + dx / L * r, c[1] + dy / L * r), anchor, dxfattribs={"layer": layer})
        msp.add_circle(anchor, 5, dxfattribs={"layer": layer})


def hw_tag(msp, pos, code, a=24):
    pts = [(pos[0] + a * math.cos(math.radians(30 + 60 * i)), pos[1] + a * math.sin(math.radians(30 + 60 * i)))
           for i in range(6)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "10-PHU-KIEN"})
    T(msp, code, pos, h=1.5 if len(code) > 1 else 1.8, align=TA.MIDDLE_CENTER, layer="10-PHU-KIEN")


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
    T(msp, title_vn, (x0 + 25, y1 - 55), h=2.5 if len(title_vn) < 40 else 2.1)
    T(msp, title_en, (x0 + 25, y1 - 105), h=1.5)
    T(msp, "Góc chiếu " + ("1 (TCVN/ISO-E)" if proj == "first" else "3 (ISO-A)") + " – đơn vị mm",
      (x0 + 25, y0 + 132), h=1.4)
    md.projection_symbol(msp, (x1 - 230, y1 - 75), proj, 0.35)
    for i, (k, v) in enumerate([("Tỉ lệ", scale), ("Tờ", sheet), ("Số BV", dwg), ("Người vẽ / Ngày", "")]):
        T(msp, k, (x0 + 375 * i + 15, y0 + 95), h=1.3)
        T(msp, v, (x0 + 375 * i + 15, y0 + 35), h=1.9)


def layer_of(q, gray=False, plain=False):
    if gray:
        return "8-CUM-DA-LAP"
    if q.ptype in METAL_TYPES:
        return METAL_LAYER
    return "1-NET-THAY" if plain else md.mod_layer(q.module)


def items_of(parts, off=lambda q: (0, 0, 0), layer=lambda q: layer_of(q)):
    return [(f"{q.tag}#{i}", s.moved(off(q)), layer(q)) for q in parts for i, s in enumerate(q.solids)]


def _union(gs):
    from shapely.ops import unary_union
    return unary_union([g for g in gs if not g.is_empty])


def by_tag(vis):
    out = {}
    for k, g in vis.items():
        out.setdefault(k.split("#")[0], []).append(g)
    return {t: _union(gs) for t, gs in out.items()}


def bbox_parts(parts):
    bs = [q.box for q in parts]
    return [min(b[k] for b in bs) for k in range(3)] + [max(b[k + 3] for b in bs) for k in range(3)]


# ================================================================== hình chiếu vuông góc
def chain_edges(vals, k, min_paper=60):
    vals = sorted(set(round(v, 1) for v in vals))
    if len(vals) < 2:
        return None
    gap = min_paper / k
    out = [vals[0]]
    for v in vals[1:-1]:
        if v - out[-1] >= gap and vals[-1] - v >= gap:
            out.append(v)
    out.append(vals[-1])
    return out


def ortho(msp, parts, region, proj, kmax=10, chain=True, hidden=False, pad=(320, 150, 290, 300), titles=True,
          th=1.9):
    x0b, y0b, z0b, x1b, y1b, z1b = bbox_parts(parts)
    dx, dy, dz = x1b - x0b, y1b - y0b, z1b - z0b
    rx0, ry0, rx1, ry1 = region
    g, top, bot, sm = pad
    k, stxt = SCALES[-1]
    for kk, t in SCALES:
        if kk <= kmax and kk * (dx + dy) + g + 2 * sm <= rx1 - rx0 and kk * (dz + dy) + g + top + bot <= ry1 - ry0:
            k, stxt = kk, t
            break
    side = "left" if proj == "first" else "right"
    X0 = rx0 + sm
    if proj == "first":
        Yf = ry1 - top - k * dz
        Yt = Yf - g - k * dy
    else:
        Yt = ry1 - top - k * dy
        Yf = Yt - g - k * dz
    Xs = X0 + k * dx + g
    fv = R.View(R.ORTHO["front"], (X0 - k * x0b, Yf - k * z0b), k)
    tv = R.View(R.ORTHO["top"], (X0 - k * x0b, Yt - k * y0b), k)
    sv = R.View(R.ORTHO[side], ((Xs + k * y1b) if side == "left" else (Xs - k * y0b), Yf - k * z0b), k)
    it = items_of(parts, layer=lambda q: layer_of(q, plain=True))
    for v in (fv, tv, sv):
        R.render(msp, v, it, hidden=hidden)
    o, oc = 65, 70
    fl, fr, fb, ft = X0, X0 + k * dx, Yf, Yf + k * dz
    dim(msp, (fl, ft + o), (fl, ft), (fr, ft), k)
    dim(msp, (fl - o, fb), (fl, fb), (fl, ft), k, 90)
    if chain:
        ch = chain_edges([q.box[2] for q in parts] + [z0b, z1b], k)
        if ch and 3 <= len(ch) <= 14:
            for a, b in zip(ch, ch[1:]):
                dim(msp, (fr + o, 0), (fr, Yf + k * (a - z0b)), (fr, Yf + k * (b - z0b)), k, 90)
    tl, tr, tb, tt = X0, X0 + k * dx, Yt, Yt + k * dy
    dim(msp, (tl - o, tb), (tl, tb), (tl, tt), k, 90)
    off = o
    if chain:
        ch = chain_edges([q.box[0] for q in parts] + [x0b, x1b], k)
        if ch and 3 <= len(ch) <= 14:
            for a, b in zip(ch, ch[1:]):
                dim(msp, (0, tb - off), (X0 + k * (a - x0b), tb), (X0 + k * (b - x0b), tb), k)
            off += oc
    dim(msp, (0, tb - off), (tl, tb), (tr, tb), k)
    sl, sr = Xs, Xs + k * dy
    soff = o
    if chain:
        ch = chain_edges([q.box[1] for q in parts] + [y0b, y1b], k)
        if ch and 3 <= len(ch) <= 14:
            for a, b in zip(ch, ch[1:]):
                ua = (Xs + k * (y1b - a)) if side == "left" else (Xs + k * (a - y0b))
                ub = (Xs + k * (y1b - b)) if side == "left" else (Xs + k * (b - y0b))
                dim(msp, (0, fb - soff), (ua, fb), (ub, fb), k)
            soff += oc
    dim(msp, (0, fb - soff), (sl, fb), (sr, fb), k)
    dim(msp, (sr + o, fb), (sr, fb), (sr, ft), k, 90)
    if titles:
        nm = {"left": "HÌNH CHIẾU CẠNH TRÁI", "right": "HÌNH CHIẾU CẠNH PHẢI"}
        T(msp, f"HÌNH CHIẾU ĐỨNG ({stxt})", (fl, fb - 130 if proj == "first" else fb - 200), h=th)
        T(msp, f"HÌNH CHIẾU BẰNG ({stxt})", (tl, tb - off - 120), h=th)
        T(msp, f"{nm[side]} ({stxt})", (sl, fb - soff - 120), h=th)
    return stxt, dict(top_bottom=tb - off - 140, side_bottom=fb - soff - 140, right=max(tr, sr) + 120)


# ================================================================== hình trục đo + hướng nhìn phụ
def draw_iso(msp, c, offs, region, labels, dirs=MAIN_ISO, square=(), gray=(), margin=150, joint_filter=None,
             r=32, gap=100, only_labels=None, title=None, circles=None, ckey=None):
    shown = [q for q in c.parts if q.tag in offs]
    it = items_of(shown, off=lambda q: offs[q.tag], layer=lambda q: layer_of(q, gray=q.tag in gray))
    v = R.fit(R.iso_dirs(*dirs), [s for _, s, _ in it], region, margin)
    vis = R.render(msp, v, it)
    vt = by_tag(vis)
    tags_pos = []
    for j in c.joints:
        if j.a not in offs or j.b not in offs or (joint_filter and not joint_filter(j)):
            continue
        for pt in j.pts:
            a = v.P(tuple(pt[i] + offs[j.a][i] for i in range(3)))
            b = v.P(tuple(pt[i] + offs[j.b][i] for i in range(3)))
            d = math.dist(a, b)
            if d > 12:
                msp.add_line(a, b, dxfattribs={"layer": "4-DUONG-BUNG"})
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if d > 100 and all(math.dist(m, t[0]) > 110 for t in tags_pos):
                    tags_pos.append((m, j.hw))
    anchors = {}
    for lab, tags in labels.items():
        if only_labels is not None and lab not in only_labels:
            continue
        best = max(tags, key=lambda t: vt[t].area if t in vt else -1)
        if best in vt and not vt[best].is_empty:
            rp = vt[best].representative_point()
            anchors[lab] = v.sheet((rp.x, rp.y))
    ol = R.to_sheet(v, _union([g for k, g in vis.items() if k.split("#")[0] not in gray]))
    bpos = []
    if anchors:
        for lab, cpos in md.place_balloons(anchors, ol, gap, r).items():
            balloon(msp, cpos, lab, anchors[lab], r=r, square=lab in square)
            bpos.append(cpos)
    for m_, hw in tags_pos:
        if all(math.dist(m_, b_) > r + 40 for b_ in bpos):
            hw_tag(msp, m_, hw)
    if circles is None:
        circles = [pt for pt in c.detail_points if pt[1] in offs]
    for lab, tg, pt in circles:
        if tg not in offs:
            continue
        o = offs[tg]
        cen = v.P(tuple(pt[i] + o[i] for i in range(3)))
        draw_khoanh(msp, cen, lab)
        if ckey:
            c.report.setdefault("circles", {}).setdefault(ckey, []).append((lab, tg))
    if title:
        T(msp, title, (region[0] + 10, region[3] - 10), h=1.8)
    return v, vt


def draw_khoanh(msp, cen, lab, R=62):
    """Vòng khoanh vùng chỗ lắp pát + ký hiệu chi tiết."""
    msp.add_circle(cen, R, dxfattribs={"layer": "13-KHOANH-VUNG"})
    q = (cen[0] + R * 0.72 + 30, cen[1] + R * 0.72 + 30)
    msp.add_line((cen[0] + R * 0.72, cen[1] + R * 0.72), q, dxfattribs={"layer": "13-KHOANH-VUNG"})
    rect(msp, q[0] - 4, q[1] - 22, q[0] + 50, q[1] + 22, layer="13-KHOANH-VUNG")
    T(msp, lab, (q[0] + 23, q[1]), h=1.9, align=TA.MIDDLE_CENTER, layer="13-KHOANH-VUNG", color=1)


def hidden_labels(c, offs, labels, dirs=MAIN_ISO, thr=0.15):
    shown = [q for q in c.parts if q.tag in offs]
    it = items_of(shown, off=lambda q: offs[q.tag])
    fr, _ = R.visibility(R.View(R.iso_dirs(*dirs)), it)
    ft = {}
    for k, f in fr.items():
        t = k.split("#")[0]
        ft[t] = max(ft.get(t, 0), f)
    return [lab for lab, tags in labels.items() if max(ft.get(t, 0) for t in tags) < thr]


def best_aux(c, offs, labels, need):
    best, score = None, -1
    for d in AUX_CAND:
        h = hidden_labels(c, offs, {k: labels[k] for k in need}, dirs=d)
        sc = len(need) - len(h)
        if sc > score:
            best, score = d, sc
    return best


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
        self.report = {}
        self.details = detail_specs(self)
        self.detail_points = [(d["label"], tg, pt) for d in self.details for tg, pt in d["points"]]

    def codes_of(self, ptype):
        return "/".join(c for c, g in self.var.items() if g["ptype"] == ptype)

    def step_text(self, i):
        title, txt = STEPS_A4[i]
        txt = txt.format(**{pt: self.codes_of(pt) for pt in PART_TYPES})
        hc = Counter(hw_name(j) for j in self.joints if j.step == i + 1 for _ in j.pts)
        hw = "; ".join(f"{n}× {k}" for k, n in hc.items())
        return title, txt, hw

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


# ================================================================== trang tổng
def pg_overview_views(c, msp):
    s, geo = ortho(msp, c.parts, (250, 300, PW - 150, PH - 150), c.proj, kmax=1, chain=False)
    region = (max(1700, geo["right"] - 900), 420, PW - 120, min(geo["side_bottom"], 1250))
    rect(msp, *region, layer="7-BANG-KE")
    offs = {q.tag: (0, 0, 0) for q in c.parts}
    draw_iso(msp, c, offs, (region[0] + 10, region[1] + 10, region[2] - 10, region[3] - 60), OrderedDict(),
             dirs=(-1, 1, 1), margin=40, circles=[])
    T(msp, "HƯỚNG NHÌN PHỤ: từ SAU-TRÁI-TRÊN (thấy ván lưng, pát nối)", (region[0] + 15, region[3] - 45), h=1.6)
    T(msp, "Không vẽ nét khuất; nét đỏ = sắt; kích thước là tham số MẪU.", (250, 140), h=1.5)
    c.report.setdefault("assembly_pages", []).append("overview_views")
    return "TỔNG THỂ – HÌNH CHIẾU", "OVERALL – VIEWS (NO HIDDEN LINES)", s


def pg_overview_exploded(c, msp):
    offs = {q.tag: explode_offset(q, c.p, "full") for q in c.parts}
    labels = OrderedDict((m, [q.tag for q in c.parts if q.module == m and q.ptype not in METAL_TYPES])
                         for m in MODULES)
    for code, g in c.var.items():
        if g["metal"]:
            labels[code] = g["tags"]
    hid = hidden_labels(c, offs, labels)
    main = (250, 420, 2150, PH - 150) if not hid else (250, 760, 2150, PH - 150)
    draw_iso(msp, c, offs, main, labels, r=38, gap=110, ckey="overview_exploded")
    if hid:
        d = best_aux(c, offs, labels, hid)
        reg = (250, 420, 2150, 740)
        rect(msp, *reg, layer="7-BANG-KE")
        gray = {q.tag for q in c.parts if not any(q.tag in labels[h] for h in hid)}
        draw_iso(msp, c, offs, (reg[0], reg[1], reg[2], reg[3] - 50), labels, dirs=d, gray=gray, only_labels=hid,
                 circles=[],
                 r=30, gap=70, margin=60, title=f"HƯỚNG NHÌN PHỤ ({R.ISO_NAMES.get(d, '')}): " + ", ".join(hid))
    rows = [[m, f"{i['vn']} / {i['en']}"] for m, i in MODULES.items()]
    rows += [[code, f"{PART_TYPES[g['ptype']][0]} (sắt)"] for code, g in c.var.items() if g["metal"]]
    y = tbl(msp, 2200, PH - 200, [("Nhãn", 140), ("Cụm / chi tiết", 520)], rows, 50, "CHÚ GIẢI")
    MT(msp, "Lục giác = phụ kiện. Nét chấm gạch = đường bung (vị trí, phương lắp). Màu theo cụm; sắt màu đỏ. "
            "Không vẽ nét khuất.", (2200, y - 40), h=1.6, width=650)
    c.report.setdefault("assembly_pages", []).append("overview_exploded")
    return "TỔNG THỂ – HÌNH BUNG", "OVERALL – EXPLODED ISOMETRIC", "không TL"


def draw_step(c, msp, step, region):
    acc, upto = set(), {}
    for i, (mods, _) in enumerate(STEP_MODULES):
        acc |= set(mods)
        upto[i + 1] = set(acc)
    new = set(STEP_MODULES[step - 1][0])
    level = STEP_MODULES[step - 1][1]
    offs, gray = {}, set()
    for q in c.parts:
        if q.module not in upto[step]:
            continue
        if q.module in new:
            o = explode_offset(q, c.p, level)
            if q.module == LEG_MODULE:
                o = (0, 0, -c.p["ex_leg"] * 0.8)
            if q.ptype in METAL_TYPES or q.ptype in ("arm_panel", "back_panel"):
                o = tuple(a + b for a, b in zip(o, q.part_off))
            offs[q.tag] = o
        else:
            offs[q.tag] = (0, 0, 0)
            gray.add(q.tag)
    newtags = [q.tag for q in c.parts if q.module in new]
    draw_iso(msp, c, offs, region, c.labels_for(newtags), square=c.square_set(), gray=gray, margin=110,
             joint_filter=lambda j: j.step == step, r=30, gap=75, ckey=f"step {step}",
             circles=[p_ for p_ in c.detail_points if p_[1] in newtags])


def pg_steps(c, msp, steps):
    n = 3
    w = (PW - 100 - 250) / n
    for i, st in enumerate(steps):
        x = 250 + i * w
        draw_step(c, msp, st, (x + 10, 780, x + w - 10, PH - 150))
        title, txt, hw = c.step_text(st - 1)
        msp.add_circle((x + 45, 720), 38, dxfattribs={"layer": "6-CHU", "color": 1})
        T(msp, str(st), (x + 45, 720), h=3.2, align=TA.MIDDLE_CENTER, color=1)
        T(msp, title, (x + 100, 710), h=1.9)
        MT(msp, txt + "\\PPhụ kiện: " + hw, (x + 10, 650), h=1.5, width=w - 40)
        if i:
            msp.add_line((x, 120), (x, PH - 120), dxfattribs={"layer": "0-KHUNG-BANVE"})
    if len(steps) < n:
        x = 250 + len(steps) * w
        MT(msp, "GHI CHÚ CHUNG:\\P1. Kích thước là tham số MẪU – đối chiếu mẫu thật trước khi sản xuất.\\P"
                "2. Chốt B bôi keo PVA, kẹp ép ≥ 30 phút.\\P3. Bulông A chỉ siết chặt sau khi lắp đủ cụm.\\P"
                "4. Số vị trí khung VUÔNG = chi tiết cùng kích thước nhưng KHÁC LỖ – kiểm tra mã trước khi lắp.\\P"
                "5. Màu xám = phần đã lắp ở bước trước. Không vẽ nét khuất.", (x + 20, PH - 230), h=1.7, width=w - 60)
        msp.add_line((x, 120), (x, PH - 120), dxfattribs={"layer": "0-KHUNG-BANVE"})
    c.report.setdefault("assembly_pages", []).append(f"steps{steps}")
    return f"CÁC BƯỚC LẮP {steps[0]}–{steps[-1]}", "ASSEMBLY SEQUENCE", "không TL"


def bom_rows(c, codes=None):
    rows = []
    for code, g in c.var.items():
        if codes is not None and code not in codes:
            continue
        L, W, Tt = g["dims"]
        note = ("Cùng KT – KHÁC LỖ: " + "/".join(g["siblings"])) if g["siblings"] else ""
        if g["metal"]:
            note = "Sắt – xem trang Lắp sắt"
        rows.append(dict(code=code, name=PART_TYPES[g["ptype"]][0], en=PART_TYPES[g["ptype"]][1],
                         cn=PART_TYPES[g["ptype"]][2], mod=g["module"], qty=len(g["tags"]),
                         size=f"{L:.4g}×{W:.4g}×{Tt:.4g}", mat=c.material(code), note=note, L=L, W=W, T=Tt,
                         metal=g["metal"], used=", ".join(loc_name(t) for t in g["tags"])))
    return rows


def pg_bom(c, msp, rows, part, total):
    cols = [("VT", 120), ("Tên chi tiết", 560), ("Cụm", 130), ("SL", 90), ("L×W×T (mm)", 400),
            ("Vật liệu", 560), ("Ghi chú", 700)]
    tbl(msp, 250, PH - 200, cols, [[r["code"], r["name"], r["mod"], r["qty"], r["size"], r["mat"], r["note"]]
                                   for r in rows], 56, f"BẢNG KÊ CHI TIẾT / PARTS LIST ({part}/{total})", h=1.55)
    T(msp, "Vật liệu: dày 3–18 mm = VÁN ÉP; dày ≥ 20 mm = LVL. VT có chữ (6A, 6B) = cùng kích thước, khác lỗ.",
      (250, 410), h=1.6)
    return "BẢNG KÊ CHI TIẾT", "BILL OF MATERIALS", "—"


def pg_hardware(c, msp):
    hc = Counter((j.hw, j.length) for j in c.joints for _ in j.pts)
    rows = []
    for (k, L), n in sorted(hc.items(), key=lambda x: (x[0][0], x[0][1] or 0)):
        steps = sorted({j.step for j in c.joints if j.hw == k and j.length == L})
        rows.append([k, hw_name(k, L).replace("Ø", "%%c"), ", ".join(map(str, steps)), n])
    y = tbl(msp, 250, PH - 200, [("Mã", 100), ("Phụ kiện", 900), ("Bước", 160), ("SL", 100)], rows, 50,
            "PHỤ KIỆN / HARDWARE", h=1.5)
    rule = [[f"Ván {t} mm", f"Bulông dài {L} mm"] for t, L in BOLT_LEN.items()]
    rule += [["Lỗ %%c10", "Ốc 4 chấu M8 (bulông M8)"], ["Lỗ %%c8", "Ốc cấy M6 (bulông M6)"]]
    y = tbl(msp, 250, y - 110, [("Điều kiện", 400), ("Phụ kiện dùng", 860)], rule, 50,
            "QUY TẮC PHỤ KIỆN BẮT PÁT VÀO VÁN", h=1.5)
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
    mrows = [["LVL (dày ≥ 20)", f"{lvl:.4f} m³ (khung bao)"], ["Ván ép (dày 3–18)", f"{ply:.4f} m³"]]
    mrows += [[k, f"{n} cái"] for k, n in nmet.items()]
    tbl(msp, 250, y - 110, [("Vật liệu", 500), ("Khối lượng tinh", 760)], mrows, 50, "TỔNG HỢP VẬT LIỆU", h=1.5)
    hrows, seen = [], set()
    for (c_, desc, dia, dep) in HOLE_SPEC.values():
        if c_ in seen:
            continue
        seen.add(c_)
        hrows.append([c_, desc.replace("Ø", "%%c"), f"{dia:g}" if dia else "-", dep])
    tbl(msp, 1600, PH - 200, [("Mã lỗ", 130), ("Mô tả lỗ khoan", 850), ("%%c", 100), ("Sâu", 140)], hrows, 48,
        "KÝ HIỆU LỖ KHOAN", h=1.4)
    return "PHỤ KIỆN – QUY TẮC – VẬT LIỆU", "HARDWARE / RULES / MATERIALS", "—"


# ================================================================== trang CỤM (1 cụm = 1 trang)
def pg_module(c, msp, m):
    mine = [q for q in c.parts if q.module == m]
    ctx = m == LEG_MODULE
    offs = {q.tag: solo_offset(q) for q in mine}
    gray = set()
    if ctx:
        for q in c.parts:
            if q.module != m:
                offs[q.tag] = (0, 0, 0)
                gray.add(q.tag)
    labels = c.labels_for([q.tag for q in mine])
    jf = (lambda j: True) if ctx else (lambda j: c.by[j.a].module == m and c.by[j.b].module == m)
    hid = hidden_labels(c, offs, labels)
    main = (250, 640, 1820, PH - 150) if not hid else (250, 1020, 1820, PH - 150)
    i = MODULES[m]
    draw_iso(msp, c, offs, main, labels, square=c.square_set(), gray=gray, joint_filter=jf, r=32, gap=100,
             title=f"HÌNH BUNG LẮP RÁP CỤM {m} – {i['vn'].upper()}", ckey=f"module {m}",
             circles=[p_ for p_ in c.detail_points if p_[1] in offs and c.by[p_[1]].module == m])
    aux_used = None
    if hid:
        d = best_aux(c, offs, labels, hid)
        aux_used = d
        reg = (250, 640, 1820, 1000)
        rect(msp, *reg, layer="7-BANG-KE")
        g2 = set(gray) | {q.tag for q in mine if not any(q.tag in labels[h] for h in hid)}
        draw_iso(msp, c, offs, (reg[0], reg[1], reg[2], reg[3] - 45), labels, dirs=d, square=c.square_set(),
                 gray=g2, only_labels=hid, r=28, gap=60, margin=50, circles=[],
                 title=f"HƯỚNG NHÌN PHỤ ({R.ISO_NAMES.get(d, '')}) – chi tiết bị che: " + ", ".join(hid))
    x0 = 1860
    s, _ = ortho(msp, mine, (x0, 1400, PW - 190, PH - 140), c.proj, kmax=1, chain=False,
                 pad=(150, 90, 130, 140), titles=False)
    T(msp, f"KÍCH THƯỚC BAO CỤM – đứng / bằng / cạnh ({s})", (x0, PH - 135), h=1.5)
    codes = list(OrderedDict.fromkeys(c.t2c[q.tag] for q in mine))
    rows = [[r["code"], r["name"], sum(1 for q in mine if c.t2c[q.tag] == r["code"]), r["size"], r["mat"]]
            for r in bom_rows(c, codes)]
    y = tbl(msp, x0, 1330, [("VT", 95), ("Tên", 330), ("SL", 60), ("L×W×T", 280), ("Vật liệu", 245)], rows, 44,
            f"CHI TIẾT CỤM {m}", h=1.3)
    grp = OrderedDict()
    for j in c.joints:
        ma, mb = c.by[j.a].module, c.by[j.b].module
        if m not in (ma, mb):
            continue
        other = mb if ma == m else ma
        key = (hw_name(j), j.hw, "Nội bộ" if other == m else f"Với {other}")
        grp[key] = grp.get(key, 0) + len(j.pts)
    rows2 = [[hw, nm.replace("Ø", "%%c"), w, n] for (nm, hw, w), n in sorted(grp.items(), key=lambda x: x[0][1])]
    tbl(msp, x0, y - 75, [("Mã", 80), ("Phụ kiện (chiều dài theo ván)", 640), ("Liên kết", 190), ("SL", 100)],
        rows2, 44, "PHỤ KIỆN", h=1.25)
    si = next(k for k, (mods, _) in enumerate(STEP_MODULES) if m in mods)
    title, txt, hw = c.step_text(si)
    MT(msp, f"BƯỚC {si + 1}: {title}. {txt}\\PSố vị trí khung VUÔNG = cùng KT, khác lỗ – xem trang chi tiết.",
       (250, 600), h=1.5, width=1080)
    c.report.setdefault("module_pages", {}).setdefault(m, 0)
    c.report["module_pages"][m] += 1
    c.report.setdefault("module_labels", {})[m] = list(labels)
    c.report.setdefault("aux", {})[m] = (hid, aux_used)
    c.report.setdefault("assembly_pages", []).append(f"module {m}")
    return f"CỤM {m} – {i['vn'].upper()}", f"{i['en'].upper()} – ASSEMBLY (1 TRANG/CỤM)", f"KT bao {s}"


# ================================================================== trang CHI TIẾT GỖ
def pick_scale(limit_w, limit_h, w, h, kmax=10):
    for kk, t in SCALES:
        if kk <= kmax and kk * w <= limit_w and kk * h <= limit_h:
            return kk, t
    return SCALES[-1]


def hole_symbol(msp, pos, dia, k, through, hidden=False):
    r = max(dia * k / 2, 8)
    lay = "2-NET-KHUAT" if hidden else "1-NET-THAY"
    msp.add_circle(pos, r, dxfattribs={"layer": lay})
    if not hidden:
        if through:
            msp.add_line((pos[0] - r, pos[1]), (pos[0] + r, pos[1]), dxfattribs={"layer": lay})
            msp.add_line((pos[0], pos[1] - r), (pos[0], pos[1] + r), dxfattribs={"layer": lay})
        else:
            msp.add_circle(pos, 2, dxfattribs={"layer": lay})
    return r


def angle_marks(msp, poly, fx, fy, k):
    n = len(poly)
    out, placed = [], []
    for i in range(n):
        p0, p1, p2 = poly[i - 1], poly[i], poly[(i + 1) % n]
        a = angle_deg(p0, p1, p2)
        if abs(a - 90) < 0.5 or abs(a - 180) < 0.5:
            continue
        a0 = math.degrees(math.atan2(p0[1] - p1[1], p0[0] - p1[0]))
        a2 = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
        st, en = (a0, a2) if (a2 - a0) % 360 <= 180 else (a2, a0)
        e1, e2 = math.dist(p0, p1), math.dist(p1, p2)
        rr = max(min(140, 0.35 * min(e1, e2) * k), 45)
        cc = (fx + k * p1[0], fy + k * p1[1])
        msp.add_arc(cc, rr, st, st + (en - st) % 360, dxfattribs={"layer": "12-GOC-VAT"})
        mid = math.radians(st + ((en - st) % 360) / 2)
        lp = (cc[0] + (rr + 45) * math.cos(mid), cc[1] + (rr + 45) * math.sin(mid))
        if any(math.dist(lp, q) < 110 for q in placed):          # trùng chữ -> đặt ra ngoài đỉnh
            lp = (cc[0] - 70 * math.cos(mid), cc[1] - 70 * math.sin(mid))
        placed.append(lp)
        T(msp, f"{a:.1f}°".replace(".0°", "°"), lp, h=1.6, align=TA.MIDDLE_CENTER, layer="12-GOC-VAT", color=1)
        out.append(round(a, 1))
    return out


def pg_part(c, msp, code):
    g = c.var[code]
    L, W, Tt = g["dims"]
    poly, holes = g["poly"], g["holes"]
    through = {cd for (cd, _d, _dia, dep) in HOLE_SPEC.values() if dep == "xuyên"}
    rect_like = len(poly) == 4 and all(abs(angle_deg(poly[i - 1], poly[i], poly[(i + 1) % 4]) - 90) < 0.5
                                       for i in range(4))
    k, stxt = pick_scale(1650, 330, L, W + Tt)
    fx, fy = 470, 1740 - k * W
    ty_top = fy - 230
    msp.add_lwpolyline([(fx + k * u, fy + k * v) for u, v in poly], close=True, dxfattribs={"layer": "1-NET-THAY"})
    rect(msp, fx, ty_top - k * Tt, fx + k * L, ty_top)
    for u, v in poly:
        if 0.5 < u < L - 0.5:
            msp.add_line((fx + k * u, ty_top - k * Tt), (fx + k * u, ty_top), dxfattribs={"layer": "1-NET-THAY"})
    T(msp, f"MẶT A – BIÊN DẠNG ({stxt})", (fx, 1890), h=1.7)
    if ty_top - k * Tt - 170 > 1110:
        T(msp, f"CẠNH C – nhìn từ trên ({stxt})", (fx, ty_top - k * Tt - 170), h=1.5)
    else:
        T(msp, f"CẠNH C – nhìn từ trên ({stxt})", (fx + k * L + 60, ty_top - k * Tt / 2), h=1.5,
          align=TA.MIDDLE_LEFT)
    top_y = fy + k * W
    dim(msp, (fx, top_y + 60), (fx, top_y), (fx + k * L, top_y), k)
    dim(msp, (fx - 75, fy), (fx, fy), (fx, top_y), k, 90)
    dim(msp, (fx - 75, ty_top - k * Tt), (fx, ty_top - k * Tt), (fx, ty_top), k, 90)
    angles = []
    if not rect_like:
        us = sorted({round(u, 1) for u, v in poly})
        for a, b in zip(us, us[1:]):
            dim(msp, (0, top_y + 125), (fx + k * a, top_y), (fx + k * b, top_y), k)
        vs = sorted({round(v, 1) for u, v in poly})
        for a, b in zip(vs, vs[1:]):
            dim(msp, (fx + k * L + 70, 0), (fx + k * L, fy + k * a), (fx + k * L, fy + k * b), k, 90)
        angles = angle_marks(msp, poly, fx, fy, k)
    msp.add_circle((fx, fy), 13, dxfattribs={"layer": "10-PHU-KIEN"})
    T(msp, "O", (fx - 40, fy - 40), h=1.5, layer="10-PHU-KIEN")
    ke, ste = pick_scale(140, 380, max(Tt, 1), W, kmax=20)
    ex0, ey0 = 2390, 1780 - ke * W
    fx0 = ex0 + ke * Tt + 150
    rect(msp, ex0, ey0, ex0 + ke * Tt, ey0 + ke * W)
    rect(msp, fx0, ey0, fx0 + ke * Tt, ey0 + ke * W)
    T(msp, "ĐẦU E", (ex0, 1880), h=1.5)
    T(msp, "ĐẦU F", (fx0, 1880), h=1.5)
    T(msp, f"({ste})", (ex0, ey0 - 210), h=1.4)
    dim(msp, (ex0, ey0 - 60), (ex0, ey0), (ex0 + ke * Tt, ey0), ke)
    dim(msp, (ex0 - 130, ey0), (ex0, ey0), (ex0, ey0 + ke * W), ke, 90)
    groups = OrderedDict()
    uA, vA, uC, wC = [], [], [], []
    vE, wE, vF, wF = [], [], [], []
    for cd, n, (u, v, w) in holes:
        if cd in ("K2", "H2", "PM"):
            continue
        fn = face_name(n, (u, v, w), g["dims"])
        dia = hole_desc(cd)[1]
        th = cd in through
        if fn in ("A", "B"):
            pos = (fx + k * u, fy + k * v)
            rr = hole_symbol(msp, pos, dia, k, th, hidden=fn == "B")
            uA.append(u); vA.append(v)
        elif fn in ("C", "D"):
            pos = (fx + k * u, ty_top - k * w)
            rr = hole_symbol(msp, pos, dia, k, th, hidden=fn == "D")
            uC.append(u); wC.append(w)
        elif fn.startswith("E"):
            pos = (ex0 + ke * w, ey0 + ke * v)
            rr = hole_symbol(msp, pos, dia, ke, th)
            vE.append(v); wE.append(w)
        else:
            pos = (fx0 + ke * (Tt - w), ey0 + ke * v)
            rr = hole_symbol(msp, pos, dia, ke, th)
            vF.append(v); wF.append(w)
        groups.setdefault((cd, fn), []).append((pos, rr))
    used = []
    for (cd, fn), lst in groups.items():
        desc, dia, dep = hole_desc(cd)
        pos, rr = lst[0]
        tx = (pos[0] + rr + 8, pos[1] + rr + 6)
        while any(abs(tx[0] - u_[0]) < 180 and abs(tx[1] - u_[1]) < 30 for u_ in used):
            tx = (tx[0], tx[1] + 32)
        used.append(tx)
        T(msp, f"{cd} {len(lst)}×%%c{dia:g}", tx, h=1.25, layer="10-PHU-KIEN")
    ch = chain_edges(uA + [0, L], k) if uA else None
    if ch and len(ch) > 2:
        for a, b in zip(ch, ch[1:]):
            dim(msp, (0, fy - 70), (fx + k * a, fy), (fx + k * b, fy), k)
    ch = chain_edges(vA + [0, W], k) if vA else None
    if ch and len(ch) > 2:
        xr = fx + k * L + (150 if not rect_like else 70)
        for a, b in zip(ch, ch[1:]):
            dim(msp, (xr, 0), (fx + k * L, fy + k * a), (fx + k * L, fy + k * b), k, 90)
    ch = chain_edges(uC + [0, L], k) if uC else None
    if ch and len(ch) > 2:
        for a, b in zip(ch, ch[1:]):
            dim(msp, (0, ty_top - k * Tt - 70), (fx + k * a, ty_top - k * Tt), (fx + k * b, ty_top - k * Tt), k)
    for vs_, ws_, xb, mirror in ((vE, wE, ex0, False), (vF, wF, fx0, True)):
        ch = chain_edges(vs_ + [0, W], ke, 45) if vs_ else None
        if ch and len(ch) > 2:
            xe = (xb + ke * Tt) if mirror else xb
            xd = (xe + 50) if mirror else (xe - 55)
            for a, b in zip(ch, ch[1:]):
                dim(msp, (xd, 0), (xe, ey0 + ke * a), (xe, ey0 + ke * b), ke, 90)
        if ws_:
            w0 = sorted(set(round(x, 1) for x in ws_))[0]
            pw = (Tt - w0) if mirror else w0
            dim(msp, (0, ey0 - 120), (xb, ey0), (xb + ke * pw, ey0), ke)
    rows = []
    agg = OrderedDict()
    for cd, n, (u, v, w) in holes:
        fn = face_name(n, (u, v, w), g["dims"])
        if fn in ("A", "B"):
            key, fixed, val = (cd, fn, round(v, 1)), f"Y={v:.4g}", ("X", u)
        elif fn in ("C", "D"):
            key, fixed, val = (cd, fn, round(w, 1)), f"Z={w:.4g}", ("X", u)
        else:
            key, fixed, val = (cd, fn, round(w, 1)), f"Z={w:.4g}", ("Y", v)
        r = agg.setdefault(key, dict(cd=cd, fn=fn, fixed=fixed, ax=val[0], vals=[]))
        r["vals"].append(round(val[1], 1))
    for r in agg.values():
        desc, dia, dep = hole_desc(r["cd"])
        rows.append([r["cd"], desc.replace("Ø", "%%c"), FACE_DESC.get(r["fn"], r["fn"]),
                     f"{r['fixed']}; {r['ax']}= " + ", ".join(f"{x:g}" for x in sorted(r["vals"])), len(r["vals"])])
    avail = 1040 - 420
    rh = max(38, min(50, avail / (len(rows) + 1.5)))
    if rows:
        tbl(msp, 250, 1040, [("Mã", 90), ("Mô tả lỗ", 860), ("Mặt", 430), ("Toạ độ từ gốc O (mm)", 1150), ("SL", 80)],
            rows, rh, f"BẢNG LỖ KHOAN – VT {code} (tổng {len(holes)} lỗ)", h=1.35)
    else:
        T(msp, "Không có lỗ khoan.", (250, 1000), h=1.8)
    name = PART_TYPES[g["ptype"]][0]
    if g["siblings"]:
        others = [s_ for s_ in g["siblings"] if s_ != code]
        x, y = 1950, 1205
        msp.add_lwpolyline([(x, y + 95), (x - 85, y - 50), (x + 85, y - 50)], close=True,
                           dxfattribs={"layer": "10-PHU-KIEN", "const_width": 5})
        T(msp, code, (x, y), h=2.1, align=TA.MIDDLE_CENTER, layer="10-PHU-KIEN")
        diffs = []
        for o in others:
            plus, minus = diff_holes(g, c.var[o])
            s_ = ", ".join([f"+{n} {k_}" for k_, n in plus.items()] + [f"−{n} {k_}" for k_, n in minus.items()])
            diffs.append(f"so với {o}: {s_ or 'vị trí lỗ khác'}")
        T(msp, f"CÙNG KÍCH THƯỚC VỚI {', '.join(others)} – KHÁC LỖ", (x + 120, y + 35), h=1.8, color=1)
        T(msp, ("; ".join(diffs))[:110], (x + 120, y - 25), h=1.3)
    MT(msp, f"{name} – SL {len(g['tags'])} – {c.material(code)}\\PDùng cho: "
            + ", ".join(loc_name(t) for t in g["tags"])
            + "\\PToạ độ: X dọc L, Y dọc W, Z dọc T; gốc O góc dưới-trái mặt A. Tròn + = lỗ xuyên; tròn chấm = "
              "lỗ tịt; nét đứt = lỗ ở mặt khuất (B, D)." + (" Góc vát: " + ", ".join(f"{a:g}°" for a in angles)
                                                           if angles else ""), (250, 365), h=1.4, width=1080)
    c.report.setdefault("part_pages", {})[code] = dict(angles=angles, rect=rect_like, holes=len(holes),
                                                      table=sum(r[4] for r in rows), sib=bool(g["siblings"]))
    return f"VT {code} – {name.upper()}", f"{PART_TYPES[g['ptype']][1].upper()} – MACHINING", stxt


# ================================================================== KHOANH VÙNG & CHI TIẾT PÁT SẮT
def _clip_poly(poly, x0, y0, x1, y1):
    def clip(pts, inside, inter):
        out = []
        for i in range(len(pts)):
            a, b = pts[i - 1], pts[i]
            ia, ib = inside(a), inside(b)
            if ib:
                if not ia:
                    out.append(inter(a, b))
                out.append(b)
            elif ia:
                out.append(inter(a, b))
        return out

    def ix(xc):
        return lambda a, b: (xc, a[1] + (b[1] - a[1]) * (xc - a[0]) / (b[0] - a[0]))

    def iy(yc):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (yc - a[1]) / (b[1] - a[1]), yc)

    pts = list(poly)
    for ins, inter in ((lambda p: p[0] >= x0, ix(x0)), (lambda p: p[0] <= x1, ix(x1)),
                       (lambda p: p[1] >= y0, iy(y0)), (lambda p: p[1] <= y1, iy(y1))):
        if not pts:
            break
        pts = clip(pts, ins, inter)
    return pts if len(pts) >= 3 and abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0]
                                            * pts[i][1] for i in range(len(pts)))) > 1e-6 else None


def clip_part(q, box):
    """Giao lăng trụ chi tiết với hộp box -> danh sách Solid (vùng gỗ quanh pát)."""
    from geom import AX, prism_solid
    ia, ib, it = AX[q.plane]
    t0, t1 = max(q.t0, box[it]), min(q.t1, box[it + 3])
    if t1 - t0 < 0.05:
        return []
    out = []
    for pc in (q.pieces or [q.poly]):
        cp = _clip_poly(pc, box[ia], box[ib], box[ia + 3], box[ib + 3])
        if cp:
            out.append(prism_solid(q.plane, cp, t0, t1))
    return out


def detail_specs(c):
    p, by = c.p, {q.tag: q for q in c.parts}
    specs = []
    pat = [q for q in c.parts if q.ptype == "pat_L"]
    if pat:
        q = by["pat_LF"]
        b = q.box
        specs.append(dict(
            label="A", short="Pat L goc khung ngoi", main="pat_LF", title="PÁT L – GÓC TRONG KHUNG NGỒI",
            points=[(x.tag, _center(x)) for x in pat],
            crop=(b[0] - 40, b[1] - 22, b[2] - 15, b[3] + 35, b[4] + 35, b[5] + 22),
            views=[("top", "MẶT BẰNG – nhìn từ trên"), ("back", "NHÌN TỪ TRONG RA THANH TRƯỚC")],
            explode=(45, 45, 60)))
    fp = [q for q in c.parts if q.ptype == "pat_flat"]
    if fp:
        q = by["fpat_L"]
        b = q.box
        specs.append(dict(
            label="B", short="Pat noi tua tay", main="fpat_L", title="PÁT NỐI TỰA LƯNG – GÁC TAY (MẶT SAU)",
            points=[(x.tag, _center(x)) for x in fp],
            crop=(b[0] - 10, b[1] - 60, b[2] - 30, b[3] + 15, b[4] + 5, b[5] + 30),
            views=[("back", "NHÌN TỪ SAU"), ("top", "MẶT BẰNG – nhìn từ trên")],
            explode=(0, 70, 0)))
    if "steel_bar" in by:
        q = by["steel_bar"]
        b = q.box
        jH = [j for j in c.joints if j.hw == "H"]
        specs.append(dict(
            label="C", short="Dau thanh gia co", main="steel_bar", title="ĐẦU THANH GIA CỐ – BẮT VÀO THANH HÔNG",
            points=[("steel_bar", j.pts[0]) for j in jH],
            crop=(b[0] - 35, b[1] - 40, b[2] - 15, b[0] + 90, b[4] + 40, b[5] + 25),
            views=[("front", "NHÌN TỪ TRƯỚC (mặt cắt qua tâm thanh)"), ("top", "MẶT BẰNG – nhìn từ trên")],
            explode=(70, 0, 0)))
    return specs


def _center(q):
    b = q.box
    return tuple((b[k] + b[k + 3]) / 2 for k in range(3))


def _fit_std(dirs, solids, region, margin, kmax=20):
    v0 = R.View(dirs)
    pts = [v0.p2(pt) for s_ in solids for pt in s_.verts]
    u0, u1 = min(x for x, _ in pts), max(x for x, _ in pts)
    w0, w1 = min(y for _, y in pts), max(y for _, y in pts)
    W_, H_ = region[2] - region[0] - 2 * margin, region[3] - region[1] - 2 * margin
    k, st = SCALES[-1]
    for kk, t in SCALES:
        if kk <= kmax and kk * (u1 - u0) <= W_ and kk * (w1 - w0) <= H_:
            k, st = kk, t
            break
    cx, cy = (region[0] + region[2]) / 2, (region[1] + region[3]) / 2
    return R.View(dirs, (cx - k * (u0 + u1) / 2, cy - k * (w0 + w1) / 2), k), st, (u0, u1, w0, w1)


def _detail_joints(c, d):
    tags = {d["main"]}
    return [j for j in c.joints if (j.a in tags or j.b in tags) and
            any(all(d["crop"][k] - 1 <= pt[k] <= d["crop"][k + 3] + 1 for k in range(3)) for pt in j.pts)]


def _hole_mark(msp, pos, num):
    msp.add_circle(pos, 11, dxfattribs={"layer": "10-PHU-KIEN"})
    msp.add_line((pos[0] - 16, pos[1]), (pos[0] + 16, pos[1]), dxfattribs={"layer": "10-PHU-KIEN"})
    msp.add_line((pos[0], pos[1] - 16), (pos[0], pos[1] + 16), dxfattribs={"layer": "10-PHU-KIEN"})
    q = (pos[0] + 34, pos[1] + 30)
    msp.add_circle(q, 17, dxfattribs={"layer": "10-PHU-KIEN"})
    T(msp, str(num), q, h=1.5, align=TA.MIDDLE_CENTER, layer="10-PHU-KIEN", color=1)


def pg_pat_overview(c, msp):
    offs = {q.tag: (0, 0, 0) for q in c.parts}
    gray = {q.tag for q in c.parts if q.ptype not in METAL_TYPES}
    draw_iso(msp, c, offs, (250, 420, 1750, PH - 150), OrderedDict(), gray=gray, margin=120, ckey="pat_overview",
             circles=[x for x in c.detail_points if x[0] != "B"],
             title="KHOANH VÙNG CHỖ LẮP SẮT – nhìn trước-phải-trên")
    draw_iso(msp, c, offs, (1800, 1150, PW - 120, PH - 150), OrderedDict(), dirs=(-1, 1, 1), gray=gray, margin=90,
             ckey="pat_overview", circles=[x for x in c.detail_points if x[0] == "B"],
             title="Nhìn sau-trái-trên (pát nối ở mặt sau)")
    rows = []
    for i, d in enumerate(c.details):
        js = _detail_joints(c, d)
        hw = "; ".join(sorted({hw_name(j).split(" (")[0] for j in js}))
        rows.append([d["label"], d["title"].split(" – ")[0].title(), len(d["points"]), hw[:70],
                     str(c.detail_page.get(d["label"], ""))])
    tbl(msp, 1800, 1080, [("CT", 80), ("Chi tiết", 330), ("SL", 70), ("Phụ kiện cố định", 500), ("Tờ", 80)],
        rows, 50, "BẢNG CHI TIẾT LẮP SẮT", h=1.35)
    MT(msp, "Vòng đỏ nét đứt = vùng lắp pát sắt, ký hiệu trong ô = tên hình chi tiết phóng to ở các trang sau. "
            "Các vị trí cùng ký hiệu giống nhau (đối xứng trái/phải, trước/sau). Gỗ vẽ xám, sắt vẽ đỏ.",
       (1800, 700), h=1.5, width=1060)
    c.report["pat_overview"] = True
    return "VỊ TRÍ LẮP PÁT SẮT – KHOANH VÙNG", "STEEL BRACKET LOCATIONS", "không TL"


def pg_detail(c, msp, d):
    box = d["crop"]
    near = []
    for q in c.parts:
        sols = clip_part(q, box)
        if sols:
            near.append((q, sols))
    main = c.by[d["main"]]
    js = _detail_joints(c, d)
    groups = OrderedDict()
    for j in js:
        groups.setdefault(hw_name(j), []).append(j)
    num_of = {id(j): i + 1 for i, (k, lst) in enumerate(groups.items()) for j in lst}
    items = [(f"{q.tag}#{i}", s_, layer_of(q, plain=True) if q.ptype not in METAL_TYPES else METAL_LAYER)
             for q, sols in near for i, s_ in enumerate(sols)]
    regions = [(230, 1090, 1180, 1900), (1200, 1090, 2150, 1900)]
    stx = []
    for (vk, vname), reg in zip(d["views"], regions):
        v, st, ext = _fit_std(R.ORTHO[vk], [s_ for _, s_, _ in items], reg, 100, kmax=10)
        stx.append(st)
        R.render(msp, v, items)
        u0, u1, w0, w1 = ext
        a, b = v.sheet((u0, w0)), v.sheet((u1, w1))
        rect(msp, a[0] - 25, a[1] - 25, b[0] + 25, b[1] + 25, layer="13-KHOANH-VUNG")
        T(msp, f"CHI TIẾT {d['label']} – {vname} ({st})", (reg[0], reg[3] - 5), h=1.6)
        # dim định vị pát + lỗ
        pu = [v.p2(pt) for s_ in main.solids for pt in s_.verts]
        cu = [v.p2(pt) for s_ in [s for q, ss in near if q.tag == main.tag for s in ss] for pt in s_.verts] or pu
        mu0, mu1 = min(x for x, _ in cu), max(x for x, _ in cu)
        mw0, mw1 = min(y for _, y in cu), max(y for _, y in cu)
        hp = [v.p2(pt) for j in js for pt in j.pts]
        hs = [v.sheet(h_) for h_ in hp]
        placed = []
        for j in js:
            for pt in j.pts:
                sp = v.P(pt)
                if all(math.dist(sp, q_) > 25 for q_ in placed):      # lỗ trùng hướng nhìn -> 1 dấu
                    placed.append(sp)
                    _hole_mark(msp, sp, num_of[id(j)])
        k = v.scale
        xs = sorted({round(x, 1) for x in [mu0, mu1] + [h_[0] for h_ in hp] if mu0 - 0.1 <= x <= mu1 + 0.1})
        ys = sorted({round(y, 1) for y in [mw0, mw1] + [h_[1] for h_ in hp] if mw0 - 0.1 <= y <= mw1 + 0.1})
        mates = {j.a for j in js} | {j.b for j in js}
        mates.discard(main.tag)
        ref_pts = [v.p2(pt) for q, ss in near if q.tag in mates for s_ in ss for pt in s_.verts]
        top_ref = max(y for _, y in ref_pts) if ref_pts else mw1        # mặt trên thanh nhận pát
        if top_ref - mw1 > 0.5:
            ys.append(round(top_ref, 1))
        xs = chain_edges(xs, k, 45) or xs
        ys = chain_edges(ys, k, 45) or ys
        by0 = v.sheet((0, w0))[1] - 95
        for p0, p1 in zip(xs, xs[1:]):
            dim(msp, (0, by0), v.sheet((p0, mw0)), v.sheet((p1, mw0)), k)
        bx0 = v.sheet((u1, 0))[0] + 95
        for p0, p1 in zip(ys, ys[1:]):
            dim(msp, (bx0, 0), v.sheet((mu1, p0)), v.sheet((mu1, p1)), k, 90)
    # hình trục đo bung nhẹ pát
    offs = {q.tag: (d["explode"] if q.tag == main.tag else (0, 0, 0)) for q, _ in near}
    it = [(f"{q.tag}#{i}", s_.moved(offs[q.tag]), METAL_LAYER if q.ptype in METAL_TYPES else "8-CUM-DA-LAP")
          for q, sols in near for i, s_ in enumerate(sols)]
    v = R.fit(R.iso_dirs(*(MAIN_ISO if d["label"] != "B" else (-1, 1, 1))), [s_ for _, s_, _ in it],
              (2150, 1120, PW - 120, 1890), 110)
    R.render(msp, v, it)
    iso_pl = []
    for j in js:
        for pt in j.pts:
            a = v.P(tuple(pt[i] + offs.get(j.a, (0, 0, 0))[i] for i in range(3)))
            b = v.P(tuple(pt[i] + offs.get(j.b, (0, 0, 0))[i] for i in range(3)))
            msp.add_line(a, b, dxfattribs={"layer": "4-DUONG-BUNG"})
            q_ = a if j.a != main.tag else b
            if all(math.dist(q_, z_) > 25 for z_ in iso_pl):
                iso_pl.append(q_)
                _hole_mark(msp, q_, num_of[id(j)])
    T(msp, f"CHI TIẾT {d['label']} – TRỤC ĐO (bung pát)", (2160, 1885), h=1.6)
    # bảng chỗ bắn + ghi chú
    rows = []
    for i, (nm, lst) in enumerate(groups.items(), 1):
        j0 = lst[0]
        other = j0.b if j0.a == main.tag else j0.a
        oq = c.by[other]
        hole = HOLE_SPEC[(j0.hw, "b" if j0.b == other else "a")]
        rows.append([str(i), nm.replace("Ø", "%%c"), f"{c.t2c.get(other, '')} {PART_TYPES[oq.ptype][0]}"[:30],
                     hole[1].replace("Ø", "%%c")[:42], sum(len(j.pts) for j in lst)])
    y = tbl(msp, 250, 1020, [("Số", 70), ("Phụ kiện bắn cố định", 600), ("Bắn vào", 390), ("Lỗ trên gỗ", 540),
                             ("SL", 80)], rows, 50, f"CHỖ BẮN CỐ ĐỊNH PÁT – CHI TIẾT {d['label']}", h=1.35)
    MT(msp, detail_note(c, d), (250, y - 40), h=1.5, width=1080)
    loc = (2020, 420, PW - 120, 1000)
    rect(msp, *loc, layer="7-BANG-KE")
    allo = {q.tag: (0, 0, 0) for q in c.parts}
    draw_iso(msp, c, allo, (loc[0], loc[1], loc[2], loc[3] - 40), OrderedDict(),
             dirs=MAIN_ISO if d["label"] != "B" else (-1, 1, 1),
             gray={q.tag for q in c.parts if q.ptype not in METAL_TYPES}, margin=40,
             circles=[x for x in c.detail_points if x[0] == d["label"]])
    T(msp, f"Vị trí chi tiết {d['label']} trong sofa ({len(d['points'])} chỗ)", (loc[0] + 10, loc[3] - 15), h=1.4)
    c.report.setdefault("details", {})[d["label"]] = dict(holes=sum(len(j.pts) for j in js), groups=len(groups))
    return f"CHI TIẾT {d['label']} – {d['title']}", "STEEL BRACKET DETAIL", " / ".join(dict.fromkeys(stx))


def detail_note(c, d):
    p = c.p
    if d["label"] == "A":
        return ("CÁCH LẮP (bước 3, lắp sau khi ghép khung ngồi, trước khi bắt nan):\\P"
                f"• Áp pát sát góc trong, mép trên pát thấp hơn mặt khung {p['pat_drop']:g} mm.\\P"
                f"• (1) Cánh áp thanh trước/sau {c.codes_of('seat_fb')}: khoan Ø10 xuyên ván 18, đóng ốc 4 chấu M8 "
                "từ MẶT NGOÀI ván, bắn bulông từ phía pát.\\P"
                f"• (2) Cánh áp thanh hông {c.codes_of('seat_side')}: khoan Ø8, vặn ốc cấy M6 từ phía pát, bắn bulông.\\P"
                "• Kiểm tra vuông góc khung rồi mới siết chặt. 4 góc giống nhau (đối xứng).").replace("Ø", "%%c")
    if d["label"] == "B":
        return ("CÁCH LẮP (bước 4, sau khi đặt tựa lưng):\\P"
                "• Áp pát phẳng lên mặt sau, nửa trái phủ trụ gác tay sau, nửa phải phủ ván lưng.\\P"
                "• (1) Bắn 2 vít gỗ vào trụ gác tay sau (khoan mồi Ø2.5 sâu 15).\\P"
                f"• (2) Ván lưng {p['back_panel_t']:g} mm: khoan Ø10 xuyên, ốc 4 chấu M8 đặt ở MẶT TRƯỚC ván "
                "(khoảng trống giữa 2 thanh đứng), bắn bulông từ phía pát.\\P"
                "• Bên phải đối xứng.").replace("Ø", "%%c")
    return ("CÁCH LẮP (bước 3):\\P"
            "• Đặt thanh thép hộp mặt 40 đứng, giữa chiều sâu khung ngồi, mặt trên phẳng với đáy nan.\\P"
            "• (1) Khoan Ø7 xuyên thanh hông, bắn bulông M6×70 vào đai ốc hàn sẵn ở đầu thanh. 2 đầu giống nhau.\\P"
            "• Sau khi bắt nan: bắn vít tự khoan 4.2×25 qua mỗi nan xuống thanh (1 vít/nan, ngoài vùng chi tiết).").replace("Ø", "%%c")


# ================================================================== lắp ráp bộ trang
def page_list(c):
    pages = [("TONG-THE_HINH-CHIEU", pg_overview_views, ()), ("TONG-THE_HINH-BUNG", pg_overview_exploded, ()),
             ("BUOC-LAP_1-3", pg_steps, ([1, 2, 3],)), ("BUOC-LAP_4-5", pg_steps, ([4, 5],))]
    rows = bom_rows(c)
    per = 22
    chunks = [rows[i:i + per] for i in range(0, len(rows), per)]
    for i, ch in enumerate(chunks):
        pages.append((f"BOM_{i + 1}", pg_bom, (ch, i + 1, len(chunks))))
    pages.append(("PHU-KIEN_QUY-TAC", pg_hardware, ()))
    pages.append(("VI-TRI-PAT-SAT", pg_pat_overview, ()))
    for d in c.details:
        pages.append((f"CHI-TIET-{d['label']}_{ascii_name(d['short'])}", pg_detail, (d,)))
    for m in MODULES:
        pages.append((f"CUM-{m}_{ascii_name(MODULES[m]['vn'])}", pg_module, (m,)))
    for code, g in c.var.items():
        if not g["metal"]:
            pages.append((f"VT{code}_{ascii_name(PART_TYPES[g['ptype']][0])}", pg_part, (code,)))
    c.detail_page = {nm.split("_")[0][9:]: i + 1 for i, (nm, _, _) in enumerate(pages) if nm.startswith("CHI-TIET-")}
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
               "Vật liệu (quy tắc)", "Thể tích bao (m³)", "Ghi chú", "Dùng cho"])
    for r in bom_rows(c):
        i = ws.max_row + 1
        ws.append([r["code"], r["name"], r["en"], r["cn"], r["mod"], r["qty"], round(r["L"], 1), round(r["W"], 1),
                   round(r["T"], 1), r["mat"], "" if r["metal"] else f"=G{i}*H{i}*I{i}/1e9*F{i}", r["note"], r["used"]])
    n = ws.max_row
    ws.append(["", "TỔNG", "", "", "", f"=SUM(F2:F{n})", "", "", "", "", f"=SUM(K2:K{n})"])
    style(ws, [6, 22, 22, 14, 6, 5, 8, 8, 7, 24, 12, 26, 30])
    ws2 = wb.create_sheet("Lỗ khoan")
    ws2.append(["VT", "Mã lỗ", "Mô tả", "Ø", "Sâu", "Mặt", "X (mm)", "Y (mm)", "Z (mm)"])
    for code, g in c.var.items():
        for cd, nn, (u, v, w) in g["holes"]:
            desc, dia, dep = hole_desc(cd)
            ws2.append([code, cd, desc, dia, dep, face_name(nn, (u, v, w), g["dims"]), round(u, 2), round(v, 2),
                        round(w, 2)])
    style(ws2, [6, 7, 40, 6, 7, 6, 9, 9, 9])
    ws3 = wb.create_sheet("Phụ kiện")
    ws3.append(["Mã", "Phụ kiện (kèm chiều dài)", "SL", "Bước"])
    hc = Counter((j.hw, j.length) for j in c.joints for _ in j.pts)
    for (k, L), nn in sorted(hc.items(), key=lambda x: (x[0][0], x[0][1] or 0)):
        ws3.append([k, hw_name(k, L), nn, ", ".join(map(str, sorted({j.step for j in c.joints
                                                                         if j.hw == k and j.length == L})))])
    style(ws3, [6, 46, 6, 10])
    ws4 = wb.create_sheet("Tham số")
    ws4.append(["Tham số", "Giá trị"])
    for k, v in c.p.items():
        ws4.append([k, v])
    style(ws4, [16, 10])
    wb.save(path)


def render_pdf(docs, path, png=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, lineweight_scaling=0.8)
    if png:
        os.makedirs(png, exist_ok=True)
    with PdfPages(path) as pp:
        for doc, p_, _ in docs:
            fig = plt.figure(figsize=(11.69, 8.27))
            ax = fig.add_axes([0, 0, 1, 1])
            Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace())
            ax.set_xlim(0, PW); ax.set_ylim(0, PH); ax.set_aspect("equal"); ax.axis("off")
            pp.savefig(fig)
            if png:
                fig.savefig(os.path.join(png, os.path.basename(p_)[:-4] + ".png"), dpi=150)
            plt.close(fig)


def build_all(params=None, proj="first", out="output", pdf=True, png=None):
    c = Ctx(params, proj)
    d4 = os.path.join(out, "A4")
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
        frame(msp, tv, te, dwg, sc, f"{i + 1}/{N}", proj)
        path = os.path.join(d4, f"{dwg}_{name}.dxf")
        doc.saveas(path)
        docs.append((doc, path, name))
    export_excel(c, os.path.join(out, "SF_BOM.xlsx"))
    if pdf:
        render_pdf(docs, os.path.join(out, "SF_A4_BO-BAN-VE.pdf"), png)
    return c, docs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params")
    ap.add_argument("--projection", choices=["first", "third"], default="first")
    ap.add_argument("--out", default="output")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--png")
    ap.add_argument("--full", action="store_true", help="xuất bộ chi tiết đầy đủ (mỗi chi tiết 1 trang)")
    a = ap.parse_args()
    prm = json.load(open(a.params, encoding="utf-8")) if a.params else None
    import selfcheck
    if a.full:
        c, docs = build_all(prm, a.projection, a.out, not a.no_pdf, a.png)
        print(f"Đã tạo {len(docs)} trang A4 (bộ đầy đủ) trong {a.out}/A4")
        selfcheck.run(c, docs, a.out)
    else:
        import compact
        c, docs = compact.build_compact(prm, a.projection, a.out, not a.no_pdf, a.png)
        print(f"Đã tạo {len(docs)} trang A4 (bộ gọn) trong {a.out}/A4")
        selfcheck.run_compact(c, docs, a.out)


if __name__ == "__main__":
    main()
