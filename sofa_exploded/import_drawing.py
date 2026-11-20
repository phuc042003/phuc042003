# -*- coding: utf-8 -*-
"""
BÓC TÁCH TỪ MÔ HÌNH 3D CỦA KHÁCH (DXF chứa 3DSOLID) -> BỘ BẢN VẼ A4 TRÊN KHUNG CỦA KHÁCH
=========================================================================================
    python import_drawing.py MODEL.dxf --frame KHUNG_A4.dxf --code HT-S801 [--rules rules.json]

Trang: 1 tổng thể + 1 trang/cụm (gác tay, tựa lưng, khung ngồi, khung đáy, mặt giường kéo).
Mỗi trang cụm chứa: hình bung (tự động), bảng tổng hợp vật liệu, lưới ô chi tiết cho MỌI loại
chi tiết (mã, tên, SL, L×W×T, vật liệu, biên dạng + dim tổng).
Phân cụm theo vị trí (rules) – kiểm tra lại bằng mắt và chỉnh trong rules.json nếu cần.
Hạn chế: mô hình không có lỗ khoan / liên kết -> không có phụ kiện, toạ độ lỗ; tên chi tiết đặt
theo hình dạng (cần đổi tên thật); cạnh cong vẽ gần đúng bằng dây cung.
"""
import argparse
import datetime
import json
import math
import os
import shutil
from collections import Counter, OrderedDict, defaultdict

from ezdxf.enums import TextEntityAlignment as TA

import frame_dxf
import make_a4 as A
import make_drawing as md
import render as R
from acis_import import load_parts
from sofa_model import material_of

PW, PH = A.PW, A.PH
CONTENT = (70, 210, 2915, 2050)                  # vùng vẽ trong khung khách (dải khung tên ở chân trang)
MODS = OrderedDict([
    ("ARM", ("GÁC TAY (TRÁI + PHẢI)", 3)),
    ("BACK", ("TỰA LƯNG", 6)),
    ("SEAT", ("KHUNG NGỒI", 140)),
    ("BASE", ("KHUNG ĐÁY", 5)),
    ("DECK", ("MẶT GIƯỜNG KÉO", 1)),
])
DEFAULT_RULES = dict(arm_band=190, body_depth=1075, back_band=215, back_top=390, base_band=150)


class P:
    """Chi tiết nhập từ mô hình (tương thích các hàm vẽ của make_a4)."""

    def __init__(self, d, tag):
        self.tag, self.raw = tag, d
        self.solids = [d["solid"]]
        self.module = None
        self.ptype = "imported"
        self.code = None

    @property
    def box(self):
        return self.solids[0].bbox


def classify(parts, rules):
    xs = [b for q in parts for b in (q.box[0], q.box[3])]
    ys = [b for q in parts for b in (q.box[1], q.box[4])]
    zs = [b for q in parts for b in (q.box[2], q.box[5])]
    x0, x1, y1, z0, z1 = min(xs), max(xs), max(ys), min(zs), max(zs)
    for q in parts:
        b = q.box
        cx, cy, cz = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2
        if cy < y1 - rules["body_depth"]:
            q.module = "DECK"
        elif cx < x0 + rules["arm_band"] or cx > x1 - rules["arm_band"]:
            q.module = "ARM"
        elif cy > y1 - rules["back_band"] or cz > z1 - rules["back_top"]:
            q.module = "BACK"
        elif cz < z0 + rules["base_band"]:
            q.module = "BASE"
        else:
            q.module = "SEAT"


def name_of(d):
    L, W, T = d["dims"]
    Tr = round(T)
    if d["layer"] == "角码":
        n = "Ke góc"
    elif Tr <= 4:
        n = f"Tấm mỏng {Tr}"
    elif Tr <= 18:
        n = f"Ván ép {Tr}" if W >= 120 else f"Nẹp ván {Tr}"
    else:
        n = "Thanh LVL" if L / max(W, 1) >= 4 else "Khối LVL"
    return n + (" (cong)" if d["curved"] else "")


def canon(poly, L, W):
    best = None
    for fu in (False, True):
        for fv in (False, True):
            pts = sorted((round(L - u if fu else u), round(W - v if fv else v)) for u, v in poly)
            best = pts if best is None or pts < best else best
    return tuple(best)


