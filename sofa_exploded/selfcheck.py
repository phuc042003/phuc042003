# -*- coding: utf-8 -*-
"""
TỰ KIỂM TRA BỘ BẢN VẼ + CHẤM ĐIỂM /10
=======================================
10 tiêu chí, mỗi tiêu chí 1 điểm (chấm theo tỉ lệ đạt). Ghi output/TU-KIEM-TRA.md.
  1. Mọi trang khổ A4 và không có nét/chữ nào lọt ra ngoài khung bản vẽ
  2. Không có chữ chồng chữ
  3. Mỗi cụm đúng 1 trang
  4. Mỗi biến thể gỗ có 1 trang chi tiết; không xuất trang chi tiết pát sắt
  5. Trang cụm có số vị trí cho mọi chi tiết của cụm
  6. Trang lắp ráp không có nét khuất
  7. Chi tiết vát / biên dạng đặc biệt có ghi góc + dim đoạn vát
  8. Chi tiết có lỗ: bảng toạ độ đủ lỗ + có dim kích thước (tổng + vị trí lỗ)
  9. Quy tắc phụ kiện (chiều dài bulông theo ván, Ø10/Ø8) + quy tắc vật liệu ván ép/LVL
 10. Chi tiết cùng KT khác lỗ có ký hiệu phân biệt (mã chữ + cảnh báo)
"""
import os
from collections import Counter

from ezdxf import bbox

from sofa_model import BOLT_LEN, MODULES

PW, PH = 2970, 2100
INNER = (200 - 5, 100 - 5, PW - 100 + 5, PH - 100 + 5)


def _text_box(e):
    h = e.dxf.height
    s = e.dxf.text.replace("%%c", "Ø")
    w = len(s) * h * 0.6 * e.dxf.get("width", 1)
    ha, va = e.dxf.get("halign", 0), e.dxf.get("valign", 0)
    p = e.dxf.align_point if (ha or va) and e.dxf.hasattr("align_point") else e.dxf.insert
    x, y = p[0], p[1]
    x0 = x - (w / 2 if ha in (1, 4) else w if ha == 2 else 0)
    y0 = y - (h / 2 if va == 2 else h if va == 3 else 0)
    return (x0, y0, x0 + w, y0 + h)


def _overlap(a, b):
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        return 0
    sa = (a[2] - a[0]) * (a[3] - a[1])
    sb = (b[2] - b[0]) * (b[3] - b[1])
    return ix * iy / max(min(sa, sb), 1e-9)


