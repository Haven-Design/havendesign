import fitz  # PyMuPDF

def redact_pdf_with_positions(input_pdf, positions, output_pdf):
    doc = fitz.open(input_pdf)

    for page_num, rect in positions:
        page = doc[page_num]
        page.add_redact_annot(rect, fill=(1, 0, 0))  # Red box (bright red, ADA friendly)
    doc.apply_redactions()

    doc.save(output_pdf)
    doc.close()
