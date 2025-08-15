import re
import uuid
from typing import Dict, List, Tuple

import fitz  # PyMuPDF

# -----------------------------
# ADA-safe bright palette (category -> hex)
# -----------------------------
CATEGORY_COLORS_HEX: Dict[str, str] = {
    "email":           "#005AB5",  # strong blue
    "phone":           "#DC322F",  # strong red
    "credit_card":     "#B58900",  # strong amber
    "ssn":             "#D33682",  # magenta
    "drivers_license": "#268BD2",  # bright sky
    "date":            "#2AA198",  # teal
    "address":         "#6C71C4",  # violet
    "name":            "#859900",  # olive
    "ip_address":      "#CB4B16",  # orange
    "bank_account":    "#00736E",  # deep teal
    "routing_number":  "#A4225B",  # raspberry
    "vin":             "#8F3B1B",  # brownish
    "passport":        "#146B3A",  # green
}

# Convert hex to RGB tuple [0..1]
def _hex_to_rgb01(h: str) -> Tuple[float, float, float]:
    h = h.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b)

CATEGORY_COLORS_RGB: Dict[str, Tuple[float, float, float]] = {
    k: _hex_to_rgb01(v) for k, v in CATEGORY_COLORS_HEX.items()
}

# -----------------------------
# Regex patterns
# -----------------------------
CATEGORY_PATTERNS: Dict[str, str] = {
    "email":           r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    "phone":           r"(?x)(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)",
    "credit_card":     r"(?x)(?<!\d)(?:\d[ -]*?){13,19}(?!\d)",
    "ssn":             r"(?x)(?<!\d)(?!000|666|9\d\d)\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}(?!\d)",
    "drivers_license": r"(?i)\b(?:DL|Driver'?s?\s+License|Lic\.?)\s*[:#\-]?\s*[A-Z0-9\-]{5,15}\b",
    "date":            r"(?ix)\b(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b",
    "address":         r"(?i)\b\d{1,6}\s+[A-Z0-9'\.\-]+\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Ln|Lane|Dr|Drive)\b(?:[,\s]+[A-Za-z\.\s]+){0,3}\b",
    "name":            r"(?x)\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b",  # simple full-name heuristic
    "ip_address":      r"(?ix)(?:\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b|\b[0-9A-F:]{2,}\b)",
    "bank_account":    r"(?x)(?<!\d)\d{10,17}(?!\d)",   # broadened, but below we exclude if recognized as CC
    "routing_number":  r"(?x)(?<!\d)\d{9}(?!\d)",
    "vin":             r"(?i)\b(?![IOQ])[A-HJ-NPR-Z0-9]{17}\b",
    "passport":        r"(?i)\b(?:Passport|PPT)\s*[:#\-]?\s*[A-Z0-9]{6,9}\b",
}

# Prioritized to avoid duplicates; earlier wins
CATEGORY_PRIORITY: List[str] = [
    "credit_card",
    "ssn",
    "phone",
    "bank_account",
    "routing_number",
    "vin",
    "ip_address",
    "email",
    "passport",
    "date",
    "address",
    "name",
    "drivers_license",
]

# -----------------------------
# Core extraction
# -----------------------------
def extract_text_and_positions(
    input_pdf_path: str,
    selected_categories: List[str],
    custom_patterns: List[str] = None,
) -> List[dict]:
    """
    Returns a list of dicts:
      { id, page, text, rect: (x0,y0,x1,y1), category }
    - Exclusivity enforced via CATEGORY_PRIORITY.
    - For each regex match we search the literal text in the page to grab precise rectangles.
    """
    custom_patterns = custom_patterns or []

    doc = fitz.open(input_pdf_path)
    results: List[dict] = []

    # Prepare compiled regexes per category (only for those selected)
    compiled: Dict[str, re.Pattern] = {}
    for cat, pat in CATEGORY_PATTERNS.items():
        if cat in selected_categories:
            compiled[cat] = re.compile(pat, re.IGNORECASE)

    compiled_custom = [re.compile(p) for p in custom_patterns]

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        # Track used spans to avoid duplicates across categories
        used_spans: List[Tuple[int, int]] = []

        def span_free(start: int, end: int) -> bool:
            for s, e in used_spans:
                if not (end <= s or start >= e):
                    return False
            return True

        # Category matches by priority
        for cat in CATEGORY_PRIORITY:
            if cat not in compiled:
                continue
            regex = compiled[cat]
            for m in regex.finditer(text):
                start, end = m.span()
                raw = m.group(0)
                # Heuristic: avoid 4-digit repeats as CC / phone if already matched elsewhere
                # (priority order already helps)
                if not span_free(start, end):
                    continue

                quads = page.search_for(raw)
                if not quads:
                    continue
                for r in quads:
                    results.append({
                        "id": str(uuid.uuid4()),
                        "page": page_num,
                        "text": raw,
                        "rect": (float(r.x0), float(r.y0), float(r.x1), float(r.y1)),
                        "category": cat,
                    })
                    used_spans.append((start, end))
                    break  # link only first visual occurrence for that text span

        # Custom patterns (always lowest priority, but still exclusive)
        for creg in compiled_custom:
            for m in creg.finditer(text):
                start, end = m.span()
                raw = m.group(0)
                if not span_free(start, end):
                    continue
                quads = page.search_for(raw)
                if not quads:
                    continue
                r = quads[0]
                results.append({
                    "id": str(uuid.uuid4()),
                    "page": page_num,
                    "text": raw,
                    "rect": (float(r.x0), float(r.y0), float(r.x1), float(r.y1)),
                    "category": "custom",
                })
                used_spans.append((start, end))

    doc.close()
    return results
