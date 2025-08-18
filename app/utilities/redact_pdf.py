import fitz
from typing import List
from extract_text import Hit

CATEGORY_COLORS = {
    "email": "#FF6B6B",
    "phone": "#6BCB77",
    "credit_card": "#4D96FF",
    "ssn": "#FFD93D",
    "drivers_license": "#FF8C42",
    "date": "#9D4EDD",
    "address": "#00C49A",
    "name": "#FF1493",
    "ip_address": "#1E90FF",
    "bank_account": "#FF4500",
    "vin": "#008B8B",
    "custom": "#A9A9A9",
}

def redact_pdf_with_hits(input_pdf: str, hits: List[Hit], output_pdf: str, preview_mode: bool = False) -> None:
    doc = fitz.open(input_pdf)

    for hit in hits:
        page = doc[hit.page]
        if preview_mode:
            color = CATEGORY_COLORS.get(hit.category, "#000000")
            page.draw_rect(hit.rect, color=fitz.utils.getColor(color), fill=None, width=2)
        else:
            page.add_redact_annot(hit.rect, fill=(0, 0, 0))

    if not preview_mode:
        doc.apply_redactions()
    doc.save(output_pdf)
    doc.close()
