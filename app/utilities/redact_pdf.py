import io
from typing import List, Optional, Dict
import fitz  # PyMuPDF
from .extract_text import Hit, CATEGORY_COLORS


# Colors in RGB (0–1 float)
def _hex_to_rgb_floats(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def redact_pdf_with_hits(
    input_path: str,
    hits: List[Hit],
    output_path: Optional[str] = None,
    preview_mode: bool = False,
) -> bytes:
    """
    Redacts or highlights hits in a PDF.
    - preview_mode=True → highlight with semi-transparent overlay
    - preview_mode=False → true white-box redaction
    """
    if not hits:
        with open(input_path, "rb") as f:
            return f.read()

    doc = fitz.open(input_path)

    # Group hits by page
    page_hits: Dict[int, List[Hit]] = {}
    for h in hits:
        page_hits.setdefault(h.page, []).append(h)

    for page_num, hlist in page_hits.items():
        page = doc[page_num]
        for h in hlist:
            bbox = getattr(h, "bbox", None)
            if not bbox:
                continue  # skip if no geometry
            rect = fitz.Rect(bbox)

            if preview_mode:
                color = CATEGORY_COLORS.get(h.category, "#FF0000")
                rgb = _hex_to_rgb_floats(color)
                page.draw_rect(rect, color=rgb, fill=(*rgb, 0.2), width=0.8)
            else:
                red = page.add_redact_annot(rect, fill=(1, 1, 1))
                if red:
                    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    out_bytes = doc.write()
    doc.close()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(out_bytes)

    return out_bytes


def save_masked_file(file_bytes: bytes, ext: str, hits: List[Hit]) -> bytes:
    """
    For DOCX/TXT: replace selected hits with █ characters.
    """
    if not hits:
        return file_bytes

    if ext == ".txt":
        text = file_bytes.decode("utf-8", errors="ignore")
        for h in hits:
            text = text.replace(h.text, "█" * len(h.text))
        return text.encode("utf-8")

    elif ext == ".docx":
        from docx import Document
        from io import BytesIO

        doc = Document(io.BytesIO(file_bytes))
        for para in doc.paragraphs:
            for h in hits:
                if h.text in para.text:
                    para.text = para.text.replace(h.text, "█" * len(h.text))

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    return file_bytes
