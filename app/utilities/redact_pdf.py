import io
import fitz  # PyMuPDF
from typing import List
from utilities.extract_text import Hit

CATEGORY_COLORS = {
    "email": "#1f77b4",
    "phone": "#ff7f0e",
    "ssn": "#2ca02c",
    "credit_card": "#d62728",
    "drivers_license": "#9467bd",
    "names": "#8c564b",
    "custom": "#e377c2",
}

def redact_pdf_with_hits(input_pdf: str, hits: List[Hit], preview_mode: bool = True) -> bytes:
    doc = fitz.open(input_pdf)
    for h in hits:
        page = doc[h.page]
        if preview_mode:
            color = tuple(int(CATEGORY_COLORS.get(h.category, "#000000")[i:i+2], 16) / 255.0 for i in (1, 3, 5))
            page.draw_rect(fitz.Rect(h.rect), color=color, fill=color, overlay=True, fill_opacity=0.4)
        else:
            page.add_redact_annot(fitz.Rect(h.rect), fill=(0, 0, 0))
    if not preview_mode:
        if hasattr(doc, "apply_redactions"):
            doc.apply_redactions()
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()

def save_masked_file(file_bytes: bytes, ext: str, hits: List[Hit]) -> bytes:
    # Mask sensitive phrases in text/docx
    text = file_bytes.decode("utf-8", errors="ignore")
    for h in hits:
        text = text.replace(h.text, "█" * len(h.text))
    return text.encode("utf-8")
