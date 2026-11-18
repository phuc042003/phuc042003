# -*- coding: utf-8 -*-
"""
SINH BẢN VẼ BÓC TÁCH LẮP RÁP KHUNG SOFA (DXF A1) + BOM EXCEL
==============================================================
Một bản vẽ gồm:
  1. 3 hình chiếu vuông góc (đứng / bằng / cạnh) có nét khuất + kích thước bao
  2. Hình bung trục đo tổng thể (exploded isometric): số vị trí, đường bung,
     nhãn phụ kiện A..E, màu theo module
  3. 4 hình bước lắp (assembly steps): cụm cũ màu xám, cụm mới màu + mũi tên
  4. Bảng kê chi tiết (BOM) + bảng phụ kiện + khung tên

Cách chạy:
    pip install ezdxf shapely openpyxl matplotlib
    python make_drawing.py                     # dùng PARAMS mặc định
    python make_drawing.py --params my.json    # ghi đè tham số (JSON)
    python make_drawing.py --projection third  # phép chiếu góc thứ ba
Kết quả trong thư mục output/: sofa_frame_exploded.dxf, _BOM.xlsx, _preview.png/.pdf
"""
import argparse
import json
import math
import os
from collections import Counter, OrderedDict
from graphlib import TopologicalSorter, CycleError

import ezdxf
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import unary_union

from sofa_model import (HARDWARE, LEG_MODULE, MODULES, PART_TYPES, STEP_MODULES, build,
                        check_overlaps, explode_offset)

S = 10          # hệ số khổ giấy: bản vẽ vẽ 1:1 trong model, khung A1 phóng ×10 => tỉ lệ 1:10
SHEET_W, SHEET_H = 841 * S, 594 * S

# ------------------------------------------------------------------ hình chiếu
R2, R3, R6 = math.sqrt(2), math.sqrt(3), math.sqrt(6)
VIEWS = {
    #        trục phải (r)       trục lên (up)          hướng về người nhìn (d)
    "front": ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
    "top":   ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "left":  ((0, -1, 0), (0, 0, 1), (-1, 0, 0)),     # nhìn từ trái (góc 1: đặt bên phải)
    "right": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),       # nhìn từ phải (góc 3: đặt bên phải)
    "iso":   ((1 / R2, 1 / R2, 0), (-1 / R6, 1 / R6, 2 / R6), (1 / R3, -1 / R3, 1 / R3)),
}

EDGES = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
# mặt hộp: (pháp tuyến, chỉ số đỉnh) — đỉnh i: bit0=x, bit1=y, bit2=z
FACES = [((-1, 0, 0), (0, 2, 4, 6)), ((1, 0, 0), (1, 3, 5, 7)), ((0, -1, 0), (0, 1, 4, 5)),
         ((0, 1, 0), (2, 3, 6, 7)), ((0, 0, -1), (0, 1, 2, 3)), ((0, 0, 1), (4, 5, 6, 7))]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def corners(box):
    x0, y0, z0, x1, y1, z1 = box
    return [(x1 if i & 1 else x0, y1 if i & 2 else y0, z1 if i & 4 else z0) for i in range(8)]


def shift(box, o):
    return (box[0] + o[0], box[1] + o[1], box[2] + o[2], box[3] + o[0], box[4] + o[1], box[5] + o[2])


class View:
    """Một hình chiếu đặt trên giấy: origin (toạ độ giấy), scale."""

    def __init__(self, name, origin, scale=1.0):
        self.r, self.u, self.d = VIEWS[name]
        self.name, self.origin, self.scale = name, origin, scale

    def p2(self, pt):          # 3D -> toạ độ chiếu (chưa scale)
        return (dot(pt, self.r), dot(pt, self.u))

    def sheet(self, uv):       # toạ độ chiếu -> toạ độ giấy
        return (self.origin[0] + uv[0] * self.scale, self.origin[1] + uv[1] * self.scale)

    def P(self, pt):           # 3D -> giấy
        return self.sheet(self.p2(pt))

    def front_depth(self, box, uv):
        """Độ sâu mặt trước của hộp theo tia chiếu qua điểm uv (lớn = gần người nhìn)."""
        o = [uv[0] * self.r[k] + uv[1] * self.u[k] for k in range(3)]
        t0, t1 = -1e18, 1e18
        for k in range(3):
            lo, hi = box[k], box[k + 3]
            if abs(self.d[k]) < 1e-12:
                if not (lo - 1e-6 <= o[k] <= hi + 1e-6):
                    return None
                continue
            a, b = (lo - o[k]) / self.d[k], (hi - o[k]) / self.d[k]
            t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
        return t1 if t0 <= t1 + 1e-6 else None


