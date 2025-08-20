import io
import fitz  # PyMuPDF
from typing import List
from .extract_text import Hit, CATEGORY_COLORS

def make_preview_pdf_with_colored_overlays(file_bytes: bytes, hits: List[Hit]) -> bytes:
    doc = fitz.open("pdf", file_bytes)
    for h in hits:
        if h.rect is None:
            continue
        color = tuple(int(CATEGORY_COLORS.get(h.category, "#000000")[i:i+2], 16) / 255.0 for i in (1, 3, 5))
        highlight = doc[h.page].add_rect_annot(h.rect)
        highlight.set_colors(stroke=color, fill=color)
        highlight.set_opacity(0.4)
        highlight.update()
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()

def make_final_blackfilled_pdf(file_bytes: bytes, hits: List[Hit]) -> bytes:
    doc = fitz.open("pdf", file_bytes)
    for h in hits:
        if h.rect is None:
            continue
        page = doc[h.page]
        red = page.add_rect_annot(h.rect)
        red.set_colors(stroke=(0, 0, 0), fill=(0, 0, 0))
        red.set_opacity(1.0)
        red.update()
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()

def mask_text_like_file(file_bytes: bytes, ext: str, hits: List[Hit]) -> bytes:
    text = file_bytes.decode("utf-8", errors="ignore") if ext == ".txt" else ""
    for h in hits:
        text = text.replace(h.text, "[REDACTED]")
    return text.encode("utf-8")
