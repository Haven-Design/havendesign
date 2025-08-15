import fitz  # PyMuPDF
from utilities.extract_text import CATEGORY_DEFS

# A safer neutral fill for preview (ADA-friendly overlay without hiding content)
PREVIEW_FILL = (0.85, 0.85, 0.85)  # light gray
PREVIEW_FILL_OPACITY = 0.35
PREVIEW_STROKE_WIDTH = 1.5

# Download redaction fill (black)
REDACT_FILL = (0, 0, 0)

def make_preview_pdf(pdf_bytes: bytes, items):
    """
    Draws translucent rectangles (with category colors as stroke) on a copy of the PDF.
    Does NOT apply redactions—just a visual preview.
    Returns PDF bytes.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    # Group items by page
    by_page = {}
    for it in items:
        by_page.setdefault(it["page"], []).append(it)

    for pno in range(len(doc)):
        page = doc[pno]
        page_items = by_page.get(pno, [])
        if not page_items:
            continue

        for it in page_items:
            color_rgb = CATEGORY_DEFS.get(it["category"], {}).get("color", (0.2, 0.2, 0.2))
            for rect in it["rects"]:
                # draw rect with semi-transparent fill & colored border (overlay=True keeps content)
                page.draw_rect(
                    rect,
                    color=color_rgb,              # stroke
                    fill=PREVIEW_FILL,            # fill
                    width=PREVIEW_STROKE_WIDTH,
                    fill_opacity=PREVIEW_FILL_OPACITY,
                    overlay=True,
                )

    out = doc.tobytes()
    doc.close()
    return out


def apply_redactions_pdf(pdf_bytes: bytes, items):
    """
    Actually applies redactions (black boxes) to the selected items and returns bytes.
    Uses page.add_redact_annot(...); then page.apply_redactions().
    Compatible with PyMuPDF 1.26.3.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    by_page = {}
    for it in items:
        by_page.setdefault(it["page"], []).append(it)

    for pno in range(len(doc)):
        page = doc[pno]
        page_items = by_page.get(pno, [])
        if not page_items:
            continue

        for it in page_items:
            for rect in it["rects"]:
                # Some versions do not accept extra args (border/stroke), so only pass fill
                page.add_redact_annot(rect, fill=REDACT_FILL)

        # IMPORTANT: apply per-page in 1.26.x
        page.apply_redactions()

    out = doc.tobytes()
    doc.close()
    return out
