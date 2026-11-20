# -*- coding: utf-8 -*-
"""
NHẬP MÔ HÌNH 3D (3DSOLID / ACIS SAB) TỪ DXF AUTOCAD
=====================================================
- Giải mã dữ liệu SAB của từng 3DSOLID: đỉnh, mặt phẳng, ma trận dời vị trí.
- Dựng khối bao lồi (convex hull) -> geom.Solid để vẽ / khử nét khuất.
- Tính hệ trục riêng của chi tiết (dày = phương có kích thước nhỏ nhất), biên dạng 2D
  (bao lồi các đỉnh chiếu lên mặt tấm), kích thước L×W×T.
Giới hạn: cạnh cong (spline) được thay bằng dây cung nối các đỉnh -> biên dạng cong là gần đúng;
mô hình không có mặt trụ thì không có lỗ khoan.
"""
import math

import ezdxf
import numpy as np
from ezdxf.acis import sab
from scipy.spatial import ConvexHull

from geom import Solid


def _vals(r, tag):
    return [t.value for t in r if getattr(t, "tag", None) == tag]


def decode_solid(e):
    dec = sab.Decoder(e.sab)
    dec.read_header()
    T, pts, planes, n_spline, n_cone = None, [], [], 0, 0
    for r in dec.read_records():
        name = r[0].value
        if name == "transform":
            v, sc = _vals(r, 20), _vals(r, 6)
            T = (v[0], v[1], v[2], v[3], sc[0] if sc else 1.0)
        elif name == "point":
            p = _vals(r, 19)
            if p:
                pts.append(p[0])
        elif name == "plane-surface":
            planes.append((_vals(r, 19)[0], _vals(r, 20)[0]))
        elif name == "spline-surface":
            n_spline += 1
        elif name == "cone-surface":
            n_cone += 1

    def tf(p):
        if not T:
            return tuple(p)
        R0, R1, R2, t, s = T
        return tuple(s * (p[0] * R0[k] + p[1] * R1[k] + p[2] * R2[k]) + t[k] for k in range(3))

    def tv(n):
        if not T:
            return tuple(n)
        R0, R1, R2, _, _ = T
        return tuple(n[0] * R0[k] + n[1] * R1[k] + n[2] * R2[k] for k in range(3))
    return dict(pts=[tf(p) for p in pts], planes=[(tf(p), tv(n)) for p, n in planes],
                spline=n_spline, cone=n_cone)


def hull_solid(P):
    P = np.unique(np.round(np.array(P, dtype=float), 3), axis=0)
    h = ConvexHull(P)
    groups = {}
    for simp, eq in zip(h.simplices, h.equations):
        groups.setdefault(tuple(np.round(eq, 4)), set()).update(simp.tolist())
    faces = []
    for key, idx in groups.items():
        n = np.array(key[:3])
        idx = list(idx)
        c = P[idx].mean(axis=0)
        u = P[idx[0]] - c
        u = u / (np.linalg.norm(u) or 1)
        v = np.cross(n, u)
        ang = [math.atan2(np.dot(P[i] - c, v), np.dot(P[i] - c, u)) for i in idx]
        faces.append((tuple(n), [i for _, i in sorted(zip(ang, idx))]))
    return Solid([tuple(p) for p in P], faces)


def _norm(v):
    L = math.sqrt(sum(x * x for x in v)) or 1.0
    return tuple(x / L for x in v)


def part_frame(planes, pts):
    """3 trục riêng: lấy theo pháp tuyến mặt phẳng phổ biến; trục dày = phương có bề dày nhỏ nhất."""
    dirs = []
    for _, n in planes:
        n = _norm(n)
        for d in dirs:
            if abs(sum(a * b for a, b in zip(n, d[0]))) > 0.999:
                d[1] += 1
                break
        else:
            dirs.append([n, 1])
    dirs.sort(key=lambda d: -d[1])
    e1 = dirs[0][0] if dirs else (0, 0, 1)
    e2 = next((d for d, _ in dirs[1:] if abs(sum(a * b for a, b in zip(d, e1))) < 0.05), None)
    if e2 is None:
        e2 = (1, 0, 0) if abs(e1[0]) < 0.9 else (0, 1, 0)
        dp = sum(a * b for a, b in zip(e2, e1))
        e2 = _norm(tuple(a - dp * b for a, b in zip(e2, e1)))
    e3 = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
    axes = [e1, e2, e3]
    ext = []
    for ax in axes:
        pr = [sum(a * b for a, b in zip(p, ax)) for p in pts]
        ext.append(max(pr) - min(pr))
    order = sorted(range(3), key=lambda k: -ext[k])           # L, W, T
    eu, ev, ew = (axes[k] for k in order)
    return eu, ev, ew, [ext[k] for k in order]


def profile2d(pts, eu, ev):
    P = np.array([[sum(a * b for a, b in zip(p, eu)), sum(a * b for a, b in zip(p, ev))] for p in pts])
    P = np.unique(np.round(P, 2), axis=0)
    if len(P) < 3:
        return [(0, 0)]
    h = ConvexHull(P)
    poly = [tuple(P[i]) for i in h.vertices]
    u0 = min(x for x, _ in poly)
    v0 = min(y for _, y in poly)
    poly = [(x - u0, y - v0) for x, y in poly]
    # bỏ đỉnh gần thẳng hàng
    out = []
    n = len(poly)
    for i in range(n):
        a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cr) > 1e-3 * max(1.0, math.dist(a, b) * math.dist(b, c)):
            out.append(b)
    return out or poly


def load_parts(path):
    d = ezdxf.readfile(path)
    out = []
    for i, e in enumerate(d.modelspace().query("3DSOLID")):
        info = decode_solid(e)
        if len(info["pts"]) < 4:
            continue
        eu, ev, ew, dims = part_frame(info["planes"], info["pts"])
        out.append(dict(idx=i, handle=e.dxf.handle, layer=e.dxf.layer, pts=info["pts"], solid=hull_solid(info["pts"]),
                        dims=dims, axes=(eu, ev, ew), poly=profile2d(info["pts"], eu, ev),
                        curved=info["spline"] > 0, holes=info["cone"]))
    return out
