# -*- coding: utf-8 -*-
"""
MÔ HÌNH THAM SỐ KHUNG SOFA 3 CHỖ (parametric sofa frame model)
================================================================
Hệ trục (world axes), đơn vị mm:
    X : chiều rộng sofa, trái -> phải (nhìn từ phía trước)
    Y : chiều sâu, trước (Y=0) -> sau (Y=D)
    Z : chiều cao, sàn (Z=0) -> lên

Mỗi chi tiết là một khối hộp (box) x0..x1, y0..y1, z0..z1.
!!! KÍCH THƯỚC MẶC ĐỊNH CHỈ LÀ MẪU (SAMPLE) — thay bằng kích thước thật
    của mẫu sofa trong dict PARAMS hoặc file JSON (xem make_drawing.py --params).

Cụm (module) — cấu tạo: CHÂN -> KHUNG ĐÁY -> KHUNG NGỒI đặt trên khung đáy,
GÁC TAY bắt 2 bên khung đáy, TỰA LƯNG bắt vào gác tay + đà đáy sau.
    M1 Khung đáy (base frame)      M2 Khung ngồi (seat frame)
    M3 Gác tay trái (left arm)     M4 Gác tay phải (right arm)
    M5 Tựa lưng (back frame)       M6 Chân (legs)
"""
from dataclasses import dataclass, field

PARAMS = dict(
    W=2000,            # rộng tổng (overall width)
    D=900,             # sâu tổng (overall depth)
    H_back=820,        # cao tựa lưng (top of back frame)
    H_arm=660,         # cao gác tay (top of arm)
    H_leg=100,         # cao chân (leg height)
    # --- gác tay ---
    T_arm=50,          # dày khung gác tay theo X
    post_d=70,         # sâu trụ gác tay theo Y
    arm_top_h=60,      # cao thanh gác tay trên
    arm_bot_h=70,      # cao giằng gác tay dưới
    arm_mid_h=50,      # cao giằng gác tay giữa
    arm_mid_z=380,     # cao độ đáy giằng giữa
    # --- khung đáy ---
    rail_t=25,         # dày đà đáy
    rail_h=150,        # cao đà đáy
    n_mid_rails=3,     # số giằng đáy giữa
    block=60,          # cạnh ke góc
    block_h=100,       # cao ke góc
    # --- khung ngồi (đặt trên khung đáy) ---
    seat_t=25,         # dày thanh viền khung ngồi
    seat_h=60,         # cao thanh viền khung ngồi
    n_slats=7,         # số nan ngồi
    slat_w=60,         # rộng nan
    slat_t=18,         # dày nan
    # --- sắt (metal) ---
    pat_a=50,          # dài cánh pát L
    pat_h=40,          # cao pát L
    pat_t=3,           # dày pát L
    pat_drop=10,       # mép trên pát thấp hơn mặt khung ngồi
    bar_w=20,          # thanh gia cố thép hộp: rộng (theo Y)
    bar_h=40,          # cao (theo Z)
    bar_wall=1.4,      # dày thành ống
    # --- tựa lưng ---
    back_t=25,         # dày khung tựa theo Y
    back_bot_h=80,     # cao thanh tựa dưới
    back_top_h=80,     # cao thanh tựa trên
    stile_w=40,        # rộng thanh đứng tựa
    n_mid_stiles=2,    # số thanh đứng tựa giữa
    # --- chân ---
    leg=50,            # tiết diện chân vuông
    # --- khoảng bung (explode distances) ---
    ex_arm=500, ex_seat_z=650, ex_back_y=500, ex_back_z=1050, ex_leg=300,
    ex_rail=250, ex_block=250, ex_top=200, ex_slat=160, ex_pat=220, ex_bar=-260,
)

MODULES = {
    "M1": dict(vn="Khung đáy", en="Base frame", cn="底框", aci=5),
    "M2": dict(vn="Khung ngồi", en="Seat frame", cn="座框", aci=140),
    "M3": dict(vn="Gác tay trái", en="Left arm", cn="左扶手", aci=3),
    "M4": dict(vn="Gác tay phải", en="Right arm", cn="右扶手", aci=3),
    "M5": dict(vn="Tựa lưng", en="Back frame", cn="靠背框", aci=6),
    "M6": dict(vn="Chân", en="Legs", cn="脚", aci=30),
}
LEG_MODULE = "M6"

