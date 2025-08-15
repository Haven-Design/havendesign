import re
import fitz  # PyMuPDF

# Color mapping for categories (same as main.py & redact_pdf.py)
CATEGORY_COLORS = {
    "email": "#1A99E5",
    "phone": "#E5A21A",
    "credit_card": "#CC1A1A",
    "ssn": "#801ACC",
    "drivers_license": "#1ACC4D",
    "date": "#995333",
    "address": "#1A4D99",
    "name": "#99991A",
    "ip_address": "#804040",
    "bank_account": "#339999",
    "vin": "#808033",
}

# Patterns for detection
PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\d{3}\)|\d{3})(?:\s*|-|\.)\d{3}(?:\s*|-|\.)\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "drivers_license": r"\b[A-Z0-9]{5,12}\b",
    "date": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    "address": r"\b\d{1,5}\s\w+(\s\w+)*\b",
    "name": r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b",
    "ip_address": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
    "bank_account": r"\b\d{8,17}\b",
    "vin": r"\b[A-HJ-NPR-Z0-9]{17}\b",
}

def extract_text_and_positions(pdf_path, selected_params):
    doc = fitz.open(pdf_path)
    found_phrases = []
    positions = []

    for page_num, page in enumerate(doc):
        text_instances = []
        words = page.get_text("words")  # list of tuples (x0, y0, x1, y1, word, block_no, line_no, word_no)

        for category in selected_params:
            pattern = None
            if category in PATTERNS:
                pattern = PATTERNS[category]
            elif isinstance(category, str):  # Custom phrase
                pattern = re.escape(category)

            if pattern:
                regex = re.compile(pattern, re.IGNORECASE)
                for w in words:
                    if regex.fullmatch(w[4]):
                        rect = fitz.Rect(w[0], w[1], w[2], w[3])
                        positions.append((page_num, rect, category if category in CATEGORY_COLORS else "custom"))
                        found_phrases.append((w[4], category if category in CATEGORY_COLORS else "custom"))

    doc.close()
    return found_phrases, positions
