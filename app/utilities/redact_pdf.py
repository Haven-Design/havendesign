import io
from typing import List, Tuple

import fitz  # PyMuPDF

from .extract_text import Hit

# UI color tokens (hex) for categories — used for preview coloring only
CATEGORY_COLORS = {
    "email": "#FF6B6B",          # red
    "phone": "#2ECC71",          # green
    "credit_card": "#4D96FF",    # blue
    "ssn": "#FFD93D",            # yellow
    "drivers_license": "#FF8C42",# orange
    "date": "#9D4EDD",           # purple
    "address": "#00C49A",        # teal/green
    "name": "#FF69B4",           # pink
    "ip_address": "#1E90FF",     # blue
    "bank_account": "#FF4500",   # orange-red
    "vin": "#8B4513",            # brown
    "custom": "#A9A9A9",         # gray
}


def _hex_to_rgb01(hx: str) -> Tuple[float, float, float]:
    hx = hx.lstrip("#")
    r = int(hx[0:2], 16) / 255.0
    g = int(hx[2:4], 16) / 255.0
    b = int(hx[4:6], 16) / 255.0
    return (r, g, b)


def _make_preview_pdf(input_pdf: str, hits: List[Hit]) -> bytes:
    """Draw semi-transparent, color overlays by category. No redaction APIs used."""
    doc = fitz.open(input_pdf)
    for h in hits:
        # guard invalid page indexes
        if h.page < 0 or h.page >= len(doc):
            continue
        page = doc[h.page]
        color = _hex_to_rgb01(CATEGORY_COLORS.get(h.category, "#000000"))
        # semi-transparent fill + visible stroke
        page.draw_rect(
            h.rect,
            color=color,
            fill=color,
            width=2,
            stroke_opacity=0.95,
            fill_opacity=0.28,
            overlay=True,
        )
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def _burn_in_black(input_pdf: str, hits: List[Hit], scale: float = 2.0) -> bytes:
    """
    Produce a final PDF with black boxes BURNED IN.
    We rasterize each page and draw solid black boxes on top in a new PDF.
    No use of Document.apply_redactions() — works on older / stripped PyMuPDF builds.
    """
    src = fitz.open(input_pdf)
    outdoc = fitz.open()

    # group rects by page
    per_page = {}
    for h in hits:
        per_page.setdefault(h.page, []).append(h.rect)

    for pno in range(len(src)):
        p = src[pno]
        # render original page to image
        pix = p.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)

        # make new page same size and place image
        out_page = outdoc.new_page(width=p.rect.width, height=p.rect.height)
        out_page.insert_image(p.rect, stream=pix.tobytes("png"))

        # draw black boxes on top
        for rect in per_page.get(pno, []):
            out_page.draw_rect(
                rect,
                color=(0, 0, 0),
                fill=(0, 0, 0),
                width=0,
                stroke_opacity=1.0,
                fill_opacity=1.0,
                overlay=True,
            )

    out = io.BytesIO()
    outdoc.save(out)
    outdoc.close()
    src.close()
    return out.getvalue()


def redact_pdf_with_hits(input_pdf: str, hits: List[Hit], preview_mode: bool) -> bytes:
    """
    preview_mode=True  -> color, semi-transparent overlays (for the on-page preview)
    preview_mode=False -> black boxes burned into an image-PDF for true redaction
    """
    if preview_mode:
        return _make_preview_pdf(input_pdf, hits)
    return _burn_in_black(input_pdf, hits)
