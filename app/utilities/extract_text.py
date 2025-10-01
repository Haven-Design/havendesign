"""
extract_text.py

Produces Hit objects for each detected sensitive phrase in a PDF/DOCX/TXT.
For PDFs, each Hit includes a merged bbox (x0,y0,x1,y1) to use for precise redaction.
The extractor accepts a list of categories (strings) and an optional custom phrase.
"""

import re
from typing import List, Optional, Tuple, Dict
import fitz  # PyMuPDF
import io

# -----------------------
# Hit model
# -----------------------
class Hit:
    def __init__(
        self,
        text: str,
        page: int,
        category: str,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ):
        self.text = text
        self.page = page
        self.category = category
        self.bbox = bbox  # (x0, y0, x1, y1)
        self.start = start
        self.end = end

# -----------------------
# Patterns, labels, colors
# -----------------------
CATEGORY_PATTERNS: Dict[str, str] = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b",
    "credit_card": r"\b(?:\d[ -]?){13,19}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "drivers_license": r"\b[A-Z0-9]{5,15}\b",
    "date": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s*\d{4})\b",
    "address": r"\b\d{1,6}\s+[0-9A-Za-z.'\-]+\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Ln|Lane|Dr|Drive|Ct|Court|Pl|Place|Terrace|Way)\b\.?",
    "name": r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b",
    "ip_address": r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}\b",
    "bank_account": r"(?:account|acct|checking|savings)\D{0,20}(\d{8,14})",
    "vin": r"\b(?!.*[IOQ])[A-HJ-NPR-Z0-9]{17}\b",
}

CATEGORY_LABELS: Dict[str, str] = {
    "email": "Email Addresses",
    "phone": "Phone Numbers",
    "credit_card": "Credit Cards",
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

# Soft modern palette (used in UI + preview)
CATEGORY_COLORS: Dict[str, str] = {
    "email": "#EF4444",         # red
    "phone": "#10B981",         # emerald
    "credit_card": "#3B82F6",   # blue
    "ssn": "#F59E0B",           # amber
    "drivers_license": "#6366F1", # indigo
    "date": "#8B5CF6",          # violet
    "address": "#14B8A6",       # teal
    "name": "#EC4899",          # pink
    "ip_address": "#0EA5E9",    # sky
    "bank_account": "#F97316",  # orange
    "vin": "#6B7280",           # gray
    "custom": "#94A3B8",        # slate
}

# -----------------------
# Helpers
# -----------------------
def _merge_rects(rects: List[fitz.Rect]) -> Optional[Tuple[float, float, float, float]]:
    """Given a list of fitz.Rect, return a bounding rectangle (x0,y0,x1,y1)."""
    if not rects:
        return None
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    x1 = max(r.x1 for r in rects)
    y1 = max(r.y1 for r in rects)
    return (x0, y0, x1, y1)

# Luhn validator for credit cards (post-filter)
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

# -----------------------
# Page-level extraction
# -----------------------
def _page_hits_from_text(page, page_text: str, categories: List[str], custom_phrase: Optional[str]) -> List[Hit]:
    hits: List[Hit] = []

    for cat, pattern in CATEGORY_PATTERNS.items():
        if cat not in categories:
            continue
        flags = re.IGNORECASE if cat in ("address", "bank_account") else 0
        for m in re.finditer(pattern, page_text, flags=flags):
            # post-filters
            match_text = m.group(0)
            if cat == "credit_card" and not luhn_valid(match_text):
                continue
            # find visual rects for this matched string and merge into one bbox
            try:
                rects = page.search_for(match_text, quads=False) or []
            except Exception:
                rects = []
            bbox = _merge_rects(rects)
            hits.append(Hit(text=match_text, page=page.number, category=cat, bbox=bbox, start=m.start(), end=m.end()))

    # custom phrase (if provided)
    if custom_phrase:
        for m in re.finditer(re.escape(custom_phrase), page_text, flags=re.IGNORECASE):
            match_text = m.group(0)
            try:
                rects = page.search_for(match_text, quads=False) or []
            except Exception:
                rects = []
            bbox = _merge_rects(rects)
            hits.append(Hit(text=match_text, page=page.number, category="custom", bbox=bbox, start=m.start(), end=m.end()))

    # remove overlaps by span and prefer higher-priority categories
    priority = ["credit_card", "ssn", "bank_account", "drivers_license", "email", "phone", "ip_address", "date", "address", "name", "vin", "custom"]
    hits.sort(key=lambda h: (h.start if h.start is not None else -1, priority.index(h.category) if h.category in priority else 999))

    filtered: List[Hit] = []
    last_spans: List[Tuple[int, int]] = []
    for h in hits:
        if h.start is None:
            filtered.append(h)
            continue
        overlap = any(not (h.end <= s or h.start >= e) for s, e in last_spans)
        if not overlap:
            filtered.append(h)
            last_spans.append((h.start, h.end))
    return filtered

# -----------------------
# Public extractor
# -----------------------
def extract_text_and_positions(file_bytes: bytes, ext: str, categories: List[str], custom_phrase: Optional[str] = None) -> List[Hit]:
    """
    ext should be '.pdf' or '.docx' or '.txt' (currently PDF robustly supported).
    categories is a list of category keys (e.g. ['email','phone','credit_card']) or may include a custom string.
    """
    hits: List[Hit] = []

    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            page_text = page.get_text()
            hits.extend(_page_hits_from_text(page, page_text, categories, custom_phrase))
        doc.close()
    elif ext == ".docx" or ext == ".txt":
        # Basic text-mode matching (no bboxes). We'll still return Hit objects with bbox=None
        try:
            import docx
        except Exception:
            docx = None
        if ext == ".docx" and docx:
            d = docx.Document(io.BytesIO(file_bytes))
            combined = "\n".join(p.text for p in d.paragraphs)
            for cat, pattern in CATEGORY_PATTERNS.items():
                if cat not in categories:
                    continue
                flags = re.IGNORECASE if cat in ("address", "bank_account") else 0
                for m in re.finditer(pattern, combined, flags=flags):
                    match_text = m.group(0)
                    if cat == "credit_card" and not luhn_valid(match_text):
                        continue
                    hits.append(Hit(text=match_text, page=0, category=cat, bbox=None, start=m.start(), end=m.end()))
            if custom_phrase:
                for m in re.finditer(re.escape(custom_phrase), combined, flags=re.IGNORECASE):
                    hits.append(Hit(text=m.group(0), page=0, category="custom", bbox=None, start=m.start(), end=m.end()))
        else:
            # txt
            txt = file_bytes.decode("utf-8", errors="ignore")
            for cat, pattern in CATEGORY_PATTERNS.items():
                if cat not in categories:
                    continue
                flags = re.IGNORECASE if cat in ("address", "bank_account") else 0
                for m in re.finditer(pattern, txt, flags=flags):
                    match_text = m.group(0)
                    if cat == "credit_card" and not luhn_valid(match_text):
                        continue
                    hits.append(Hit(text=match_text, page=0, category=cat, bbox=None, start=m.start(), end=m.end()))
            if custom_phrase:
                for m in re.finditer(re.escape(custom_phrase), txt, flags=re.IGNORECASE):
                    hits.append(Hit(text=m.group(0), page=0, category="custom", bbox=None, start=m.start(), end=m.end()))

    return hits
