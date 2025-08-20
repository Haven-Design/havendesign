import re
import fitz
from typing import List

class Hit:
    def __init__(self, page: int, text: str, rect, category: str):
        self.page = page
        self.text = text
        self.rect = rect
        self.category = category

CATEGORY_LABELS = {
    "email": "Emails",
    "phone": "Phone Numbers",
    "ssn": "SSNs",
    "credit_card": "Credit Cards",
    "drivers_license": "Driver's License",
    "name": "Names",
    "custom": "Custom Phrases"
}

CATEGORY_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "drivers_license": r"\b[A-Z]\d{6,8}\b",
    "name": r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b"
}

def extract_text_and_positions(input_path, params, custom_phrase="") -> List[Hit]:
    hits: List[Hit] = []
    doc = fitz.open(input_path)

    for page_num, page in enumerate(doc):
        blocks = page.get_text("blocks")
        for b in blocks:
            text = b[4]
            rect = fitz.Rect(b[:4])

            for category, pattern in CATEGORY_PATTERNS.items():
                if params.get(category, False):
                    for m in re.finditer(pattern, text):
                        hits.append(Hit(page_num, m.group(), rect, category))

            if custom_phrase and params.get("custom", False):
                if custom_phrase in text:
                    hits.append(Hit(page_num, custom_phrase, rect, "custom"))

    return hits
