import io
from typing import List

import fitz  # PyMuPDF
from .extract_text import Hit

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

def _hex_to_rgb01(hex_color: str):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r, g, b)

def redact_pdf_with_hits(input_pdf: str, hits: List[Hit], preview_mode: bool = False) -> bytes:
    doc = fitz.open(input_pdf)

    for h in hits:
        if h.rect is None:
            continue
        page = doc[h.page]
        rect = fitz.Rect(*h.rect)

        if preview_mode:
            rgb = _hex_to_rgb01(CATEGORY_COLORS.get(h.category, "#000000"))
            page.draw_rect(rect, color=rgb, width=2)
        else:
            page.add_redact_annot(rect, fill=(0, 0, 0))

    if not preview_mode:
        # Requires PyMuPDF >= 1.19
        doc.apply_redactions()

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()

def save_masked_file(file_bytes: bytes, ext: str, hits: List[Hit]) -> bytes:
    if ext in (".txt", ".csv"):
        text = file_bytes.decode("utf-8", errors="ignore")
        # Mask longest phrases first to reduce partial overlaps
        for t in sorted({h.text for h in hits}, key=len, reverse=True):
            text = text.replace(t, "████")
        return text.encode("utf-8")

    if ext == ".docx":
        # Simple paragraph-level masking
        import tempfile
        from docx import Document
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        tmp.write(file_bytes); tmp.close()
        doc = Document(tmp.name)
        targets = sorted({h.text for h in hits}, key=len, reverse=True)
        for para in doc.paragraphs:
            for t in targets:
                if t in para.text:
                    para.text = para.text.replace(t, "████")
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    # Default: return original
    return file_bytes
