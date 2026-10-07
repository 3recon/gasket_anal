"""Approximate slide renderer for QA when LibreOffice is unavailable.

Draws every shape box, picture, table grid and wrapped text (real Malgun Gothic metrics)
to PNG, and reports text that does not fit its box.
Usage: python pptx_preview.py deck.pptx outdir
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.util import Emu

sys.stdout.reconfigure(encoding="utf-8")
DPI = 110
FONT_R = "C:/Windows/Fonts/malgun.ttf"
FONT_B = "C:/Windows/Fonts/malgunbd.ttf"


def px(emu):
    return int(Emu(emu).inches * DPI)


def wrap(text, font, width):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            if font.getlength(cur + ch) <= width:
                cur += ch
            else:
                # break at last space if possible
                sp = cur.rfind(" ")
                if sp > 0:
                    lines.append(cur[:sp])
                    cur = cur[sp + 1:] + ch
                else:
                    lines.append(cur)
                    cur = ch
        lines.append(cur)
    return lines


def layout_size(slide, sh):
    """font size (pt) declared on the matching layout placeholder, if any"""
    try:
        lp = slide.slide_layout.placeholders.get(idx=sh.placeholder_format.idx)
        for el in lp._element.iter():
            sz = el.get("sz")
            if sz and el.tag.endswith(("defRPr", "rPr", "endParaRPr")):
                return int(sz) / 100
    except Exception:
        pass
    return None


def color_of(shape):
    try:
        if shape.fill.type == 1:
            try:
                return "#" + str(shape.fill.fore_color.rgb)
            except Exception:
                return "#E3EAF0"      # theme colour: draw a neutral card
    except Exception:
        pass
    return None


def main(path, outdir):
    os.makedirs(outdir, exist_ok=True)
    prs = Presentation(path)
    W, H = px(prs.slide_width), px(prs.slide_height)
    issues = []
    for i, slide in enumerate(prs.slides, 1):
        bg = "#1B2631" if "DARK" in slide.slide_layout.name else "#FFFFFF"
        img = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(img)
        shapes = list(slide.slide_layout.placeholders) + list(slide.shapes)
        for sh in slide.shapes:
            if sh.left is None:
                continue
            x, y, w, h = px(sh.left), px(sh.top), px(sh.width), px(sh.height)
            fill = color_of(sh)
            if sh.shape_type == 13:  # picture
                d.rectangle([x, y, x + w, y + h], outline="#888888", fill="#DDE6EE")
                d.text((x + 4, y + 4), "PICTURE", fill="#555555")
            elif sh.has_chart if hasattr(sh, "has_chart") else False:
                d.rectangle([x, y, x + w, y + h], outline="#0E7C86")
                d.text((x + 4, y + 4), "CHART", fill="#0E7C86")
            elif sh.has_table if hasattr(sh, "has_table") else False:
                tbl = sh.table
                yy = y
                for r in tbl.rows:
                    xx = x
                    rh = px(r.height)
                    for ci, c in enumerate(r.cells):
                        cw = px(tbl.columns[ci].width)
                        d.rectangle([xx, yy, xx + cw, yy + rh], outline="#999999")
                        f = ImageFont.truetype(FONT_R, int(10.5 * DPI / 72))
                        lines = wrap(c.text, f, cw - 6)
                        need = len(lines) * f.size * 1.2
                        for li, ln in enumerate(lines):
                            d.text((xx + 3, yy + 2 + li * f.size * 1.2), ln, font=f, fill="#111111")
                        if need > rh + 2:
                            issues.append(f"slide {i}: table cell grows ({c.text[:30]!r}, {len(lines)} lines)")
                        xx += cw
                    yy += rh
            elif fill:
                d.rounded_rectangle([x, y, x + w, y + h], radius=6, fill=fill)
            if getattr(sh, "has_text_frame", False) and sh.has_text_frame and sh.text_frame.text.strip():
                tf = sh.text_frame
                ty = y
                total_h = 0
                for p in tf.paragraphs:
                    txt = "".join(r.text for r in p.runs)
                    size = None
                    bold = False
                    col = "#111111" if bg == "#FFFFFF" else "#EEEEEE"
                    for r in p.runs:
                        if r.font.size:
                            size = r.font.size.pt
                        bold = bold or bool(r.font.bold)
                        try:
                            col = "#" + str(r.font.color.rgb)
                        except Exception:
                            pass
                    if size is None and sh.is_placeholder:
                        size = layout_size(slide, sh)
                    size = size or 14
                    f = ImageFont.truetype(FONT_B if bold else FONT_R, max(6, int(size * DPI / 72)))
                    indent = 14 if p.level or (p._p.pPr is not None and p._p.pPr.find(
                        "{http://schemas.openxmlformats.org/drawingml/2006/main}buChar") is not None) else 0
                    lines = wrap(txt, f, max(10, w - indent)) if txt else [""]
                    for ln in lines:
                        d.text((x + indent, ty), ln, font=f, fill=col)
                        ty += f.size * 1.2
                        total_h += f.size * 1.2
                if total_h > h + 3 and not sh.is_placeholder:
                    issues.append(f"slide {i}: text overflows box '{sh.name}' ({total_h:.0f}px > {h}px): {tf.text[:40]!r}")
                if sh.is_placeholder and total_h > h + 3:
                    issues.append(f"slide {i}: placeholder text overflow '{sh.name}' ({total_h:.0f}px > {h}px)")
            if x + w > W + 1 or y + h > H + 1:
                issues.append(f"slide {i}: shape '{sh.name}' exceeds slide bounds")
        img.save(os.path.join(outdir, f"slide-{i:02d}.png"))
    print("\n".join(issues) if issues else "no overflow issues detected")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
