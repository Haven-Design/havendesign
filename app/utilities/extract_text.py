import re
from typing import List, Optional, Dict, Tuple
import fitz  # PyMuPDF
from docx import Document

# -------------------------------
# Data structure for hits
# -------------------------------
class Hit:
    def __init__(self, page: int, text: str, category: str, bbox: Optional[Tuple[float, float, float, float]] = None):
        self.page = page
        self.text = text
        self.category = category
        self.bbox = bbox

# -------------------------------
# Regex patterns for categories
# -------------------------------
CATEGORY_PATTERNS: Dict[str, str] = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+?\d{1,2}\s?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "drivers_license": r"\b[A-Z0-9]{5,12}\b",
    "date": r"\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b",
    "address": r"\b\d{1,5}\s+\w+(?:\s\w+){0,3},?\s\w+,?\s\w{2}\s\d{5}\b",
    "name": r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)\b",
    "ip_address": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
    "bank_account": r"\b\d{9,18}\b",
    "vin": r"\b[A-HJ-NPR-Z0-9]{17}\b",
}

# -------------------------------
# Labels (for UI display)
# -------------------------------
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

# -------------------------------
# Helper: luhn check for credit cards
# -------------------------------
def luhn_valid(num_str: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", num_str)]
    checksum = 0
    parity = len(digits) % 2
    for i, digit in enumerate(digits):
        if i % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0

# -------------------------------
# Extract matches from one page
# -------------------------------
def _page_hits_from_text(page, page_text: str, params: List[str], custom_phrase: Optional[str]) -> List[Hit]:
    hits: List[Hit] = []

    for cat, pattern in CATEGORY_PATTERNS.items():
        if cat not in params:
            continue

        flags = re.IGNORECASE if cat in ("address", "iban", "bank_account") else 0
        for m in re.finditer(pattern, page_text, flags=flags):
            if cat == "credit_card" and not luhn_valid(m.group(0)):
                continue

            text = m.group(0)
            bbox = None

            # Try to find bbox for match
            for inst in page.search_for(text):
                bbox = tuple(inst)
                break

            hits.append(Hit(page=page.number, text=text, category=cat, bbox=bbox))

    if custom_phrase:
        for m in re.finditer(re.escape(custom_phrase), page_text, flags=re.IGNORECASE):
            text = m.group(0)
            bbox = None
            for inst in page.search_for(text):
                bbox = tuple(inst)
                break
            hits.append(Hit(page=page.number, text=text, category="custom", bbox=bbox))

    return hits

# -------------------------------
# Main extraction
# -------------------------------
def extract_text_and_positions(file_bytes: bytes, ext: str, params: List[str], custom_phrase: Optional[str] = None) -> List[Hit]:
    hits: List[Hit] = []

    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            text = page.get_text()
            hits.extend(_page_hits_from_text(page, text, params, custom_phrase))
        doc.close()

    elif ext == ".docx":
        doc = Document(file_bytes)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        dummy_page = type("DummyPage", (), {"number": 0, "search_for": lambda self, t: []})()
        hits.extend(_page_hits_from_text(dummy_page, full_text, params, custom_phrase))

    elif ext == ".txt":
        text = file_bytes.decode("utf-8")
        dummy_page = type("DummyPage", (), {"number": 0, "search_for": lambda self, t: []})()
        hits.extend(_page_hits_from_text(dummy_page, text, params, custom_phrase))

    return hits