def fit_view(name, boxes, region, margin=0):
    """Tạo View sao cho toàn bộ các hộp nằm gọn trong vùng giấy region=(x0,y0,x1,y1)."""
    v = View(name, (0, 0), 1.0)
    pts = [v.p2(c) for b in boxes for c in corners(b)]
    u0, u1 = min(u for u, _ in pts), max(u for u, _ in pts)
    w0, w1 = min(w for _, w in pts), max(w for _, w in pts)
    x0, y0, x1, y1 = region[0] + margin, region[1] + margin, region[2] - margin, region[3] - margin
    sc = min((x1 - x0) / (u1 - u0), (y1 - y0) / (w1 - w0))
    ox = (x0 + x1) / 2 - sc * (u0 + u1) / 2
    oy = (y0 + y1) / 2 - sc * (w0 + w1) / 2
    return View(name, (ox, oy), sc)


# ------------------------------------------------------------------ DXF setup
def setup_doc():
    doc = ezdxf.new("R2018", setup=True)
    doc.units = ezdxf.units.MM
    doc.header["$LTSCALE"] = 1.0 * S
    doc.header["$MEASUREMENT"] = 1
    doc.styles.add("VN", font="arial.ttf")                      # hỗ trợ tiếng Việt Unicode
    layers = [
        ("0-KHUNG-BANVE", 7, "CONTINUOUS", 70),       # border
        ("1-NET-THAY", 7, "CONTINUOUS", 50),          # visible (ortho)
        ("2-NET-KHUAT", 8, "HIDDEN", 25),             # hidden
        ("3-KICH-THUOC", 1, "CONTINUOUS", 18),        # dimensions
        ("4-DUONG-BUNG", 4, "DASHDOT", 18),           # explode lines
        ("5-SO-VI-TRI", 7, "CONTINUOUS", 25),         # balloons
        ("6-CHU", 7, "CONTINUOUS", 25),               # text
        ("7-BANG-KE", 7, "CONTINUOUS", 25),           # tables
        ("8-CUM-DA-LAP", 8, "CONTINUOUS", 18),        # step: assembled (gray)
        ("9-MUI-TEN", 1, "CONTINUOUS", 35),           # arrows
        ("10-PHU-KIEN", 1, "CONTINUOUS", 25),         # hardware tags
    ]
    for m, info in MODULES.items():
        layers.append((f"M-{m}-{info['en'].upper().replace(' ', '_')}", info["aci"], "CONTINUOUS", 35))
    for name, col, lt, lw in layers:
        doc.layers.add(name, color=col, linetype=lt, lineweight=lw)
    ds = doc.dimstyles.new("SOFA_1-10")
    ds.dxf.dimscale = S
    ds.dxf.dimtxt = 2.5
    ds.dxf.dimasz = 2.5
    ds.dxf.dimexe = 1.5
    ds.dxf.dimexo = 1.0
    ds.dxf.dimgap = 0.8
    ds.dxf.dimdec = 0
    ds.dxf.dimtad = 1
    ds.dxf.dimtxsty = "VN"
    ds.dxf.dimclrd = 1
    ds.dxf.dimclre = 1
    ds.dxf.dimclrt = 7
    return doc


def mod_layer(m):
    return f"M-{m}-{MODULES[m]['en'].upper().replace(' ', '_')}"


def text(msp, s, pos, h=2.5, layer="6-CHU", align=TextEntityAlignment.LEFT, color=None):
    a = {"layer": layer, "style": "VN", "height": h * S}
    if color is not None:
        a["color"] = color
    msp.add_text(s, dxfattribs=a).set_placement(pos, align=align)


def mtext(msp, s, pos, h=2.5, width=None, layer="6-CHU"):
    mt = msp.add_mtext(s, dxfattribs={"layer": layer, "style": "VN", "char_height": h * S})
    mt.set_location(pos, attachment_point=1)
    if width:
        mt.dxf.width = width
    return mt


