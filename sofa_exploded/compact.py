# -*- coding: utf-8 -*-
"""
BỘ BẢN VẼ GỌN – 5 TRANG A4
===========================
  1. TỔNG THỂ SẢN PHẨM : hình chiếu KT bao, hình bung nhãn cụm + khoanh pát, trình tự lắp, tổng phụ kiện
  2. GÁC TAY (trái + phải) : hình bung, KT bao, bảng kê, phụ kiện
  3. TỰA LƯNG              : + chi tiết pát nối B (phóng to)
  4. KHUNG NGỒI            : + chi tiết pát L (A) và đầu thanh gia cố (C)
  5. KHUNG ĐÁY + CHÂN
Toạ độ lỗ khoan từng chi tiết: file Excel (sheet "Lỗ khoan"). Bộ đầy đủ: make_a4.py --full
"""
import math
import os
import shutil
from collections import Counter, OrderedDict

import make_a4 as A
import render as R
from ezdxf.enums import TextEntityAlignment as TA
from sofa_model import HOLE_SPEC, METAL_TYPES, MODULES, PART_TYPES, explode_offset, hw_name, solo_offset

PW, PH = A.PW, A.PH
PAGES = [
    ("TONG-THE", "TỔNG THỂ SẢN PHẨM", "OVERALL PRODUCT", None),
    ("GAC-TAY", "GÁC TAY (TRÁI + PHẢI)", "ARMS – LEFT & RIGHT", ["M3", "M4"]),
    ("TUA-LUNG", "TỰA LƯNG", "BACK FRAME", ["M5"]),
    ("KHUNG-NGOI", "KHUNG NGỒI", "SEAT FRAME", ["M2"]),
    ("KHUNG-DAY", "KHUNG ĐÁY + CHÂN", "BASE FRAME + LEGS", ["M1", "M6"]),
]
TITLE = {k: t for k, t, _, _ in PAGES}
STEP_OF = {"M1": 1, "M3": 2, "M4": 2, "M2": 3, "M5": 4, "M6": 5}


# ------------------------------------------------------------------ bảng gọn
def part_rows(c, tags):
    cnt = Counter(c.t2c[t] for t in tags)
    rows = []
    for code in OrderedDict.fromkeys(c.t2c[t] for t in tags):
        g = c.var[code]
        L, W, T = g["dims"]
        note = []
        if g["siblings"]:
            note.append("khác lỗ " + "/".join(s for s in g["siblings"] if s != code))
        from geom import angle_deg
        P = g["poly"]
        angs = sorted({round(angle_deg(P[i - 1], P[i], P[(i + 1) % len(P)]))
                       for i in range(len(P))} - {90, 180})
        if angs and not g["metal"]:
            note.append("vát " + "/".join(f"{a}°" for a in angs))
        if g["metal"]:
            note.append("sắt")
        rows.append([code, PART_TYPES[g["ptype"]][0], cnt[code], f"{L:.4g}×{W:.4g}×{T:.4g}",
                     c.material(code).replace("Ván ép ", "Ván ").replace(" (ngoại lệ – xác nhận)", "*"),
                     ", ".join(note)])
    return rows


def hw_rows(c, mods):
    grp = OrderedDict()
    for j in c.joints:
        ma, mb = c.by[j.a].module, c.by[j.b].module
        if ma not in mods and mb not in mods:
            continue
        key = (j.hw, hw_name(j))
        grp[key] = grp.get(key, 0) + len(j.pts)
    return [[hw, nm.replace("Ø", "%%c"), n] for (hw, nm), n in sorted(grp.items())]


def right_column(c, msp, mods, tags, x0=1790, top=1950, ortho_tags=None, cap=""):
    parts = [c.by[t] for t in (ortho_tags or tags)]
    s, _ = A.ortho(msp, parts, (x0, top - 600, PW - 190, top - 30), c.proj, kmax=1, chain=False,
                   pad=(110, 75, 95, 120), titles=False)
    A.T(msp, f"KÍCH THƯỚC BAO {cap}– đứng / bằng / cạnh ({s})", (x0, top + 25), h=1.4)
    y = top - 640
    y = A.tbl(msp, x0, y, [("VT", 90), ("Tên chi tiết", 290), ("SL", 55), ("L×W×T", 250), ("Vật liệu", 165),
                           ("Ghi chú", 230)], part_rows(c, tags), 40, "BẢNG KÊ CHI TIẾT", h=1.2)
    y = A.tbl(msp, x0, y - 70, [("Mã", 80), ("Phụ kiện (chiều dài bulông theo ván)", 900), ("SL", 100)],
              hw_rows(c, mods), 40, "PHỤ KIỆN", h=1.2)
    return y


