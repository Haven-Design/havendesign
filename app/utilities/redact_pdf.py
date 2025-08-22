import io
from collections import defaultdict
from typing import List, Optional

import fitz  # PyMuPDF

from utilities.extract_text import Hit, CATEGORY_COLORS

def redact_pdf_with_hits(input_path: str, hits: List[Hit], output_path: Optional[str] = None, preview_mode: bool = True) -> bytes:
    """
    If preview_mode=True, draws semi-transparent colored boxes (no permanent redaction).
    If preview_mode=False, applies black redaction boxes permanently.
    """
    doc = fitz.open(input_path)

    # Group hits by page for more efficient apply_redactions
    hits_by_page = defaultdict(list)
    for h in hits:
        if h.rect is None:
            continue
        hits_by_page[h.page].append(h)

    for page_num, page_hits in hits_by_page.items():
        page = doc[page_num]
        if preview_mode:
            for h in page_hits:
                color_hex = CATEGORY_COLORS.get(h.category, "#000000")
                rgb = tuple(int(color_hex.lstrip("#")[i:i+2], 16)/255 for i in (0, 2, 4))
                rect = fitz.Rect(h.rect)
                page.draw_rect(rect, color=rgb, fill=(*rgb, 0.2), width=1)
        else:
            # Add redaction annots first, then apply once
            for h in page_hits:
                rect = fitz.Rect(h.rect)
                page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)

    out = io.BytesIO()
    # Incremental save disabled to ensure preview marks persist
    doc.save(out, incremental=False)
    doc.close()

    data = out.getvalue()
    if output_path and preview_mode:
        with open(output_path, "wb") as f:
            f.write(data)
    return data

def save_masked_file(file_bytes: bytes, ext: str, hits: List[Hit]) -> bytes:
    """
    For non-PDF: replace each hit's text with same-length block characters.
    DOCX replacement is paragraph-level and may simplify formatting.
    """
    if ext == ".txt":
        text = file_bytes.decode("utf-8", errors="ignore")
        for h in sorted(hits, key=lambda x: len(x.text), reverse=True):
            text = text.replace(h.text, "█" * len(h.text))
        return text.encode("utf-8")

    if ext == ".docx":
        from docx import Document
        import io as sysio

        doc = Document(io.BytesIO(file_bytes))
        # naive run-level replacement
        for para in doc.paragraphs:
            if not para.text:
                continue
            new_text = para.text
            for h in sorted(hits, key=lambda x: len(x.text), reverse=True):
                if h.text in new_text:
                    new_text = new_text.replace(h.text, "█" * len(h.text))
            if new_text != para.text:
                # replace runs wholesale to preserve basic structure
                for r in para.runs:
                    r.text = ""
                para.add_run(new_text)

        output = sysio.BytesIO()
        doc.save(output)
        return output.getvalue()

    # Fallback: unchanged
    return file_bytes
