# -*- coding: utf-8 -*-
"""
TÍNH LỖ KHOAN & TÁCH BIẾN THỂ CHI TIẾT (hole extraction & part variants)
=========================================================================
- Mỗi điểm liên kết (Joint) nằm trên mặt tiếp xúc giữa 2 chi tiết -> sinh 1 lỗ trên
  mỗi chi tiết, loại lỗ lấy từ HOLE_SPEC[(phụ kiện, vai trò a/b)].
- Toạ độ lỗ đổi về hệ toạ độ RIÊNG của chi tiết: X dọc chiều dài L, Y dọc chiều rộng W,
  Z dọc chiều dày T (hệ thuận / right-handed), gốc O ở góc nhỏ nhất.
- Hai chi tiết cùng loại, cùng kích thước được coi là GIỐNG NHAU nếu mẫu lỗ trùng nhau
  sau khi xoay 180° quanh một trục (lật đầu / lật mặt). KHÔNG coi đối xứng gương là giống
  (chi tiết trái/phải khác lỗ sẽ thành 2 mã: 9A, 9B...).
"""
from collections import OrderedDict, defaultdict

from sofa_model import HOLE_SPEC, METAL_TYPES, PART_TYPES

TOL = 0.01
FACE_NAMES = {(2, 1): "A", (2, -1): "B", (1, 1): "C", (1, -1): "D", (0, -1): "E", (0, 1): "F"}
FACE_DESC = {"A": "mặt A (+Z, mặt lớn trên)", "B": "mặt B (−Z, mặt lớn dưới)",
             "C": "cạnh C (+Y)", "D": "cạnh D (−Y)", "E": "đầu E (X=0)", "F": "đầu F (X=L)"}


def _on(box, pt):
    return all(box[k] - TOL <= pt[k] <= box[k + 3] + TOL for k in range(3))


def _contact(ba, bb, pt):
    for k in range(3):
        if abs(ba[k + 3] - bb[k]) < TOL and abs(pt[k] - ba[k + 3]) < TOL:
            return (k, 1), (k, -1)
        if abs(ba[k] - bb[k + 3]) < TOL and abs(pt[k] - ba[k]) < TOL:
            return (k, -1), (k, 1)
    return None


def instance_holes(parts, joints):
    """-> {tag: [ {pt, face(axis,sign), box, code, hw} ]}, problems"""
    by = {q.tag: q for q in parts}
    holes, problems = defaultdict(list), []
    for j in joints:
        A, B = by[j.a], by[j.b]
        for pt in j.pts:
            hit = None
            for ba in A.boxes:
                for bb in B.boxes:
                    if _on(ba, pt) and _on(bb, pt):
                        c = _contact(ba, bb, pt)
                        if c:
                            hit = (ba, bb, c)
                            break
                if hit:
                    break
            if not hit:
                problems.append((j.hw, j.a, j.b, pt))
                continue
            ba, bb, (fa, fb) = hit
            holes[A.tag].append(dict(pt=pt, face=fa, code=HOLE_SPEC[(j.hw, "a")][0], hw=j.hw))
            holes[B.tag].append(dict(pt=pt, face=fb, code=HOLE_SPEC[(j.hw, "b")][0], hw=j.hw))
    return holes, problems


def local_frame(box):
    """Thứ tự trục world -> (L, W, T), có lật trục T nếu cần để giữ hệ thuận."""
    size = [box[k + 3] - box[k] for k in range(3)]
    order = sorted(range(3), key=lambda k: (-size[k], k))
    # chẵn/lẻ của hoán vị
    perm = list(order)
    parity = 0
    for i in range(3):
        for j in range(i + 1, 3):
            if perm[i] > perm[j]:
                parity ^= 1
    dims = tuple(size[k] for k in order)
    return order, dims, parity


