import fitz  # PyMuPDF

def extract_text_from_pdf(pdf_bytes):
    """Return a list of page texts."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [page.get_text("text") for page in doc]
