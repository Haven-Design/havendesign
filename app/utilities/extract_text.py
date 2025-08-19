import re
import fitz
from typing import List, NamedTuple

class Hit(NamedTuple):
    id: int
    text: str
    category: str
    page: int
    rect: fitz.Rect

CATEGORY_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
    "credit_card": r"\b(?!\d{4}\s*\1{3})(?:\d{4}[-\s]?){3,4}\d{3,4}\b",
    "ssn": r"\b(?!000|666|9\d\d)(\d{3})-(?!00)(\d{2})-(?!0000)(\d{4})\b",
    "drivers_license": r"\b([A-Z]\d{7}|\d{8}|[A-Z0-9]{5,9})\b",
    "date": r"\b(?:0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])[-/](\d{2}|\d{4})\b",
    "address": r"\b\d{1,5}\s(?:[A-Z][a-z]*\s?){1,4}(Street|St|Ave|Avenue|Rd|Road|Blvd|Lane|Ln|Dr|Drive|Court|Ct)\b",
    "name": r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b",
    "ip_address": r"\b((25[0-5]|2[0-4]\d|[01]?\d?\d)(\.|$)){4}\b",
    "bank_account": r"\b\d{9,18}\b",
    "vin": r"\b[A-HJ-NPR-Z0-9]{17}\b",
}

CATEGORY_PRIORITY = [
    "email",
    "ssn",
    "credit_card",
    "bank_account",
    "phone",
    "drivers_license",
    "vin",
    "ip_address",
    "date",
    "address",
    "name",
    "custom",
]

def extract_text_and_positions(pdf_path: str, selected_params: List[str]) -> List[Hit]:
    doc = fitz.open(pdf_path)
    hits: List[Hit] = []
    seen_texts = set()

    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    span_text = span["text"]
                    for category in CATEGORY_PRIORITY:
                        if category not in selected_params:
                            continue
                        if category in CATEGORY_PATTERNS:
                            for match in re.finditer(CATEGORY_PATTERNS[category], span_text):
                                match_text = match.group()
                                key = (match_text, page_num)
                                if key in seen_texts:
                                    continue
                                seen_texts.add(key)
                                rect = fitz.Rect(span["bbox"])
                                hits.append(Hit(len(hits), match_text, category, page_num, rect))
                                break
                        else:
                            if category.lower() in span_text.lower():
                                key = (category, page_num)
                                if key in seen_texts:
                                    continue
                                seen_texts.add(key)
                                rect = fitz.Rect(span["bbox"])
                                hits.append(Hit(len(hits), category, "custom", page_num, rect))
                                break
    doc.close()
    return hits
