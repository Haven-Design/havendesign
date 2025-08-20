import fitz
import io
from typing import List
from utilities.extract_text import Hit

CATEGORY_COLORS = {
    "email": "#1f77b4",
    "phone": "#ff7f0e",
    "ssn": "#2ca02c",
    "credit_card": "#d62728",
    "drivers_license": "#9467bd",
    "name": "#8c564b",
    "custom": "#e377c2"
}

def redact_pdf_with_hits(input_pdf: str, hits: List[Hit], preview_mode=True) -> bytes:
    doc = fitz.open(input_pdf)

    for h in hits:
        page = doc[h.page]
        color = tuple(int(CATEGORY_COLORS.get(h.category, "#000000")[i:i+2], 16)/255 for i in (1, 3, 5))

        if preview_mode:
            page.draw_rect(h.rect, color=color, fill=color + (0.3,), overlay=True)
        else:
            page.add_redact_annot(h.rect, fill=(0, 0, 0))
            if hasattr(doc, "apply_redactions"):
                doc.apply_redactions()

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()

def save_masked_file(file_bytes, ext: str) -> bytes:
    return file_bytes
