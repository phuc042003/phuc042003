# -*- coding: utf-8 -*-
"""
LỖ KHOAN & BIẾN THỂ CHI TIẾT (mặt bất kỳ, kể cả mặt vát)
==========================================================
Hệ toạ độ RIÊNG của chi tiết (local):
    X (u) dọc cạnh dài nhất của biên dạng, Z (w) theo chiều dày (trục đùn), Y (v) = Z × X.
    Gốc O = góc nhỏ nhất của khung bao biên dạng; L×W×T = kích thước theo u, v, w.
Mặt: A (+Z) / B (−Z) = 2 mặt lớn; C (+Y) / D (−Y) cạnh dọc; E (X=0) / F (X=L) đầu;
     mặt nghiêng (vát) ghi thêm "vát".
Biến thể: cùng loại + cùng biên dạng + cùng mẫu lỗ (sau khi lật 180° quanh X/Y/Z) => cùng mã;
không coi đối xứng gương là giống; lỗ xuyên không phân biệt mặt vào.
"""
import math
from collections import OrderedDict, defaultdict

from geom import v_cross, v_dot, v_norm, v_sub
from sofa_model import HOLE_SPEC, METAL_TYPES

TOL = 0.02
THROUGH = {c for (c, _d, _dia, dep) in HOLE_SPEC.values() if dep == "xuyên"}
FACE_DESC = {"A": "mặt A (+Z)", "B": "mặt B (−Z)", "C": "cạnh C (+Y)", "D": "cạnh D (−Y)",
             "E": "đầu E (X=0)", "F": "đầu F (X=L)", "Ev": "đầu E – mặt vát", "Fv": "đầu F – mặt vát"}


class Frame:
    def __init__(self, part):
        from geom import AX, embed
        ax = [0.0, 0.0, 0.0]
        ax[AX[part.plane][2]] = 1.0
        self.ew = tuple(ax)
        pts3 = [embed(part.plane, a, b, part.t0) for a, b in part.poly]
        n = len(pts3)
        best = max(range(n), key=lambda i: (math.dist(pts3[i], pts3[(i + 1) % n]), -i))
        self.eu = v_norm(v_sub(pts3[(best + 1) % n], pts3[best]))
        self.ev = v_cross(self.ew, self.eu)
        us = [v_dot(p, self.eu) for p in pts3]
        vs = [v_dot(p, self.ev) for p in pts3]
        self.o = (min(us), min(vs), part.t0 if self.ew[AX[part.plane][2]] > 0 else part.t1)
        self.poly = [(u - self.o[0], v - self.o[1]) for u, v in zip(us, vs)]
        self.dims = (max(us) - min(us), max(vs) - min(vs), part.t1 - part.t0)

    def pt(self, p):
        return (v_dot(p, self.eu) - self.o[0], v_dot(p, self.ev) - self.o[1], v_dot(p, self.ew) - self.o[2])

    def vec(self, n):
        return (v_dot(n, self.eu), v_dot(n, self.ev), v_dot(n, self.ew))


def _contact(A, B, pt):
    for sa in A.solids:
        fa = sa.faces_at(pt, TOL)
        if not fa:
            continue
        for sb in B.solids:
            for nb, _ in sb.faces_at(pt, TOL):
                for na, _ in fa:
                    if v_dot(na, nb) < -0.999:
                        return na, nb
    return None


def instance_holes(parts, joints):
    by = {q.tag: q for q in parts}
    holes, problems = defaultdict(list), []
    for j in joints:
        A, B = by[j.a], by[j.b]
        for pt in j.pts:
            c = _contact(A, B, pt)
            if not c:
                problems.append((j.hw, j.a, j.b, pt))
                continue
            holes[A.tag].append(dict(pt=pt, n=c[0], code=HOLE_SPEC[(j.hw, "a")][0], hw=j.hw, length=j.length))
            holes[B.tag].append(dict(pt=pt, n=c[1], code=HOLE_SPEC[(j.hw, "b")][0], hw=j.hw, length=j.length))
    return holes, problems


def _r(x, d=1):
    return round(x + 0.0, d) + 0.0