# ------------------------------------------------------------------ khử nét khuất
def render_boxes(msp, view, items, hidden=False, min_len=0.3):
    """items: list of (key, box, layer). Vẽ nét thấy (và nét khuất nếu hidden=True)
    bằng thuật toán sắp độ sâu theo tia + trừ vùng che (shapely).
    Trả về dict key -> polygon phần nhìn thấy (toạ độ chiếu)."""
    hulls = {}
    for key, box, _ in items:
        hulls[key] = MultiPoint([view.p2(c) for c in corners(box)]).convex_hull
    boxes = {k: b for k, b, _ in items}
    keys = [k for k, _, _ in items]
    # quan hệ che: front -> back
    ts = TopologicalSorter({k: set() for k in keys})
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            inter = hulls[a].intersection(hulls[b])
            if inter.area < 1e-3:
                continue
            rp = inter.representative_point()
            da, db = view.front_depth(boxes[a], (rp.x, rp.y)), view.front_depth(boxes[b], (rp.x, rp.y))
            if da is None or db is None:
                continue
            if da > db + 1e-6:
                ts.add(b, a)        # a vẽ trước (ở trước)
            elif db > da + 1e-6:
                ts.add(a, b)
    try:
        order = list(ts.static_order())
    except CycleError:
        c = lambda k: dot([(boxes[k][i] + boxes[k][i + 3]) / 2 for i in range(3)], view.d)
        order = sorted(keys, key=c, reverse=True)
    layer_of = {k: l for k, _, l in items}
    occl = Polygon()
    visible = {}
    for k in order:
        cs = corners(boxes[k])
        front_faces = [f for n, f in FACES if dot(n, view.d) > 1e-9]
        segs = set()
        for f in front_faces:
            for e in EDGES:
                if e[0] in f and e[1] in f:
                    segs.add(e)
        for i, j in segs:
            a, b = view.p2(cs[i]), view.p2(cs[j])
            if math.dist(a, b) < 1e-6:
                continue
            ln = LineString([a, b])
            vis = ln.difference(occl) if not occl.is_empty else ln
            emit(msp, view, vis, layer_of[k], min_len)
            if hidden and not occl.is_empty:
                hid = ln.intersection(occl.buffer(-0.5))
                emit(msp, view, hid, "2-NET-KHUAT", min_len * 3)
        visible[k] = hulls[k].difference(occl) if not occl.is_empty else hulls[k]
        occl = unary_union([occl, hulls[k]])
    return visible


def emit(msp, view, geom, layer, min_len):
    if geom.is_empty:
        return
    geoms = getattr(geom, "geoms", [geom])
    for g in geoms:
        if g.geom_type == "LineString" and g.length * view.scale > min_len:
            pts = [view.sheet(c) for c in g.coords]
            msp.add_line(pts[0], pts[-1], dxfattribs={"layer": layer})
        elif g.geom_type in ("MultiLineString", "GeometryCollection"):
            emit(msp, view, g, layer, min_len)


# ------------------------------------------------------------------ chú thích
def balloon(msp, center, num, anchor, r=45, layer="5-SO-VI-TRI"):
    msp.add_circle(center, r, dxfattribs={"layer": layer})
    text(msp, str(num), center, h=4.0, layer=layer, align=TextEntityAlignment.MIDDLE_CENTER)
    dx, dy = anchor[0] - center[0], anchor[1] - center[1]
    L = math.hypot(dx, dy)
    if L > r:
        s = (center[0] + dx / L * r, center[1] + dy / L * r)
        msp.add_line(s, anchor, dxfattribs={"layer": layer})
        msp.add_circle(anchor, 7, dxfattribs={"layer": layer})
        h = msp.add_hatch(dxfattribs={"layer": layer})
        h.paths.add_edge_path().add_arc(anchor, 7, 0, 360)


def hw_tag(msp, pos, code):
    a = 34
    pts = [(pos[0] + a * math.cos(math.radians(30 + 60 * i)), pos[1] + a * math.sin(math.radians(30 + 60 * i)))
           for i in range(6)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "10-PHU-KIEN"})
    text(msp, code, pos, h=3.2, layer="10-PHU-KIEN", align=TextEntityAlignment.MIDDLE_CENTER)


def arrow(msp, a, b, layer="9-MUI-TEN", head=90, w=40):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < head * 1.5:
        return
    m = (b[0] - dx / L * head, b[1] - dy / L * head)
    msp.add_lwpolyline([a, m], dxfattribs={"layer": layer, "const_width": 8})
    pl = msp.add_lwpolyline([m, b], dxfattribs={"layer": layer})
    pl.set_points([(m[0], m[1], w, 0), (b[0], b[1], 0, 0)], format="xyse")


def place_balloons(anchors, outline, gap, r, iters=400):
    """Đặt số vị trí 'bám viền': chiếu mỗi điểm neo ra đường bao (outline nới rộng gap),
    sắp theo chu vi rồi giãn cách đều tối thiểu ~2.7r => leader không cắt chéo nhau."""
    ring = outline.convex_hull.buffer(gap, join_style=2).exterior
    per = ring.length
    c = outline.convex_hull.centroid
    svals = {}
    for k, a in anchors.items():
        dx, dy = a[0] - c.x, a[1] - c.y
        L = math.hypot(dx, dy) or 1
        far = (c.x + dx / L * 1e5, c.y + dy / L * 1e5)
        hit = LineString([(c.x, c.y), far]).intersection(ring)
        if hit.is_empty:
            hp = Point(a)
        elif hit.geom_type == "Point":
            hp = hit
        elif hasattr(hit, "geoms"):
            hp = list(hit.geoms)[0]
            hp = hp if hp.geom_type == "Point" else Point(hp.coords[0])
        else:
            hp = Point(hit.coords[0])
        svals[k] = ring.project(hp)
    keys = sorted(svals, key=svals.get)
    n = len(keys)
    need = min(2.7 * r, per / max(n, 1))
    # cắt vòng tại khe hở lớn nhất -> bài toán 1D
    sv = [svals[k] for k in keys]
    gaps = [((sv[(i + 1) % n] - sv[i]) % per, i) for i in range(n)]
    cut = max(gaps)[1] + 1
    keys = keys[cut:] + keys[:cut]
    want = []
    for k in keys:
        v = svals[k]
        if want and v < want[-1]:
            v += per
        want.append(v)
    # gộp cụm: mỗi cụm là dãy liên tiếp cách đều need, tâm = trung bình vị trí mong muốn
    clusters = [[i] for i in range(n)]
    def place(c):
        mean = sum(want[i] for i in c) / len(c)
        start = mean - need * (len(c) - 1) / 2
        return start, start + need * (len(c) - 1)
    changed = True
    while changed:
        changed = False
        for i in range(len(clusters) - 1):
            if place(clusters[i])[1] + need > place(clusters[i + 1])[0] + 1e-6:
                clusters[i] = clusters[i] + clusters.pop(i + 1)
                changed = True
                break
    s = []
    for c in clusters:
        st, _ = place(c)
        s += [st + need * j for j in range(len(c))]
    return {k: tuple(ring.interpolate(v % per).coords[0]) for k, v in zip(keys, s)}


