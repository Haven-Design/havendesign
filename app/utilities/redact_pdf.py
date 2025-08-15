import fitz  # PyMuPDF
from .extract_text import CATEGORY_COLORS

def redact_pdf_with_positions(input_pdf, positions, output_pdf):
    """
    Redacts specific positions in the PDF with category-specific colors.
    positions: list of (page_num, rect, category)
    """
    doc = fitz.open(input_pdf)

    for page_num, rect, category in positions:
        page = doc[page_num]
        color = tuple(int(CATEGORY_COLORS.get(category, "#FF0000").lstrip("#")[i:i+2], 16) / 255
                      for i in (0, 2, 4))
        page.draw_rect(rect, color=color, fill=color, overlay=True)

    doc.save(output_pdf)
    doc.close()
