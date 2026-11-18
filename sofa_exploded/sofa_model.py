# -*- coding: utf-8 -*-
"""
MÔ HÌNH THAM SỐ KHUNG SOFA 3 CHỖ (parametric sofa frame model)
================================================================
Hệ trục world, mm:  X rộng (trái->phải)  |  Y sâu (trước Y=0 -> sau)  |  Z cao.
Mỗi chi tiết = biên dạng 2D đùn theo chiều dày (geom.prism_solid) => vẽ được vát đầu,
ke tam giác, pát chữ L...
!!! KÍCH THƯỚC MẶC ĐỊNH LÀ MẪU — thay bằng số thật trong PARAMS hoặc file JSON.

Cụm: M1 Khung đáy | M2 Khung ngồi | M3/M4 Gác tay trái/phải | M5 Tựa lưng | M6 Chân
Vật liệu: dày 3–18 mm = VÁN ÉP; dày ≥ 20 mm = LVL.
Phụ kiện bắt pát vào ván: lỗ Ø10 -> ốc 4 chấu M8; lỗ Ø8 -> ốc cấy M6;
    chiều dài bulông theo độ dày ván: 9->12, 12->16, 15->18, 18->21 (BOLT_LEN).
"""
import math
from dataclasses import dataclass, field

from geom import box_profile, is_convex, prism_solid, v_cross, v_dot, v_norm, v_sub

PARAMS = dict(
    W=2000, D=900, H_back=820, H_arm=660, H_leg=100,
    # gác tay
    arm_panel_t=15,    # ván hông tay (ván ép)
    T_arm=50,          # dày khung gác tay (LVL) theo X
    post_d=70, arm_top_h=60, arm_bot_h=70, arm_mid_h=50, arm_mid_z=380,
    brace_w=40,        # rộng thanh chéo (vuông góc trục thanh)
    brace_angle=41,    # góc vát đầu thanh chéo (độ, so với phương ngang)
    brace_y0=420,      # vị trí chân thanh chéo
    # khung đáy (LVL)
    rail_t=25, rail_h=150, n_mid_rails=3, block=60, block_h=100,
    # khung ngồi (ván ép 18)
    seat_t=18, seat_h=60, n_slats=7, slat_w=60, slat_t=18,
    # sắt
    pat_a=50, pat_h=40, pat_t=3, pat_drop=10,
    bar_w=20, bar_h=40, bar_wall=1.4,
    fp_w=125, fp_h=60, fp_t=3, fp_z=520,          # pát nối tựa–tay (phẳng)
    # tựa lưng
    back_t=25, back_panel_t=9, back_bot_h=80, back_top_h=80, stile_w=40, n_mid_stiles=2,
    # chân
    leg=50,
    # khoảng bung
    ex_arm=500, ex_seat_z=650, ex_back_y=500, ex_back_z=1050, ex_leg=300,
    ex_rail=250, ex_block=250, ex_top=200, ex_slat=160, ex_pat=220, ex_bar=-260,
    ex_panel=220, ex_bpanel=250,
)

BOLT_LEN = {9: 12, 12: 16, 15: 18, 18: 21}          # độ dày ván -> chiều dài bulông
NUT_OF_HOLE = {10: ("M8", "ốc 4 chấu M8"), 8: ("M6", "ốc cấy M6")}

MODULES = {
    "M1": dict(vn="Khung đáy", en="Base frame", cn="底框", aci=5),
    "M2": dict(vn="Khung ngồi", en="Seat frame", cn="座框", aci=140),
    "M3": dict(vn="Gác tay trái", en="Left arm", cn="左扶手", aci=3),
    "M4": dict(vn="Gác tay phải", en="Right arm", cn="右扶手", aci=3),
    "M5": dict(vn="Tựa lưng", en="Back frame", cn="靠背框", aci=6),
    "M6": dict(vn="Chân", en="Legs", cn="脚", aci=30),
}
LEG_MODULE = "M6"
STEP_MODULES = [(["M1"], "part"), (["M3", "M4"], "module"), (["M2"], "module"), (["M5"], "module"),
                (["M6"], "module")]