# ------------------------------------------------------------------ các khối bản vẽ
def sheet_outline(v, vis):
    from shapely import affinity
    g = unary_union([x for x in vis.values() if not x.is_empty])
    g = affinity.scale(g, v.scale, v.scale, origin=(0, 0))
    return affinity.translate(g, v.origin[0], v.origin[1])


def part_numbers(parts):
    used = {q.ptype for q in parts}
    return OrderedDict((t, i + 1) for i, t in enumerate([t for t in PART_TYPES if t in used]))


def draw_ortho(msp, p, parts, proj):
    W, D, H = p["W"], p["D"], p["H_back"]
    side = "left" if proj == "first" else "right"
    x0 = 650
    if proj == "first":
        fy, ty = 3800, 2450           # front trên, top dưới
    else:
        fy, ty = 2450, 3600           # góc 3: top trên, front dưới
    fv = View("front", (x0, fy))
    tv = View("top", (x0, ty))
    sx = x0 + W + 550
    sv = View(side, (sx + (D if side == "left" else 0), fy))
    items = [(q.tag, q.box, "1-NET-THAY") for q in parts]
    for v in (fv, tv, sv):
        render_boxes(msp, v, items, hidden=True)
    # tên hình chiếu
    names = {"front": "HÌNH CHIẾU ĐỨNG / FRONT VIEW", "top": "HÌNH CHIẾU BẰNG / TOP VIEW",
             "left": "HÌNH CHIẾU CẠNH TRÁI / LEFT VIEW", "right": "HÌNH CHIẾU CẠNH PHẢI / RIGHT VIEW"}
    text(msp, names["front"] + "  (1:10)", (x0, fy - 330), h=3.5)
    text(msp, names["top"] + "  (1:10)", (x0, ty - 320), h=3.5)
    text(msp, names[side] + "  (1:10)", (sx, fy - 330), h=3.5)
    dim = lambda b, p1, p2, ang=0: msp.add_linear_dim(base=b, p1=p1, p2=p2, angle=ang,
                                                      dimstyle="SOFA_1-10",
                                                      dxfattribs={"layer": "3-KICH-THUOC"}).render()
    F = fv.P
    # --- hình chiếu đứng
    dim(F((0, 0, H + 180)), F((0, 0, H)), F((W, 0, H)))
    dim(F((0, 0, H + 80)), F((0, 0, p["H_arm"])), F((p["T_arm"], 0, p["H_arm"])))
    dim(F((-300, 0, 0)), F((0, 0, 0)), F((0, 0, H)), 90)
    dim(F((-180, 0, 0)), F((0, 0, 0)), F((0, 0, p["H_arm"])), 90)
    dim(F((W + 150, 0, 0)), F((W, 0, 0)), F((W, 0, p["H_leg"])), 90)
    dim(F((W + 150, 0, 0)), F((W, 0, p["H_leg"])), F((W, 0, p["H_leg"] + p["rail_h"])), 90)
    # --- hình chiếu bằng
    T = tv.P
    dim(T((-200, 0, 0)), T((0, 0, 0)), T((0, D, 0)), 90)
    dim(T((W + 150, 0, 0)), T((W, D - p["back_t"], 0)), T((W, D, 0)), 90)
    dim(T((0, -150, 0)), T((p["T_arm"], 0, 0)), T((W - p["T_arm"], 0, 0)))
    # --- hình chiếu cạnh
    Sv = sv.P
    dim(Sv((0, 0, -150)), Sv((0, 0, 0)), Sv((0, D, 0)))
    dim(Sv((0, -150 if side == "left" else D + 150, 0)), Sv((0, D, 0)), Sv((0, D, H)), 90)
    return fv, tv, sv


