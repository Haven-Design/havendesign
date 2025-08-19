import re
import fitz
import docx
import csv
from typing import List, NamedTuple

class Hit(NamedTuple):
    id: int
    text: str
    category: str
    page: int
    rect: tuple | None

CATEGORY_PATTERNS = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "phone": r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "drivers_license": r"\b[A-Z0-9]{5,12}\b",
    "date": r"\b(?:\d{1,2}[/.-]){2}\d{2,4}\b",
    "address": r"\d{1,5}\s\w+(\s\w+)*",
    "name": r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b",
    "ip_address": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
    "bank_account": r"\b\d{9,18}\b",
    "vin": r"\b[A-HJ-NPR-Z0-9]{17}\b",
}

CATEGORY_PRIORITY = [
    "email","ssn","credit_card","bank_account","phone",
    "drivers_license","vin","ip_address","date","address","name","custom",
]

def extract_text_and_positions(file_path: str, selected_params: List[str]) -> List[Hit]:
    hits: List[Hit] = []
    ext = file_path.lower().split(".")[-1]
    seen = set()

    if ext == "pdf":
        doc = fitz.open(file_path)
        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_text = span["text"]
                        for category in CATEGORY_PRIORITY:
                            if category not in selected_params:
                                continue
                            if category in CATEGORY_PATTERNS:
                                for m in re.finditer(CATEGORY_PATTERNS[category], span_text):
                                    key = (m.group(), page_num)
                                    if key in seen: continue
                                    seen.add(key)
                                    rect = tuple(span["bbox"])
                                    hits.append(Hit(len(hits), m.group(), category, page_num, rect))
                                    break
                            else:
                                if category.lower() in span_text.lower():
                                    key = (category, page_num)
                                    if key in seen: continue
                                    seen.add(key)
                                    rect = tuple(span["bbox"])
                                    hits.append(Hit(len(hits), category, "custom", page_num, rect))
                                    break
        doc.close()

    elif ext == "docx":
        doc = docx.Document(file_path)
        for i, para in enumerate(doc.paragraphs):
            for category in CATEGORY_PRIORITY:
                if category not in selected_params: continue
                text = para.text
                if category in CATEGORY_PATTERNS:
                    for m in re.finditer(CATEGORY_PATTERNS[category], text):
                        key = (m.group(), i)
                        if key in seen: continue
                        seen.add(key)
                        hits.append(Hit(len(hits), m.group(), category, i, None))
                else:
                    if category.lower() in text.lower():
                        key = (category, i)
                        if key in seen: continue
                        seen.add(key)
                        hits.append(Hit(len(hits), category, "custom", i, None))

    elif ext in ("txt","csv"):
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f) if ext == "csv" else enumerate(f.readlines())
            for i, row in enumerate(reader):
                line = " ".join(row) if ext == "csv" else row
                for category in CATEGORY_PRIORITY:
                    if category not in selected_params: continue
                    if category in CATEGORY_PATTERNS:
                        for m in re.finditer(CATEGORY_PATTERNS[category], line):
                            key = (m.group(), i)
                            if key in seen: continue
                            seen.add(key)
                            hits.append(Hit(len(hits), m.group(), category, i, None))
                    else:
                        if category.lower() in line.lower():
                            key = (category, i)
                            if key in seen: continue
                            seen.add(key)
                            hits.append(Hit(len(hits), category, "custom", i, None))
    return hits