# ------------------------------------------------------------------ chi tiết pát (khung nhỏ)
def detail_inset(c, msp, d, region, view_keys):
    box = d["crop"]
    near = [(q, A.clip_part(q, box)) for q in c.parts]
    near = [(q, s) for q, s in near if s]
    main = c.by[d["main"]]
    js = A._detail_joints(c, d)
    groups = OrderedDict()
    for j in js:
        groups.setdefault(hw_name(j), []).append(j)
    num_of = {id(j): i + 1 for i, (_, lst) in enumerate(groups.items()) for j in lst}
    items = [(f"{q.tag}#{i}", s_, A.METAL_LAYER if q.ptype in METAL_TYPES else "1-NET-THAY")
             for q, ss in near for i, s_ in enumerate(ss)]
    x0, y0, x1, y1 = region
    A.rect(msp, x0, y0, x1, y1, layer="13-KHOANH-VUNG")
    leg_h = 34 * len(groups) + 20
    n = len(view_keys)
    w = (x1 - x0) / n
    sts = []
    for i, (vk, vname) in enumerate(view_keys):
        reg = (x0 + i * w, y0 + leg_h, x0 + (i + 1) * w, y1 - 50)
        v, st, ext = A._fit_std(R.ORTHO[vk], [s_ for _, s_, _ in items], reg, 85, kmax=10)
        sts.append(st)
        R.render(msp, v, items)
        cu = [v.p2(pt) for q, ss in near if q.tag == main.tag for s_ in ss for pt in s_.verts]
        mu0, mu1 = min(p[0] for p in cu), max(p[0] for p in cu)
        mw0, mw1 = min(p[1] for p in cu), max(p[1] for p in cu)
        hp = [v.p2(pt) for j in js for pt in j.pts]
        placed = []
        for j in js:
            for pt in j.pts:
                sp = v.P(pt)
                if all(math.dist(sp, q_) > 25 for q_ in placed):
                    placed.append(sp)
                    A._hole_mark(msp, sp, num_of[id(j)])
        mates = ({j.a for j in js} | {j.b for j in js}) - {main.tag}
        ref = [v.p2(pt) for q, ss in near if q.tag in mates for s_ in ss for pt in s_.verts]
        top_ref = max(p[1] for p in ref) if ref else mw1
        k = v.scale
        xs = sorted({round(x, 1) for x in [mu0, mu1] + [h[0] for h in hp] if mu0 - .1 <= x <= mu1 + .1})
        ys = sorted({round(y, 1) for y in [mw0, mw1] + [h[1] for h in hp] if mw0 - .1 <= y <= mw1 + .1})
        xs = A.chain_edges(xs, k, 45) or xs
        ys = A.chain_edges(ys, k, 45) or ys
        u0, u1, w0, w1 = ext
        for p0, p1 in zip(xs, xs[1:]):
            A.dim(msp, (0, v.sheet((0, w0))[1] - 60), v.sheet((p0, mw0)), v.sheet((p1, mw0)), k)
        bx = v.sheet((u1, 0))[0] + 60
        for p0, p1 in zip(ys, ys[1:]):
            A.dim(msp, (bx, 0), v.sheet((mu1, p0)), v.sheet((mu1, p1)), k, 90)
        if top_ref - mw1 > 0.5:          # khoảng hạ mép pát so với mặt thanh: luôn ghi, cột ngoài
            A.dim(msp, (bx + 70, 0), v.sheet((mu1, mw1)), v.sheet((mu1, top_ref)), k, 90)
        A.T(msp, vname, (reg[0] + 15, y1 - 100), h=1.2)
    ttl = f"CHI TIẾT {d['label']} – {d['title']} ({len(d['points'])} chỗ, {' / '.join(dict.fromkeys(sts))})"
    if len(ttl) * 15 * 0.72 > x1 - x0 - 30:
        ttl = f"CHI TIẾT {d['label']} ({len(d['points'])} chỗ, {' / '.join(dict.fromkeys(sts))})"
        A.T(msp, d["title"].capitalize()[:int((x1 - x0 - 30) / (12.5 * 0.75))], (x0 + 15, y1 - 60), h=1.25)
    A.T(msp, ttl, (x0 + 15, y1 - 30), h=1.5, color=1)
    yy = y0 + leg_h - 30
    for i, (nm, lst) in enumerate(groups.items(), 1):
        j0 = lst[0]
        other = j0.b if j0.a == main.tag else j0.a
        hole = HOLE_SPEC[(j0.hw, "b" if j0.b == other else "a")][1]
        txt = (f"({i}) {nm} → {c.t2c[other]} {PART_TYPES[c.by[other].ptype][0]}: {hole} "
               f"[{sum(len(j.pts) for j in lst)}/chỗ]").replace("Ø", "%%c")
        maxc = int((x1 - x0 - 30) / (11.5 * 0.78))
        if len(txt) > maxc:
            txt = txt[:maxc - 1] + "…"
        A.T(msp, txt, (x0 + 15, yy), h=1.15)
        yy -= 34
    c.report.setdefault("insets", []).append(d["label"])