# Trình tự lắp: (cụm mới lắp ở bước này, kiểu bung trong hình bước)
STEP_MODULES = [
    (["M1"], "part"),
    (["M3", "M4"], "module"),
    (["M2"], "module"),
    (["M5"], "module"),
    (["M6"], "module"),
]

# Loại chi tiết -> tên VN / EN / CN, vật liệu (thứ tự khai báo = số vị trí)
PART_TYPES = {
    "base_front":  ("Đà đáy trước", "Base front rail", "底框前横档", "Gỗ thông / Pine"),
    "base_back":   ("Đà đáy sau", "Base back rail", "底框后横档", "Gỗ thông / Pine"),
    "base_end":    ("Giằng đáy đầu", "Base end rail", "底框端撑", "Gỗ thông / Pine"),
    "base_mid":    ("Giằng đáy giữa", "Base middle rail", "底框中撑", "Gỗ thông / Pine"),
    "block":       ("Ke góc", "Corner block", "角码", "Gỗ thông / Pine"),
    "seat_fb":     ("Thanh ngồi trước/sau", "Seat front/back rail", "座框前后档", "Gỗ thông / Pine"),
    "seat_side":   ("Thanh ngồi hông", "Seat side rail", "座框侧档", "Gỗ thông / Pine"),
    "seat_slat":   ("Nan ngồi", "Seat slat", "座板条", "Gỗ thông / Pine"),
    "pat_L":       ("Pát L sắt", "Steel L-bracket", "L型铁角码", "Thép SS400"),
    "steel_bar":   ("Thanh gia cố sắt", "Steel reinforcement bar", "加固铁管", "Thép hộp"),
    "arm_post":    ("Trụ gác tay", "Arm post", "扶手立柱", "Gỗ thông / Pine"),
    "arm_top":     ("Thanh gác tay trên", "Arm top rail", "扶手上横档", "Gỗ thông / Pine"),
    "arm_bot":     ("Giằng gác tay dưới", "Arm bottom rail", "扶手下横档", "Gỗ thông / Pine"),
    "arm_mid":     ("Giằng gác tay giữa", "Arm middle rail", "扶手中横档", "Gỗ thông / Pine"),
    "back_bot":    ("Thanh tựa dưới", "Back bottom rail", "靠背下横档", "Gỗ thông / Pine"),
    "back_top":    ("Thanh tựa trên", "Back top rail", "靠背上横档", "Gỗ thông / Pine"),
    "back_stile":  ("Thanh đứng tựa", "Back stile", "靠背立档", "Gỗ thông / Pine"),
    "leg":         ("Chân", "Leg", "脚", "Gỗ cao su / Rubberwood"),
}

METAL_TYPES = {"pat_L", "steel_bar"}
# Ngoại lệ không áp quy tắc ván ép / LVL (cần xác nhận với khách)
MATERIAL_OVERRIDE = {"leg": "Gỗ cao su (ngoại lệ – xác nhận)"}


def material_of(ptype, dims, p=None):
    """Quy tắc vật liệu: dày 3–18 mm = VÁN ÉP; dày ≥ 20 mm = LVL.
    dims = (L, W, T) với T là kích thước nhỏ nhất."""
    p = p or PARAMS
    if ptype == "pat_L":
        return f"Thép SS400 dày {p['pat_t']:g}, sơn tĩnh điện"
    if ptype == "steel_bar":
        return f"Thép hộp {p['bar_w']:g}×{p['bar_h']:g}×{p['bar_wall']:g}, sơn tĩnh điện"
    if ptype in MATERIAL_OVERRIDE:
        return MATERIAL_OVERRIDE[ptype]
    T = dims[2]
    if 3 <= T <= 18:
        return f"Ván ép {T:g} mm"
    if T >= 20:
        return "LVL"
    return f"CHƯA XÁC ĐỊNH (dày {T:g} mm ngoài quy tắc)"


