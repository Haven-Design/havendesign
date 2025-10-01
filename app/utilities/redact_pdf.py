import io
from typing import List, Dict
import fitz  # PyMuPDF
from .extract_text import Hit

CATEGORY_COLORS: Dict[str, str] = {
    "email": "#1f77b4",         # blue
    "phone": "#2ca02c",         # green
    "credit_card": "#d62728",   # red
    "ssn": "#9467bd",           # purple
    "drivers_license": "#ff7f0e",  # orange
    "date": "#8c564b",
    "address": "#17becf",
    "name": "#e377c2",
    "ip_address": "#7f7f7f",
    "bank_account": "#bcbd22",
    "vin": "#17becf",
    "custom": "#000000",
}

def redact_pdf_with_hits(file_bytes: bytes, hits: List[Hit], preview_mode: bool = True) -> bytes:
    """Apply destructive black-box redactions to PDF."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    # Group hits by page
    page_hits: Dict[int, List[Hit]] = {}
    for h in hits:
        page_hits.setdefault(h.page, []).append(h)

    for page_num, phits in page_hits.items():
        page = doc[page_num]
        for h in phits:
            if h.bbox:
                rect = fitz.Rect(h.bbox)
                # Add redaction annotation
                page.add_redact_annot(rect, fill=(0, 0, 0))  # Black box
        # Apply all redactions on this page
        page.apply_redactions()

    out_bytes = io.BytesIO()
    doc.save(out_bytes)
    doc.close()
    return out_bytes.getvalue()
