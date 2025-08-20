import io
import re
from dataclasses import dataclass, replace
from typing import List, Dict, Tuple, Optional

import fitz  # PyMuPDF
from docx import Document  # python-docx

# Accessible, distinct colors per category (used for preview + list dots)
CATEGORY_COLORS: Dict[str, str] = {
    "email": "#1363DF",           # blue
    "phone": "#0CA678",           # teal/green
    "credit_card": "#E11D48",     # red-rose
    "ssn": "#F59E0B",             # amber
    "drivers_license": "#7C3AED", # violet
    "date": "#0891B2",            # cyan
    "address": "#10B981",         # emerald
    "name": "#EF4444",            # red
    "ip_address": "#6366F1",      # indigo
    "bank_account": "#F97316",    # orange
    "vin": "#0EA5E9",             # sky blue
    "custom": "#6B7280",          # gray
}

# Human labels
CATEGORY_LABELS: Dict[str, str] = {
    "email": "Email Addresses",
    "phone": "Phone Numbers",
    "credit_card": "Credit Card Numbers",
    "ssn": "Social Security Numbers",
    "drivers_license": "Driver's Licenses",
    "date": "Dates",
    "address": "Addresses",
    "name": "Names (people & companies)",
    "ip_address": "IP Addresses",
    "bank_account": "Bank Account Numbers",
    "vin": "VIN Numbers",
}

# Tighter, fewer false-positives
CATEGORY_PATTERNS: Dict[str, str] = {
    "email": r"\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?|\d{3}[-.\s])\d{3}[-.\s]\d{4}\b",
    "credit_card": r"\b(?:\d[ -]?){13,16}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "drivers_license": r"\b[A-Z0-9]{5,12}\b",
    "date": r"\b(?:\d{1,2}[/-]){2}\d{2,4}\b",
    "address": r"\b\d{1,6}\s+[A-Za-z0-9.'-]+\s+[A-Za-z0-9.'-]+(?:\s+(?:Ave|Avenue|St|Street|Rd|Road|Blvd|Lane|Ln|Dr|Drive|Ct|Court|Pl|Place|Way))?\b",
    "name": r"\b(?:[A-Z][a-z]+(?:\s[A-Z][a-z]+)+(?:\s(?:LLC|Inc|Corp|Co\.?|Ltd\.?))?)\b",
    "ip_address": r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b",
    "bank_account": r"\b\d{9,18}\b",
    "vin": r"\b[A-HJ-NPR-Z0-9]{17}\b",
}

CATEGORY_PRIORITY: List[str] = [
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

@dataclass(frozen=True)
class Hit:
    id: int
    text: str
    category: str
    page: int
    rect: Tuple[float, float, float, float]

    def _replace(self, **kwargs):
        return replace(self, **kwargs)

# ---------- Helper: PDF extraction ----------
def _extract_pdf_hits(pdf_bytes: bytes, selected: List[str], custom_phrase: Optional[str]) -> List[Hit]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    hits: List[Hit] = []
    hit_id = 0

    # We’ll scan at span-level (fast, fairly accurate).
    for pno, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            lines = b.get("lines", [])
            for line in lines:
                for span in line.get("spans", []):
                    stext = span.get("text", "")
                    if not stext.strip():
                        continue
                    bbox = span.get("bbox", None)
                    if not bbox:
                        continue
                    rect = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))

                    # categories in priority order
                    for cat in CATEGORY_PRIORITY:
                        if cat == "custom":
                            if custom_phrase:
                                if custom_phrase.lower() in stext.lower():
                                    hits.append(Hit(hit_id, custom_phrase, "custom", pno, rect))
                                    hit_id += 1
                            continue
                        if cat not in selected:
                            continue
                        pattern = CATEGORY_PATTERNS.get(cat)
                        if not pattern:
                            continue
                        if re.search(pattern, stext):
                            # Basic gating to reduce duplicates across categories
                            # Prefer higher-priority category; skip if a higher-priority already matched the same text
                            hits.append(Hit(hit_id, stext.strip(), cat, pno, rect))
                            hit_id += 1
                            break

    doc.close()
    # Dedup same (page, rect) keeping first (higher priority) found
    seen = set()
    uniq: List[Hit] = []
    for h in hits:
        k = (h.page, round(h.rect[0], 2), round(h.rect[1], 2), round(h.rect[2], 2), round(h.rect[3], 2))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(h)
    # re-id
    for i in range(len(uniq)):
        uniq[i] = uniq[i]._replace(id=i)
    return uniq

# ---------- Helper: DOCX/TXT extraction ----------
def _extract_text_hits(text: str, selected: List[str], custom_phrase: Optional[str]) -> List[Hit]:
    hits: List[Hit] = []
    hit_id = 0
    # For non-PDF, we can’t get coordinates; we’ll use page=-1 and rect=(0,0,0,0)
    for cat in CATEGORY_PRIORITY:
        if cat == "custom":
            if custom_phrase and (custom_phrase.lower() in text.lower()):
                hits.append(Hit(hit_id, custom_phrase, "custom", -1, (0, 0, 0, 0)))
                hit_id += 1
            continue
        if cat not in selected:
            continue
        pattern = CATEGORY_PATTERNS.get(cat)
        if not pattern:
            continue
        if re.search(pattern, text):
            hits.append(Hit(hit_id, f"[{CATEGORY_LABELS.get(cat, cat)} match]", cat, -1, (0, 0, 0, 0)))
            hit_id += 1
    return hits

def _read_docx_bytes(docx_bytes: bytes) -> str:
    f = io.BytesIO(docx_bytes)
    doc = Document(f)
    parts = []
    for p in doc.paragraphs:
        parts.append(p.text)
    return "\n".join(parts)

# ---------- Public: extract from file ----------
def extract_hits_from_file(
    file_bytes: bytes,
    ext: str,
    selected_categories: List[str],
    custom_phrase: Optional[str] = None
) -> List[Hit]:
    ext = (ext or ".pdf").lower()
    if ext == ".pdf":
        return _extract_pdf_hits(file_bytes, selected_categories, custom_phrase)

    if ext == ".docx":
        text = _read_docx_bytes(file_bytes)
        return _extract_text_hits(text, selected_categories, custom_phrase)

    if ext == ".txt":
        text = file_bytes.decode("utf-8", errors="ignore")
        return _extract_text_hits(text, selected_categories, custom_phrase)

    # default: treat as text
    text = file_bytes.decode("utf-8", errors="ignore")
    return _extract_text_hits(text, selected_categories, custom_phrase)