def draw_exploded(msp, p, parts, joints, nums, region):
    items, by_tag = [], {}
    for q in parts:
        b = shift(q.box, explode_offset(q, p, "full"))
        items.append((q.tag, b, mod_layer(q.module)))
        by_tag[q.tag] = q
    v = fit_view("iso", [b for _, b, _ in items], region, margin=330)
    vis = render_boxes(msp, v, items)
    # đường bung + nhãn phụ kiện
    tagged, tag_pos = set(), []
    for j in joints:
        oa = explode_offset(by_tag[j.a], p, "full")
        ob = explode_offset(by_tag[j.b], p, "full")
        for k, pt in enumerate(j.pts):
            a = v.P(tuple(pt[i] + oa[i] for i in range(3)))
            b = v.P(tuple(pt[i] + ob[i] for i in range(3)))
            if math.dist(a, b) > 20:
                msp.add_line(a, b, dxfattribs={"layer": "4-DUONG-BUNG"})
                key = (j.hw, j.step, by_tag[j.a].ptype, by_tag[j.b].ptype)
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if key not in tagged and math.dist(a, b) > 160 and \
                        all(math.dist(m, t) > 140 for t in tag_pos):
                    tagged.add(key)
                    tag_pos.append(m)
                    hw_tag(msp, m, j.hw)
    # số vị trí: mỗi loại 1 balloon, tại chi tiết lộ diện nhiều nhất
    anchors = {}
    for ptype in nums:
        best = max((q for q in parts if q.ptype == ptype), key=lambda q: vis[q.tag].area)
        poly = vis[best.tag]
        if poly.is_empty:
            continue
        rp = poly.representative_point()
        anchors[ptype] = v.sheet((rp.x, rp.y))
    pos = place_balloons(anchors, sheet_outline(v, vis), 160, 45)
    for ptype, c in pos.items():
        balloon(msp, c, nums[ptype], anchors[ptype])
    return v


def draw_step(msp, p, parts, joints, nums, step, region, title, lines):
    """Hình bước lắp: cụm đã lắp xám, chi tiết mới màu + bung + mũi tên."""
    mods_upto, acc = {}, set()
    for i, (mods, _) in enumerate(STEP_MODULES):
        acc |= set(mods)
        mods_upto[i + 1] = set(acc)
    new = set(STEP_MODULES[step - 1][0])
    level = STEP_MODULES[step - 1][1]
    items, offs = [], {}
    by_tag = {q.tag: q for q in parts}
    for q in parts:
        if q.module not in mods_upto[step]:
            continue
        if q.module in new:
            o = explode_offset(q, p, level)
            if q.module == LEG_MODULE:
                o = (0, 0, -p["ex_leg"] * 0.8)
            items.append((q.tag, shift(q.box, o), mod_layer(q.module)))
        else:
            o = (0, 0, 0)
            items.append((q.tag, q.box, "8-CUM-DA-LAP"))
        offs[q.tag] = o
    v = fit_view("iso", [b for _, b, _ in items], region, margin=170)
    vis = render_boxes(msp, v, items)
    for j in joints:
        if j.step != step or j.a not in offs or j.b not in offs:
            continue
        for pt in j.pts:
            a = v.P(tuple(pt[i] + offs[j.a][i] for i in range(3)))
            b = v.P(tuple(pt[i] + offs[j.b][i] for i in range(3)))
            if math.dist(a, b) > 10:
                msp.add_line(a, b, dxfattribs={"layer": "4-DUONG-BUNG"})
    # mũi tên chiều lắp cho mỗi cụm mới
    groups = {}
    for q in parts:
        if q.module in new and math.dist((0, 0, 0), offs[q.tag]) > 1:
            groups.setdefault((q.module, offs[q.tag]), []).append(q)
    for (m, o), qs in groups.items():
        c = [sum((q.box[i] + q.box[i + 3]) / 2 for q in qs) / len(qs) for i in range(3)]
        a = v.P(tuple(c[i] + o[i] * 1.0 for i in range(3)))
        b = v.P(tuple(c[i] + o[i] * 0.35 for i in range(3)))
        if level == "part":
            continue
        arrow(msp, a, b)
    # số vị trí chi tiết mới
    anchors = {}
    for ptype in nums:
        cands = [q for q in parts if q.ptype == ptype and q.module in new]
        if not cands:
            continue
        best = max(cands, key=lambda q: vis[q.tag].area)
        if vis[best.tag].is_empty:
            continue
        rp = vis[best.tag].representative_point()
        anchors[ptype] = v.sheet((rp.x, rp.y))
    pos = place_balloons(anchors, sheet_outline(v, vis), 90, 38)
    for ptype, c in pos.items():
        balloon(msp, c, nums[ptype], anchors[ptype], r=38)
    # tiêu đề + hướng dẫn
    tx, ty = region[0], region[1] - 90
    msp.add_circle((tx + 55, ty + 15), 55, dxfattribs={"layer": "6-CHU", "color": 1})
    text(msp, str(step), (tx + 55, ty + 15), h=6, align=TextEntityAlignment.MIDDLE_CENTER, color=1)
    text(msp, title, (tx + 130, ty), h=3.0)
    mtext(msp, "\\P".join(lines), (tx, ty - 90), h=2.5, width=region[2] - region[0])


