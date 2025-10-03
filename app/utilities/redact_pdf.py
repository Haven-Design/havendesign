"""
redact_pdf.py (v1.5)

- Converts hex colors to normalized RGB for PyMuPDF.
- preview_mode=True -> translucent colored rectangles (non-destructive preview)
- preview_mode=False -> destructive black-box redaction
- Applies redactions only where bbox exists
"""

from typing import List, Dict, Tuple
import fitz  # PyMuPDF
from utilities.extract_text import Hit

CATEGORY_COLORS: Dict[str, str] = {
    "email": "#EF4444",
    "phone": "#10B981",
    "credit_card": "#3B82F6",
    "ssn": "#F59E0B",
    "drivers_license": "#6366F1",
    "date": "#8B5CF6",
    "address": "#14B8A6",
    "name": "#EC4899",
    "ip_address": "#0EA5E9",
    "bank_account": "#F97316",
    "vin": "#6B7280",
    "custom": "#94A3B8",
}

def hex_to_rgb_norm(hex_color: str) -> Tuple[float, float, float]:
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16); g = int(h[2:4], 16); b = int(h[4:6], 16)
    return (r / 255.0, g / 255.0, b / 255.0)

def redact_pdf_with_hits(file_bytes: bytes, hits: List[Hit], preview_mode: bool = False) -> bytes:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page_map: Dict[int, List[Hit]] = {}
    for h in hits:
        page_map.setdefault(h.page, []).append(h)

    pages_to_apply = set()
    for pnum, phits in page_map.items():
        if pnum < 0 or pnum >= len(doc):
            continue
        page = doc[pnum]
        for h in phits:
            if not h.bbox:
                # if bbox not available, skip redaction (we only redact bbox-based matches)
                continue
            x0, y0, x1, y1 = h.bbox
            pad = 1.2
            rect = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad)
            if preview_mode:
                rgb = hex_to_rgb_norm(CATEGORY_COLORS.get(h.category, "#000000"))
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=rgb, fill=rgb)
                annot.set_opacity(0.35)
                annot.update()
            else:
                page.add_redact_annot(rect, fill=(0, 0, 0))
                pages_to_apply.add(pnum)

    # apply redactions
    for p in pages_to_apply:
        try:
            doc[p].apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        except Exception:
            doc[p].apply_redactions()

    out = doc.tobytes()
    doc.close()
    return out