def to_local(h, box, order, dims, parity):
    c = [h["pt"][order[i]] - box[order[i]] for i in range(3)]
    ax, sg = h["face"]
    li = order.index(ax)
    if parity:                          # lật trục T để hệ toạ độ là hệ thuận
        c[2] = dims[2] - c[2]
        if li == 2:
            sg = -sg
    return (h["code"], li, sg, c[0], c[1], c[2])


THROUGH = {c for (c, _d, _dia, dep) in HOLE_SPEC.values() if dep == "xuyên"}


def _norm(hs, dims):
    """Lỗ xuyên: không phân biệt mặt vào -> quy về mặt dương."""
    out = []
    for code, li, sg, *c in hs:
        if code in THROUGH and sg < 0:
            c = list(c)
            c[li] = dims[li]
            sg = 1
        out.append((code, li, sg, *c))
    return out


def _rot(hs, dims, r):
    if r is None:
        return hs
    out = []
    for code, li, sg, *c in hs:
        c = list(c)
        for j in range(3):
            if j != r:
                c[j] = dims[j] - c[j]
        out.append((code, li, sg if li == r else -sg, *c))
    return out


def signature(hs, dims):
    best = None
    for r in (None, 0, 1, 2):
        rh = _norm(_rot(hs, dims, r), dims)
        sig = tuple(sorted((code, li, sg, round(a, 1), round(b, 1), round(c, 1))
                           for code, li, sg, a, b, c in rh))
        if best is None or sig < best[0]:
            best = (sig, rh)
    return best


def variants(parts, joints, nums):
    """Gom chi tiết thành biến thể. Trả về OrderedDict code -> dict(...), map tag->code, problems."""
    ih, problems = instance_holes(parts, joints)
    groups = OrderedDict()
    for q in parts:
        order, dims, parity = local_frame(q.box)
        hs = [to_local(h, q.box, order, dims, parity) for h in ih.get(q.tag, [])]
        sig, canon = signature(hs, dims)
        key = (q.ptype, tuple(round(d, 1) for d in dims), sig)
        g = groups.setdefault(key, dict(ptype=q.ptype, dims=dims, holes=canon, tags=[], module=q.module))
        g["tags"].append(q.tag)
    by_type = defaultdict(list)
    for key, g in groups.items():
        by_type[g["ptype"]].append(g)
    out, tag2code = OrderedDict(), {}
    for ptype, n in nums.items():
        gs = sorted(by_type[ptype], key=lambda g: -len(g["tags"]))
        for i, g in enumerate(gs):
            code = str(n) if len(gs) == 1 else f"{n}{chr(65 + i)}"
            g["code"] = code
            g["n"] = n
            g["siblings"] = [f"{n}{chr(65 + k)}" for k in range(len(gs))] if len(gs) > 1 else []
            g["metal"] = ptype in METAL_TYPES
            out[code] = g
            for t in g["tags"]:
                tag2code[t] = code
    return out, tag2code, problems


def hole_rows(holes):
    """Gom lỗ cho bảng: (mã lỗ, mặt, nhãn toạ độ cố định, danh sách toạ độ còn lại)."""
    rows = OrderedDict()
    for code, li, sg, x, y, z in holes:
        face = FACE_NAMES[(li, sg)]
        if li == 2:
            key, fixed, var = (code, face, round(y, 1)), f"Y={y:g}", ("X", x)
        elif li == 1:
            key, fixed, var = (code, face, round(z, 1)), f"Z={z:g}", ("X", x)
        else:
            key, fixed, var = (code, face, round(z, 1)), f"Z={z:g}", ("Y", y)
        r = rows.setdefault(key, dict(code=code, face=face, fixed=fixed, axis=var[0], vals=[]))
        r["vals"].append(var[1])
    for r in rows.values():
        r["vals"].sort()
    return list(rows.values())


def hole_desc(code):
    for (hw, role), (c, desc, dia, dep) in HOLE_SPEC.items():
        if c == code:
            return desc, dia, dep
    return code, 0, ""
