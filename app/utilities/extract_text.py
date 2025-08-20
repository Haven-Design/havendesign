import re
import fitz
from typing import List, Dict

CATEGORY_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?\d{1,2}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "drivers_license": re.compile(r"\b[A-Z]{1,2}\d{6,8}\b"),
    "date": re.compile(r"\b(?:\d{1,2}[/-]){2}\d{2,4}\b"),
    "address": re.compile(r"\b\d{1,5}\s+[A-Za-z0-9\s]+(?:Street|St|Ave|Road|Rd|Blvd|Ln|Drive|Dr)\b"),
    "name": re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+|[A-Z][a-zA-Z]+(?:, Inc| LLC)?)\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "bank_account": re.compile(r"\b\d{8,17}\b"),
    "vin": re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"),
}

CATEGORY_PRIORITY = {
    "credit_card": 1,
    "ssn": 1,
    "drivers_license": 1,
    "bank_account": 1,
    "vin": 1,
    "phone": 2,
    "email": 2,
    "ip_address": 2,
    "date": 3,
    "address": 3,
    "name": 4,
    "custom": 5,
}

class Hit:
    def __init__(self, text, page, rect, category):
        self.text = text
        self.page = page
        self.rect = rect
        self.category = category

def extract_text_and_positions(path: str, params: List[str]) -> List[Hit]:
    doc = fitz.open(path)
    hits: List[Hit] = []

    for page_num, page in enumerate(doc):
        blocks = page.get_text("blocks")
        for b in blocks:
            if len(b) < 5:
                continue
            text = b[4]
            rect = b[:4]
            for param in params:
                if param in CATEGORY_PATTERNS:
                    for m in CATEGORY_PATTERNS[param].finditer(text):
                        match_text = m.group()
                        hits.append(Hit(match_text, page_num, rect, param))
                else:
                    if param.lower() in text.lower():
                        hits.append(Hit(param, page_num, rect, "custom"))
    doc.close()
    unique_hits = {}
    for h in hits:
        key = (h.page, h.text, h.rect)
        if key not in unique_hits or CATEGORY_PRIORITY.get(h.category, 99) < CATEGORY_PRIORITY.get(unique_hits[key].category, 99):
            unique_hits[key] = h
    return list(unique_hits.values())