def draw_tables(msp, p, parts, joints, nums, x0, y_top):
    """Bảng kê chi tiết + phụ kiện, vẽ từ trên xuống. Trả về y đáy."""
    cols = [("VT", 90), ("Tên chi tiết / Part name", 720), ("Module", 230),
            ("SL", 100), ("Kích thước L×W×T (mm)", 430), ("Vật liệu", 330)]
    rh = 62
    width = sum(w for _, w in cols)
    cnt = Counter(q.ptype for q in parts)
    rows = []
    for ptype, n in nums.items():
        q = next(q for q in parts if q.ptype == ptype)
        mods = sorted({x.module for x in parts if x.ptype == ptype})
        L, Wd, T = q.size
        rows.append([str(n), f"{PART_TYPES[ptype][0]} / {PART_TYPES[ptype][1]}", ",".join(mods),
                     str(cnt[ptype]), f"{L:g}×{Wd:g}×{T:g}", PART_TYPES[ptype][3].split(" / ")[0]])
    y = table(msp, x0, y_top, cols, rows, rh, "BẢNG KÊ CHI TIẾT / PARTS LIST")
    hc = Counter(j.hw for j in joints for _ in j.pts)
    cols2 = [("Mã", 90), ("Phụ kiện / Hardware", 1150), ("Dùng ở bước", 330), ("SL", 100), ("Ghi chú", 230)]
    rows2 = []
    for code, (vn, en, _) in HARDWARE.items():
        steps = sorted({j.step for j in joints if j.hw == code})
        rows2.append([code, f"{vn} / {en}".replace("Ø", "%%c"), ", ".join(map(str, steps)), str(hc[code]), ""])
    y = table(msp, x0, y - 80, cols2, rows2, rh, "BẢNG PHỤ KIỆN / HARDWARE LIST")
    return y, width


def table(msp, x0, y_top, cols, rows, rh, title):
    width = sum(w for _, w in cols)
    text(msp, title, (x0, y_top + 25), h=3.5, layer="7-BANG-KE")
    y = y_top
    allrows = [[c for c, _ in cols]] + rows
    for ri, r in enumerate(allrows):
        x = x0
        for (name, w), cell in zip(cols, r):
            msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y - rh), (x, y - rh)], close=True,
                               dxfattribs={"layer": "7-BANG-KE"})
            text(msp, cell, (x + 15, y - rh / 2), h=2.2 if ri else 2.3, layer="7-BANG-KE",
                 align=TextEntityAlignment.MIDDLE_LEFT)
            x += w
        y -= rh
    msp.add_lwpolyline([(x0, y_top), (x0 + width, y_top), (x0 + width, y), (x0, y)], close=True,
                       dxfattribs={"layer": "0-KHUNG-BANVE"})
    return y


def projection_symbol(msp, c, proj, k=1.0):
    """Ký hiệu phép chiếu (ISO 128 / TCVN): nón cụt."""
    x, y = c
    h = 60 * k
    L = "0-KHUNG-BANVE"
    cone_x = x + (0 if proj == "first" else 220 * k)
    circ_x = x + (220 * k if proj == "first" else 0)
    msp.add_lwpolyline([(cone_x, y - h / 2), (cone_x + 120 * k, y - h), (cone_x + 120 * k, y + h),
                        (cone_x, y + h / 2)], close=True, dxfattribs={"layer": L})
    msp.add_circle((circ_x + 60 * k, y), h, dxfattribs={"layer": L})
    msp.add_circle((circ_x + 60 * k, y), h / 2, dxfattribs={"layer": L})


