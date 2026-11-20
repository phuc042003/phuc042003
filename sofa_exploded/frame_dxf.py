# -*- coding: utf-8 -*-
"""
DÙNG KHUNG BẢN VẼ CỦA KHÁCH (DXF) THAY KHUNG MẶC ĐỊNH
======================================================
- Nạp toàn bộ modelspace của file khung (vd KHUNG_A4.dxf xuất từ AutoCAD: SAVEAS -> DXF)
  thành block "KHUNG_A4", tự co giãn để khung bao vừa khổ A4 của bộ bản vẽ (297×210 mm × 10).
- Nếu khung có block thuộc tính (ATTDEF/ATTRIB), điền theo tên tag (không phân biệt hoa thường):
    TEN_BV / TITLE / TENBANVE      -> tên bản vẽ        SO_BV / DWG_NO / SOBANVE -> số bản vẽ
    TI_LE / SCALE / TILE            -> tỉ lệ             TO / SHEET / SO_TO       -> tờ
    TEN_EN / TITLE_EN               -> tên tiếng Anh     NGAY / DATE              -> ngày
"""
import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer

TAGS = {
    "title": ("CHITIET", "TEN_BV", "TITLE", "TENBANVE", "TEN_BAN_VE", "DRAWING_TITLE"),
    "title_en": ("TEN_EN", "TITLE_EN"),
    "dwg": ("SO_BV", "DWG_NO", "SOBANVE", "SO_BAN_VE", "DRAWING_NO"),
    "scale": ("SCALE", "TI_LE", "TILE", "TY_LE"),
    "sheet": ("SỐTRANG", "TO", "SHEET", "SO_TO", "SHEET_NO", "SOTRANG"),
    "date": ("NGÀYVẼ", "NGAY", "DATE", "NGAYVE"),
    "product": ("TÊNSP", "TENSP", "PRODUCT"),
    "code": ("MÃHÀNG", "MAHANG", "ITEM_NO"),
    "qty": ("SỐLUONG", "SỐLƯỢNG", "SOLUONG", "QTY"),
    "customer": ("KHÁCH", "KHACH", "CUSTOMER"),
}


class UserFrame:
    def __init__(self, path, PW, PH):
        self.src = ezdxf.readfile(path)
        ext = bbox.extents(self.src.modelspace())
        if not ext.has_data:
            raise SystemExit(f"Khung {path} trống")
        self.w, self.h = ext.size.x, ext.size.y
        self.base = (ext.extmin.x, ext.extmin.y)
        self.scale = min(PW / self.w, PH / self.h)
        self.PW, self.PH = PW, PH
        self.atts = [a.dxf.tag for a in self.src.modelspace().query("ATTDEF")]
        for ins in self.src.modelspace().query("INSERT"):
            self.atts += [a.dxf.tag for a in ins.attribs]

    def place(self, doc, values):
        """values: dict title/title_en/dwg/scale/sheet/date. Trả về các key đã điền."""
        imp = Importer(self.src, doc)
        blk = doc.blocks.new("KHUNG_A4", base_point=(*self.base, 0))
        imp.import_entities(self.src.modelspace(), blk)
        imp.finalize()
        msp = doc.modelspace()
        ref = msp.add_blockref("KHUNG_A4", (0, 0), dxfattribs={"xscale": self.scale, "yscale": self.scale,
                                                               "layer": "0-KHUNG-BANVE"})
        filled = set()
        # ATTDEF ở cấp khung -> thêm ATTRIB vào INSERT
        defs = {a.dxf.tag.upper(): a for a in blk.query("ATTDEF")}
        for key, tags in TAGS.items():
            if key not in values:
                continue
            for t in tags:
                if t in defs:
                    a = defs[t]
                    p = a.dxf.insert
                    ref.add_attrib(a.dxf.tag, str(values[key]),
                                   ((p[0] - self.base[0]) * self.scale, (p[1] - self.base[1]) * self.scale),
                                   dxfattribs={"height": a.dxf.height * self.scale, "style": "VN"})
                    filled.add(key)
                    break
        # block khung tên có thuộc tính bên trong khung
        for e in blk.query("INSERT"):
            for att in e.attribs:
                for key, tags in TAGS.items():
                    if key in values and att.dxf.tag.upper() in tags:
                        att.dxf.text = str(values[key])
                        filled.add(key)
        return filled
