# -*- coding: utf-8 -*-
"""
HÌNH HỌC LĂNG TRỤ (prism geometry)
===================================
Mọi chi tiết = biên dạng 2D (polygon) trong 1 mặt phẳng chính, đùn theo trục thứ 3 (chiều dày).
    plane "xy": (a,b) = (x,y), đùn theo z      plane "yz": (a,b) = (y,z), đùn theo x
    plane "xz": (a,b) = (x,z), đùn theo y
Biên dạng lõm (vd pát L) khai thêm 'pieces' = các đa giác lồi ghép lại.
Solid = đa diện lồi dùng để khử nét khuất / tìm mặt tiếp xúc.
"""
import math

AX = {"xy": (0, 1, 2), "yz": (1, 2, 0), "xz": (0, 2, 1)}


def v_sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def v_dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def v_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def v_norm(a):
    L = math.sqrt(v_dot(a, a)) or 1.0
    return tuple(x / L for x in a)


def area2(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2


def ccw(poly):
    return list(poly) if area2(poly) > 0 else list(reversed(poly))


def embed(plane, a, b, t):
    ia, ib, it = AX[plane]
    p = [0.0, 0.0, 0.0]
    p[ia], p[ib], p[it] = a, b, t
    return tuple(p)


class Solid:
    """Đa diện lồi: verts + faces[(normal, [idx...], c)] với n·x = c trên mặt, n·x ≤ c bên trong."""

    def __init__(self, verts, faces):
        self.verts = [tuple(float(x) for x in v) for v in verts]
        cen = tuple(sum(v[k] for v in self.verts) / len(self.verts) for k in range(3))
        self.faces = []
        for n, idx in faces:
            n = v_norm(n)
            c = v_dot(n, self.verts[idx[0]])
            if v_dot(n, cen) > c:            # bảo đảm pháp tuyến hướng ra ngoài
                n = tuple(-x for x in n)
                c = -c
            self.faces.append((n, list(idx), c))
        es = set()
        for _, idx, _ in self.faces:
            for i in range(len(idx)):
                a, b = idx[i], idx[(i + 1) % len(idx)]
                es.add((min(a, b), max(a, b)))
        self.edges = sorted(es)

    @property
    def bbox(self):
        return tuple(min(v[k] for v in self.verts) for k in range(3)) + \
            tuple(max(v[k] for v in self.verts) for k in range(3))

    def moved(self, o):
        s = Solid.__new__(Solid)
        s.verts = [tuple(v[k] + o[k] for k in range(3)) for v in self.verts]
        s.faces = [(n, idx, c + v_dot(n, o)) for n, idx, c in self.faces]
        s.edges = self.edges
        return s

    def contains(self, p, tol=0.01):
        return all(v_dot(n, p) <= c + tol for n, _, c in self.faces)

    def faces_at(self, p, tol=0.01):
        """Các mặt chứa điểm p (p nằm trên biên)."""
        if not self.contains(p, tol):
            return []
        return [(n, c) for n, _, c in self.faces if abs(v_dot(n, p) - c) < tol]

    def ray_front(self, o, d):
        """Tia o + t·d; trả về t lớn nhất (mặt gần người nhìn) hoặc None."""
        t0, t1 = -1e18, 1e18
        for n, _, c in self.faces:
            nd, no = v_dot(n, d), v_dot(n, o)
            if abs(nd) < 1e-12:
                if no > c + 1e-6:
                    return None
                continue
            t = (c - no) / nd
            if nd > 0:
                t1 = min(t1, t)
            else:
                t0 = max(t0, t)
        return t1 if t0 <= t1 + 1e-6 else None


def prism_solid(plane, poly, t0, t1):
    poly = ccw(poly)
    n = len(poly)
    verts = [embed(plane, a, b, t0) for a, b in poly] + [embed(plane, a, b, t1) for a, b in poly]
    ax = [0, 0, 0]
    ax[AX[plane][2]] = 1
    faces = [(tuple(-x for x in ax), list(range(n))), (tuple(ax), list(range(n, 2 * n)))]
    for i in range(n):
        j = (i + 1) % n
        (a0, b0), (a1, b1) = poly[i], poly[j]
        nn = embed(plane, b1 - b0, -(a1 - a0), 0)       # pháp tuyến ngoài của cạnh (đa giác CCW)
        faces.append((nn, [i, j, n + j, n + i]))
    return Solid(verts, faces)


def is_convex(poly):
    poly = ccw(poly)
    n = len(poly)
    for i in range(n):
        a, b, c = poly[i], poly[(i + 1) % n], poly[(i + 2) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -1e-9:
            return False
    return True


def box_profile(box):
    """Hộp -> (plane, poly, t0, t1) với trục đùn = kích thước nhỏ nhất."""
    size = [box[k + 3] - box[k] for k in range(3)]
    ax = min(range(3), key=lambda k: (size[k], -k))
    plane = {2: "xy", 0: "yz", 1: "xz"}[ax]
    ia, ib, it = AX[plane]
    poly = [(box[ia], box[ib]), (box[ia + 3], box[ib]), (box[ia + 3], box[ib + 3]), (box[ia], box[ib + 3])]
    return plane, poly, box[it], box[it + 3]


def angle_deg(p0, p1, p2):
    """Góc tại p1 giữa p1->p0 và p1->p2 (độ)."""
    a, b = (p0[0] - p1[0], p0[1] - p1[1]), (p2[0] - p1[0], p2[1] - p1[1])
    cs = (a[0] * b[0] + a[1] * b[1]) / (math.hypot(*a) * math.hypot(*b))
    return math.degrees(math.acos(max(-1, min(1, cs))))
