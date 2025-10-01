import re
from typing import List, Optional, Tuple, Dict
import fitz  # PyMuPDF

# -----------------------
# Data class
# -----------------------
class Hit:
    def __init__(self, text: str, page: int, category: str, bbox: Optional[Tuple[float, float, float, float]] = None):
        self.text = text
        self.page = page
        self.category = category
        self.bbox = bbox  # (x0, y0, x1, y1)

# -----------------------
# Regex Patterns
# -----------------------
CATEGORY_PATTERNS: Dict[str, str] = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b(?:\+?1\s?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "drivers_license": r"\b[A-Z0-9]{5,15}\b",
    "date": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    "address": r"\d{1,5}\s\w+(\s\w+)*\s(?:Street|St|Ave|Avenue|Blvd|Rd|Road|Ln|Lane)\b",
    "name": r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b",
    "ip_address": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
    "bank_account": r"\b\d{9,18}\b",
    "vin": r"\b[A-HJ-NPR-Z0-9]{17}\b",
}

# -----------------------
# Display Labels
# -----------------------
CATEGORY_LABELS: Dict[str, str] = {
    "email": "Email Addresses",
    "phone": "Phone Numbers",
    "credit_card": "Credit Card Numbers",
    "ssn": "Social Security Numbers",
    "drivers_license": "Driver's Licenses",
    "date": "Dates",
    "address": "Addresses",
    "name": "Names",
    "ip_address": "IP Addresses",
    "bank_account": "Bank Account Numbers",
    "vin": "VIN Numbers",
    "custom": "Custom Phrases",
}

# -----------------------
# Helpers
# -----------------------
def _page_hits_from_text(page, page_text: str, categories: List[str], custom_phrase: Optional[str] = None) -> List[Hit]:
    hits: List[Hit] = []

    # Normal categories
    for cat, pattern in CATEGORY_PATTERNS.items():
        if cat not in categories:
            continue
        for m in re.finditer(pattern, page_text, flags=re.IGNORECASE):
            text = m.group(0)
            rects = page.search_for(text)
            if rects:
                for rect in rects:
                    hits.append(Hit(text=text, page=page.number, category=cat, bbox=(rect.x0, rect.y0, rect.x1, rect.y1)))

    # Custom phrase
    if custom_phrase:
        for m in re.finditer(re.escape(custom_phrase), page_text, flags=re.IGNORECASE):
            text = m.group(0)
            rects = page.search_for(text)
            if rects:
                for rect in rects:
                    hits.append(Hit(text=text, page=page.number, category="custom", bbox=(rect.x0, rect.y0, rect.x1, rect.y1)))

    return hits

# -----------------------
# Main Extractor
# -----------------------
def extract_text_and_positions(file_bytes: bytes, ext: str, categories: List[str], custom_phrase: Optional[str] = None) -> List[Hit]:
    hits: List[Hit] = []

    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            text = page.get_text()
            hits.extend(_page_hits_from_text(page, text, categories, custom_phrase))
        doc.close()

    # (Future: add DOCX, TXT support if needed)

    return hits