PART_TYPES = {
    "base_front":  ("Đà đáy trước", "Base front rail", "底框前横档"),
    "base_back":   ("Đà đáy sau", "Base back rail", "底框后横档"),
    "base_end":    ("Giằng đáy đầu", "Base end rail", "底框端撑"),
    "base_mid":    ("Giằng đáy giữa", "Base middle rail", "底框中撑"),
    "block":       ("Ke góc tam giác", "Triangle corner block", "三角角码"),
    "seat_fb":     ("Thanh ngồi trước/sau", "Seat front/back rail", "座框前后档"),
    "seat_side":   ("Thanh ngồi hông", "Seat side rail", "座框侧档"),
    "seat_slat":   ("Nan ngồi", "Seat slat", "座板条"),
    "pat_L":       ("Pát L sắt", "Steel L-bracket", "L型铁角码"),
    "steel_bar":   ("Thanh gia cố sắt", "Steel reinforcement bar", "加固铁管"),
    "arm_panel":   ("Ván hông tay", "Arm outer panel", "扶手外侧板"),
    "arm_post":    ("Trụ gác tay", "Arm post", "扶手立柱"),
    "arm_top":     ("Thanh gác tay trên", "Arm top rail", "扶手上横档"),
    "arm_bot":     ("Giằng gác tay dưới", "Arm bottom rail", "扶手下横档"),
    "arm_mid":     ("Giằng gác tay giữa", "Arm middle rail", "扶手中横档"),
    "arm_brace":   ("Thanh chéo vát 41°", "Diagonal brace 41°", "41°斜撑"),
    "back_bot":    ("Thanh tựa dưới", "Back bottom rail", "靠背下横档"),
    "back_top":    ("Thanh tựa trên", "Back top rail", "靠背上横档"),
    "back_stile":  ("Thanh đứng tựa", "Back stile", "靠背立档"),
    "back_panel":  ("Ván lưng", "Back panel", "靠背板"),
    "pat_flat":    ("Pát nối tựa–tay", "Back-arm flat bracket", "靠背连接铁片"),
    "leg":         ("Chân", "Leg", "脚"),
}
METAL_TYPES = {"pat_L", "steel_bar", "pat_flat"}
MATERIAL_OVERRIDE = {"leg": "Gỗ cao su (ngoại lệ – xác nhận)"}


def material_of(ptype, dims, p=None):
    p = p or PARAMS
    if ptype == "pat_L":
        return f"Thép SS400 dày {p['pat_t']:g}"
    if ptype == "pat_flat":
        return f"Thép SS400 dày {p['fp_t']:g}"
    if ptype == "steel_bar":
        return f"Thép hộp {p['bar_w']:g}×{p['bar_h']:g}×{p['bar_wall']:g}"
    if ptype in MATERIAL_OVERRIDE:
        return MATERIAL_OVERRIDE[ptype]
    T = min(dims)
    if 3 <= T <= 18:
        return f"Ván ép {T:g} mm"
    if T >= 20:
        return "LVL"
    return f"CHƯA XÁC ĐỊNH (dày {T:g})"


HARDWARE = {
    "A": ("Bulông M8×90 + ốc cấy ngang Ø10", "KD bolt M8×90 + barrel nut"),
    "B": ("Chốt gỗ Ø8×40 + keo PVA", "Dowel Ø8×40 + PVA glue"),
    "C": ("Vít gỗ 4×40", "Wood screw 4×40"),
    "D": ("Bulông treo chân M8 + tán cấy", "Hanger bolt M8 + T-nut"),
    "E": ("Vít gỗ 4×50 (ke góc)", "Wood screw 4×50"),
    "F": ("Vít gỗ 4×60 (ngồi–đáy)", "Wood screw 4×60"),
    "G": ("Vít gỗ 4×20 (bắt pát vào LVL)", "Wood screw 4×20"),
    "H": ("Bulông M6×70 + đai ốc hàn", "Bolt M6×70 + weld nut"),
    "K": ("Vít tự khoan 4.2×25", "Self-drilling screw 4.2×25"),
    "P8": ("Bulông M8 + ốc 4 chấu M8 (lỗ Ø10)", "Bolt M8 + 4-prong tee nut"),
    "P6": ("Bulông M6 + ốc cấy M6 (lỗ Ø8)", "Bolt M6 + insert nut"),
}

