import fitz  # PyMuPDF

def redact_pdf_with_positions(input_pdf, positions, output_pdf, preview_mode=False):
    """
    Redacts a PDF at the given positions.
    If preview_mode=True, uses category colors for boxes (non-destructive).
    If False, applies black redactions permanently.
    """
    doc = fitz.open(input_pdf)

    for page_num, rect, category in positions:
        page = doc[page_num]
        if preview_mode:
            # Draw a semi-transparent rectangle in category color
            category_colors = {
                "email": (0.1, 0.6, 0.9),
                "phone": (0.9, 0.6, 0.1),
                "credit_card": (0.8, 0.1, 0.1),
                "ssn": (0.5, 0.1, 0.8),
                "drivers_license": (0.1, 0.8, 0.3),
                "date": (0.6, 0.3, 0.1),
                "address": (0.1, 0.3, 0.6),
                "name": (0.6, 0.6, 0.1),
                "ip_address": (0.5, 0.2, 0.2),
                "bank_account": (0.2, 0.5, 0.5),
                "vin": (0.5, 0.5, 0.2),
            }
            rgb = category_colors.get(category, (0, 0, 0))
            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=rgb, fill=rgb, fill_opacity=0.4)
            shape.commit()
        else:
            page.add_redact_annot(rect, fill=(0, 0, 0))
    if not preview_mode:
        doc.apply_redactions()

    doc.save(output_pdf)
    doc.close()
