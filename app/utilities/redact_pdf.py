import io
from collections import defaultdict
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

from utilities.extract_text import Hit, CATEGORY_COLORS

def _hex_to_rgb01(color_hex: str) -> Tuple[float, float, float]:
    color_hex = color_hex.lstrip("#")
    return tuple(int(color_hex[i:i+2], 16) / 255 for i in (0, 2, 4))  # type: ignore

def redact_pdf_with_hits(input_path: str, hits: List[Hit], output_path: Optional[str] = None, preview_mode: bool = True) -> bytes:
    """
    If preview_mode=True: draw semi-transparent colored boxes (non-destructive).
    If preview_mode=False: add redaction annots for the exact rectangles and apply.
    """
    doc = fitz.open(input_path)

    # Group by page for efficiency
    hits_by_page = defaultdict(list)
    for h in hits:
        if not h.rects:
            continue
        hits_by_page[h.page].append(h)

    for page_num, page_hits in hits_by_page.items():
        page = doc[page_num]

        if preview_mode:
            for h in page_hits:
                color_hex = CATEGORY_COLORS.get(h.category, "#000000")
                rgb = _hex_to_rgb01(color_hex)
                for rect in h.rects:
                    r = fitz.Rect(rect)
                    page.draw_rect(r, color=rgb, fill=(*rgb, 0.22), width=1)
        else:
            # Add redact annots for each rectangle tied to each selected hit
            for h in page_hits:
                for rect in h.rects:
                    r = fitz.Rect(rect)
                    page.add_redact_annot(r, fill=(1, 1, 1))  # white fill (common expectation)
            # Apply once per page (limiting scope to annotations just added)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)

    out = io.BytesIO()
    doc.save(out, incremental=False)
    doc.close()

    data = out.getvalue()
    if output_path:
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
        for para in doc.paragraphs:
            if not para.text:
                continue
            new_text = para.text
            for h in sorted(hits, key=lambda x: len(x.text), reverse=True):
                if h.text in new_text:
                    new_text = new_text.replace(h.text, "█" * len(h.text))
            if new_text != para.text:
                for r in para.runs:
                    r.text = ""
                para.add_run(new_text)

        output = sysio.BytesIO()
        doc.save(output)
        return output.getvalue()

    # Fallback
    return file_bytes
