# -*- coding: utf-8 -*-
"""
ENGINE VẼ: khử nét khuất cho đa diện lồi, hướng nhìn bất kỳ, tự chọn hướng nhìn phụ.
"""
import math
from graphlib import CycleError, TopologicalSorter

from shapely import affinity
from shapely.geometry import LineString, MultiPoint, Polygon
from shapely.ops import unary_union

from geom import v_cross, v_dot, v_norm

ORTHO = {
    "front": ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
    "back":  ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    "top":   ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "left":  ((0, -1, 0), (0, 0, 1), (-1, 0, 0)),
    "right": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
}


def iso_dirs(sx, sy, sz):
    d = v_norm((sx, sy, sz))
    r = v_norm((-d[1], d[0], 0))
    u = v_cross(d, r)
    return r, u, d


ISO_NAMES = {(1, -1, 1): "trước-phải-trên", (-1, -1, 1): "trước-trái-trên", (1, 1, 1): "sau-phải-trên",
             (-1, 1, 1): "sau-trái-trên", (1, -1, -1): "trước-phải-dưới", (-1, 1, -1): "sau-trái-dưới"}


class View:
    def __init__(self, dirs, origin=(0, 0), scale=1.0):
        self.r, self.u, self.d = dirs
        self.origin, self.scale = origin, scale

    def p2(self, p):
        return (v_dot(p, self.r), v_dot(p, self.u))

    def sheet(self, uv):
        return (self.origin[0] + uv[0] * self.scale, self.origin[1] + uv[1] * self.scale)

    def P(self, p):
        return self.sheet(self.p2(p))

    def ray(self, uv):
        return tuple(uv[0] * self.r[k] + uv[1] * self.u[k] for k in range(3))


def fit(dirs, solids, region, margin=0):
    v = View(dirs)
    pts = [v.p2(p) for s in solids for p in s.verts]
    u0, u1 = min(p[0] for p in pts), max(p[0] for p in pts)
    w0, w1 = min(p[1] for p in pts), max(p[1] for p in pts)
    x0, y0, x1, y1 = region[0] + margin, region[1] + margin, region[2] - margin, region[3] - margin
    sc = min((x1 - x0) / max(u1 - u0, 1e-6), (y1 - y0) / max(w1 - w0, 1e-6))
    return View(dirs, ((x0 + x1) / 2 - sc * (u0 + u1) / 2, (y0 + y1) / 2 - sc * (w0 + w1) / 2), sc)


def _order(view, items, hulls):
    keys = [k for k, _, _ in items]
    sol = {k: s for k, s, _ in items}
    ts = TopologicalSorter({k: set() for k in keys})
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            inter = hulls[a].intersection(hulls[b])
            if inter.area < 1e-3:
                continue
            rp = inter.representative_point()
            o = view.ray((rp.x, rp.y))
            da, db = sol[a].ray_front(o, view.d), sol[b].ray_front(o, view.d)
            if da is None or db is None:
                continue
            if da > db + 1e-6:
                ts.add(b, a)
            elif db > da + 1e-6:
                ts.add(a, b)
    try:
        return list(ts.static_order())
    except CycleError:
        c = lambda k: v_dot(tuple(sum(p[i] for p in sol[k].verts) / len(sol[k].verts) for i in range(3)), view.d)
        return sorted(keys, key=c, reverse=True)


def render(msp, view, items, hidden=False, min_len=0.3, draw=True):
    """items: [(key, Solid, layer)]. Trả về dict key -> polygon nhìn thấy (toạ độ chiếu)."""
    hulls = {k: MultiPoint([view.p2(p) for p in s.verts]).convex_hull for k, s, _ in items}
    order = _order(view, items, hulls)
    sol = {k: s for k, s, _ in items}
    lay = {k: l for k, _, l in items}
    occl = Polygon()
    vis = {}
    for k in order:
        s = sol[k]
        segs = set()
        for n, idx, _ in s.faces:
            if v_dot(n, view.d) > 1e-9:
                for i in range(len(idx)):
                    a, b = idx[i], idx[(i + 1) % len(idx)]
                    segs.add((min(a, b), max(a, b)))
        if draw:
            for a, b in segs:
                pa, pb = view.p2(s.verts[a]), view.p2(s.verts[b])
                if math.dist(pa, pb) < 1e-6:
                    continue
                ln = LineString([pa, pb])
                v = ln.difference(occl) if not occl.is_empty else ln
                _emit(msp, view, v, lay[k], min_len)
                if hidden and not occl.is_empty:
                    _emit(msp, view, ln.intersection(occl.buffer(-0.5)), "2-NET-KHUAT", min_len * 3)
        h = hulls[k]
        vis[k] = h.difference(occl) if not occl.is_empty else h
        occl = unary_union([occl, h])
    return vis


def _emit(msp, view, g, layer, min_len):
    if g.is_empty:
        return
    for x in getattr(g, "geoms", [g]):
        if x.geom_type == "LineString" and x.length * view.scale > min_len:
            p = [view.sheet(c) for c in x.coords]
            msp.add_line(p[0], p[-1], dxfattribs={"layer": layer})
        elif hasattr(x, "geoms"):
            _emit(msp, view, x, layer, min_len)


def visibility(view, items):
    """Tỉ lệ diện tích nhìn thấy / diện tích hình chiếu của từng key."""
    vis = render(None, view, items, draw=False)
    hulls = {k: MultiPoint([view.p2(p) for p in s.verts]).convex_hull for k, s, _ in items}
    return {k: (vis[k].area / hulls[k].area if hulls[k].area > 1e-9 else 0) for k in vis}, vis


def to_sheet(view, geom):
    g = affinity.scale(geom, view.scale, view.scale, origin=(0, 0))
    return affinity.translate(g, view.origin[0], view.origin[1])
