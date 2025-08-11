# app/utilities/extract_text.py
import fitz  # PyMuPDF

def extract_text_from_pdf(pdf_bytes):
    """
    Returns a list where each element corresponds to a page.
    Each page is a list of word tuples returned by page.get_text('words'):
      (x0, y0, x1, y1, word, block_no, line_no, word_no)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_words = []
    for page in doc:
        words = page.get_text("words")  # words as tuples
        pages_words.append(words)
    doc.close()
    return pages_words
