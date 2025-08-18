import fitz  # PyMuPDF

def redact_pdf_with_positions(input_pdf, positions, output_pdf, preview=False):
    """
    Apply redactions (black fill if final, transparent color if preview).
    """
    doc = fitz.open(input_pdf)

    for page_num, rect, color, category in positions:
        page = doc[page_num]
        if preview:
            # Transparent color overlay for preview
            r, g, b = fitz.utils.getColor(color)
            page.draw_rect(rect, color=(r, g, b), fill=(r, g, b), overlay=True, width=0.5, fill_opacity=0.3)
        else:
            # Solid black box for final redaction
            page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()

    doc.save(output_pdf)
    doc.close()
