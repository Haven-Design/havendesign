import io
from typing import List, Tuple, Dict

import fitz  # PyMuPDF
from PIL import Image, ImageDraw

from .extract_text import Hit, CATEGORY_COLORS

# ---------- Preview (colored translucent overlays) ----------
def make_preview_pdf_with_colored_overlays(pdf_bytes: bytes, hits: List[Hit]) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # group hits by page
    by_page: Dict[int, List[Hit]] = {}
    for h in hits:
        if h.page < 0:
            continue
        by_page.setdefault(h.page, []).append(h)

    # draw translucent colored fills for preview only
    for pno, page in enumerate(doc):
        if pno not in by_page:
            continue
        for h in by_page[pno]:
            x0, y0, x1, y1 = h.rect
            color_hex = CATEGORY_COLORS.get(h.category, "#444444")
            rgb = _hex_to_rgb01(color_hex)
            # use both stroke and fill with 30% opacity
            page.draw_rect(
                fitz.Rect(x0, y0, x1, y1),
                color=rgb,
                fill=rgb,
                fill_opacity=0.30,
                width=0.6,
            )

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()

# ---------- Final (black-fill) without apply_redactions ----------
# We rasterize each page, draw black boxes, then rebuild a PDF from images.
def make_final_blackfilled_pdf(pdf_bytes: bytes, hits: List[Hit], dpi: int = 200) -> bytes:
    src = fitz.open(stream=pdf_bytes, filetype="pdf")

    # bucket hits by page
    by_page: Dict[int, List[Hit]] = {}
    for h in hits:
        if h.page < 0:
            continue
        by_page.setdefault(h.page, []).append(h)

    out_doc = fitz.open()
    for pno, page in enumerate(src):
        # Render page to image
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # draw black rectangles in pixel coords
        draw = ImageDraw.Draw(img)
        if pno in by_page:
            for h in by_page[pno]:
                x0, y0, x1, y1 = h.rect
                # convert PDF points to pixels
                rx0, ry0 = int(x0 * zoom), int(y0 * zoom)
                rx1, ry1 = int(x1 * zoom), int(y1 * zoom)
                draw.rectangle([rx0, ry0, rx1, ry1], fill=(0, 0, 0))

        # insert page image back into a new PDF page sized as original
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes = img_bytes.getvalue()

        new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, stream=img_bytes)

    out = io.BytesIO()
    out_doc.save(out)
    out_doc.close()
    src.close()
    return out.getvalue()

# ---------- For non-PDF textual formats ----------
def mask_text_like_file(file_bytes: bytes, ext: str, hits: List[Hit]) -> tuple[bytes, str, str]:
    # simplistic masking: for .txt -> replace matched substrings with █ chars
    # for .docx, we export a .txt with masked content (keeps it simple & consistent)
    text = file_bytes.decode("utf-8", errors="ignore")
    # collect unique matched texts (non-empty) from hits (non-PDF hits may have generic text labels)
    patterns = set()
    for h in hits:
        if h.text and "[" not in h.text:  # skip generic labels like "[Email Addresses match]"
            patterns.add(h.text)

    masked = text
    for t in sorted(patterns, key=len, reverse=True):
        masked = masked.replace(t, "█" * len(t))

    out_bytes = masked.encode("utf-8")
    out_name = "redacted.txt"
    out_mime = "text/plain"
    return out_bytes, out_name, out_mime

# ---------- Utilities ----------
def _hex_to_rgb01(hex_color: str) -> Tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r, g, b)