# Phụ kiện (hardware): mã -> (VN, EN, CN)
HARDWARE = {
    "A": ("Bulông M8×90 + ốc cấy Ø10", "KD bolt M8×90 + barrel nut", "M8×90螺栓+圆柱螺母"),
    "B": ("Chốt gỗ Ø8×40 + keo PVA", "Wood dowel Ø8×40 + PVA glue", "木榫Ø8×40+白乳胶"),
    "C": ("Vít gỗ 4×40", "Wood screw 4×40", "木螺丝4×40"),
    "D": ("Bulông treo chân M8 + tán cấy", "Hanger bolt M8 + T-nut", "M8脚螺栓+预埋螺母"),
    "E": ("Vít gỗ 4×50 (ke góc)", "Wood screw 4×50 (block)", "木螺丝4×50(角码)"),
    "F": ("Vít gỗ 4×60 (khung ngồi–đáy)", "Wood screw 4×60 (seat–base)", "木螺丝4×60(座框-底框)"),
    "G": ("Vít gỗ 4×20 (bắt pát L)", "Wood screw 4×20 (L-bracket)", "木螺丝4×20(角码)"),
    "H": ("Bulông M6×70 + đai ốc hàn", "Bolt M6×70 + weld nut", "M6×70螺栓+焊接螺母"),
    "K": ("Vít tự khoan 4.2×25", "Self-drilling screw 4.2×25", "自攻钻尾螺丝4.2×25"),
}

# Lỗ khoan theo (phụ kiện, vai trò chi tiết a/b): (mã lỗ, mô tả, Ø, sâu)
HOLE_SPEC = {
    ("A", "a"): ("A1", "Lỗ bulông Ø9 xuyên", 9, "xuyên"),
    ("A", "b"): ("A2", "Lỗ Ø9 sâu 70 + lỗ ốc cấy Ø10 sâu 30 cách mặt 50", 9, 70),
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
    ("G", "b"): ("G1", "Lỗ đột sẵn Ø5 trên pát", 5, "xuyên"),
    ("H", "a"): ("H1", "Lỗ bulông Ø7 xuyên", 7, "xuyên"),
    ("H", "b"): ("H2", "Đai ốc hàn M6 ở đầu thanh", 6, "-"),
    ("K", "a"): ("K2", "Vít tự khoan – không khoan trước", 0, "-"),
    ("K", "b"): ("K1", "Lỗ Ø4.5 xuyên + khoét đầu Ø8", 4.5, "xuyên"),
}


def loc_name(tag):
    """Mô tả vị trí lắp từ mã chi tiết (để ghi 'Dùng cho')."""
    m = {"L": "trái", "R": "phải", "F": "trước", "B": "sau", "M": "giữa"}
    t = tag
    out = []
    if t.startswith("arm"):
        out.append(m[t[3]])
        if t.endswith(("_F", "_B")):
            out.append(m[t[-1]])
    elif t.startswith(("leg_", "block_")):
        s_ = t.split("_")[1]
        out += [m[c] for c in s_]
    elif t[-2:] in ("_L", "_R"):
        out.append(m[t[-1]])
    elif t[-2] == "_" and t[-1].isdigit():
        out.append(f"số {int(t[-1]) + 1}")
    elif t.startswith("pat_"):
        out += [m[c] for c in t.split("_")[1]]
    for k, v in (("front", "trước"), ("back", "sau")):
        if k in t and t.startswith(("base_", "seat_")) and t.split("_")[1] == k:
            out.append(v)
    return "-".join(out) if out else "—"


@dataclass
class Part:
    tag: str                 # mã duy nhất từng chi tiết (instance id)
    ptype: str               # loại -> PART_TYPES
    module: str              # M1..M6
    box: tuple               # (x0, y0, z0, x1, y1, z1)
    part_off: tuple = (0, 0, 0)    # bung cấp chi tiết (part-level explode)
    follow: str = None       # chân đi theo cụm nào khi bung (vd chân góc theo gác tay)
    solo_off: tuple = None   # bung riêng trong bản vẽ từng cụm (None = dùng part_off)
    subs: list = None        # chi tiết ghép nhiều khối (vd pát L = 2 cánh); box = khối bao

    @property
    def boxes(self):
        return self.subs or [self.box]

    @property
    def size(self):
        x0, y0, z0, x1, y1, z1 = self.box
        return sorted((x1 - x0, y1 - y0, z1 - z0), reverse=True)  # L, W, T


@dataclass
class Joint:
    """Nhóm liên kết: các điểm (toạ độ lắp ráp) giữa 2 chi tiết, mỗi điểm = 1 phụ kiện."""
    hw: str                  # mã phụ kiện
    a: str                   # tag chi tiết A
    b: str                   # tag chi tiết B
    pts: list = field(default_factory=list)
    step: int = 1            # bước lắp


