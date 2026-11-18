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

Module (cụm lắp):
    M1 Khung ngồi (seat frame)   M2 Tay vịn trái (left arm)
    M3 Tay vịn phải (right arm)  M4 Khung tựa (back frame)   M5 Chân (legs)
"""
from dataclasses import dataclass, field

PARAMS = dict(
    W=2000,            # rộng tổng (overall width)
    D=900,             # sâu tổng (overall depth)
    H_back=820,        # cao khung tựa (top of back frame)
    H_arm=660,         # cao tay vịn (top of arm)
    H_leg=100,         # cao chân (leg height)
    T_arm=50,          # dày khung tay theo X (arm frame thickness)
    post_d=70,         # sâu trụ tay theo Y (arm post depth)
    arm_top_h=60,      # cao thanh tay trên (arm top rail height)
    arm_bot_h=70,      # cao giằng dưới tay (arm bottom rail)
    arm_mid_h=50,      # cao giằng giữa tay (arm middle rail)
    arm_mid_z=380,     # cao độ đáy giằng giữa tay
    rail_t=25,         # dày đà ngồi (seat rail thickness)
    rail_h=150,        # cao đà ngồi (seat rail height)
    n_mid_rails=3,     # số thanh giằng ngồi giữa (middle seat cross rails)
    back_t=25,         # dày khung tựa theo Y
    back_bot_h=80,     # cao thanh tựa dưới
    back_top_h=80,     # cao thanh tựa trên
    stile_w=40,        # rộng thanh đứng tựa (back stile)
    n_mid_stiles=2,    # số thanh đứng tựa giữa
    leg=50,            # tiết diện chân vuông (leg section)
    block=60,          # cạnh ke góc (corner block)
    block_h=100,       # cao ke góc
    # --- khoảng bung (explode distances) ---
    ex_arm=450, ex_back_y=350, ex_back_z=450, ex_leg=300,
    ex_rail=250, ex_block=250, ex_top=200,
)

MODULES = {
    "M1": dict(vn="Khung ngồi", en="Seat frame", cn="座框", aci=5),
    "M2": dict(vn="Tay vịn trái", en="Left arm", cn="左扶手", aci=3),
    "M3": dict(vn="Tay vịn phải", en="Right arm", cn="右扶手", aci=3),
    "M4": dict(vn="Khung tựa", en="Back frame", cn="靠背框", aci=6),
    "M5": dict(vn="Chân", en="Legs", cn="脚", aci=30),
}

# Loại chi tiết -> số vị trí (balloon), tên VN/EN/CN, vật liệu
PART_TYPES = {
    "front_rail":  ("Đà ngồi trước", "Front seat rail", "前座横档", "Gỗ thông / Pine"),
    "back_rail":   ("Đà ngồi sau", "Back seat rail", "后座横档", "Gỗ thông / Pine"),
    "end_rail":    ("Giằng ngồi đầu", "End seat rail", "端座撑", "Gỗ thông / Pine"),
    "mid_rail":    ("Giằng ngồi giữa", "Middle seat rail", "中座撑", "Gỗ thông / Pine"),
    "block":       ("Ke góc", "Corner block", "角码", "Gỗ thông / Pine"),
    "arm_post":    ("Trụ tay", "Arm post", "扶手立柱", "Gỗ thông / Pine"),
    "arm_top":     ("Thanh tay trên", "Arm top rail", "扶手上横档", "Gỗ thông / Pine"),
    "arm_bot":     ("Giằng tay dưới", "Arm bottom rail", "扶手下横档", "Gỗ thông / Pine"),
    "arm_mid":     ("Giằng tay giữa", "Arm middle rail", "扶手中横档", "Gỗ thông / Pine"),
    "back_bot":    ("Thanh tựa dưới", "Back bottom rail", "靠背下横档", "Gỗ thông / Pine"),
    "back_top":    ("Thanh tựa trên", "Back top rail", "靠背上横档", "Gỗ thông / Pine"),
    "back_stile":  ("Thanh đứng tựa", "Back stile", "靠背立档", "Gỗ thông / Pine"),
    "leg":         ("Chân", "Leg", "脚", "Gỗ cao su / Rubberwood"),
}

# Phụ kiện (hardware): mã -> (VN, EN, CN)
HARDWARE = {
    "A": ("Bulông M8×90 + ốc cấy Ø10", "KD bolt M8×90 + barrel nut", "M8×90螺栓+圆柱螺母"),
    "B": ("Chốt gỗ Ø8×40 + keo PVA", "Wood dowel Ø8×40 + PVA glue", "木榫Ø8×40+白乳胶"),
    "C": ("Vít gỗ 4×40", "Wood screw 4×40", "木螺丝4×40"),
    "D": ("Bulông treo chân M8 + tán cấy", "Hanger bolt M8 + T-nut", "M8脚螺栓+预埋螺母"),
    "E": ("Vít gỗ 4×50 (ke góc)", "Wood screw 4×50 (block)", "木螺丝4×50(角码)"),
}


@dataclass
class Part:
    tag: str                 # mã duy nhất từng chi tiết (instance id)
    ptype: str               # loại -> PART_TYPES
    module: str              # M1..M5
    box: tuple               # (x0, y0, z0, x1, y1, z1)
    part_off: tuple = (0, 0, 0)    # bung cấp chi tiết (part-level explode)
    follow: str = None       # chân đi theo module nào khi bung (vd chân góc theo tay)

    @property
    def size(self):
        x0, y0, z0, x1, y1, z1 = self.box
        return sorted((x1 - x0, y1 - y0, z1 - z0), reverse=True)  # L, W, T


@dataclass
class Joint:
    """Nhóm liên kết: các điểm (toạ độ lắp ráp) giữa 2 chi tiết, mỗi điểm = 1 phụ kiện."""
    hw: str                  # mã phụ kiện A..E
    a: str                   # tag chi tiết A
    b: str                   # tag chi tiết B
    pts: list = field(default_factory=list)
    step: int = 1            # bước lắp


def module_offsets(p):
    return {
        "M1": (0, 0, 0),
        "M2": (-p["ex_arm"], 0, 0),
        "M3": (p["ex_arm"], 0, 0),
        "M4": (0, p["ex_back_y"], p["ex_back_z"]),
        "M5": (0, 0, 0),
    }


def build(p=None):
    """Trả về (parts, joints) từ bộ tham số."""
    p = dict(PARAMS, **(p or {}))
    W, D = p["W"], p["D"]
    Ta, Hl, Pd = p["T_arm"], p["H_leg"], p["post_d"]
    rt, rh = p["rail_t"], p["rail_h"]
    parts, joints = [], []
    add = lambda *a, **k: parts.append(Part(*a, **k))

    z_seat0, z_seat1 = Hl, Hl + rh            # đà ngồi
    xi0, xi1 = Ta, W - Ta                       # mép trong 2 tay

    # ---------------- M1 KHUNG NGỒI ----------------
    add("front_rail", "front_rail", "M1", (xi0, 0, z_seat0, xi1, rt, z_seat1),
        part_off=(0, -p["ex_rail"], 0))
    add("back_rail", "back_rail", "M1", (xi0, D - rt, z_seat0, xi1, D, z_seat1),
        part_off=(0, p["ex_rail"], 0))
    add("end_rail_L", "end_rail", "M1", (xi0, rt, z_seat0, xi0 + rt, D - rt, z_seat1))
    add("end_rail_R", "end_rail", "M1", (xi1 - rt, rt, z_seat0, xi1, D - rt, z_seat1))
    n = p["n_mid_rails"]
    mid_x = [xi0 + (xi1 - xi0) * (i + 1) / (n + 1) for i in range(n)]
    for i, xc in enumerate(mid_x):
        add(f"mid_rail_{i}", "mid_rail", "M1",
            (xc - rt / 2, rt, z_seat0, xc + rt / 2, D - rt, z_seat1))
    b, bh = p["block"], p["block_h"]
    zb0 = z_seat0 + (rh - bh) / 2
    for side, (bx0, bx1) in (("L", (xi0 + rt, xi0 + rt + b)), ("R", (xi1 - rt - b, xi1 - rt))):
        for fb, (by0, by1) in (("F", (rt, rt + b)), ("B", (D - rt - b, D - rt))):
            add(f"block_{side}{fb}", "block", "M1", (bx0, by0, zb0, bx1, by1, zb0 + bh),
                part_off=(0, 0, p["ex_block"]))

    # ---------------- M2/M3 TAY VỊN ----------------
    zt0 = p["H_arm"] - p["arm_top_h"]
    for side, mod, (ax0, ax1) in (("L", "M2", (0, Ta)), ("R", "M3", (W - Ta, W))):
        add(f"arm{side}_post_F", "arm_post", mod, (ax0, 0, Hl, ax1, Pd, zt0))
        add(f"arm{side}_post_B", "arm_post", mod, (ax0, D - Pd, Hl, ax1, D, zt0))
        add(f"arm{side}_top", "arm_top", mod, (ax0, 0, zt0, ax1, D, p["H_arm"]),
            part_off=(0, 0, p["ex_top"]))
        add(f"arm{side}_bot", "arm_bot", mod, (ax0, Pd, Hl, ax1, D - Pd, Hl + p["arm_bot_h"]))
        add(f"arm{side}_mid", "arm_mid", mod,
            (ax0, Pd, p["arm_mid_z"], ax1, D - Pd, p["arm_mid_z"] + p["arm_mid_h"]))

    # ---------------- M4 KHUNG TỰA ----------------
    bt, sw = p["back_t"], p["stile_w"]
    zb_top = z_seat1 + p["back_bot_h"]
    zt_bot = p["H_back"] - p["back_top_h"]
    add("back_bot", "back_bot", "M4", (xi0, D - bt, z_seat1, xi1, D, zb_top),
        part_off=(0, 0, -150))
    add("back_top", "back_top", "M4", (xi0, D - bt, zt_bot, xi1, D, p["H_back"]),
        part_off=(0, 0, p["ex_top"]))
    m = p["n_mid_stiles"]
    stile_x = [xi0, xi1 - sw] + [xi0 + (xi1 - xi0) * (i + 1) / (m + 1) - sw / 2 for i in range(m)]
    for i, sx in enumerate(stile_x):
        add(f"stile_{i}", "back_stile", "M4", (sx, D - bt, zb_top, sx + sw, D, zt_bot))

    # ---------------- M5 CHÂN ----------------
    lg = p["leg"]
    yoff = (Pd - lg) / 2
    for side, lx0, fol in (("L", 0, "M2"), ("R", W - Ta, "M3")):
        lx = lx0 + (Ta - lg) / 2
        add(f"leg_{side}F", "leg", "M5", (lx, yoff, 0, lx + lg, yoff + lg, Hl),
            part_off=(0, 0, -p["ex_leg"]), follow=fol)
        add(f"leg_{side}B", "leg", "M5", (lx, D - Pd + yoff, 0, lx + lg, D - Pd + yoff + lg, Hl),
            part_off=(0, 0, -p["ex_leg"]), follow=fol)
    xc = W / 2
    add("leg_MF", "leg", "M5", (xc - lg / 2, 0, 0, xc + lg / 2, lg, Hl), part_off=(0, 0, -p["ex_leg"]))
    add("leg_MB", "leg", "M5", (xc - lg / 2, D - lg, 0, xc + lg / 2, D, Hl), part_off=(0, 0, -p["ex_leg"]))

    # ---------------- LIÊN KẾT (JOINTS) ----------------
    J = lambda *a, **k: joints.append(Joint(*a, **k))
    zc = (z_seat0 + z_seat1) / 2
    # Bước 1: khung ngồi — chốt gỗ + keo, vít; ke góc
    for t in ["end_rail_L", "end_rail_R"] + [f"mid_rail_{i}" for i in range(n)]:
        pr = next(q for q in parts if q.tag == t)
        x = (pr.box[0] + pr.box[3]) / 2
        J("B", "front_rail", t, [(x, rt, zc - 35), (x, rt, zc + 35)], step=1)
        J("B", "back_rail", t, [(x, D - rt, zc - 35), (x, D - rt, zc + 35)], step=1)
    for t in ("end_rail_L", "end_rail_R"):
        pr = next(q for q in parts if q.tag == t)
        x = (pr.box[0] + pr.box[3]) / 2
        J("C", "front_rail", t, [(x, rt, zc)], step=1)
        J("C", "back_rail", t, [(x, D - rt, zc)], step=1)
    for q in [q for q in parts if q.ptype == "block"]:
        x0, y0, z0, x1, y1, z1 = q.box
        yr = y0 if q.tag.endswith("F") else y1
        J("E", "front_rail" if q.tag.endswith("F") else "back_rail", q.tag,
          [((x0 + x1) / 2, yr, (z0 + z1) / 2)], step=1)
        xr = x0 if q.tag[6] == "L" else x1
        J("E", "end_rail_" + q.tag[6], q.tag, [(xr, (y0 + y1) / 2, (z0 + z1) / 2)], step=1)
    # Bước 2: tay vịn — lắp trong (chốt) + bắt bulông KD vào khung ngồi
    for side, xa in (("L", Ta), ("R", W - Ta)):
        xm = Ta / 2 if side == "L" else W - Ta / 2
        for pst in ("F", "B"):
            y0 = Pd * 0.3 if pst == "F" else D - Pd * 0.7
            J("B", f"arm{side}_post_{pst}", f"arm{side}_top",
              [(xm, y0, zt0), (xm, y0 + Pd * 0.4, zt0)], step=2)
        J("A", f"arm{side}_post_F", "front_rail", [(xa, rt / 2, zc - 40), (xa, rt / 2, zc + 40)], step=2)
        J("A", f"arm{side}_post_B", "back_rail", [(xa, D - rt / 2, zc - 40), (xa, D - rt / 2, zc + 40)], step=2)
        J("A", f"arm{side}_bot", f"end_rail_{side}",
          [(xa, D * 0.33, Hl + p["arm_bot_h"] / 2), (xa, D * 0.67, Hl + p["arm_bot_h"] / 2)], step=2)
    # Bước 3: khung tựa — bulông vào trụ sau tay, vít xuống đà sau
    for i, sx in enumerate(stile_x):
        xm = sx + sw / 2
        J("B", "back_top", f"stile_{i}", [(xm, D - bt / 2, zt_bot)], step=3)
        J("B", "back_bot", f"stile_{i}", [(xm, D - bt / 2, zb_top)], step=3)
    for side, xa, st in (("L", Ta, "stile_0"), ("R", W - Ta, "stile_1")):
        J("A", f"arm{side}_post_B", st, [(xa, D - bt / 2, zb_top + 80), (xa, D - bt / 2, zb_top + 200)], step=3)
    J("C", "back_rail", "back_bot",
      [(xi0 + (xi1 - xi0) * k / 5, D - bt / 2, z_seat1) for k in range(1, 5)], step=3)
    # Bước 4: chân
    for q in [q for q in parts if q.ptype == "leg"]:
        x0, y0, z0, x1, y1, z1 = q.box
        host = {"leg_MF": "front_rail", "leg_MB": "back_rail"}.get(q.tag)
        if host is None:
            host = f"arm{q.tag[4]}_post_{q.tag[5]}"
        J("D", host, q.tag, [((x0 + x1) / 2, (y0 + y1) / 2, z1)], step=4)

    return p, parts, joints


def explode_offset(part, p, level="full"):
    """Vector bung của chi tiết.
    level='full'   : bung module + bung chi tiết (hình bung tổng)
    level='module' : chỉ bung module (dùng cho các bước lắp)
    level='part'   : chỉ bung chi tiết
    """
    mo = module_offsets(p)
    base = mo[part.follow] if part.follow else mo[part.module]
    if level == "module":
        o = base if part.module != "M5" else part.part_off
        return o
    if level == "part":
        return part.part_off
    return tuple(a + b for a, b in zip(base, part.part_off))


def check_overlaps(parts, tol=0.01):
    """Kiểm tra không có 2 chi tiết chồng thể tích (interference check)."""
    bad = []
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            ov = [min(a.box[k + 3], b.box[k + 3]) - max(a.box[k], b.box[k]) for k in range(3)]
            if all(o > tol for o in ov):
                bad.append((a.tag, b.tag, ov))
    return bad