HOLE_SPEC = {
    ("A", "a"): ("A1", "Lỗ bulông Ø9 xuyên", 9, "xuyên"),
    ("A", "b"): ("A2", "Lỗ Ø9 sâu 70 + lỗ ốc cấy ngang Ø10", 9, 70),
    ("B", "a"): ("B1", "Lỗ chốt Ø8 sâu 22", 8, 22),
    ("B", "b"): ("B1", "Lỗ chốt Ø8 sâu 22", 8, 22),
    ("C", "a"): ("C1", "Lỗ vít Ø4.5 xuyên + khoét đầu Ø8", 4.5, "xuyên"),
    ("C", "b"): ("C2", "Lỗ mồi Ø3 sâu 30", 3, 30),
    ("D", "a"): ("D1", "Lỗ tán cấy M8: Ø10 sâu 15", 10, 15),
    ("D", "b"): ("D2", "Lỗ bulông treo Ø6 sâu 40", 6, 40),
    ("E", "a"): ("E2", "Lỗ mồi Ø3 sâu 35", 3, 35),
    ("E", "b"): ("E1", "Lỗ vít Ø4.5 xuyên", 4.5, "xuyên"),
    ("F", "a"): ("F2", "Lỗ mồi Ø3 sâu 40", 3, 40),
    ("F", "b"): ("F1", "Lỗ vít Ø4.5 xuyên + khoét đầu Ø8", 4.5, "xuyên"),
    ("G", "a"): ("G2", "Lỗ mồi Ø2.5 sâu 15", 2.5, 15),
    ("G", "b"): ("PM", "Lỗ đột sẵn trên pát", 0, "-"),
    ("H", "a"): ("H1", "Lỗ bulông Ø7 xuyên", 7, "xuyên"),
    ("H", "b"): ("H2", "Đai ốc hàn M6 ở đầu thanh sắt", 0, "-"),
    ("K", "a"): ("K2", "Vít tự khoan – không khoan trước", 0, "-"),
    ("K", "b"): ("K1", "Lỗ Ø4.5 xuyên + khoét đầu Ø8", 4.5, "xuyên"),
    ("P8", "a"): ("PM", "Lỗ đột sẵn trên pát", 0, "-"),
    ("P8", "b"): ("T10", "Lỗ Ø10 xuyên – lắp ốc 4 chấu M8 mặt sau", 10, "xuyên"),
    ("P6", "a"): ("PM", "Lỗ đột sẵn trên pát", 0, "-"),
    ("P6", "b"): ("N8", "Lỗ Ø8 xuyên – lắp ốc cấy M6", 8, "xuyên"),
}


def loc_name(tag):
    m = {"L": "trái", "R": "phải", "F": "trước", "B": "sau", "M": "giữa"}
    out = []
    t = tag
    if t.startswith("arm") and t[3] in "LR":
        out.append(m[t[3]])
        if t.endswith(("_F", "_B")):
            out.append(m[t[-1]])
    elif t.startswith(("leg_", "block_", "pat_")):
        out += [m[c] for c in t.split("_")[1]]
    elif t[-2:] in ("_L", "_R"):
        out.append(m[t[-1]])
    elif t[-2] == "_" and t[-1].isdigit():
        out.append(f"số {int(t[-1]) + 1}")
    if t.split("_")[0] in ("base", "seat") and len(t.split("_")) == 2 and t.split("_")[1] in ("front", "back"):
        out.append({"front": "trước", "back": "sau"}[t.split("_")[1]])
    return "-".join(out) if out else "—"


@dataclass
class Part:
    tag: str
    ptype: str
    module: str
    plane: str
    poly: list
    t0: float
    t1: float
    part_off: tuple = (0, 0, 0)
    follow: str = None
    solo_off: tuple = None
    pieces: list = None
    solids: list = field(default=None, repr=False)

    def __post_init__(self):
        pcs = self.pieces or [self.poly]
        for pc in pcs:
            assert is_convex(pc), f"{self.tag}: biên dạng lõm phải khai 'pieces'"
        self.solids = [prism_solid(self.plane, pc, self.t0, self.t1) for pc in pcs]

    @property
    def box(self):
        bs = [s.bbox for s in self.solids]
        return tuple(min(b[k] for b in bs) for k in range(3)) + tuple(max(b[k + 3] for b in bs) for k in range(3))

    @property
    def size(self):
        b = self.box
        return sorted((b[3] - b[0], b[4] - b[1], b[5] - b[2]), reverse=True)

    @property
    def thick(self):
        return self.t1 - self.t0