def module_offsets(p):
    return {
        "M1": (0, 0, 0),
        "M2": (0, 0, p["ex_seat_z"]),
        "M3": (-p["ex_arm"], 0, 0),
        "M4": (p["ex_arm"], 0, 0),
        "M5": (0, p["ex_back_y"], p["ex_back_z"]),
        "M6": (0, 0, 0),
    }


def build(p=None):
    """Trả về (params, parts, joints) từ bộ tham số."""
    p = dict(PARAMS, **(p or {}))
    W, D = p["W"], p["D"]
    Ta, Hl, Pd = p["T_arm"], p["H_leg"], p["post_d"]
    rt, rh = p["rail_t"], p["rail_h"]
    bt = p["back_t"]
    parts, joints = [], []
    add = lambda *a, **k: parts.append(Part(*a, **k))
    get = lambda t: next(q for q in parts if q.tag == t)

    zb0, zb1 = Hl, Hl + rh                      # khung đáy
    zs0, zs1 = zb1, zb1 + p["seat_h"]           # khung ngồi
    xi0, xi1 = Ta, W - Ta                       # mép trong 2 gác tay

    # ---------------- M1 KHUNG ĐÁY ----------------
    add("base_front", "base_front", "M1", (xi0, 0, zb0, xi1, rt, zb1), part_off=(0, -p["ex_rail"], 0))
    add("base_back", "base_back", "M1", (xi0, D - rt, zb0, xi1, D, zb1), part_off=(0, p["ex_rail"], 0))
    add("base_end_L", "base_end", "M1", (xi0, rt, zb0, xi0 + rt, D - rt, zb1))
    add("base_end_R", "base_end", "M1", (xi1 - rt, rt, zb0, xi1, D - rt, zb1))
    n = p["n_mid_rails"]
    mid_x = [xi0 + (xi1 - xi0) * (i + 1) / (n + 1) for i in range(n)]
    for i, xc in enumerate(mid_x):
        add(f"base_mid_{i}", "base_mid", "M1", (xc - rt / 2, rt, zb0, xc + rt / 2, D - rt, zb1))
    b, bh = p["block"], p["block_h"]
    zk0 = zb0 + (rh - bh) / 2
    for side, (bx0, bx1) in (("L", (xi0 + rt, xi0 + rt + b)), ("R", (xi1 - rt - b, xi1 - rt))):
        for fb, (by0, by1) in (("F", (rt, rt + b)), ("B", (D - rt - b, D - rt))):
            add(f"block_{side}{fb}", "block", "M1", (bx0, by0, zk0, bx1, by1, zk0 + bh),
                part_off=(0, 0, p["ex_block"]))

    # ---------------- M2 KHUNG NGỒI (trên khung đáy, trước tựa lưng) ----------------
    st = p["seat_t"]
    ys1 = D - bt                                 # mép sau khung ngồi = mặt trước tựa lưng
    add("seat_front", "seat_fb", "M2", (xi0, 0, zs0, xi1, st, zs1), part_off=(0, -150, 0))
    add("seat_back", "seat_fb", "M2", (xi0, ys1 - st, zs0, xi1, ys1, zs1), part_off=(0, 150, 0))
    add("seat_side_L", "seat_side", "M2", (xi0, st, zs0, xi0 + st, ys1 - st, zs1))
    add("seat_side_R", "seat_side", "M2", (xi1 - st, st, zs0, xi1, ys1 - st, zs1))
    ns, sw_, stk = p["n_slats"], p["slat_w"], p["slat_t"]
    slat_x = [xi0 + st + (xi1 - xi0 - 2 * st) * (i + 1) / (ns + 1) for i in range(ns)]
    for i, xc in enumerate(slat_x):
        add(f"slat_{i}", "seat_slat", "M2", (xc - sw_ / 2, st, zs1 - stk, xc + sw_ / 2, ys1 - st, zs1),
            part_off=(0, 0, p["ex_slat"]))

    # ---- SẮT: 4 pát L ở 4 góc trong khung ngồi + 1 thanh gia cố đỡ nan ----
    pa, ph, pt_ = p["pat_a"], p["pat_h"], p["pat_t"]
    zp1 = zs1 - p["pat_drop"]
    zp0 = zp1 - ph
    ix0, ix1 = xi0 + st, xi1 - st                # mặt trong 2 thanh hông
    iy0, iy1 = st, ys1 - st                      # mặt trong thanh trước / sau
    for side in "LR":
        for fb in "FB":
            sx_ = 1 if side == "L" else -1
            sy_ = 1 if fb == "F" else -1
            xc0 = ix0 if side == "L" else ix1
            yc0 = iy0 if fb == "F" else iy1
            # cánh 1 áp thanh trước/sau, cánh 2 áp thanh hông
            w1 = (min(xc0, xc0 + sx_ * pa), min(yc0, yc0 + sy_ * pt_), zp0,
                  max(xc0, xc0 + sx_ * pa), max(yc0, yc0 + sy_ * pt_), zp1)
            w2 = (min(xc0, xc0 + sx_ * pt_), min(yc0 + sy_ * pt_, yc0 + sy_ * pa), zp0,
                  max(xc0, xc0 + sx_ * pt_), max(yc0 + sy_ * pt_, yc0 + sy_ * pa), zp1)
            bb = tuple(min(w1[k], w2[k]) for k in range(3)) + tuple(max(w1[k + 3], w2[k + 3]) for k in range(3))
            add(f"pat_{side}{fb}", "pat_L", "M2", bb, part_off=(0, 0, p["ex_pat"]), subs=[w1, w2])
    yb = (iy0 + iy1) / 2
    add("steel_bar", "steel_bar", "M2",
        (ix0, yb - p["bar_w"] / 2, zs1 - stk - p["bar_h"], ix1, yb + p["bar_w"] / 2, zs1 - stk),
        part_off=(0, 0, p["ex_bar"]))

    # ---------------- M3/M4 GÁC TAY ----------------
    zt0 = p["H_arm"] - p["arm_top_h"]
    for side, mod, (ax0, ax1) in (("L", "M3", (0, Ta)), ("R", "M4", (W - Ta, W))):
        add(f"arm{side}_post_F", "arm_post", mod, (ax0, 0, Hl, ax1, Pd, zt0), solo_off=(0, -250, 0))
        add(f"arm{side}_post_B", "arm_post", mod, (ax0, D - Pd, Hl, ax1, D, zt0), solo_off=(0, 250, 0))
        add(f"arm{side}_top", "arm_top", mod, (ax0, 0, zt0, ax1, D, p["H_arm"]), part_off=(0, 0, p["ex_top"]))
        add(f"arm{side}_bot", "arm_bot", mod, (ax0, Pd, Hl, ax1, D - Pd, Hl + p["arm_bot_h"]))
        add(f"arm{side}_mid", "arm_mid", mod,
            (ax0, Pd, p["arm_mid_z"], ax1, D - Pd, p["arm_mid_z"] + p["arm_mid_h"]))

    # ---------------- M5 TỰA LƯNG (đứng trên đà đáy sau) ----------------
    sw = p["stile_w"]
    zbk = zb1 + p["back_bot_h"]
    ztk = p["H_back"] - p["back_top_h"]
    add("back_bot", "back_bot", "M5", (xi0, D - bt, zb1, xi1, D, zbk), part_off=(0, 0, -150))
    add("back_top", "back_top", "M5", (xi0, D - bt, ztk, xi1, D, p["H_back"]), part_off=(0, 0, p["ex_top"]))
    m = p["n_mid_stiles"]
    stile_x = [xi0, xi1 - sw] + [xi0 + (xi1 - xi0) * (i + 1) / (m + 1) - sw / 2 for i in range(m)]
    for i, sx in enumerate(stile_x):
        add(f"stile_{i}", "back_stile", "M5", (sx, D - bt, zbk, sx + sw, D, ztk))

    # ---------------- M6 CHÂN ----------------
    lg = p["leg"]
    yoff = (Pd - lg) / 2
    for side, lx0, fol in (("L", 0, "M3"), ("R", W - Ta, "M4")):
        lx = lx0 + (Ta - lg) / 2
        add(f"leg_{side}F", "leg", "M6", (lx, yoff, 0, lx + lg, yoff + lg, Hl),
            part_off=(0, 0, -p["ex_leg"]), follow=fol)
        add(f"leg_{side}B", "leg", "M6", (lx, D - Pd + yoff, 0, lx + lg, D - Pd + yoff + lg, Hl),
            part_off=(0, 0, -p["ex_leg"]), follow=fol)
    xc = W / 2
    add("leg_MF", "leg", "M6", (xc - lg / 2, 0, 0, xc + lg / 2, lg, Hl), part_off=(0, 0, -p["ex_leg"]))
    add("leg_MB", "leg", "M6", (xc - lg / 2, D - lg, 0, xc + lg / 2, D, Hl), part_off=(0, 0, -p["ex_leg"]))

    # ================= LIÊN KẾT (JOINTS) =================
    J = lambda *a, **k: joints.append(Joint(*a, **k))
    zc = (zb0 + zb1) / 2
    cx = lambda t: (get(t).box[0] + get(t).box[3]) / 2
    # Bước 1: khung đáy — chốt + keo, vít, ke góc
    for t in ["base_end_L", "base_end_R"] + [f"base_mid_{i}" for i in range(n)]:
        x = cx(t)
        J("B", "base_front", t, [(x, rt, zc - 35), (x, rt, zc + 35)], step=1)
        J("B", "base_back", t, [(x, D - rt, zc - 35), (x, D - rt, zc + 35)], step=1)
    for t in ("base_end_L", "base_end_R"):
        J("C", "base_front", t, [(cx(t), rt, zc)], step=1)
        J("C", "base_back", t, [(cx(t), D - rt, zc)], step=1)
    for q in [q for q in parts if q.ptype == "block"]:
        x0, y0, z0, x1, y1, z1 = q.box
        front = q.tag.endswith("F")
        J("E", "base_front" if front else "base_back", q.tag,
          [((x0 + x1) / 2, y0 if front else y1, (z0 + z1) / 2)], step=1)
        J("E", "base_end_" + q.tag[6], q.tag,
          [(x0 if q.tag[6] == "L" else x1, (y0 + y1) / 2, (z0 + z1) / 2)], step=1)
    # Bước 2: gác tay — ghép trong bằng chốt, bắt bulông KD vào khung đáy
    for side, xa in (("L", Ta), ("R", W - Ta)):
        xm = Ta / 2 if side == "L" else W - Ta / 2
        for pst in ("F", "B"):
            y0 = Pd * 0.3 if pst == "F" else D - Pd * 0.7
            J("B", f"arm{side}_post_{pst}", f"arm{side}_top", [(xm, y0, zt0), (xm, y0 + Pd * 0.4, zt0)], step=2)
            yf = Pd if pst == "F" else D - Pd
            for rail, z0r, hr in (("bot", Hl, p["arm_bot_h"]), ("mid", p["arm_mid_z"], p["arm_mid_h"])):
                J("B", f"arm{side}_post_{pst}", f"arm{side}_{rail}",
                  [(xm, yf, z0r + hr * 0.3), (xm, yf, z0r + hr * 0.7)], step=2)
        J("A", f"arm{side}_post_F", "base_front", [(xa, rt / 2, zc - 40), (xa, rt / 2, zc + 40)], step=2)
        J("A", f"arm{side}_post_B", "base_back", [(xa, D - rt / 2, zc - 40), (xa, D - rt / 2, zc + 40)], step=2)
        J("A", f"arm{side}_bot", f"base_end_{side}",
          [(xa, D * 0.33, Hl + p["arm_bot_h"] / 2), (xa, D * 0.67, Hl + p["arm_bot_h"] / 2)], step=2)
    # Bước 3: khung ngồi — ghép viền + nan, đặt lên khung đáy, vít F, bulông A vào trụ trước
    zsm = (zs0 + zs1) / 2
    for t in ("seat_side_L", "seat_side_R"):
        J("B", "seat_front", t, [(cx(t), st, zsm)], step=3)
        J("B", "seat_back", t, [(cx(t), ys1 - st, zsm)], step=3)
    for i, x in enumerate(slat_x):
        J("C", "seat_front", f"slat_{i}", [(x, st, zs1 - stk / 2)], step=3)
        J("C", "seat_back", f"slat_{i}", [(x, ys1 - st, zs1 - stk / 2)], step=3)
    for x in (W * 0.25, W * 0.5, W * 0.75):
        J("F", "base_front", "seat_front", [(x, rt / 2, zb1)], step=3)
    for side in ("L", "R"):
        x = cx(f"seat_side_{side}")
        J("F", f"base_end_{side}", f"seat_side_{side}", [(x, D * 0.35, zb1), (x, D * 0.65, zb1)], step=3)
    for i in range(n):
        J("F", f"base_mid_{i}", "seat_back", [(mid_x[i], ys1 - st / 2, zb1)], step=3)
    zpm = (zp0 + zp1) / 2
    for side in "LR":
        for fb in "FB":
            tg = f"pat_{side}{fb}"
            xc0 = ix0 if side == "L" else ix1
            yc0 = iy0 if fb == "F" else iy1
            sx_ = 1 if side == "L" else -1
            sy_ = 1 if fb == "F" else -1
            J("G", "seat_front" if fb == "F" else "seat_back", tg,
              [(xc0 + sx_ * pa * 0.3, yc0, zpm), (xc0 + sx_ * pa * 0.75, yc0, zpm)], step=3)
            J("G", f"seat_side_{side}", tg,
              [(xc0, yc0 + sy_ * pa * 0.3, zpm), (xc0, yc0 + sy_ * pa * 0.75, zpm)], step=3)
    zbm = zs1 - stk - p["bar_h"] / 2
    J("H", "seat_side_L", "steel_bar", [(ix0, yb, zbm)], step=3)
    J("H", "seat_side_R", "steel_bar", [(ix1, yb, zbm)], step=3)
    for i, x in enumerate(slat_x):
        J("K", "steel_bar", f"slat_{i}", [(x, yb, zs1 - stk)], step=3)
    J("A", "armL_post_F", "seat_front", [(Ta, st / 2, zsm)], step=3)
    J("A", "armR_post_F", "seat_front", [(W - Ta, st / 2, zsm)], step=3)
    # Bước 4: tựa lưng — ghép khung, bulông vào trụ gác tay sau, vít xuống đà đáy sau
    for i, sx in enumerate(stile_x):
        xm = sx + sw / 2
        J("B", "back_top", f"stile_{i}", [(xm, D - bt / 2, ztk)], step=4)
        J("B", "back_bot", f"stile_{i}", [(xm, D - bt / 2, zbk)], step=4)
    for side, xa, s_ in (("L", Ta, "stile_0"), ("R", W - Ta, "stile_1")):
        J("A", f"arm{side}_post_B", s_, [(xa, D - bt / 2, zbk + 80), (xa, D - bt / 2, zbk + 200)], step=4)
    J("C", "base_back", "back_bot", [(xi0 + (xi1 - xi0) * k / 5, D - bt / 2, zb1) for k in range(1, 5)], step=4)
    # Bước 5: chân
    for q in [q for q in parts if q.ptype == "leg"]:
        x0, y0, z0, x1, y1, z1 = q.box
        host = {"leg_MF": "base_front", "leg_MB": "base_back"}.get(q.tag) or f"arm{q.tag[4]}_post_{q.tag[5]}"
        J("D", host, q.tag, [((x0 + x1) / 2, (y0 + y1) / 2, z1)], step=5)

    return p, parts, joints


def explode_offset(part, p, level="full"):
    """Vector bung của chi tiết.
    level='full'   : bung cụm + bung chi tiết (hình bung tổng)
    level='module' : chỉ bung cụm (dùng cho các bước lắp)
    level='part'   : chỉ bung chi tiết
    """
    mo = module_offsets(p)
    base = mo[part.follow] if part.follow else mo[part.module]
    if level == "module":
        return part.part_off if part.module == LEG_MODULE else mo[part.module]
    if level == "part":
        return part.part_off
    return tuple(a + b for a, b in zip(base, part.part_off))


def solo_offset(part):
    """Vector bung trong bản vẽ riêng của cụm."""
    return part.solo_off if part.solo_off is not None else part.part_off


def check_overlaps(parts, tol=0.01):
    """Kiểm tra không có 2 chi tiết chồng thể tích (interference check)."""
    bad = []
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            for ba in a.boxes:
                for bb in b.boxes:
                    ov = [min(ba[k + 3], bb[k + 3]) - max(ba[k], bb[k]) for k in range(3)]
                    if all(o > tol for o in ov):
                        bad.append((a.tag, b.tag, ov))
    return bad
