import re
import fitz
from typing import List, Tuple, NamedTuple

# Hit data structure
class Hit(NamedTuple):
    id: int
    text: str
    category: str
    page: int
    rect: fitz.Rect

CATEGORY_PATTERNS = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "phone": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "drivers_license": r"\b[A-Z0-9]{1,9}\b",
    "date": r"\b(?:\d{1,2}[/.-]){2}\d{2,4}\b",
    "address": r"\d{1,5}\s\w+(\s\w+)*",
    "name": r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b",
    "ip_address": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
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
                            pattern = CATEGORY_PATTERNS[category]
                            for match in re.finditer(pattern, span_text):
                                match_text = match.group()
                                key = (match_text, page_num)
                                if key in seen_texts:
                                    continue
                                seen_texts.add(key)
                                rect = fitz.Rect(span["bbox"])
                                hit_id = len(hits)
                                hits.append(Hit(hit_id, match_text, category, page_num, rect))
                                break
                        else:  # custom phrase
                            if category.lower() in span_text.lower():
                                key = (category, page_num)
                                if key in seen_texts:
                                    continue
                                seen_texts.add(key)
                                rect = fitz.Rect(span["bbox"])
                                hit_id = len(hits)
                                hits.append(Hit(hit_id, category, "custom", page_num, rect))
                                break

    doc.close()
    return hits
