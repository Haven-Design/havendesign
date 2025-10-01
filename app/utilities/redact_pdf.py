import io
from typing import List, Optional, Dict
import fitz  # PyMuPDF
from .extract_text import Hit, CATEGORY_COLORS


def _hex_to_rgb_floats(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def redact_pdf_with_hits(
    input_path,
    hits: List[Hit],
    output_path: Optional[str] = None,
    preview_mode: bool = False,
    black_box: bool = True,
) -> bytes:
    """
    Redacts or highlights hits in a PDF.
    - input_path may be a file path OR raw PDF bytes.
    - preview_mode=True → highlight with semi-transparent overlay
    - preview_mode=False + black_box=True → destructive black box redaction
    - preview_mode=False + black_box=False → destructive white redaction
    """
    if not hits:
        if isinstance(input_path, (bytes, bytearray)):
            return input_path
        else:
            with open(input_path, "rb") as f:
                return f.read()

    if isinstance(input_path, (bytes, bytearray)):
        doc = fitz.open(stream=input_path, filetype="pdf")
    else:
        doc = fitz.open(input_path)

    page_hits: Dict[int, List[Hit]] = {}
    for h in hits:
        page_hits.setdefault(h.page, []).append(h)

    for page_num, hlist in page_hits.items():
        page = doc[page_num]
        for h in hlist:
            bbox = getattr(h, "bbox", None)
            if not bbox:
                continue
            rect = fitz.Rect(bbox)

            if preview_mode:
                # Colored highlight preview
                color = CATEGORY_COLORS.get(h.category, "#FF0000")
                rgb = _hex_to_rgb_floats(color)
                page.draw_rect(rect, color=rgb, fill=(*rgb, 0.25), width=0.8)
            else:
                # True redaction (black or white box)
                fill_color = (0, 0, 0) if black_box else (1, 1, 1)
                red = page.add_redact_annot(rect, fill=fill_color)
                if red:
                    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    out_bytes = doc.write()
    doc.close()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(out_bytes)

    return out_bytes