def group(parts):
    """Gom loại: cùng cụm + tên + kích thước + biên dạng (cho lật/xoay tấm vì không có lỗ)."""
    groups = OrderedDict()
    for q in parts:
        d = q.raw
        L, W, T = d["dims"]
        Lp = max(u for u, _ in d["poly"])
        Wp = max(v for _, v in d["poly"])
        key = (q.module, name_of(d), round(L), round(W), round(T), canon(d["poly"], Lp, Wp))
        groups.setdefault(key, []).append(q)
    codes = OrderedDict()
    n = 0
    for m in MODS:
        ks = sorted([k for k in groups if k[0] == m], key=lambda k: (-k[2], -k[3], -k[4]))
        for k in ks:
            n += 1
            code = str(n)
            qs = groups[k]
            d = qs[0].raw
            codes[code] = dict(module=m, name=k[1], dims=d["dims"], poly=d["poly"], qty=len(qs), tags=[q.tag for q in qs],
                               mat=material_of("x", [round(x, 1) for x in d["dims"]]), curved=d["curved"],
                               handles=[q.raw["handle"] for q in qs])
            for q in qs:
                q.code = code
    return codes


# ------------------------------------------------------------------ vẽ
def lay(q, colored=True, gray=False):
    if gray:
        return "8-CUM-DA-LAP"
    return f"IMP-{q.module}" if colored else "1-NET-THAY"


def setup():
    doc = A.setup()
    for m, (_, c) in MODS.items():
        doc.layers.add(f"IMP-{m}", color=c, lineweight=30)
    ds = doc.dimstyles.new("A4S")
    for k, v in dict(dimscale=A.S, dimtxt=1.15, dimasz=1.0, dimexe=0.8, dimexo=0.6, dimgap=0.4, dimdec=0, dimtad=1,
                     dimtxsty="VN", dimclrd=1, dimclre=1, dimclrt=7).items():
        ds.dxf.set(k, v)
    return doc


def sdim(msp, base, p1, p2, k, angle=0):
    if math.dist(p1, p2) < 1:
        return
    msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="A4S", override={"dimlfac": 1.0 / k},
                       dxfattribs={"layer": "3-KICH-THUOC"}).render()


def exploded(msp, parts, offs, region, labels, dirs=(1, -1, 1), layer_fn=lay, r=26, gap=70, margin=90, title=None,
             h=1.5):
    it = [(q.tag, q.solids[0].moved(offs[q.tag]), layer_fn(q)) for q in parts]
    v = R.fit(R.iso_dirs(*dirs), [s for _, s, _ in it], region, margin)
    vis = R.render(msp, v, it)
    anchors = {}
    for lab, tags in labels.items():
        best = max(tags, key=lambda t: vis[t].area if t in vis else -1)
        if best in vis and not vis[best].is_empty:
            rp = vis[best].representative_point()
            anchors[lab] = v.sheet((rp.x, rp.y))
    ol = R.to_sheet(v, A._union(list(vis.values())))
    if anchors:
        for lab, c in md.place_balloons(anchors, ol, gap, r).items():
            A.balloon(msp, c, lab, anchors[lab], r=r, h=h)
    if title:
        A.T(msp, title, (region[0] + 10, region[3] - 15), h=1.6)
    return anchors


def auto_offsets(parts, factor=0.55, extra=(0, 0, 0)):
    """Bung tự động: dời mỗi chi tiết ra xa tâm cụm theo hướng tâm chi tiết."""
    bs = [q.box for q in parts]
    c0 = [(min(b[k] for b in bs) + max(b[k + 3] for b in bs)) / 2 for k in range(3)]
    offs = {}
    for q in parts:
        b = q.box
        c = [(b[k] + b[k + 3]) / 2 for k in range(3)]
        offs[q.tag] = tuple((c[k] - c0[k]) * factor + extra[k] for k in range(3))
    return offs


