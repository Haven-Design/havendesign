import re
import io
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
import docx  # python-docx

# -----------------------
# Data model
# -----------------------
class Hit:
    def __init__(
        self,
        page: int,
        rects: Optional[List[Tuple[float, float, float, float]]],
        text: str,
        category: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ):
        self.page = page
        self.rects = rects or []
        self.text = text
        self.category = category
        self.start = start
        self.end = end

# -----------------------
# Categories, labels, colors
# -----------------------
CATEGORY_LABELS = {
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
    "routing_number": "US Routing Numbers",
    "iban": "IBANs",
    "vin": "VIN Numbers",
    "custom": "Custom Phrases",
}

CATEGORY_COLORS = {
    "email": "#EF4444",           # red
    "phone": "#22C55E",           # green
    "credit_card": "#3B82F6",     # blue
    "ssn": "#EAB308",             # yellow
    "drivers_license": "#F97316", # orange
    "date": "#A855F7",            # purple
    "address": "#10B981",         # teal-ish
    "name": "#8B5CF6",            # violet
    "ip_address": "#60A5FA",      # light blue
    "bank_account": "#F59E0B",    # amber
    "routing_number": "#0EA5E9",  # sky
    "iban": "#84CC16",            # lime
    "vin": "#A16207",             # brown
    "custom": "#9CA3AF",          # gray
}

# -----------------------
# Regex patterns
# -----------------------
CATEGORY_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    # Credit card candidates: 13–19 digits with spaces/dashes; Luhn check applied afterward
    "credit_card": r"\b(?:\d[ -]?){13,19}\b",
    # Generic US driver's license (loose, state-specific formats vary)
    "drivers_license": r"\b[A-Z0-9]{5,12}\b",
    # Dates:  MM/DD/YYYY, YYYY-MM-DD, or Month Day, Year
    "date": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
            r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s*\d{4}"
            r"|\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))\b",
    # Simple US street address
    "address": r"\b\d{1,6}\s+[0-9A-Za-z.'\-]+\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Ln|Lane|Dr|Drive|Ct|Court|Pl|Place|Terrace|Way)\b\.?",
    # Capitalized First Last (optional middle)
    "name": r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b",
    # IPv4 and IPv6
    "ip_address": r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}\b"
                  r"|\b(?:[A-Fa-f0-9]{0,4}:){2,7}[A-Fa-f0-9]{0,4}\b",
    # Bank account: 8–14 digits after common keywords (case-insensitive handled via flags)
    "bank_account": r"(?:account|acct|checking|savings)\D{0,20}(\d{8,14})",
    # US ABA routing: exactly 9 digits
    "routing_number": r"\b\d{9}\b",
    # IBAN
    "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
    # VIN: 17 chars excluding I, O, Q
    "vin": r"\b(?!.*[IOQ])[A-HJ-NPR-Z0-9]{17}\b",
}

# -----------------------
# Validators
# -----------------------
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

def aba_routing_valid(num: str) -> bool:
    if not re.fullmatch(r"\d{9}", num):
        return False
    digits = [int(c) for c in num]
    checksum = (
        3 * (digits[0] + digits[3] + digits[6])
        + 7 * (digits[1] + digits[4] + digits[7])
        + 1 * (digits[2] + digits[5] + digits[8])
    ) % 10
    return checksum == 0

# -----------------------
# Core extractor (PDF page-level helper)
# -----------------------
def _page_hits_from_text(page, page_text: str, params, custom_phrase: Optional[str]) -> List[Hit]:
    hits: List[Hit] = []

    def add_match(cat: str, m: re.Match):
        txt = m.group(0)
        start, end = m.start(), m.end()
        rects = []
        try:
            found = page.search_for(txt, quads=False)
            for r in found:
                rects.append((r.x0, r.y0, r.x1, r.y1))
        except Exception:
            rects = []
        hits.append(Hit(page.number, rects, txt, cat, start, end))

    for cat, pattern in CATEGORY_PATTERNS.items():
        if not params.get(cat, False):
            continue
        flags = re.IGNORECASE if cat in ("address", "iban", "bank_account") else 0
        for m in re.finditer(pattern, page_text, flags=flags):
            if cat == "credit_card" and not luhn_valid(m.group(0)):
                continue
            if cat == "routing_number" and not aba_routing_valid(m.group(0)):
                continue
            add_match(cat, m)

    if custom_phrase:
        for m in re.finditer(re.escape(custom_phrase), page_text, flags=re.IGNORECASE):
            add_match("custom", m)

    # Remove overlapping (by character spans) to reduce duplicate category collisions
    priority = [
        "credit_card", "ssn", "routing_number", "iban", "bank_account",
        "drivers_license", "ip_address", "date", "address",
        "vin", "email", "phone", "name", "custom"
    ]
    hits.sort(key=lambda h: (h.start if h.start is not None else -1,
                             priority.index(h.category) if h.category in priority else 999))

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
# Public API
# -----------------------
def extract_text_and_positions(file_bytes, ext, params, custom_phrase: Optional[str]) -> List[Hit]:
    hits: List[Hit] = []

    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            text = page.get_text()
            hits.extend(_page_hits_from_text(page, text, params, custom_phrase))
        doc.close()

    elif ext == ".docx":
        d = docx.Document(io.BytesIO(file_bytes))
        combined = "\n".join(p.text for p in d.paragraphs)
        for cat, pattern in CATEGORY_PATTERNS.items():
            if not params.get(cat, False):
                continue
            flags = re.IGNORECASE if cat in ("address", "iban", "bank_account") else 0
            for m in re.finditer(pattern, combined, flags=flags):
                if cat == "credit_card" and not luhn_valid(m.group(0)):
                    continue
                if cat == "routing_number" and not aba_routing_valid(m.group(0)):
                    continue
                hits.append(Hit(0, [], m.group(0), cat))
        if custom_phrase:
            for m in re.finditer(re.escape(custom_phrase), combined, flags=re.IGNORECASE):
                hits.append(Hit(0, [], m.group(0), "custom"))

    elif ext == ".txt":
        text = file_bytes.decode("utf-8", errors="ignore")
        for cat, pattern in CATEGORY_PATTERNS.items():
            if not params.get(cat, False):
                continue
            flags = re.IGNORECASE if cat in ("address", "iban", "bank_account") else 0
            for m in re.finditer(pattern, text, flags=flags):
                if cat == "credit_card" and not luhn_valid(m.group(0)):
                    continue
                if cat == "routing_number" and not aba_routing_valid(m.group(0)):
                    continue
                hits.append(Hit(0, [], m.group(0), cat))
        if custom_phrase:
            for m in re.finditer(re.escape(custom_phrase), text, flags=re.IGNORECASE):
                hits.append(Hit(0, [], m.group(0), "custom"))

    return hits
