import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Pattern
import fitz  # PyMuPDF
from docx import Document
import io


@dataclass
class Hit:
    page: int
    text: str
    category: str
    start: Optional[int] = None   # for DOCX/TXT
    end: Optional[int] = None     # for DOCX/TXT
    bbox: Optional[tuple] = None  # (x0, y0, x1, y1) for PDF hits


# -----------------------------
# Category regex patterns
# -----------------------------
CATEGORY_PATTERNS: Dict[str, str] = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "phone": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "drivers_license": r"\b[A-Z0-9]{5,12}\b",
    "date": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    "address": r"\d{1,5}\s\w+(\s\w+)*",
    "name": r"\b[A-Z][a-z]+ [A-Z][a-z]+\b",
    "ip_address": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
    "bank_account": r"\b\d{6,17}\b",
    "vin": r"\b[A-HJ-NPR-Z0-9]{17}\b",
}

CATEGORY_COLORS: Dict[str, str] = {
    "email": "#e74c3c",
    "phone": "#2ecc71",
    "credit_card": "#3498db",
    "ssn": "#f1c40f",
    "drivers_license": "#e67e22",
    "date": "#9b59b6",
    "address": "#1abc9c",
    "name": "#8e44ad",
    "ip_address": "#2980b9",
    "bank_account": "#d35400",
    "vin": "#7f8c8d",
    "custom": "#95a5a6",
}

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


# -----------------------------
# Helpers
# -----------------------------
def luhn_valid(number: str) -> bool:
    """Luhn algorithm for credit card validation"""
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _page_hits_from_text(page, text: str, params: Dict[str, bool], custom_phrase: Optional[str] = None) -> List[Hit]:
    hits: List[Hit] = []

    for cat, pattern in CATEGORY_PATTERNS.items():
        if not params.get(cat, False):
            continue

        flags = re.IGNORECASE if cat in ("address", "iban", "bank_account") else 0
        for m in re.finditer(pattern, text, flags=flags):
            if cat == "credit_card" and not luhn_valid(m.group(0)):
                continue

            rects = page.search_for(m.group(0)) if page else []
            if rects:
                for r in rects:
                    hits.append(Hit(page=page.number, text=m.group(0), category=cat, bbox=(r.x0, r.y0, r.x1, r.y1)))
            else:
                # fallback with no bbox (for TXT/DOCX or missed PDF matches)
                hits.append(Hit(page=page.number, text=m.group(0), category=cat))

    if custom_phrase and params.get("custom", False):
        for m in re.finditer(re.escape(custom_phrase), text, flags=re.IGNORECASE):
            rects = page.search_for(m.group(0)) if page else []
            if rects:
                for r in rects:
                    hits.append(Hit(page=page.number, text=m.group(0), category="custom", bbox=(r.x0, r.y0, r.x1, r.y1)))
            else:
                hits.append(Hit(page=page.number, text=m.group(0), category="custom"))

    return hits


# -----------------------------
# Master Extractor
# -----------------------------
def extract_text_and_positions(file_bytes: bytes, ext: str, params: Dict[str, bool], custom_phrase: Optional[str] = None) -> List[Hit]:
    hits: List[Hit] = []

    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            text = page.get_text()
            hits.extend(_page_hits_from_text(page, text, params, custom_phrase))
        doc.close()

    elif ext == ".docx":
        doc = Document(io.BytesIO(file_bytes))
        for pi, para in enumerate(doc.paragraphs):
            for cat, pattern in CATEGORY_PATTERNS.items():
                if not params.get(cat, False):
                    continue
                for m in re.finditer(pattern, para.text):
                    hits.append(Hit(page=pi, text=m.group(0), category=cat, start=m.start(), end=m.end()))
        if custom_phrase and params.get("custom", False):
            for pi, para in enumerate(doc.paragraphs):
                for m in re.finditer(re.escape(custom_phrase), para.text, flags=re.IGNORECASE):
                    hits.append(Hit(page=pi, text=m.group(0), category="custom", start=m.start(), end=m.end()))

    elif ext == ".txt":
        text = file_bytes.decode("utf-8", errors="ignore")
        for cat, pattern in CATEGORY_PATTERNS.items():
            if not params.get(cat, False):
                continue
            for m in re.finditer(pattern, text):
                hits.append(Hit(page=0, text=m.group(0), category=cat, start=m.start(), end=m.end()))
        if custom_phrase and params.get("custom", False):
            for m in re.finditer(re.escape(custom_phrase), text, flags=re.IGNORECASE):
                hits.append(Hit(page=0, text=m.group(0), category="custom", start=m.start(), end=m.end()))

    return hits
