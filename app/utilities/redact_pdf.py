from typing import Dict, List, Tuple
import fitz  # PyMuPDF


def _rect_tuple_to_rect(rt: Tuple[float, float, float, float]) -> fitz.Rect:
    return fitz.Rect(rt[0], rt[1], rt[2], rt[3])


def build_preview_pdf(
    input_pdf_path: str,
    items: List[dict],
    out_pdf_path: str,
    color_map: Dict[str, Tuple[float, float, float]],
):
    """
    Build a *non-destructive* preview PDF by drawing colored rectangles
    where redactions would be applied. Uses square annotations so viewers
    show them reliably; does *not* redact content.
    """
    doc = fitz.open(input_pdf_path)
    # group by page
    per_page: Dict[int, List[dict]] = {}
    for it in items:
        per_page.setdefault(it["page"], []).append(it)

    for pno, lst in per_page.items():
        page = doc[pno]
        for it in lst:
            rect = _rect_tuple_to_rect(it["rect"])
            color = color_map.get(it["category"], (0.2, 0.2, 0.2))
            annot = page.add_rect_annot(rect)  # square annotation
            # set border color + thin border
            annot.set_border(width=1)
            annot.set_colors(stroke=color, fill=None)
            annot.update()

    doc.save(out_pdf_path)
    doc.close()


def redact_pdf_with_positions(
    input_pdf_path: str,
    items: List[dict],
    tmp_out_path: str,
):
    """
    Apply true redactions:
      - add_redact_annot(rect, fill=(0,0,0)) for selected items
      - IMPORTANT: call page.apply_redactions() per page (PyMuPDF 1.26.x)
    """
    doc = fitz.open(input_pdf_path)

    per_page: Dict[int, List[Tuple[float, float, float, float]]] = {}
    for it in items:
        per_page.setdefault(it["page"], []).append(it["rect"])

    for pno, rects in per_page.items():
        page = doc[pno]
        for rt in rects:
            rect = _rect_tuple_to_rect(rt)
            page.add_redact_annot(rect, fill=(0, 0, 0))
        # Apply redactions for this page (older PyMuPDF requires per-page call)
        page.apply_redactions()

    doc.save(tmp_out_path)
    doc.close()
