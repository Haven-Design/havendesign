"""
extract_text.py (v1.4.2)

Produces Hit objects with text, page, category, start/end spans and merged bbox where possible.
"""

import re
from typing import List, Optional, Tuple, Dict
import fitz  # PyMuPDF
import io

class Hit:
    def __init__(
        self,
        text: str,
        page: int,
        category: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        bbox: Optional[Tuple[float, float, float, float]] = None,
    ):
        self.text = text
        self.page = page
        self.category = category
        self.start = start
        self.end = end
        self.bbox = bbox

    def __repr__(self):
        return f"Hit({self.category!r}, p{self.page+1}, {self.text!r})"

# Patterns
CATEGORY_PATTERNS: Dict[str, str] = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b",
    "credit_card": r"\b(?:\d[ -]?){13,19}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "drivers_license": r"\b[A-Z0-9]{5,15}\b",
    "date": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b",
    "address": r"\b\d{1,6}\s+[0-9A-Za-z.'\-]+\s+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Ln|Lane|Dr|Drive|Ct|Court)\b\.?",
    "name": r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}\b",
    "ip_address": r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}\b",
    "bank_account": r"\b\d{8,18}\b",
    "vin": r"\b(?!.*[IOQ])[A-HJ-NPR-Z0-9]{17}\b",
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

CATEGORY_COLORS: Dict[str, str] = {
    "email": "#EF4444",
    "phone": "#10B981",
    "credit_card": "#3B82F6",
    "ssn": "#F59E0B",
    "drivers_license": "#6366F1",
    "date": "#8B5CF6",
    "address": "#14B8A6",
    "name": "#EC4899",
    "ip_address": "#0EA5E9",
    "bank_account": "#F97316",
    "vin": "#6B7280",
    "custom": "#94A3B8",
}

def _merge_rects(rects: List[fitz.Rect]) -> Optional[Tuple[float, float, float, float]]:
    if not rects:
        return None
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    x1 = max(r.x1 for r in rects)
    y1 = max(r.y1 for r in rects)
    return (x0, y0, x1, y1)

def luhn_valid(num: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", num)]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = (len(digits) - 2) % 2
    for i, d in enumerate(digits[:-1]):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return (checksum + digits[-1]) % 10 == 0

PRIORITY = [
    "credit_card",
    "ssn",
    "bank_account",
    "drivers_license",
    "email",
    "phone",
    "ip_address",
    "date",
    "address",
    "name",
    "vin",
    "custom",
]

def _page_hits_from_text(page, page_text: str, categories: List[str], custom_phrase: Optional[str]) -> List[Hit]:
    hits: List[Hit] = []
    for cat, pattern in CATEGORY_PATTERNS.items():
        if cat not in categories:
            continue
        for m in re.finditer(pattern, page_text, flags=re.IGNORECASE):
            text = m.group(0)
            if cat == "credit_card" and not luhn_valid(text):
                continue
            start, end = m.start(), m.end()
            rects = []
            try:
                rects = page.search_for(text, quads=False) or []
            except Exception:
                rects = []
            bbox = _merge_rects(rects)
            hits.append(Hit(text=text, page=page.number, category=cat, start=start, end=end, bbox=bbox))

    if custom_phrase:
        for m in re.finditer(re.escape(custom_phrase), page_text, flags=re.IGNORECASE):
            text = m.group(0)
            start, end = m.start(), m.end()
            rects = []
            try:
                rects = page.search_for(text, quads=False) or []
            except Exception:
                rects = []
            bbox = _merge_rects(rects)
            hits.append(Hit(text=text, page=page.number, category="custom", start=start, end=end, bbox=bbox))

    # sort & filter overlaps by priority
    hits.sort(key=lambda h: (h.start if h.start is not None else -1, PRIORITY.index(h.category) if h.category in PRIORITY else 999))
    filtered: List[Hit] = []
    occupied: List[Tuple[int, int]] = []
    for h in hits:
        if h.start is None:
            filtered.append(h)
            continue
        overlap = any(not (h.end <= s or h.start >= e) for s, e in occupied)
        if not overlap:
            filtered.append(h)
            occupied.append((h.start, h.end))
    return filtered

def extract_text_and_positions(file_bytes: bytes, ext: str, categories: List[str], custom_phrase: Optional[str] = None) -> List[Hit]:
    hits: List[Hit] = []
    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            page_text = page.get_text()
            hits.extend(_page_hits_from_text(page, page_text, categories, custom_phrase))
        doc.close()
    elif ext == ".docx":
        try:
            import docx
            d = docx.Document(io.BytesIO(file_bytes))
            combined = "\n".join(p.text for p in d.paragraphs)
            class Dummy:
                number = 0
                def search_for(self, s): return []
            hits.extend(_page_hits_from_text(Dummy(), combined, categories, custom_phrase))
        except Exception:
            txt = file_bytes.decode("utf-8", errors="ignore")
            class Dummy:
                number = 0
                def search_for(self, s): return []
            hits.extend(_page_hits_from_text(Dummy(), txt, categories, custom_phrase))
    elif ext == ".txt":
        txt = file_bytes.decode("utf-8", errors="ignore")
        class Dummy:
            number = 0
            def search_for(self, s): return []
        hits.extend(_page_hits_from_text(Dummy(), txt, categories, custom_phrase))
    return hits