def run(c, docs, out):
    res, notes = [], {}
    N = len(docs)
    # 1. A4 + trong khung
    bad1 = []
    for doc, path, name in docs:
        msp = doc.modelspace()
        ents = [e for e in msp if not (e.dxf.layer == "0-KHUNG-BANVE" and e.dxftype() == "LWPOLYLINE")]
        ext = bbox.extents(ents)
        if ext.has_data and (ext.extmin.x < INNER[0] or ext.extmin.y < INNER[1] or ext.extmax.x > INNER[2]
                             or ext.extmax.y > INNER[3]):
            bad1.append(f"{name} ({ext.extmin.x:.0f},{ext.extmin.y:.0f})–({ext.extmax.x:.0f},{ext.extmax.y:.0f})")
    res.append(("Khổ A4, không lọt khung", 1 - len(bad1) / N, bad1))
    # 2. chữ chồng chữ
    bad2 = []
    for doc, path, name in docs:
        boxes = [(_text_box(e), e.dxf.text) for e in doc.modelspace().query("TEXT")]
        n = 0
        ex = []
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if _overlap(boxes[i][0], boxes[j][0]) > 0.25:
                    n += 1
                    if len(ex) < 3:
                        ex.append(f"'{boxes[i][1][:18]}'×'{boxes[j][1][:18]}'")
        if n:
            bad2.append(f"{name}: {n} cặp ({'; '.join(ex)})")
    res.append(("Không chữ chồng chữ", 1 - len(bad2) / N, bad2))
    # 3. mỗi cụm 1 trang
    mp = c.report.get("module_pages", {})
    bad3 = [m for m in MODULES if mp.get(m, 0) != 1]
    res.append(("Mỗi cụm đúng 1 trang", 1 - len(bad3) / len(MODULES), bad3))
    # 4. trang chi tiết
    pp = c.report.get("part_pages", {})
    wood = [k for k, g in c.var.items() if not g["metal"]]
    metal_pages = [k for k, g in c.var.items() if g["metal"] and k in pp]
    bad4 = [k for k in wood if k not in pp] + [f"có trang sắt {k}" for k in metal_pages]
    res.append(("Trang chi tiết đủ, không xuất pát", 1 - len(bad4) / max(len(wood), 1), bad4))
    # 5. số vị trí trên trang cụm
    bad5 = []
    for doc, path, name in docs:
        if not name.startswith("CUM-"):
            continue
        m = name.split("_")[0][4:]
        texts = {e.dxf.text for e in doc.modelspace().query("TEXT") if e.dxf.layer == "5-SO-VI-TRI"}
        miss = [l for l in c.report["module_labels"][m] if l not in texts]
        if miss:
            bad5.append(f"{m}: thiếu {miss}")
    res.append(("Đủ số vị trí trên trang cụm", 1 - len(bad5) / len(MODULES), bad5))
    # 6. không nét khuất ở trang lắp
    bad6 = []
    asm = [d for d in docs if not d[2].startswith("VT")]
    for doc, path, name in asm:
        n = len(doc.modelspace().query('*[layer=="2-NET-KHUAT"]'))
        if n:
            bad6.append(f"{name}: {n} nét khuất")
    res.append(("Hình lắp không nét khuất", 1 - len(bad6) / max(len(asm), 1), bad6))
    # 7. góc vát
    special = [k for k, v in pp.items() if not v["rect"]]
    bad7 = [k for k in special if not pp[k]["angles"]]
    for doc, path, name in docs:
        for k in special:
            if name.startswith(f"VT{k}_") and not any("°" in e.dxf.text for e in doc.modelspace().query("TEXT")):
                bad7.append(f"{k}: không có chữ góc")
    res.append(("Vát/biên dạng có ghi góc", 1 - len(set(bad7)) / max(len(special), 1), bad7))
    notes["special"] = special
    # 8. lỗ: bảng đủ + có dim
    bad8 = []
    for doc, path, name in docs:
        if not name.startswith("VT"):
            continue
        code = name.split("_")[0][2:]
        info = pp.get(code)
        if not info:
            continue
        ndim = len(doc.modelspace().query("DIMENSION"))
        if info["holes"] and info["table"] != info["holes"]:
            bad8.append(f"{code}: bảng {info['table']}/{info['holes']} lỗ")
        if ndim < 3 + (1 if info["holes"] else 0):
            bad8.append(f"{code}: chỉ {ndim} dim")
    res.append(("Lỗ có bảng toạ độ + dim", 1 - len(bad8) / max(len(pp), 1), bad8))
    # 9. quy tắc phụ kiện + vật liệu
    bad9 = []
    for j in c.joints:
        if j.hw in ("P8", "P6"):
            t = round(c.by[j.b].thick)
            if j.length is None or BOLT_LEN.get(t) != j.length:
                bad9.append(f"{j.hw} {j.a}->{j.b}: ván {t}, bulông {j.length}")
    from holes import hole_desc
    for code, dia in (("T10", 10), ("N8", 8)):
        if hole_desc(code)[1] != dia:
            bad9.append(f"lỗ {code} sai Ø")
    for k in c.var:
        if "CHƯA XÁC ĐỊNH" in c.material(k):
            bad9.append(f"vật liệu {k} chưa xác định")
    njt = sum(1 for j in c.joints if j.hw in ("P8", "P6")) + len(c.var)
    res.append(("Quy tắc phụ kiện + vật liệu", 1 - len(bad9) / max(njt, 1), bad9))
    # 10. phân biệt biến thể
    sib = [k for k, v in pp.items() if v["sib"]]
    bad10 = []
    for doc, path, name in docs:
        for k in sib:
            if name.startswith(f"VT{k}_") and not any("KHÁC LỖ" in e.dxf.text for e in doc.modelspace().query("TEXT")):
                bad10.append(k)
    res.append(("Biến thể khác lỗ có ký hiệu", 1 - len(bad10) / max(len(sib), 1), bad10))

    # 11. khoanh vùng + chi tiết pát sắt
    bad11 = []
    circ = c.report.get("circles", {})
    metal_tags = [q.tag for q in c.parts if q.ptype in ("pat_L", "pat_flat", "steel_bar")]
    ov = {tg for _, tg in circ.get("pat_overview", [])}
    bad11 += [f"chưa khoanh {t_} ở trang vị trí pát" for t_ in metal_tags if t_ not in ov]
    for m in ("M2", "M5"):
        mt = {tg for _, tg in circ.get(f"module {m}", [])}
        need = [q.tag for q in c.parts if q.module == m and q.tag in metal_tags]
        bad11 += [f"trang cụm {m} chưa khoanh {t_}" for t_ in need if t_ not in mt]
    for d in c.details:
        info = c.report.get("details", {}).get(d["label"])
        if not info or not info["holes"]:
            bad11.append(f"chi tiết {d['label']} thiếu chỗ bắn")
    res.append(("Khoanh vùng + chi tiết pát", 1 - len(bad11) / max(len(metal_tags) * 2, 1), bad11))

    score = round(sum(max(0, r[1]) for r in res) / len(res) * 10, 2)
    lines = [f"# TỰ KIỂM TRA BỘ BẢN VẼ – {N} trang A4", "", f"**ĐIỂM: {score} / 10**", "",
             "| # | Tiêu chí | Điểm | Lỗi |", "|---|---|---|---|"]
    for i, (nm, sc, bad) in enumerate(res, 1):
        lines.append(f"| {i} | {nm} | {max(0, sc):.2f} | {'; '.join(map(str, bad[:6])) or '—'} |")
    lines += ["", f"Chi tiết biên dạng đặc biệt: {', '.join(notes['special']) or '—'}",
              f"Biến thể cùng KT khác lỗ: {', '.join(sib) or '—'}",
              f"Hướng nhìn phụ tự động ở trang cụm: " + ", ".join(f"{m}: {v[0] or 'không cần'}"
                                                             for m, v in c.report.get('aux', {}).items())]
    with open(os.path.join(out, "TU-KIEM-TRA.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return score, res


def run_compact(c, docs, out):
    """Tự kiểm tra bộ GỌN 5 trang."""
    res = []
    N = len(docs)
    texts = {name: [e.dxf.text for e in doc.modelspace().query("TEXT")] for doc, _, name in docs}
    tbl_txt = {name: " | ".join(e.dxf.text for e in doc.modelspace().query("TEXT") if e.dxf.layer == "7-BANG-KE")
               for doc, _, name in docs}
    # 1 A4 trong khung
    bad = []
    for doc, path, name in docs:
        ents = [e for e in doc.modelspace() if not (e.dxf.layer == "0-KHUNG-BANVE" and e.dxftype() == "LWPOLYLINE")]
        ext = bbox.extents(ents)
        if ext.has_data and (ext.extmin.x < INNER[0] or ext.extmin.y < INNER[1] or ext.extmax.x > INNER[2]
                             or ext.extmax.y > INNER[3]):
            bad.append(f"{name} ({ext.extmin.x:.0f},{ext.extmin.y:.0f})–({ext.extmax.x:.0f},{ext.extmax.y:.0f})")
    res.append(("Khổ A4, không lọt khung", 1 - len(bad) / N, bad))
    # 2 chữ chồng chữ
    bad = []
    for doc, path, name in docs:
        bx = [(_text_box(e), e.dxf.text) for e in doc.modelspace().query("TEXT")]
        n, ex = 0, []
        for i in range(len(bx)):
            for j in range(i + 1, len(bx)):
                if _overlap(bx[i][0], bx[j][0]) > 0.25:
                    n += 1
                    if len(ex) < 3:
                        ex.append(f"'{bx[i][1][:16]}'×'{bx[j][1][:16]}'")
        if n:
            bad.append(f"{name}: {n} cặp ({'; '.join(ex)})")
    res.append(("Không chữ chồng chữ", 1 - len(bad) / N, bad))
    # 3 đúng 5 trang, mỗi cụm thuộc đúng 1 trang
    pm = c.report.get("page_mods", {})
    cover = Counter(m for mods in pm.values() for m in mods)
    bad = ([f"có {N} trang"] if N != 5 else []) + [m for m in MODULES if cover.get(m) != 1]
    res.append(("5 trang, mỗi cụm 1 trang", 1 - len(bad) / (len(MODULES) + 1), bad))
    # 4 mọi chi tiết có trong bảng kê
    bad = []
    for key, mods in pm.items():
        for code in {c.t2c[q.tag] for q in c.parts if q.module in mods}:
            if code not in tbl_txt[key].split(" | "):
                bad.append(f"{key}: thiếu {code}")
    res.append(("Đủ chi tiết trong bảng kê", 1 - len(bad) / max(len(c.var), 1), bad))
    # 5 số vị trí
    bad = []
    for key, labs in c.report.get("page_labels", {}).items():
        have = {e.dxf.text for doc, _, nm in docs if nm == key for e in doc.modelspace().query("TEXT")
                if e.dxf.layer == "5-SO-VI-TRI"}
        bad += [f"{key}: thiếu số {l}" for l in labs if l not in have]
    nl = sum(len(v) for v in c.report.get("page_labels", {}).values())
    res.append(("Đủ số vị trí trên hình bung", 1 - len(bad) / max(nl, 1), bad))
    # 6 không nét khuất
    bad = [f"{name}: {len(doc.modelspace().query('*[layer==\"2-NET-KHUAT\"]'))}" for doc, _, name in docs
           if len(doc.modelspace().query('*[layer=="2-NET-KHUAT"]'))]
    res.append(("Không nét khuất", 1 - len(bad) / N, bad))
    # 7 vát ghi góc trong bảng kê
    from geom import angle_deg
    bad, nsp = [], 0
    for code, g in c.var.items():
        P = g["poly"]
        angs = {round(angle_deg(P[i - 1], P[i], P[(i + 1) % len(P)])) for i in range(len(P))} - {90, 180}
        if angs and not g["metal"]:
            nsp += 1
            key = next(k for k, mods in pm.items() if g["module"] in mods)
            if not any(f"{a}°" in tbl_txt[key] for a in angs):
                bad.append(code)
    res.append(("Vát / biên dạng có ghi góc", 1 - len(bad) / max(nsp, 1), bad))
    # 8 lỗ khoan đủ trong Excel + bulông có chiều dài trên trang
    from openpyxl import load_workbook
    ws = load_workbook(os.path.join(out, "SF_BOM.xlsx"))["Lỗ khoan"]
    nh = sum(len(g["holes"]) for g in c.var.values())
    bad = [] if ws.max_row - 1 == nh else [f"Excel {ws.max_row - 1}/{nh} lỗ"]
    for j in c.joints:
        if j.hw in ("P8", "P6"):
            key = next(k for k, mods in pm.items() if c.by[j.b].module in mods)
            if f"×{j.length}" not in tbl_txt[key]:
                bad.append(f"{key}: thiếu bulông ×{j.length}")
    res.append(("Lỗ khoan (Excel) + chiều dài bulông", 1 - len(set(bad)) / 4, sorted(set(bad))))
    # 9 quy tắc
    bad = []
    for j in c.joints:
        if j.hw in ("P8", "P6") and BOLT_LEN.get(round(c.by[j.b].thick)) != j.length:
            bad.append(f"{j.hw} {j.b}")
    bad += [k for k in c.var if "CHƯA XÁC ĐỊNH" in c.material(k)]
    res.append(("Quy tắc phụ kiện + vật liệu", 1 - len(bad) / max(len(c.var), 1), bad))
    # 10 biến thể khác lỗ được ghi chú
    sib = [k for k, g in c.var.items() if g["siblings"]]
    bad = []
    for code in sib:
        key = next(k for k, mods in pm.items() if c.var[code]["module"] in mods)
        if "khác lỗ" not in tbl_txt[key]:
            bad.append(code)
    res.append(("Biến thể khác lỗ có ghi chú", 1 - len(bad) / max(len(sib), 1), bad))
    # 11 pát: khoanh vùng + chi tiết trong trang cụm
    circ = c.report.get("circles", {})
    bad = []
    for d in c.details:
        key = next(k for k, mods in pm.items() if c.by[d["main"]].module in mods)
        got = {tg for _, tg in circ.get(f"page {key}", [])}
        bad += [f"{key}: chưa khoanh {tg}" for tg, _ in d["points"] if tg not in got]
        if d["label"] not in c.report.get("insets", []):
            bad.append(f"thiếu chi tiết {d['label']}")
    res.append(("Pát: khoanh vùng + chi tiết", 1 - len(bad) / max(len(c.detail_points) + len(c.details), 1), bad))

    # 12 mọi chi tiết gỗ có ô gia công trên trang cụm
    cells = c.report.get("cells", set())
    wood = [k for k, g in c.var.items() if not g["metal"]]
    bad = [k for k in wood if k not in cells]
    res.append(("Ô gia công từng chi tiết trong trang cụm", 1 - len(bad) / max(len(wood), 1), bad))

    score = round(sum(max(0, r[1]) for r in res) / len(res) * 10, 2)
    lines = [f"# TỰ KIỂM TRA BỘ GỌN – {N} trang A4", "", f"**ĐIỂM: {score} / 10**", "",
             "| # | Tiêu chí | Điểm | Lỗi |", "|---|---|---|---|"]
    for i, (nm, sc, bd) in enumerate(res, 1):
        lines.append(f"| {i} | {nm} | {max(0, sc):.2f} | {'; '.join(map(str, bd[:6])) or '—'} |")
    with open(os.path.join(out, "TU-KIEM-TRA.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return score, res
