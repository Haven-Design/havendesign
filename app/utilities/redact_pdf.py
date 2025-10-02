"""
redact_pdf.py (v1.4)

- Converts hex category colors to normalized RGB values for PyMuPDF.
- preview_mode=True -> translucent colored rectangles (non-destructive preview)
- preview_mode=False -> destructive black box redaction
- Applies redactions only on pages that have redact annotations
"""

from typing import List, Dict, Tuple
import fitz  # PyMuPDF
from utilities.extract_text import Hit

# Category color hex palette (kept consistent with extractor)
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
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (r / 255.0, g / 255.0, b / 255.0)

def redact_pdf_with_hits(file_bytes: bytes, hits: List[Hit], preview_mode: bool = False) -> bytes:
    """
    Input: raw PDF bytes and list of Hit objects.
    Returns modified PDF bytes (either preview annotated or redacted).
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    # Group hits by page
    page_map: Dict[int, List[Hit]] = {}
    for h in hits:
        page_map.setdefault(h.page, []).append(h)

    # Track which pages had redaction annots so we only apply where necessary
    pages_to_apply = set()

    for page_num, phits in page_map.items():
        if page_num < 0 or page_num >= len(doc):
            continue
        page = doc[page_num]
        for h in phits:
            # Only handle hits with bbox for PDF operations
            if not h.bbox:
                continue
            x0, y0, x1, y1 = h.bbox
            pad = 1.0  # small padding to avoid stray letters
            rect = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad)

            if preview_mode:
                hexc = CATEGORY_COLORS.get(h.category, "#000000")
                rgb = hex_to_rgb_norm(hexc)
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=rgb, fill=rgb)
                annot.set_opacity(0.30)
                annot.update()
            else:
                # destructive black box
                page.add_redact_annot(rect, fill=(0, 0, 0))
                pages_to_apply.add(page_num)

    # Apply redactions only where added
    for pnum in pages_to_apply:
        try:
            doc[pnum].apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        except Exception:
            # fallback
            doc[pnum].apply_redactions()

    out = doc.tobytes()
    doc.close()
    return out
