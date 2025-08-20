import re
import fitz  # PyMuPDF
from typing import List, Dict

class Hit:
    def __init__(self, text: str, page: int, rect, category: str):
        self.text = text
        self.page = page
        self.rect = rect
        self.category = category

CATEGORY_LABELS = {
    "email": "Email Addresses",
    "phone": "Phone Numbers",
    "ssn": "Social Security Numbers",
    "credit_card": "Credit Card Numbers",
    "drivers_license": "Driver’s Licenses",
    "names": "Names (Biological / Company)",
}

CATEGORY_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}", re.I),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "drivers_license": re.compile(r"\b[A-Z]{1}\d{6,8}\b"),
    "names": re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"),
}

def extract_text_and_positions(input_path: str, params: Dict[str, bool], custom_phrases: List[str]) -> List[Hit]:
    hits: List[Hit] = []
    doc = fitz.open(input_path)

    for page_num, page in enumerate(doc):
        blocks = page.get_text("blocks")
        for block in blocks:
            text = block[4]
            rect = block[:4]
            for cat, enabled in params.items():
                if enabled:
                    for match in CATEGORY_PATTERNS[cat].finditer(text):
                        hits.append(Hit(match.group(), page_num, rect, cat))

            for phrase in custom_phrases:
                if phrase in text:
                    hits.append(Hit(phrase, page_num, rect, "custom"))

    doc.close()
    return hits
