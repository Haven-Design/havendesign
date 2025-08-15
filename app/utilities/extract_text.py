import re
import fitz  # PyMuPDF

# Accessible, bright (WCAG-oriented contrast when used as strokes)
CATEGORY_DEFS = {
    "email":   {"label": "Email addresses",           "color": (0.00, 0.45, 0.74), "color_hex": "#0072C6",
                "help": "name@domain.com"},
    "phone":   {"label": "Phone numbers",             "color": (0.85, 0.33, 0.10), "color_hex": "#D95319",
                "help": "US formats, intl variants"},
    "credit":  {"label": "Credit cards",              "color": (0.47, 0.67, 0.19), "color_hex": "#77AC30",
                "help": "16-digit, common separators"},
    "ssn":     {"label": "SSN",                       "color": (0.93, 0.69, 0.13), "color_hex": "#F0AD4E",
                "help": "###-##-####"},
    "dl":      {"label": "Driver’s licenses",         "color": (0.49, 0.18, 0.56), "color_hex": "#7E3794",
                "help": "Generic US patterns"},
    "date":    {"label": "Dates",                     "color": (0.30, 0.75, 0.93), "color_hex": "#4DCFE0",
                "help": "MM/DD/YYYY, YYYY-MM-DD, etc."},
    "name":    {"label": "Names",                     "color": (0.64, 0.08, 0.18), "color_hex": "#A5142E",
                "help": "Consecutive capitalized words (heuristic)"},
    "address": {"label": "Addresses",                 "color": (0.00, 0.50, 0.00), "color_hex": "#008000",
                "help": "Street number + road word"},
    "ipv4":    {"label": "IPv4 / IPv6",               "color": (0.20, 0.20, 0.20), "color_hex": "#333333",
                "help": "Network addresses"},
    "bank":    {"label": "Bank numbers",              "color": (0.00, 0.60, 0.52), "color_hex": "#009985",
                "help": "Routing + account formats"},
    "passport":{"label": "Passports",                 "color": (0.85, 0.20, 0.53), "color_hex": "#D93687",
                "help": "Generic US/EU formats"},
    "mrn":     {"label": "Medical Record Numbers",    "color": (0.55, 0.55, 0.00), "color_hex": "#8C8C00",
                "help": "US MRN-like"},
    "vin":     {"label": "Vehicle VIN",               "color": (0.00, 0.60, 0.90), "color_hex": "#0099E6",
                "help": "17-char VIN"},
}

# You can choose a subset to pre-check—but we start with none checked in UI.
DEFAULT_CATEGORY_KEYS = list(CATEGORY_DEFS.keys())

# Regex library (case-insensitive where appropriate)
REGEXES = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){1}\d{3}[-.\s]?\d{4}\b"),
    "credit": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "dl": re.compile(r"\b[A-Z]{1}\d{7,12}\b|\b\d{8,12}\b"),  # very generic
    "date": re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[12]\d{3}-\d{1,2}-\d{1,2})\b"),
    "name": re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b"),
    "address": re.compile(
        r"\b\d{1,6}\s+(?:[A-Za-z0-9]+\s+){0,4}(Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b",
        re.I
    ),
    "ipv4": re.compile(
        r"\b(?:(?:\d{1,3}\.){3}\d{1,3})\b|\b(?:[A-F0-9]{0,4}:){2,7}[A-F0-9]{0,4}\b",
        re.I
    ),
    "bank": re.compile(r"\b\d{9}\b|\b\d{4,17}\b"),
    "passport": re.compile(r"\b[A-Z]\d{7}\b|\b\d{9}\b"),
    "mrn": re.compile(r"\b(?:MRN[:\s]*)?\d{6,10}\b", re.I),
    "vin": re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"),
}


def _union_rect(rects):
    """Return a single rect that covers all rects (min/max bounds)."""
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    x1 = max(r.x1 for r in rects)
    y1 = max(r.y1 for r in rects)
    return fitz.Rect(x0, y0, x1, y1)


def _find_phrase_rects_on_page(page, phrase):
    """
    Robust geometry: find word boxes that together match `phrase` (case-insensitive).
    Returns a list of rects (one per occurrence).
    """
    words = page.get_text("words")  # list of (x0, y0, x1, y1, word, block, line, word_no)
    if not words:
        return []

    # Build normalized token list
    toks = [(fitz.Rect(w[0], w[1], w[2], w[3]), w[4]) for w in words]
    lower_toks = [(rect, txt.lower()) for rect, txt in toks]

    target_tokens = phrase.strip().split()
    if not target_tokens:
        return []
    target_tokens_lower = [t.lower() for t in target_tokens]

    results = []
    i = 0
    while i < len(lower_toks):
        # try to match starting at i
        if lower_toks[i][1] == target_tokens_lower[0]:
            j = i
            k = 0
            acc_rects = []
            while j < len(lower_toks) and k < len(target_tokens_lower):
                # Allow simple punctuation equivalence: strip basic punctuation from token compare
                tok_clean = re.sub(r"[^\w@.-]", "", lower_toks[j][1])
                tgt_clean = re.sub(r"[^\w@.-]", "", target_tokens_lower[k])
                if tok_clean == tgt_clean:
                    acc_rects.append(lower_toks[j][0])
                    j += 1
                    k += 1
                else:
                    break
            if k == len(target_tokens_lower):
                results.append(_union_rect(acc_rects))
                i = j
                continue
        i += 1

    # Fallback: if no multi-token path found, try search_for the raw phrase
    if not results:
        for r in page.search_for(phrase, flags=fitz.TEXT_DEHYPHENATE):
            results.append(r)

    return results


def detect_matches_in_pdf(pdf_bytes: bytes, selected_keys, custom_regex_text: str):
    """
    Return a list of items with geometry:
      { id, page, phrase, rects, category }
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    items = []
    uid = 0

    # Compile custom regex lines if provided
    custom_res = []
    if custom_regex_text and custom_regex_text.strip():
        for line in custom_regex_text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                custom_res.append(re.compile(line, re.I))
            except re.error:
                # Skip bad regex; in a production app you might surface this nicely
                continue

    for page_index in range(len(doc)):
        page = doc[page_index]
        text = page.get_text("text")

        # Built-ins
        for key in selected_keys:
            rx = REGEXES.get(key)
            if not rx:
                continue
            for m in rx.finditer(text):
                phrase = m.group(0)
                rects = _find_phrase_rects_on_page(page, phrase)
                if not rects:
                    continue
                items.append({
                    "id": f"i{uid}",
                    "page": page_index,
                    "phrase": phrase,
                    "rects": [fitz.Rect(r) for r in rects],
                    "category": key
                })
                uid += 1

        # Customs
        for crx in custom_res:
            for m in crx.finditer(text):
                phrase = m.group(0)
                rects = _find_phrase_rects_on_page(page, phrase)
                if not rects:
                    continue
                items.append({
                    "id": f"i{uid}",
                    "page": page_index,
                    "phrase": phrase,
                    "rects": [fitz.Rect(r) for r in rects],
                    "category": "custom",
                })
                uid += 1

    doc.close()
    return items


def build_summary_counts(items):
    counts = {}
    for it in items:
        counts[it["category"]] = counts.get(it["category"], 0) + 1
    return counts
