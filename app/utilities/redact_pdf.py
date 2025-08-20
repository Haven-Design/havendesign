import fitz
import io
import docx
from typing import List
from utilities.extract_text import Hit

CATEGORY_COLORS = {
    "email": (1, 0, 0),
    "phone": (0, 1, 0),
    "credit_card": (0, 0, 1),
    "ssn": (1, 1, 0),
    "drivers_license": (1, 0.5, 0),
    "date": (0.5, 0, 0.5),
    "address": (0, 0.5, 0),
    "name": (0.5, 0, 0.5),
    "ip_address": (0, 0, 0.5),
    "bank_account": (1, 0.5, 0.5),
    "vin": (0.6, 0.3, 0.1),
    "custom": (0.8, 0.8, 0.8),
}

def redact_pdf_with_hits(input_path, hits: List[Hit], preview_mode=True):
    doc = fitz.open(input_path)
    for h in hits:
        rect = fitz.Rect(h.rect)
        page = doc[h.page]
        if preview_mode:
            color = CATEGORY_COLORS.get(h.category, (0, 0, 0))
            page.draw_rect(rect, color=color, fill=color + (0.3,), width=0.5)
        else:
            page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0), width=0)
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()

def save_masked_file(file_bytes: bytes, ext: str, hits: List[Hit]):
    if ext == ".txt":
        text = file_bytes.decode("utf-8", errors="ignore")
        for h in hits:
            text = text.replace(h.text, "█" * len(h.text))
        return text.encode("utf-8")

    elif ext == ".docx":
        doc = docx.Document(io.BytesIO(file_bytes))
        for p in doc.paragraphs:
            for h in hits:
                if h.text in p.text:
                    inline = p.runs
                    for run in inline:
                        run.text = run.text.replace(h.text, "█" * len(h.text))
        out = io.BytesIO()
        doc.save(out)
        return out.getvalue()

    else:
        return file_bytes