@dataclass
class Joint:
    hw: str
    a: str
    b: str
    pts: list = field(default_factory=list)
    step: int = 1
    length: float = None      # chiều dài bulông (P8/P6) theo độ dày ván


def hw_name(j_or_code, length=None):
    code = j_or_code if isinstance(j_or_code, str) else j_or_code.hw
    L = length if isinstance(j_or_code, str) else j_or_code.length
    if code == "P8":
        return f"Bulông M8×{L if L else '?'} + ốc 4 chấu M8 (lỗ Ø10)"
    if code == "P6":
        return f"Bulông M6×{L if L else '?'} + ốc cấy M6 (lỗ Ø8)"
    return HARDWARE[code][0]


def module_offsets(p):
    return {"M1": (0, 0, 0), "M2": (0, 0, p["ex_seat_z"]), "M3": (-p["ex_arm"], 0, 0),
            "M4": (p["ex_arm"], 0, 0), "M5": (0, p["ex_back_y"], p["ex_back_z"]), "M6": (0, 0, 0)}


def build(p=None):
    p = dict(PARAMS, **(p or {}))
    W, D = p["W"], p["D"]
    Pt, Ta, Hl, Pd = p["arm_panel_t"], p["T_arm"], p["H_leg"], p["post_d"]
    rt, rh = p["rail_t"], p["rail_h"]
    bt, bp = p["back_t"], p["back_panel_t"]
    parts, joints = [], []

    def addb(tag, ptype, mod, box, **kw):
        plane, poly, t0, t1 = box_profile(box)
        parts.append(Part(tag, ptype, mod, plane, poly, t0, t1, **kw))

    def addp(tag, ptype, mod, plane, poly, t0, t1, **kw):
        parts.append(Part(tag, ptype, mod, plane, poly, t0, t1, **kw))

    get = lambda t: next(q for q in parts if q.tag == t)
    zb0, zb1 = Hl, Hl + rh
    zs0, zs1 = zb1, zb1 + p["seat_h"]
    xi0, xi1 = Pt + Ta, W - Pt - Ta
    yback = D - bp                                    # mặt sau khung tựa = mặt trước ván lưng
    ys1 = yback - bt                                  # mép sau khung ngồi

    # ---------------- M1 KHUNG ĐÁY ----------------
    addb("base_front", "base_front", "M1", (xi0, 0, zb0, xi1, rt, zb1), part_off=(0, -p["ex_rail"], 0))
    addb("base_back", "base_back", "M1", (xi0, D - rt, zb0, xi1, D, zb1), part_off=(0, p["ex_rail"], 0))
    addb("base_end_L", "base_end", "M1", (xi0, rt, zb0, xi0 + rt, D - rt, zb1))
    addb("base_end_R", "base_end", "M1", (xi1 - rt, rt, zb0, xi1, D - rt, zb1))
    n = p["n_mid_rails"]
    mid_x = [xi0 + (xi1 - xi0) * (i + 1) / (n + 1) for i in range(n)]
    for i, xc in enumerate(mid_x):
        addb(f"base_mid_{i}", "base_mid", "M1", (xc - rt / 2, rt, zb0, xc + rt / 2, D - rt, zb1))
    b, bh = p["block"], p["block_h"]
    zk0 = zb0 + (rh - bh) / 2
    for side in "LR":
        for fb in "FB":
            cx = xi0 + rt if side == "L" else xi1 - rt
            cy = rt if fb == "F" else D - rt
            sx, sy = (1 if side == "L" else -1), (1 if fb == "F" else -1)
            addp(f"block_{side}{fb}", "block", "M1", "xy", [(cx, cy), (cx + sx * b, cy), (cx, cy + sy * b)],
                 zk0, zk0 + bh, part_off=(0, 0, p["ex_block"]))

    # ---------------- M2 KHUNG NGỒI (ván ép 18) ----------------
    st = p["seat_t"]
    addb("seat_front", "seat_fb", "M2", (xi0, 0, zs0, xi1, st, zs1), part_off=(0, -150, 0))
    addb("seat_back", "seat_fb", "M2", (xi0, ys1 - st, zs0, xi1, ys1, zs1), part_off=(0, 150, 0))
    addb("seat_side_L", "seat_side", "M2", (xi0, st, zs0, xi0 + st, ys1 - st, zs1))
    addb("seat_side_R", "seat_side", "M2", (xi1 - st, st, zs0, xi1, ys1 - st, zs1))
    ns, sw_, stk = p["n_slats"], p["slat_w"], p["slat_t"]
    slat_x = [xi0 + st + (xi1 - xi0 - 2 * st) * (i + 1) / (ns + 1) for i in range(ns)]
    for i, xc in enumerate(slat_x):
        addb(f"slat_{i}", "seat_slat", "M2", (xc - sw_ / 2, st, zs1 - stk, xc + sw_ / 2, ys1 - st, zs1),
             part_off=(0, 0, p["ex_slat"]))
    pa, ph, ptk = p["pat_a"], p["pat_h"], p["pat_t"]
    zp1 = zs1 - p["pat_drop"]
    zp0 = zp1 - ph
    ix0, ix1 = xi0 + st, xi1 - st
    iy0, iy1 = st, ys1 - st
    for side in "LR":
        for fb in "FB":
            sx, sy = (1 if side == "L" else -1), (1 if fb == "F" else -1)
            X0, Y0 = (ix0 if side == "L" else ix1), (iy0 if fb == "F" else iy1)
            w1 = [(X0, Y0), (X0 + sx * pa, Y0), (X0 + sx * pa, Y0 + sy * ptk), (X0, Y0 + sy * ptk)]
            w2 = [(X0, Y0 + sy * ptk), (X0 + sx * ptk, Y0 + sy * ptk), (X0 + sx * ptk, Y0 + sy * pa), (X0, Y0 + sy * pa)]
            poly = [(X0, Y0), (X0 + sx * pa, Y0), (X0 + sx * pa, Y0 + sy * ptk), (X0 + sx * ptk, Y0 + sy * ptk),
                    (X0 + sx * ptk, Y0 + sy * pa), (X0, Y0 + sy * pa)]
            addp(f"pat_{side}{fb}", "pat_L", "M2", "xy", poly, zp0, zp1, pieces=[w1, w2],
                 part_off=(0, 0, p["ex_pat"]))
    yb = (iy0 + iy1) / 2
    addb("steel_bar", "steel_bar", "M2", (ix0, yb - p["bar_w"] / 2, zs1 - stk - p["bar_h"], ix1, yb + p["bar_w"] / 2,
                                          zs1 - stk), part_off=(0, 0, p["ex_bar"]))

    # ---------------- M3/M4 GÁC TAY ----------------
    zt0 = p["H_arm"] - p["arm_top_h"]
    zbr0, zbr1 = Hl + p["arm_bot_h"], p["arm_mid_z"]
    ang = math.radians(p["brace_angle"])
    run = (zbr1 - zbr0) / math.tan(ang)
    wb = p["brace_w"] / math.sin(ang)
    by0 = p["brace_y0"]
    for side, mod in (("L", "M3"), ("R", "M4")):
        sg = -1 if side == "L" else 1
        pnl = (0, Pt) if side == "L" else (W - Pt, W)
        ax0, ax1 = (Pt, Pt + Ta) if side == "L" else (W - Pt - Ta, W - Pt)
        addb(f"arm_panel_{side}", "arm_panel", mod, (pnl[0], 0, Hl, pnl[1], D, p["H_arm"]),
             part_off=(sg * p["ex_panel"], 0, 0))
        addb(f"arm{side}_post_F", "arm_post", mod, (ax0, 0, Hl, ax1, Pd, zt0), solo_off=(0, -250, 0))
        addb(f"arm{side}_post_B", "arm_post", mod, (ax0, D - Pd, Hl, ax1, D, zt0), solo_off=(0, 250, 0))
        addb(f"arm{side}_top", "arm_top", mod, (ax0, 0, zt0, ax1, D, p["H_arm"]), part_off=(0, 0, p["ex_top"]))
        addb(f"arm{side}_bot", "arm_bot", mod, (ax0, Pd, Hl, ax1, D - Pd, zbr0))
        addb(f"arm{side}_mid", "arm_mid", mod, (ax0, Pd, zbr1, ax1, D - Pd, zbr1 + p["arm_mid_h"]))
        addp(f"brace_{side}", "arm_brace", mod, "yz",
             [(by0, zbr0), (by0 + wb, zbr0), (by0 + run + wb, zbr1), (by0 + run, zbr1)], ax0, ax1,
             solo_off=(-sg * 160, 0, 0))

    # ---------------- M5 TỰA LƯNG ----------------
    sw = p["stile_w"]
    zbk = zb1 + p["back_bot_h"]
    ztk = p["H_back"] - p["back_top_h"]
    addb("back_bot", "back_bot", "M5", (xi0, ys1, zb1, xi1, yback, zbk), part_off=(0, 0, -150))
    addb("back_top", "back_top", "M5", (xi0, ys1, ztk, xi1, yback, p["H_back"]), part_off=(0, 0, p["ex_top"]))
    m = p["n_mid_stiles"]
    stile_x = [xi0, xi1 - sw] + [xi0 + (xi1 - xi0) * (i + 1) / (m + 1) - sw / 2 for i in range(m)]
    for i, sx_ in enumerate(stile_x):
        addb(f"stile_{i}", "back_stile", "M5", (sx_, ys1, zbk, sx_ + sw, yback, ztk))
    addb("back_panel", "back_panel", "M5", (xi0, yback, zb1, xi1, D, p["H_back"]),
         part_off=(0, p["ex_bpanel"], 0))
    fw, fh, ft = p["fp_w"], p["fp_h"], p["fp_t"]
    for side in "LR":
        x0 = Pt + 10 if side == "L" else W - Pt - 10 - fw
        addb(f"fpat_{side}", "pat_flat", "M5", (x0, D, p["fp_z"] - fh / 2, x0 + fw, D + ft, p["fp_z"] + fh / 2),
             part_off=(0, 200, 0), follow="M5")

    # ---------------- M6 CHÂN ----------------
    lg = p["leg"]
    yoff = (Pd - lg) / 2
    for side, fol in (("L", "M3"), ("R", "M4")):
        lx = (Pt + (Ta - lg) / 2) if side == "L" else (W - Pt - Ta + (Ta - lg) / 2)
        addb(f"leg_{side}F", "leg", "M6", (lx, yoff, 0, lx + lg, yoff + lg, Hl), part_off=(0, 0, -p["ex_leg"]), follow=fol)
        addb(f"leg_{side}B", "leg", "M6", (lx, D - Pd + yoff, 0, lx + lg, D - Pd + yoff + lg, Hl),
             part_off=(0, 0, -p["ex_leg"]), follow=fol)
    xc = W / 2
    addb("leg_MF", "leg", "M6", (xc - lg / 2, 0, 0, xc + lg / 2, lg, Hl), part_off=(0, 0, -p["ex_leg"]))
    addb("leg_MB", "leg", "M6", (xc - lg / 2, D - lg, 0, xc + lg / 2, D, Hl), part_off=(0, 0, -p["ex_leg"]))

    # ================= LIÊN KẾT =================
    J = lambda *a, **k: joints.append(Joint(*a, **k))
    zc = (zb0 + zb1) / 2
    cxp = lambda t: (get(t).box[0] + get(t).box[3]) / 2
    # B1 khung đáy
    for t in ["base_end_L", "base_end_R"] + [f"base_mid_{i}" for i in range(n)]:
        x = cxp(t)
        J("B", "base_front", t, [(x, rt, zc - 35), (x, rt, zc + 35)], step=1)
        J("B", "base_back", t, [(x, D - rt, zc - 35), (x, D - rt, zc + 35)], step=1)
    for t in ("base_end_L", "base_end_R"):
        J("C", "base_front", t, [(cxp(t), rt, zc)], step=1)
        J("C", "base_back", t, [(cxp(t), D - rt, zc)], step=1)
    for side in "LR":
        for fb in "FB":
            cx = xi0 + rt if side == "L" else xi1 - rt
            cy = rt if fb == "F" else D - rt
            sx, sy = (1 if side == "L" else -1), (1 if fb == "F" else -1)
            tg = f"block_{side}{fb}"
            J("E", "base_front" if fb == "F" else "base_back", tg, [(cx + sx * b * 0.35, cy, zc)], step=1)
            J("E", f"base_end_{side}", tg, [(cx, cy + sy * b * 0.35, zc)], step=1)
    # B2 gác tay
    for side in "LR":
        ax0, ax1 = (Pt, Pt + Ta) if side == "L" else (W - Pt - Ta, W - Pt)
        xm = (ax0 + ax1) / 2
        xa = ax1 if side == "L" else ax0                        # mặt trong khung tay
        xp = ax0 if side == "L" else ax1                        # mặt áp ván hông
        for pst in "FB":
            y0 = Pd * 0.3 if pst == "F" else D - Pd * 0.7
            J("B", f"arm{side}_post_{pst}", f"arm{side}_top", [(xm, y0, zt0), (xm, y0 + Pd * 0.4, zt0)], step=2)
            yf = Pd if pst == "F" else D - Pd
            for rail, z0r, hr in (("bot", Hl, p["arm_bot_h"]), ("mid", zbr1, p["arm_mid_h"])):
                J("B", f"arm{side}_post_{pst}", f"arm{side}_{rail}", [(xm, yf, z0r + hr * 0.3), (xm, yf, z0r + hr * 0.7)],
                  step=2)
        J("B", f"arm{side}_bot", f"brace_{side}", [(xm, by0 + wb / 2, zbr0)], step=2)
        J("B", f"arm{side}_mid", f"brace_{side}", [(xm, by0 + run + wb / 2, zbr1)], step=2)
        pnl = f"arm_panel_{side}"
        J("C", pnl, f"arm{side}_post_F", [(xp, Pd / 2, 250), (xp, Pd / 2, 480)], step=2)
        J("C", pnl, f"arm{side}_post_B", [(xp, D - Pd / 2, 250), (xp, D - Pd / 2, 480)], step=2)
        J("C", pnl, f"arm{side}_top", [(xp, D * 0.35, zt0 + 30), (xp, D * 0.65, zt0 + 30)], step=2)
        J("C", pnl, f"arm{side}_bot", [(xp, D * 0.5, Hl + 35)], step=2)
        J("A", f"arm{side}_post_F", "base_front", [(xa, rt / 2, zc - 40), (xa, rt / 2, zc + 40)], step=2)
        J("A", f"arm{side}_post_B", "base_back", [(xa, D - rt / 2, zc - 40), (xa, D - rt / 2, zc + 40)], step=2)
        J("A", f"arm{side}_bot", f"base_end_{side}", [(xa, D * 0.33, Hl + 35), (xa, D * 0.67, Hl + 35)], step=2)
    # B3 khung ngồi + sắt
    zsm = (zs0 + zs1) / 2
    for t in ("seat_side_L", "seat_side_R"):
        J("B", "seat_front", t, [(cxp(t), st, zsm)], step=3)
        J("B", "seat_back", t, [(cxp(t), ys1 - st, zsm)], step=3)
    for i, x in enumerate(slat_x):
        J("C", "seat_front", f"slat_{i}", [(x, st, zs1 - stk / 2)], step=3)
        J("C", "seat_back", f"slat_{i}", [(x, ys1 - st, zs1 - stk / 2)], step=3)
    zpm = (zp0 + zp1) / 2
    for side in "LR":
        for fb in "FB":
            sx, sy = (1 if side == "L" else -1), (1 if fb == "F" else -1)
            X0, Y0 = (ix0 if side == "L" else ix1), (iy0 if fb == "F" else iy1)
            tg = f"pat_{side}{fb}"
            J("P8", tg, "seat_front" if fb == "F" else "seat_back",
              [(X0 + sx * pa * 0.35, Y0, zpm), (X0 + sx * pa * 0.75, Y0, zpm)], step=3)
            J("P6", tg, f"seat_side_{side}", [(X0, Y0 + sy * pa * 0.35, zpm), (X0, Y0 + sy * pa * 0.75, zpm)], step=3)
    zbm = zs1 - stk - p["bar_h"] / 2
    J("H", "seat_side_L", "steel_bar", [(ix0, yb, zbm)], step=3)
    J("H", "seat_side_R", "steel_bar", [(ix1, yb, zbm)], step=3)
    for i, x in enumerate(slat_x):
        J("K", "steel_bar", f"slat_{i}", [(x, yb, zs1 - stk)], step=3)
    for x in (W * 0.25, W * 0.5, W * 0.75):
        J("F", "base_front", "seat_front", [(x, st / 2, zb1)], step=3)
    for side in "LR":
        x = cxp(f"seat_side_{side}")
        J("F", f"base_end_{side}", f"seat_side_{side}", [(x, D * 0.35, zb1), (x, D * 0.65, zb1)], step=3)
    for i in range(n):
        J("F", f"base_mid_{i}", "seat_back", [(mid_x[i], ys1 - st / 2, zb1)], step=3)
    J("A", "armL_post_F", "seat_front", [(xi0, st / 2, zsm)], step=3)
    J("A", "armR_post_F", "seat_front", [(xi1, st / 2, zsm)], step=3)
    # B4 tựa lưng
    for i, sx_ in enumerate(stile_x):
        xm = sx_ + sw / 2
        J("B", "back_top", f"stile_{i}", [(xm, (ys1 + yback) / 2, ztk)], step=4)
        J("B", "back_bot", f"stile_{i}", [(xm, (ys1 + yback) / 2, zbk)], step=4)
        J("C", "back_panel", f"stile_{i}", [(xm, yback, zbk + 100), (xm, yback, ztk - 100)], step=4)
    for rail in ("back_bot", "back_top"):
        zr = (get(rail).box[2] + get(rail).box[5]) / 2
        J("C", "back_panel", rail, [(xi0 + (xi1 - xi0) * k / 4, yback, zr) for k in (1, 2, 3)], step=4)
    for side, st_ in (("L", "stile_0"), ("R", "stile_1")):
        xa = xi0 if side == "L" else xi1
        J("A", f"arm{side}_post_B", st_, [(xa, (ys1 + yback) / 2, zbk + 80), (xa, (ys1 + yback) / 2, zbk + 200)], step=4)
    yrest = (max(ys1, D - rt) + yback) / 2
    J("C", "base_back", "back_bot", [(xi0 + (xi1 - xi0) * k / 5, yrest, zb1) for k in range(1, 5)], step=4)
    for side in "LR":
        fp = get(f"fpat_{side}")
        x0, x1 = fp.box[0], fp.box[3]
        post_x = Pt + Ta / 2 if side == "L" else W - Pt - Ta / 2
        pan_x = x1 - 18 if side == "L" else x0 + 18
        zz = p["fp_z"]
        J("G", f"arm{side}_post_B", f"fpat_{side}", [(post_x, D, zz - 15), (post_x, D, zz + 15)], step=4)
        J("P8", f"fpat_{side}", "back_panel", [(pan_x, D, zz - 15), (pan_x, D, zz + 15)], step=4)
    # B5 chân
    for q in [q for q in parts if q.ptype == "leg"]:
        x0, y0, z0, x1, y1, z1 = q.box
        host = {"leg_MF": "base_front", "leg_MB": "base_back"}.get(q.tag) or f"arm{q.tag[4]}_post_{q.tag[5]}"
        J("D", host, q.tag, [((x0 + x1) / 2, (y0 + y1) / 2, z1)], step=5)

    # chiều dài bulông P8/P6 theo độ dày ván nhận ốc
    for j in joints:
        if j.hw in ("P8", "P6"):
            j.length = BOLT_LEN.get(round(get(j.b).thick))
    return p, parts, joints