# ------------------------------------------------------------------ các trang
def pg_overall(c, msp):
    s, geo = A.ortho(msp, c.parts, (230, 1180, 1480, PH - 130), c.proj, kmax=1, chain=False,
                     pad=(170, 90, 150, 180), titles=False)
    A.T(msp, f"HÌNH CHIẾU ĐỨNG / BẰNG / CẠNH – KT bao ({s})", (250, PH - 125), h=1.5)
    offs = {q.tag: explode_offset(q, c.p, "full") for q in c.parts}
    labels = OrderedDict((m, [q.tag for q in c.parts if q.module == m and q.ptype not in METAL_TYPES])
                         for m in MODULES)
    A.draw_iso(msp, c, offs, (1500, 420, PW - 120, PH - 130), labels, r=36, gap=100, margin=130,
               ckey="p1", title="HÌNH BUNG TỔNG – nhãn cụm, vòng đỏ = chỗ lắp pát (chi tiết ở trang cụm)")
    lines = []
    for i in range(5):
        t, txt, _ = c.step_text(i)
        pg = {1: "trang 5", 2: "trang 2", 3: "trang 4", 4: "trang 3", 5: "trang 5"}[i + 1]
        lines.append(f"{i + 1}. {t} – {pg}")
    A.MT(msp, "TRÌNH TỰ LẮP RÁP:\\P" + "\\P".join(lines) +
         "\\PVật liệu: dày 3–18 = ván ép, ≥ 20 = LVL. Bulông bắt pát vào ván: ván 9→12, 12→16, 15→18, 18→21; "
         "lỗ %%c10 = ốc 4 chấu M8, lỗ %%c8 = ốc cấy M6. Kích thước là tham số MẪU.", (250, 1150), h=1.4,
         width=1150)
    hc = Counter(hw_name(j) for j in c.joints for _ in j.pts)
    rows = [[k.replace("Ø", "%%c"), n] for k, n in sorted(hc.items())]
    A.tbl(msp, 250, 830, [("Tổng phụ kiện cả bộ", 1000), ("SL", 100)], rows, 29, None, h=1.1)
    c.report.setdefault("page_tags", {})["TONG-THE"] = [t for v_ in labels.values() for t in v_]
    c.report.setdefault("page_labels", {})["TONG-THE"] = list(labels)
    return s


