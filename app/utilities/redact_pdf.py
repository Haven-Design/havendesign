import re
import fitz  # PyMuPDF

# Detection patterns
PATTERNS = {
    "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "Phone": r"\b(?:\+?1\s*[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "Zip": r"\b\d{5}(?:-\d{4})?\b",
    "Credit Card": r"\b(?:\d[ -]*?){13,16}\b",
    "Date": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s*\d{4})\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b"
}

def detect_sensitive_info(pdf_path):
    doc = fitz.open(pdf_path)
    detections = []
    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        for name, pattern in PATTERNS.items():
            matches = re.findall(pattern, text)
            for match in matches:
                detections.append((page_num, match, name))
    doc.close()
    return detections

def redact_pdf(pdf_path, selections, output_path):
    doc = fitz.open(pdf_path)
    for page_num, match, _ in selections:
        page = doc[page_num]
        areas = page.search_for(match)
        for rect in areas:
            page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()
    doc.save(output_path)
    doc.close()
