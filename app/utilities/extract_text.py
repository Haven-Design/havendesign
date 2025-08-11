import fitz  # PyMuPDF

def extract_phrases_with_bboxes(pdf_bytes):
    """
    Returns a dict:
    {
        page_num: [
            {"text": phrase_text, "rect": fitz.Rect},
            ...
        ],
        ...
    }
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    phrases_by_page = {}

    for page_num, page in enumerate(doc):
        phrases = []
        blocks = page.get_text("blocks")  # Returns list of (x0,y0,x1,y1,"text", ...)
        for b in blocks:
            rect = fitz.Rect(b[:4])
            text = b[4].strip()
            if text:
                phrases.append({"text": text, "rect": rect})
        if phrases:
            phrases_by_page[page_num] = phrases

    return phrases_by_page
