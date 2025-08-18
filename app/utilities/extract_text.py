import re
import fitz
from typing import List, TypedDict

# TypedDict for a single hit with duplicate count
class Hit(TypedDict):
    text: str
    category: str
    page: int
    rect: fitz.Rect
    count: int  # number of times this text occurs globally

CATEGORY_PATTERNS: dict[str, tuple[str, str]] = {
    "email": (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "#FF6B6B"),
    "phone": (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "#6BCB77"),
    "credit_card": (r"\b(?:\d[ -]*?){13,16}\b", "#4D96FF"),
    "ssn": (r"\b\d{3}-\d{2}-\d{4}\b", "#FFD93D"),
    "drivers_license": (r"\b[A-Z0-9]{1,9}\b", "#FF8C42"),
    "date": (r"\b(?:\d{1,2}[/.-]){2}\d{2,4}\b", "#9D4EDD"),
    "address": (r"\d{1,5}\s\w+(\s\w+)*", "#00C49A"),
    "name": (r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b", "#FF1493"),
    "ip_address": (r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "#1E90FF"),
    "bank_account": (r"\b\d{9,18}\b", "#FF4500"),
    "vin": (r"\b[A-HJ-NPR-Z0-9]{17}\b", "#008B8B"),
}

CATEGORY_PRIORITY: list[str] = [
    "email", "ssn", "credit_card", "bank_account", "phone",
    "drivers_license", "vin", "ip_address", "date",
    "address", "name", "custom"
]

def extract_text_and_positions(pdf_path: str, selected_params: list[str]) -> list[Hit]:
    """
    Extract text and positions from PDF, deduplicated globally across pages, with counts.
    """
    doc = fitz.open(pdf_path)
    hits: list[Hit] = []
    seen_texts: dict[str, int] = {}  # key: lowercased text, value: count

    for page_num, page in enumerate(doc):
        text_instances = page.get_text("dict").get("blocks", [])
        for block in text_instances:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    span_text: str = span["text"]

                    for category in CATEGORY_PRIORITY:
                        if category not in selected_params:
                            continue

                        if category in CATEGORY_PATTERNS:
                            pattern, _color = CATEGORY_PATTERNS[category]
                            for match in re.finditer(pattern, span_text):
                                match_text: str = match.group()
                                key: str = match_text.lower()
                                count: int = seen_texts.get(key, 0) + 1
