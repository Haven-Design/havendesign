from typing import List, Dict, Tuple
import fitz  # PyMuPDF
from utilities.extract_text import Hit

# -------------------------------
# Convert hex colors → normalized RGB (0–1)
# -------------------------------
def hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (r / 255.0, g / 255.0, b / 255.0)

# -------------------------------
# Category color palette
# -------------------------------
CATEGORY_COLORS: Dict[str, str] = {
    "email": "#e74c3c",          # red
    "phone": "#2ecc71",          # green
    "credit_card": "#3498db",    # blue
    "ssn": "#f1c40f",            # yellow
    "drivers_license": "#e67e22",# orange
    "date": "#9b59b6",           # purple
    "address": "#1abc9c",        # teal
    "name": "#34495e",           # dark gray-blue
    "ip_address": "#16a085",     # green/teal
    "bank_account": "#d35400",   # dark orange
    "vin": "#7f8c8d",            # gray
    "custom": "#95a5a6",         # light gray
}

# -------------------------------
# Redaction function
# -------------------------------
def redact_pdf_with_hits(file_bytes: bytes, hits: List[Hit], preview_mode: bool = False) -> bytes:
    """Apply highlights (preview) or black-box redactions (download)."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    # Group hits by page
    page_hits: Dict[int, List[Hit]] = {}
    for h in hits:
        page_hits.setdefault(h.page, []).append(h)

    for page_num, phits in page_hits.items():
        page = doc[page_num]

        for h in phits:
            if not h.bbox:
                continue
            rect = fitz.Rect(h.bbox)

            if preview_mode:
                # Show semi-transparent colored box
                color = hex_to_rgb(CATEGORY_COLORS.get(h.category, "#000000"))
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=color, fill=color)
                annot.set_opacity(0.35)
                annot.update()
            else:
                # True destructive redaction (solid black box)
                page.add_redact_annot(rect, fill=(0, 0, 0))

        if not preview_mode:
            page.apply_redactions()

    out_bytes = doc.tobytes()
    doc.close()
    return out_bytes