def part_cell(c, msp, code, region):
    """Ô chi tiết gia công thu gọn: biên dạng + dim tổng + dim vị trí lỗ + ký hiệu lỗ + góc vát."""
    from holes import face_name, hole_desc
    from geom import angle_deg
    g = c.var[code]
    L, W, T = g["dims"]
    poly, holes = g["poly"], g["holes"]
    x0, y0, x1, y1 = region
    A.rect(msp, x0, y0, x1, y1, layer="7-BANG-KE")
    sq = bool(g["siblings"])
    cc = (x0 + 38, y1 - 36)
    if sq:
        A.rect(msp, cc[0] - 26, cc[1] - 22, cc[0] + 26, cc[1] + 22, layer="5-SO-VI-TRI")
    else:
        msp.add_circle(cc, 25, dxfattribs={"layer": "5-SO-VI-TRI"})
    A.T(msp, code, cc, h=1.7 if len(code) < 3 else 1.4, align=TA.MIDDLE_CENTER, layer="5-SO-VI-TRI")
    name = PART_TYPES[g["ptype"]][0]
    mat = c.material(code).replace(" (ngoại lệ – xác nhận)", "*")
    maxc = int((x1 - x0 - 90) / (13 * 0.72))
    A.T(msp, f"{name} – SL {len(g['tags'])}"[:maxc], (x0 + 75, y1 - 30), h=1.3)
    line2 = f"{L:.4g}×{W:.4g}×{T:.4g} – {mat}" + (f" – KHÁC LỖ {'/'.join(s for s in g['siblings'] if s != code)}"
                                                  if sq else "")
    A.T(msp, line2[:int((x1 - x0 - 90) / (11 * 0.72))], (x0 + 75, y1 - 62), h=1.1, color=1 if sq else None)
    # vùng hình
    nleg = len({(h[0], face_name(h[1], h[2], g["dims"])[0]) for h in holes if h[0] not in ("K2", "H2", "PM")})
    leg_h = 26 * min(3, (nleg + 2) // 3) + 18
    ax0, ay0, ax1, ay1 = x0 + 75, y0 + leg_h + 70, x1 - 55, y1 - 120
    k, st = A.pick_scale(ax1 - ax0, ay1 - ay0, L, W, kmax=10)
    fx = (ax0 + ax1) / 2 - k * L / 2
    fy = (ay0 + ay1) / 2 - k * W / 2
    msp.add_lwpolyline([(fx + k * u, fy + k * v) for u, v in poly], close=True, dxfattribs={"layer": "1-NET-THAY"})
    A.dim(msp, (fx, fy + k * W + 35), (fx, fy + k * W), (fx + k * L, fy + k * W), k)
    A.dim(msp, (fx - 40, fy), (fx, fy), (fx, fy + k * W), k, 90)
    A.T(msp, f"({st})", (x1 - 12, y1 - 95), h=1.1, align=TA.RIGHT)
    rect_like = len(poly) == 4 and all(abs(angle_deg(poly[i - 1], poly[i], poly[(i + 1) % 4]) - 90) < .5
                                       for i in range(4))
    if not rect_like:
        A.angle_marks(msp, poly, fx, fy, k)
    through = {cd for (cd, _d, _dia, dep) in HOLE_SPEC.values() if dep == "xuyên"}
    us, legend = [], OrderedDict()
    for cd, n, (u, v, w) in holes:
        if cd in ("K2", "H2", "PM"):
            continue
        fn = face_name(n, (u, v, w), g["dims"])
        dia = hole_desc(cd)[1]
        if fn == "A":
            A.hole_symbol(msp, (fx + k * u, fy + k * v), dia, k, cd in through)
        elif fn == "B":                         # lỗ mặt B: nét liền + gạch chéo (không dùng nét khuất)
            pc, rr = (fx + k * u, fy + k * v), max(dia * k / 2, 8)
            msp.add_circle(pc, rr, dxfattribs={"layer": "10-PHU-KIEN"})
            msp.add_line((pc[0] - rr * .7, pc[1] - rr * .7), (pc[0] + rr * .7, pc[1] + rr * .7),
                         dxfattribs={"layer": "10-PHU-KIEN"})
        else:                                   # lỗ trên cạnh / đầu: ô vuông nhỏ trên đường biên
            if fn in ("C", "D"):
                p = (fx + k * u, fy + (k * W if fn == "C" else 0))
            else:
                p = (fx + (0 if fn.startswith("E") else k * L), fy + k * v)
            A.rect(msp, p[0] - 7, p[1] - 7, p[0] + 7, p[1] + 7, layer="10-PHU-KIEN")
        us.append(u)
        legend.setdefault((cd, fn[0]), [0, dia])[0] += 1
    ch = A.chain_edges(us + [0, L], k, 75) if us else None
    if ch and len(ch) > 2:
        for p0, p1 in zip(ch, ch[1:]):
            A.dim(msp, (0, fy - 38), (fx + k * p0, fy), (fx + k * p1, fy), k)
    items = [f"{cd}×{n} %%c{dia:g} {fc}" for (cd, fc), (n, dia) in legend.items()]
    per = max(1, int((x1 - x0 - 30) / (11 * 0.62 * 17)))
    yy = y0 + leg_h - 22
    for i in range(0, min(len(items), per * 3), per):
        A.T(msp, "  ".join(items[i:i + per]), (x0 + 15, yy), h=1.05, layer="10-PHU-KIEN")
        yy -= 26
    c.report.setdefault("cells", set()).add(code)


def grid(region, spans, rows=None):
    tot = sum(spans)
    rows = rows or (1 if tot <= 3 else 2)
    per = math.ceil(tot / rows)
    x0, y0, x1, y1 = region
    cw, rh = (x1 - x0) / per, (y1 - y0) / rows
    out, col, row = [], 0, 0
    for sp in spans:
        if col + sp > per:
            col, row = 0, row + 1
        out.append((x0 + col * cw + 6, y1 - (row + 1) * rh + 6, x0 + (col + sp) * cw - 6, y1 - row * rh - 6))
        col += sp
    return out


def pg_module(c, msp, key, mods):
    mine = [q for q in c.parts if q.module in mods]
    tags = [q.tag for q in mine]
    offs = {q.tag: solo_offset(q) for q in mine}
    if key == "GAC-TAY":
        sh = -(c.p["W"] - 1000)
        for q in mine:
            if q.module == "M4":
                offs[q.tag] = tuple(a + b for a, b in zip(offs[q.tag], (sh, 0, 0)))
    if key == "KHUNG-DAY":
        for q in mine:
            if q.module == "M6":
                offs[q.tag] = (0, 0, -c.p["ex_leg"])
    # bảng (phải trên)
    x0 = 1400
    y = A.tbl(msp, x0, 1950, [("VT", 85), ("Tên chi tiết", 330), ("SL", 50), ("L×W×T", 240), ("Vật liệu", 230),
                              ("Ghi chú", 535)], part_rows(c, tags), 33, "BẢNG KÊ CHI TIẾT", h=1.15)
    y = A.tbl(msp, x0, y - 55, [("Mã", 75), ("Phụ kiện (chiều dài bulông theo ván)", 1220), ("SL", 175)],
              hw_rows(c, mods), 33, "PHỤ KIỆN", h=1.15)
    note = " ".join(dict.fromkeys(c.step_text(STEP_OF[m] - 1)[1] for m in mods))
    bb = A.bbox_parts(mine)
    A.MT(msp, f"KT bao cụm: {bb[3] - bb[0]:.0f} × {bb[4] - bb[1]:.0f} × {bb[5] - bb[2]:.0f} mm. CÁCH LẮP: " + note,
         (x0, y - 25), h=1.1, width=1460)
    grid_top = min(y - 150, 1230)
    # hình bung (trái trên)
    labels = c.labels_for(tags)
    jf = lambda j: c.by[j.a].module in mods and c.by[j.b].module in mods
    A.draw_iso(msp, c, offs, (250, grid_top + 20, 1370, PH - 130), labels, square=c.square_set(), joint_filter=jf,
               r=28, gap=75, margin=95, ckey=f"page {key}", circles=[p for p in c.detail_points if p[1] in offs],
               title="HÌNH BUNG LẮP RÁP" + (" (tay phải vẽ dời sát tay trái)" if key == "GAC-TAY" else ""))
    # lưới chi tiết (dưới)
    codes = [cd for cd in OrderedDict.fromkeys(c.t2c[t] for t in tags) if not c.var[cd]["metal"]]
    details = [d for d in c.details if c.by[d["main"]].module in mods]
    spans = [1] * len(codes) + [2] * len(details)
    cells = grid((250, 420, PW - 120, grid_top), spans)
    A.T(msp, "CHI TIẾT GIA CÔNG (toạ độ đầy đủ từng lỗ: Excel sheet 'Lỗ khoan')   Ký hiệu: tròn + = xuyên, tròn chấm = "
             "lỗ tịt mặt A, tròn gạch chéo = lỗ mặt B, ô vuông = lỗ trên cạnh/đầu", (250, grid_top + 8), h=1.15)
    for cd, reg in zip(codes, cells):
        part_cell(c, msp, cd, reg)
    for d, reg in zip(details, cells[len(codes):]):
        detail_inset(c, msp, d, reg, d["views"])
    c.report.setdefault("page_tags", {})[key] = tags
    c.report.setdefault("page_labels", {})[key] = list(labels)
    c.report.setdefault("page_mods", {})[key] = mods
    return "không TL"


def build_compact(params=None, proj="first", out="output", pdf=True, png=None):
    c = A.Ctx(params, proj)
    d4 = os.path.join(out, "A4")
    shutil.rmtree(d4, ignore_errors=True)
    os.makedirs(d4)
    docs = []
    for i, (key, tv, te, mods) in enumerate(PAGES):
        doc = A.setup()
        msp = doc.modelspace()
        sc = pg_overall(c, msp) if mods is None else pg_module(c, msp, key, mods)
        dwg = f"SF-{i + 1:02d}"
        A.frame(msp, tv, te, dwg, sc if mods is None else "không TL", f"{i + 1}/{len(PAGES)}", proj)
        path = os.path.join(d4, f"{dwg}_{key}.dxf")
        doc.saveas(path)
        docs.append((doc, path, key))
    A.export_excel(c, os.path.join(out, "SF_BOM.xlsx"))
    if pdf:
        A.render_pdf(docs, os.path.join(out, "SF_5TRANG_BAN-VE.pdf"), png)
    return c, docs
