import re
import fitz  # PyMuPDF

# Patterns for sensitive data
patterns = {
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "Credit Card": r"\b(?:\d[ -]*?){13,16}\b",
    "Phone": r"\b\d{3}[-.\s]??\d{3}[-.\s]??\d{4}\b",
    "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "ZIP": r"\b\d{5}(?:-\d{4})?\b",
}

def process_pdf(file_path):
    """Extract all unique phrases matching sensitive patterns."""
    doc = fitz.open(file_path)
    found_phrases = set()

    for page in doc:
        text = page.get_text()
        for label, pattern in patterns.items():
            matches = re.findall(pattern, text)
            for match in matches:
                found_phrases.add(match)
    doc.close()
    return sorted(list(found_phrases))

def redact_pdf_phrases(file_path, phrases, output_path):
    """Redact all specified phrases from PDF."""
    doc = fitz.open(file_path)
    for page in doc:
        for phrase in phrases:
            areas = page.search_for(phrase)
            for area in areas:
                page.add_redact_annot(area, fill=(0, 0, 0))
        page.apply_redactions()
    doc.save(output_path)
    doc.close()