def _norm_through(h, dims):
    code, n, p = h
    if code not in THROUGH:
        return h
    p = list(p)
    n = list(n)
    for k in range(3):
        if n[k] < -0.999:
            n[k] = 1.0
            p[k] = dims[k]
    return (code, tuple(n), tuple(p))


def _transform(poly, holes, dims, r):
    L, W, T = dims
    if r is None:
        return poly, holes
    f = {0: lambda u, v, w: (u, W - v, T - w), 1: lambda u, v, w: (L - u, v, T - w),
         2: lambda u, v, w: (L - u, W - v, w)}[r]
    s = {0: (1, -1, -1), 1: (-1, 1, -1), 2: (-1, -1, 1)}[r]
    P = [f(u, v, 0)[:2] for u, v in poly]
    H = [(c, tuple(n[k] * s[k] for k in range(3)), f(*p)) for c, n, p in holes]
    return P, H


def signature(poly, holes, dims):
    best = None
    for r in (None, 0, 1, 2):
        P, H = _transform(poly, holes, dims, r)
        H = [_norm_through(h, dims) for h in H]
        sig = (tuple(sorted((_r(u), _r(v)) for u, v in P)),
               tuple(sorted((c, tuple(_r(x, 2) for x in n), tuple(_r(x) for x in p)) for c, n, p in H)))
        if best is None or sig < best[0]:
            best = (sig, P, H)
    return best


def face_name(n, p=None, dims=None):
    """Tên mặt; mặt nghiêng (vát) đặt theo đầu gần nhất: 'Ev' / 'Fv'."""
    nu, nv, nw = n
    if nw > 0.9:
        return "A"
    if nw < -0.9:
        return "B"
    if abs(nv) > 0.999:
        return "C" if nv > 0 else "D"
    if abs(nu) > 0.999:
        return "F" if nu > 0 else "E"
    if p is not None and dims is not None:
        return ("E" if p[0] < dims[0] / 2 else "F") + "v"
    return ("F" if nu > 0 else "E") + "v"


def variants(parts, joints, nums):
    ih, problems = instance_holes(parts, joints)
    groups = OrderedDict()
    for q in parts:
        fr = Frame(q)
        hs = [(h["code"], fr.vec(h["n"]), fr.pt(h["pt"])) for h in ih.get(q.tag, [])]
        sig, P, H = signature(fr.poly, hs, fr.dims)
        key = (q.ptype, tuple(_r(d) for d in fr.dims), sig)
        g = groups.setdefault(key, dict(ptype=q.ptype, dims=fr.dims, poly=P, holes=H, tags=[], module=q.module,
                                        lengths=sorted({h["length"] for h in ih.get(q.tag, []) if h["length"]})))
        g["tags"].append(q.tag)
    by_type = defaultdict(list)
    for g in groups.values():
        by_type[g["ptype"]].append(g)
    out, tag2code = OrderedDict(), {}
    for ptype, n in nums.items():
        gs = sorted(by_type[ptype], key=lambda g: -len(g["tags"]))
        for i, g in enumerate(gs):
            code = str(n) if len(gs) == 1 else f"{n}{chr(65 + i)}"
            g.update(code=code, n=n, metal=ptype in METAL_TYPES,
                     siblings=[f"{n}{chr(65 + k)}" for k in range(len(gs))] if len(gs) > 1 else [])
            out[code] = g
            for t in g["tags"]:
                tag2code[t] = code
    return out, tag2code, problems


def hole_desc(code):
    for (c, desc, dia, dep) in HOLE_SPEC.values():
        if c == code:
            return desc, dia, dep
    return code, 0, ""


def diff_holes(a, b):
    """Lỗ có ở biến thể a mà không có ở b (đếm theo mã lỗ)."""
    from collections import Counter
    ca = Counter(h[0] for h in a["holes"])
    cb = Counter(h[0] for h in b["holes"])
    plus = {k: ca[k] - cb.get(k, 0) for k in ca if ca[k] > cb.get(k, 0)}
    minus = {k: cb[k] - ca.get(k, 0) for k in cb if cb[k] > ca.get(k, 0)}
    return plus, minus