def cell(msp, code, g, region):
    x0, y0, x1, y1 = region
    A.rect(msp, x0, y0, x1, y1, layer="7-BANG-KE")
    cc = (x0 + 26, y1 - 26)
    msp.add_circle(cc, 19, dxfattribs={"layer": "5-SO-VI-TRI"})
    A.T(msp, code, cc, h=1.3 if len(code) < 3 else 1.1, align=TA.MIDDLE_CENTER, layer="5-SO-VI-TRI")
    L, W, T = g["dims"]
    wchar = 10.5 * 0.7
    nmax = int((x1 - x0 - 60) / wchar)
    A.T(msp, f"{g['name']} – SL {g['qty']}"[:nmax], (x0 + 52, y1 - 20), h=1.05)
    A.T(msp, f"{L:.0f}×{W:.0f}×{T:.0f} – {g['mat']}"[:int((x1 - x0 - 60) / (9.5 * 0.7))], (x0 + 52, y1 - 45),
        h=0.95)
    poly = g["poly"]
    Lp = max(u for u, _ in poly) or 1
    Wp = max(v for _, v in poly) or 1
    ax0, ay0, ax1, ay1 = x0 + 55, y0 + 38, x1 - 25, y1 - 92
    k = min((ax1 - ax0) / Lp, (ay1 - ay0) / Wp)
    st = next((t for kk, t in A.SCALES if kk <= k), None)
    kk = next((kk for kk, t in A.SCALES if kk <= k), k)
    if st is None:
        kk, st = k, f"~1:{1 / k:.0f}"
    fx = (ax0 + ax1) / 2 - kk * Lp / 2
    fy = (ay0 + ay1) / 2 - kk * Wp / 2
    msp.add_lwpolyline([(fx + kk * u, fy + kk * v) for u, v in poly], close=True, dxfattribs={"layer": "1-NET-THAY"})
    sdim(msp, (fx, fy + kk * Wp + 18), (fx, fy + kk * Wp), (fx + kk * Lp, fy + kk * Wp), kk)
    sdim(msp, (fx - 25, fy), (fx, fy), (fx, fy + kk * Wp), kk, 90)
    A.T(msp, f"({st}){' ~cong' if g['curved'] else ''}", (x1 - 8, y0 + 10), h=0.9, align=TA.RIGHT)