def draw_frame(msp, p, proj):
    L = "0-KHUNG-BANVE"
    msp.add_lwpolyline([(0, 0), (SHEET_W, 0), (SHEET_W, SHEET_H), (0, SHEET_H)], close=True,
                       dxfattribs={"layer": L, "const_width": 0})
    msp.add_lwpolyline([(200, 100), (SHEET_W - 100, 100), (SHEET_W - 100, SHEET_H - 100), (200, SHEET_H - 100)],
                       close=True, dxfattribs={"layer": L, "const_width": 7})
    # khung tên 1800 × 560 (180 × 56 mm)
    x1, y0 = SHEET_W - 100, 100
    x0, y1 = x1 - 1800, y0 + 560
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                       dxfattribs={"layer": L, "const_width": 5})
    for yy in (y0 + 140, y0 + 280, y0 + 420):
        msp.add_line((x0, yy), (x1, yy), dxfattribs={"layer": L})
    for xx in (x0 + 600, x0 + 1200):
        msp.add_line((xx, y0), (xx, y0 + 280), dxfattribs={"layer": L})
    text(msp, "BẢN VẼ BÓC TÁCH LẮP RÁP KHUNG SOFA", (x0 + 40, y1 - 70), h=4.0)
    text(msp, "SOFA FRAME – EXPLODED ASSEMBLY DRAWING", (x0 + 40, y1 - 120), h=2.5)
    text(msp, f"Kích thước bao / Overall: {p['W']:g} × {p['D']:g} × {p['H_back']:g} mm (tham số mẫu)",
         (x0 + 40, y0 + 370), h=2.3)
    cells = [("Tỉ lệ / Scale", "1:10 (3D: không TL)"), ("Khổ / Size", "A1  841×594"),
             ("Đơn vị / Unit", "mm"), ("Người vẽ / Drawn", ""), ("Ngày / Date", ""),
             ("Số BV / Dwg No.", "SF-KHUNG-00")]
    for i, (k, val) in enumerate(cells):
        cx = x0 + 600 * (i % 3) + 25
        cy = y0 + 280 - 140 * (i // 3)
        text(msp, k, (cx, cy - 40), h=2.0)
        text(msp, val, (cx, cy - 105), h=3.0)
    text(msp, "Phép chiếu góc thứ " + ("nhất (ISO-E / TCVN)" if proj == "first" else "ba (ISO-A)"),
         (x0 + 40, y0 + 305), h=2.3)
    projection_symbol(msp, (x0 + 1450, y0 + 350), proj, 0.75)
    return x0, y1


def notes(msp, pos):
    s = ("GHI CHÚ / NOTES:\\P"
         "1. Kích thước trong bản vẽ là tham số MẪU – phải đối chiếu mẫu thật trước khi sản xuất.\\P"
         "2. Màu theo cụm: xanh dương = khung đáy, xanh nhạt = khung ngồi, xanh lá = gác tay,\\P"
         "    tím = tựa lưng, cam = chân.\\P"
         "3. Nét chấm gạch xanh = đường bung, chỉ vị trí & phương lắp phụ kiện (lục giác A..F).\\P"
         "4. Liên kết chốt (B) bôi keo PVA, kẹp ép ≥ 30 phút; bulông KD (A) chỉ siết sau khi\\P"
         "    đã lắp đủ cụm, kiểm tra vuông góc (đo 2 đường chéo khung đáy lệch ≤ 2 mm).")
    mtext(msp, s, pos, h=2.4, width=1800)


STEPS = [
    ("KHUNG ĐÁY (M1) / BASE FRAME",
     ["Ghép giằng 3, 4 vào đà đáy trước 1 và đà đáy sau 2 bằng chốt B + keo;",
      "vít C ở 2 giằng đầu. Bắt ke góc 5 bằng vít E. Đo chéo kiểm tra vuông."]),
    ("GÁC TAY (M3, M4) / ARMS",
     ["Ghép trụ 9, giằng 11, 12 và thanh 10 bằng chốt B + keo.",
      "Áp gác tay vào 2 đầu khung đáy, bắt bulông A (6 bộ/bên)."]),
    ("KHUNG NGỒI (M2) / SEAT FRAME",
     ["Ghép thanh 6, 7 bằng chốt B; bắt nan 8 bằng vít C.",
      "Đặt lên khung đáy, vít F xuống đà/giằng đáy,",
      "bulông A qua trụ gác tay trước (1 bộ/bên)."]),
    ("TỰA LƯNG (M5) / BACK FRAME",
     ["Ghép thanh đứng 15 với thanh 13, 14 bằng chốt B + keo.",
      "Đặt lên đà đáy sau 2, bulông A vào trụ gác tay sau",
      "(2 bộ/bên), vít C xuống đà đáy sau."]),
    ("CHÂN (M6) / LEGS",
     ["Lật úp sofa lên mặt phẳng có lót, vặn 6 chân 16",
      "bằng bulông treo D. Lật lại, kiểm tra cân bằng,",
      "siết chặt toàn bộ bulông A."]),
]


def make(params=None, proj="first", outdir="output"):
    p, parts, joints = build(params)
    bad = check_overlaps(parts)
    if bad:
        raise SystemExit(f"Lỗi: chi tiết chồng nhau (interference): {bad}")
    nums = part_numbers(parts)
    doc = setup_doc()
    msp = doc.modelspace()
    draw_frame(msp, p, proj)
    draw_ortho(msp, p, parts, proj)
    draw_exploded(msp, p, parts, joints, nums, region=(4300, 2950, 8250, 5600))
    text(msp, "HÌNH BUNG TỔNG THỂ / EXPLODED ISOMETRIC VIEW (không theo tỉ lệ)", (4350, 5680), h=4.0)
    text(msp, "BƯỚC LẮP RÁP / ASSEMBLY SEQUENCE", (300, 1960), h=4.0)
    msp.add_line((250, 2040), (6330, 2040), dxfattribs={"layer": "0-KHUNG-BANVE"})
    sw = (6330 - 280) / len(STEPS)
    for i, (title, lines) in enumerate(STEPS):
        x = 280 + i * sw
        draw_step(msp, p, parts, joints, nums, i + 1, region=(x + 20, 600, x + sw - 40, 1880),
                  title=title, lines=lines)
        if i:
            msp.add_line((x, 150), (x, 1900), dxfattribs={"layer": "0-KHUNG-BANVE"})
    tx = SHEET_W - 100 - 1900
    ybot, _ = draw_tables(msp, p, parts, joints, nums, tx, 2780)
    notes(msp, (tx, ybot - 60))
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "sofa_frame_exploded.dxf")
    doc.saveas(path)
    return doc, path, p, parts, joints, nums


