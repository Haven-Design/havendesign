import io
import fitz
import docx
import csv
from typing import List
from .extract_text import Hit

CATEGORY_COLORS = {
    "email": "#FF6B6B","phone": "#6BCB77","credit_card": "#4D96FF","ssn": "#FFD93D",
    "drivers_license": "#FF8C42","date": "#9D4EDD","address": "#00C49A","name": "#FF1493",
    "ip_address": "#1E90FF","bank_account": "#FF4500","vin": "#008B8B","custom": "#A9A9A9",
}

def redact_pdf_with_hits(input_pdf: str, hits: List[Hit], output_pdf: str | None = None, preview_mode: bool = False):
    doc = fitz.open(input_pdf)
    for h in hits:
        page = doc[h.page]
        rect = fitz.Rect(*h.rect)
        if preview_mode:
            color = CATEGORY_COLORS.get(h.category, "#000000")
            page.draw_rect(rect, color=fitz.utils.getColor(color), fill=None, width=2)
        else:
            page.add_redact_annot(rect, fill=(0,0,0))
    if not preview_mode:
        doc.apply_redactions()
        out = io.BytesIO()
        doc.save(out)
        doc.close()
        return out.getvalue()
    else:
        doc.save(output_pdf)
        doc.close()

def save_masked_file(file_bytes: bytes, ext: str, hits: List[Hit]) -> bytes:
    masked_text = None
    if ext == ".txt" or ext == ".csv":
        text = file_bytes.decode("utf-8", errors="ignore")
        for h in hits:
            text = text.replace(h.text, "████")
        masked_text = text.encode("utf-8")

    elif ext == ".docx":
        from docx import Document
        import tempfile
        temp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        temp_in.write(file_bytes); temp_in.close()
        doc = Document(temp_in.name)
        for para in doc.paragraphs:
            for h in hits:
                if h.text in para.text:
                    para.text = para.text.replace(h.text, "████")
        out = io.BytesIO()
        doc.save(out)
        masked_text = out.getvalue()
    return masked_text