def grid(n, region, min_h=190):
    x0, y0, x1, y1 = region
    cols = max(3, min(9, math.ceil(math.sqrt(n * 2.3))))
    rows = math.ceil(n / cols)
    cw = (x1 - x0) / cols
    rh = (y1 - y0) / rows
    return [(x0 + (i % cols) * cw + 4, y1 - (i // cols + 1) * rh + 4, x0 + (i % cols + 1) * cw - 4,
             y1 - (i // cols) * rh - 4) for i in range(n)]


# ------------------------------------------------------------------ trang
def pg_overall(ctx, msp):
    parts = ctx.parts
    s, geo = A.ortho(msp, parts, (CONTENT[0], 1050, 1500, CONTENT[3]), "first", kmax=1, chain=False,
                     pad=(170, 90, 150, 170), titles=False)
    A.T(msp, f"HÌNH CHIẾU ĐỨNG / BẰNG / CẠNH – KT bao ({s}) – không vẽ nét khuất", (CONTENT[0] + 20, CONTENT[3] - 10),
        h=1.5)
    mo = dict(ARM=None, BACK=(0, 450, 380), SEAT=(0, -120, 520), BASE=(0, 0, -380), DECK=(0, -450, 0))
    bs = [q.box for q in parts]
    cx = (min(b[0] for b in bs) + max(b[3] for b in bs)) / 2
    offs = {}
    for q in parts:
        b = q.box
        if q.module == "ARM":
            o = (-420 if (b[0] + b[3]) / 2 < cx else 420, 0, 0)
        else:
            o = mo[q.module]
        offs[q.tag] = o
    present = [m for m in MODS if any(q.module == m for q in parts)]
    labels = OrderedDict((str(i + 2), [q.tag for q in parts if q.module == m]) for i, m in enumerate(present))
    exploded(msp, parts, offs, (1520, 760, CONTENT[2], CONTENT[3]), labels, r=30, gap=90, h=1.8,
             title="HÌNH BUNG TỔNG – số trong vòng = trang của cụm (xem bảng danh mục)")
    rows = []
    for i, m in enumerate(MODS):
        cs = [c for c, g in ctx.codes.items() if g["module"] == m]
        rows.append([str(i + 2), MODS[m][0], sum(ctx.codes[c]["qty"] for c in cs), len(cs),
                     f"{cs[0]}–{cs[-1]}" if cs else ""])
    y = A.tbl(msp, CONTENT[0] + 20, 960, [("Trang", 100), ("Cụm", 520), ("Số CT", 140), ("Số loại", 140),
                                          ("Mã", 220)], rows, 42, "DANH MỤC CỤM", h=1.3)
    mc = Counter()
    vol = defaultdict(float)
    for g in ctx.codes.values():
        mc[g["mat"]] += g["qty"]
        L, W, T = g["dims"]
        vol[g["mat"]] += L * W * T / 1e9 * g["qty"]
    rows2 = [[m_, n_, f"{vol[m_]:.4f}"] for m_, n_ in sorted(mc.items())]
    A.tbl(msp, CONTENT[0] + 20, y - 70, [("Vật liệu (quy tắc dày)", 520), ("Số CT", 140), ("m³ khối bao", 200)],
          rows2[:9], 36, "TỔNG HỢP VẬT LIỆU", h=1.2)
    A.MT(msp, "GHI CHÚ: bóc tách tự động từ mô hình 3D. Mô hình không có lỗ khoan / liên kết nên chưa có phụ kiện và "
              "toạ độ lỗ. Tên chi tiết đặt theo hình dạng – cần đổi tên thật. Cạnh cong vẽ gần đúng. "
              "Vật liệu: dày 3–18 = ván ép, ≥ 20 = LVL.", (1550, 700), h=1.25, width=1350)
    ctx.report["labels"]["TONG-THE"] = list(labels)
    return "TỔNG THỂ SẢN PHẨM", s, len(parts)


def pg_module(ctx, msp, m):
    parts = [q for q in ctx.parts if q.module == m]
    codes = [c for c, g in ctx.codes.items() if g["module"] == m]
    n = len(codes)
    cols = max(3, min(9, math.ceil(math.sqrt(n * 2.3))))
    rows = math.ceil(n / cols)
    gh = min(1250, max(560, rows * 205))
    gtop = CONTENT[1] + gh
    cells = grid(n, (CONTENT[0], CONTENT[1], CONTENT[2], gtop))
    A.T(msp, f"CHI TIẾT ({n} loại, {len(parts)} chi tiết) – biên dạng + kích thước bao; cạnh cong vẽ gần đúng",
        (CONTENT[0], gtop + 12), h=1.2)
    for c, reg in zip(codes, cells):
        cell(msp, c, ctx.codes[c], reg)
    labels = OrderedDict()
    for q in parts:
        labels.setdefault(q.code, []).append(q.tag)
    small = n > 25
    if m == "ARM":                     # tay trái vẽ lớn đủ mã; tay phải vẽ nhỏ, chỉ ghi mã khác tay trái
        bs = [q.box for q in parts]
        cx = (min(b[0] for b in bs) + max(b[3] for b in bs)) / 2
        left = [q for q in parts if (q.box[0] + q.box[3]) / 2 < cx]
        right = [q for q in parts if q not in left]
        lc = {q.code for q in left}
        labL = OrderedDict((c, [t for t in tg if t in {q.tag for q in left}]) for c, tg in labels.items() if c in lc)
        labR = OrderedDict((c, [t for t in tg if t in {q.tag for q in right}]) for c, tg in labels.items()
                           if c not in lc)
        exploded(msp, left, auto_offsets(left, 0.55), (CONTENT[0], gtop + 40, 1380, CONTENT[3]), labL, r=22, gap=60,
                 margin=70, h=1.2, title="HÌNH BUNG – GÁC TAY TRÁI")
        exploded(msp, right, auto_offsets(right, 0.55), (1400, gtop + 40, 1890, CONTENT[3] - 60), labR, r=22, gap=50,
                 margin=60, h=1.2, title="TAY PHẢI (đối xứng – chỉ ghi mã khác)", dirs=(-1, -1, 1))
    else:
        exploded(msp, parts, auto_offsets(parts, 0.6), (CONTENT[0], gtop + 40, 1880, CONTENT[3]), labels,
                 r=22 if small else 26, gap=55 if small else 70, margin=70, h=1.2 if small else 1.4,
                 title="HÌNH BUNG LẮP RÁP")
    mc = Counter()
    vol = defaultdict(float)
    for c in codes:
        g = ctx.codes[c]
        mc[g["mat"]] += g["qty"]
        L, W, T = g["dims"]
        vol[g["mat"]] += L * W * T / 1e9 * g["qty"]
    bs = [q.box for q in parts]
    bb = [round(max(b[k + 3] for b in bs) - min(b[k] for b in bs)) for k in range(3)]
    y = A.tbl(msp, 1920, CONTENT[3] - 30, [("Vật liệu", 420), ("SL", 120), ("m³ bao", 160), ("Mã", 280)],
              [[m_, n_, f"{vol[m_]:.4f}", ",".join(c for c in codes if ctx.codes[c]["mat"] == m_)[:22]]
               for m_, n_ in sorted(mc.items())], 36, f"{MODS[m][0]} – VẬT LIỆU", h=1.15)
    A.MT(msp, f"KT bao cụm (lắp): {bb[0]} × {bb[2]} × {bb[1]} mm (rộng × cao × sâu). {len(parts)} chi tiết / {n} loại."
              f" Chi tiết trái–phải đối xứng dùng chung mã (lật tấm). Mô hình không có lỗ khoan.",
         (1920, y - 30), h=1.15, width=980)
    ctx.report["labels"][m] = list(labels)
    ctx.report["cells"].update(codes)
    return MODS[m][0], "NTS", len(parts)


class Ctx:
    def __init__(self, model, rules):
        raw = load_parts(model)
        self.parts = [P(d, f"S{d['idx']}") for d in raw]
        classify(self.parts, rules)
        self.codes = group(self.parts)
        self.report = dict(labels={}, cells=set(), frame={})


def export_excel(ctx, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook()
    ws = wb.active
    ws.title = "BOM"
    ws.append(["Mã", "Cụm", "Tên (theo hình dạng – sửa lại)", "SL", "Dài L", "Rộng W", "Dày T", "Vật liệu (quy tắc)",
               "Cạnh cong", "Thể tích bao (m³)", "Handle trong DXF"])
    for c, g in ctx.codes.items():
        i = ws.max_row + 1
        L, W, T = g["dims"]
        ws.append([c, MODS[g["module"]][0], g["name"], g["qty"], round(L, 1), round(W, 1), round(T, 1), g["mat"],
                   "có" if g["curved"] else "", f"=E{i}*F{i}*G{i}/1e9*D{i}", " ".join(g["handles"])])
    n = ws.max_row
    ws.append(["", "TỔNG", "", f"=SUM(D2:D{n})", "", "", "", "", "", f"=SUM(J2:J{n})"])
    thin = Side(style="thin")
    for row in ws.iter_rows():
        for cl in row:
            cl.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            cl.alignment = Alignment(vertical="center", wrap_text=True)
    for cl in ws[1]:
        cl.font = Font(bold=True, color="FFFFFF")
        cl.fill = PatternFill("solid", fgColor="305496")
    for col, w in zip("ABCDEFGHIJK", [6, 22, 26, 5, 8, 8, 7, 16, 8, 12, 40]):
        ws.column_dimensions[col].width = w
    wb.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--frame")
    ap.add_argument("--code", default="")
    ap.add_argument("--product", default="")
    ap.add_argument("--rules")
    ap.add_argument("--out", default="output_import")
    ap.add_argument("--png")
    a = ap.parse_args()
    rules = dict(DEFAULT_RULES, **(json.load(open(a.rules, encoding="utf-8")) if a.rules else {}))
    ctx = Ctx(a.model, rules)
    uf = frame_dxf.UserFrame(a.frame, PW, PH) if a.frame else None
    pages = [("TONG-THE", pg_overall, ())] + [(m, pg_module, (m,)) for m in MODS
                                              if any(q.module == m for q in ctx.parts)]
    d4 = os.path.join(a.out, "A4")
    shutil.rmtree(d4, ignore_errors=True)
    os.makedirs(d4)
    docs = []
    today = datetime.date.today().strftime("%d/%m/%Y")
    for i, (key, fn, args) in enumerate(pages):
        doc = setup()
        msp = doc.modelspace()
        title, sc, nqty = fn(ctx, msp, *args)
        vals = dict(title=title, scale=sc, sheet=f"{i + 1}/{len(pages)}", date=today, qty=str(nqty),
                    product=a.product or a.code, code=a.code)
        if uf:
            ctx.report["frame"][key] = uf.place(doc, vals)
        else:
            A.frame(msp, title, a.code, f"{a.code}-{i + 1:02d}", sc, vals["sheet"], "first")
        path = os.path.join(d4, f"{a.code or 'SP'}-{i + 1:02d}_{key}.dxf")
        doc.saveas(path)
        docs.append((doc, path, key))
    export_excel(ctx, os.path.join(a.out, f"{a.code or 'SP'}_BOM.xlsx"))
    json.dump(rules, open(os.path.join(a.out, "rules.json"), "w"), indent=1)
    A.render_pdf(docs, os.path.join(a.out, f"{a.code or 'SP'}_BAN-VE.pdf"), a.png)
    import selfcheck
    selfcheck.run_import(ctx, docs, a.out, MODS, uf is not None)


if __name__ == "__main__":
    main()
