import fitz  # PyMuPDF

def redact_pdf(input_path, areas, output_path):
    doc = fitz.open(input_path)

    for page_num, page_areas in areas.items():
        page = doc[int(page_num)]

        for area in page_areas:
            rect = fitz.Rect(area['x0'], area['y0'], area['x1'], area['y1'])
            page.add_redact_annot(rect, fill=(0, 0, 0))

        page.apply_redactions()

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()