def export_bom(p, parts, joints, nums, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook()
    ws = wb.active
    ws.title = "BOM chi tiết"
    thin = Side(style="thin")
    bd = Border(left=thin, right=thin, top=thin, bottom=thin)
    hdr = ["VT", "Tên chi tiết (VN)", "Part name (EN)", "零件名称 (CN)", "Module", "SL",
           "Dài L", "Rộng W", "Dày T", "Vật liệu", "Thể tích tinh 1 cái (m³)", "Tổng thể tích (m³)"]
    ws.append(["BẢNG KÊ CHI TIẾT KHUNG SOFA – " + f"{p['W']:g}×{p['D']:g}×{p['H_back']:g} mm (tham số mẫu)"])
    ws.append(hdr)
    cnt = Counter(q.ptype for q in parts)
    for ptype, n in nums.items():
        q = next(q for q in parts if q.ptype == ptype)
        L, Wd, T = q.size
        r = ws.max_row + 1
        vn, en, cn, mat = PART_TYPES[ptype]
        ws.append([n, vn, en, cn, ",".join(sorted({x.module for x in parts if x.ptype == ptype})),
                   cnt[ptype], L, Wd, T, mat, f"=G{r}*H{r}*I{r}/1e9", f"=K{r}*F{r}"])
    last = ws.max_row
    ws.append(["", "TỔNG / TOTAL", "", "", "", f"=SUM(F3:F{last})", "", "", "", "", "", f"=SUM(L3:L{last})"])
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for c in row:
            c.border = bd
            c.alignment = Alignment(vertical="center", wrap_text=True)
    for c in ws[2]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="305496")
    ws["A1"].font = Font(bold=True, size=13)
    for col, w in zip("ABCDEFGHIJKL", [5, 20, 20, 14, 9, 6, 8, 8, 8, 20, 14, 14]):
        ws.column_dimensions[col].width = w
    for r in range(3, ws.max_row + 1):
        ws[f"K{r}"].number_format = ws[f"L{r}"].number_format = "0.00000"
    ws2 = wb.create_sheet("Phụ kiện")
    ws2.append(["Mã", "Phụ kiện (VN)", "Hardware (EN)", "五金 (CN)", "Bước", "SL"])
    hc = Counter(j.hw for j in joints for _ in j.pts)
    for code, (vn, en, cn) in HARDWARE.items():
        ws2.append([code, vn, en, cn, ", ".join(map(str, sorted({j.step for j in joints if j.hw == code}))),
                    hc[code]])
    for row in ws2.iter_rows():
        for c in row:
            c.border = bd
    for c in ws2[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="305496")
    for col, w in zip("ABCDEF", [6, 32, 32, 22, 8, 6]):
        ws2.column_dimensions[col].width = w
    ws3 = wb.create_sheet("Tham số")
    ws3.append(["Tham số", "Giá trị (mm)"])
    for k, val in p.items():
        ws3.append([k, val])
    ws3.column_dimensions["A"].width = 16
    wb.save(path)


def preview(doc, base):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    fig = plt.figure(figsize=(33.1, 23.4))
    ax = fig.add_axes([0, 0, 1, 1])
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.COLOR,
                        lineweight_scaling=1.2)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace())
    ax.set_xlim(0, SHEET_W); ax.set_ylim(0, SHEET_H); ax.set_aspect("equal"); ax.axis("off")
    fig.savefig(base + "_preview.png", dpi=110)
    fig.savefig(base + "_preview.pdf")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", help="file JSON ghi đè PARAMS")
    ap.add_argument("--projection", choices=["first", "third"], default="first")
    ap.add_argument("--out", default="output")
    ap.add_argument("--no-preview", action="store_true")
    a = ap.parse_args()
    prm = json.load(open(a.params, encoding="utf-8")) if a.params else None
    doc, path, p, parts, joints, nums = make(prm, a.projection, a.out)
    base = os.path.splitext(path)[0]
    export_bom(p, parts, joints, nums, base + "_BOM.xlsx")
    if not a.no_preview:
        preview(doc, base)
    print("Đã tạo:", path, base + "_BOM.xlsx", base + "_preview.png")