def explode_offset(part, p, level="full"):
    mo = module_offsets(p)
    base = mo[part.follow] if part.follow else mo[part.module]
    if level == "module":
        return part.part_off if part.module == LEG_MODULE else mo[part.module]
    if level == "part":
        return part.part_off
    return tuple(a + b for a, b in zip(base, part.part_off))


def solo_offset(part):
    return part.solo_off if part.solo_off is not None else part.part_off


def _sat_overlap(A, B, tol=0.05):
    axes = [n for n, _, _ in A.faces] + [n for n, _, _ in B.faces]
    for ea in A.edges:
        da = v_sub(A.verts[ea[1]], A.verts[ea[0]])
        for eb in B.edges:
            c = v_cross(da, v_sub(B.verts[eb[1]], B.verts[eb[0]]))
            if v_dot(c, c) > 1e-6:
                axes.append(v_norm(c))
    for ax in axes:
        pa = [v_dot(ax, v) for v in A.verts]
        pb = [v_dot(ax, v) for v in B.verts]
        if min(max(pa), max(pb)) - max(min(pa), min(pb)) <= tol:
            return False
    return True


def check_overlaps(parts):
    bad = []
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            ba, bb = a.box, b.box
            if any(min(ba[k + 3], bb[k + 3]) - max(ba[k], bb[k]) <= 0.05 for k in range(3)):
                continue
            if any(_sat_overlap(sa, sb) for sa in a.solids for sb in b.solids):
                bad.append((a.tag, b.tag))
    return bad
