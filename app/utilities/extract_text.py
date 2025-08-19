import io
import re
from typing import List, NamedTuple, Optional, Dict, Tuple

import fitz  # PyMuPDF
from docx import Document
from openpyxl import load_workbook

# unified color map + labels
CATEGORY_COLORS: Dict[str, str] = {
    "email": "#FF6B6B",
    "phone": "#2ECC71",
    "credit_card": "#4D96FF",
    "ssn": "#FFD93D",
    "drivers_license": "#FF8C42",
    "date": "#9D4EDD",
    "address": "#00C49A",
    "name": "#FF1493",
    "ip_address": "#1E90FF",
    "bank_account": "#FF4500",
    "vin": "#008B8B",
    "custom": "#888888",
}
CATEGORY_LABELS: Dict[str, str] = {
    "email": "Email Addresses",
    "phone": "Phone Numbers",
    "credit_card": "Credit Cards",
    "ssn": "SSNs",
    "drivers_license": "Driver's Licenses",
    "date": "Dates",
    "address": "Addresses",
    "name": "Names",
    "ip_address": "IP Addresses",
    "bank_account": "Bank Accounts",
    "vin": "VIN Numbers",
    "custom": "Custom Phrases",
}

# tighter regex + anchors; will still not be perfect but reduces collisions
CATEGORY_PATTERNS: Dict[str, re.Pattern] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)[0-9]{3}[-.\s]?[0-9]{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    # DL varies; keep broad but not every short token
    "drivers_license": re.compile(r"\b[A-Z0-9]{5,12}\b"),
    "date": re.compile(r"\b(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\b"),
    "address": re.compile(r"\b\d{1,6}\s+[A-Za-z0-9'.\-]+\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct)\b", re.IGNORECASE),
    "name": re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "bank_account": re.compile(r"\b\d{9,18}\b"),
    # VIN excludes I, O, Q
    "vin": re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"),
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

class Hit(NamedTuple):
    id: int
    text: str
    category: str
    page: int              # -1 for non-pdf linear contexts
    rect: Optional[Tuple[float, float, float, float]]  # (x0,y0,x1,y1) for PDF; None otherwise
    context: Optional[Tuple[str, int, int]]            # for non-PDF: (scope_id, start, end)

def _disambiguate_category(token: str) -> Optional[str]:
    for cat in CATEGORY_PRIORITY:
        if cat == "custom":
            continue
        pat = CATEGORY_PATTERNS.get(cat)
        if pat and pat.fullmatch(token):
            return cat
    return None

def _extract_pdf(memory: bytes, selected: List[str]) -> List[Hit]:
    doc = fitz.open(stream=memory, filetype="pdf")
    hits: List[Hit] = []
    hid = 0
    custom_terms = [s for s in selected if s not in CATEGORY_PATTERNS]

    for pno, page in enumerate(doc):
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    stext = span.get("text", "")
                    if not stext.strip():
                        continue
                    for cat in CATEGORY_PRIORITY:
                        if cat not in selected and cat != "custom":
                            continue
                        if cat in CATEGORY_PATTERNS:
                            for m in CATEGORY_PATTERNS[cat].finditer(stext):
                                token = m.group(0)
                                # disambiguation: only accept if highest-priority match
                                winner = _disambiguate_category(token) or cat
                                if winner != cat:
                                    continue
                                rect = tuple(span["bbox"])
                                hits.append(Hit(hid, token, cat, pno, rect, None))
                                hid += 1
                        else:  # custom phrases
                            for term in custom_terms:
                                idx = stext.lower().find(term.lower())
                                if idx != -1:
                                    rect = tuple(span["bbox"])
                                    hits.append(Hit(hid, term, "custom", pno, rect, None))
                                    hid += 1
    doc.close()
    return hits

def _extract_docx(memory: bytes, selected: List[str]) -> List[Hit]:
    doc = Document(io.BytesIO(memory))
    hits: List[Hit] = []
    hid = 0
    custom_terms = [s for s in selected if s not in CATEGORY_PATTERNS]

    for pi, para in enumerate(doc.paragraphs):
        text = para.text or ""
        # build non-overlapping matches based on priority
        for cat in CATEGORY_PRIORITY:
            if cat not in selected and cat != "custom":
                continue
            if cat in CATEGORY_PATTERNS:
                for m in CATEGORY_PATTERNS[cat].finditer(text):
                    token = m.group(0)
                    winner = _disambiguate_category(token) or cat
                    if winner != cat:
                        continue
                    hits.append(Hit(hid, token, cat, -1, None, (f"p{pi}", m.start(), m.end())))
                    hid += 1
            else:
                for term in custom_terms:
                    start = text.lower().find(term.lower())
                    if start != -1:
                        hits.append(Hit(hid, term, "custom", -1, None, (f"p{pi}", start, start+len(term))))
                        hid += 1
    return hits

def _extract_txt(memory: bytes, selected: List[str]) -> List[Hit]:
    s = memory.decode("utf-8", errors="ignore")
    lines = s.splitlines()
    hits: List[Hit] = []
    hid = 0
    custom_terms = [x for x in selected if x not in CATEGORY_PATTERNS]
    for li, line in enumerate(lines):
        for cat in CATEGORY_PRIORITY:
            if cat not in selected and cat != "custom":
                continue
            if cat in CATEGORY_PATTERNS:
                for m in CATEGORY_PATTERNS[cat].finditer(line):
                    token = m.group(0)
                    winner = _disambiguate_category(token) or cat
                    if winner != cat:
                        continue
                    hits.append(Hit(hid, token, cat, -1, None, (f"line{li}", m.start(), m.end())))
                    hid += 1
            else:
                for term in custom_terms:
                    start = line.lower().find(term.lower())
                    if start != -1:
                        hits.append(Hit(hid, term, "custom", -1, None, (f"line{li}", start, start+len(term))))
                        hid += 1
    return hits

def _extract_xlsx(memory: bytes, selected: List[str]) -> List[Hit]:
    wb = load_workbook(io.BytesIO(memory), data_only=True)
    hits: List[Hit] = []
    hid = 0
    custom_terms = [x for x in selected if x not in CATEGORY_PATTERNS]

    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if cell is None:
                    continue
                val = str(cell)
                for cat in CATEGORY_PRIORITY:
                    if cat not in selected and cat != "custom":
                        continue
                    if cat in CATEGORY_PATTERNS:
                        for m in CATEGORY_PATTERNS[cat].finditer(val):
                            token = m.group(0)
                            winner = _disambiguate_category(token) or cat
                            if winner != cat:
                                continue
                            hits.append(Hit(hid, token, cat, -1, None, (ws.title, m.start(), m.end())))
                            hid += 1
                    else:
                        for term in custom_terms:
                            start = val.lower().find(term.lower())
                            if start != -1:
                                hits.append(Hit(hid, term, "custom", -1, None, (ws.title, start, start+len(term))))
                                hid += 1
    return hits

def extract_hits_for_file(file_bytes: bytes, ext: str, selected_params: List[str]) -> List[Hit]:
    ext = ext.lower()
    if ext == ".pdf":
        return _extract_pdf(file_bytes, selected_params)
    if ext == ".docx":
        return _extract_docx(file_bytes, selected_params)
    if ext == ".txt":
        return _extract_txt(file_bytes, selected_params)
    if ext == ".xlsx":
        return _extract_xlsx(file_bytes, selected_params)
    return []

# -----------------------
# basic HTML preview (non-PDF)
# -----------------------
def build_html_preview(file_bytes: bytes, ext: str, chosen_hits: List[Hit]) -> str:
    color_by_cat = CATEGORY_COLORS
    if ext == ".txt":
        s = file_bytes.decode("utf-8", errors="ignore")
        # naive highlight: wrap each hit occurrence
        out = s
        # Sort by descending start to avoid shifting
        positions = []
        for h in chosen_hits:
            if h.context:
                positions.append((h.context[0], h.context[1], h.context[2], h))
        positions.sort(key=lambda t: t[2], reverse=True)

        # linearize per line tag; simply replace in string (best-effort demo)
        for _, start, end, h in positions:
            color = color_by_cat.get(h.category, "#999999")
            seg = out[start:end]
            out = out[:start] + f'<span style="background:{color}">{seg}</span>' + out[end:]
        return "<pre style='white-space:pre-wrap;word-wrap:break-word;'>" + out + "</pre>"

    elif ext == ".docx":
        # Show paragraph text with inline highlights (read-only preview)
        doc = Document(io.BytesIO(file_bytes))
        html_parts: List[str] = []
        for pi, para in enumerate(doc.paragraphs):
            text = para.text or ""
            marks = [(h.context[1], h.context[2], h) for h in chosen_hits if h.context and h.context[0] == f"p{pi}"]
            if not marks:
                html_parts.append(f"<div>{text}</div>")
                continue
            marks.sort(key=lambda x: x[1], reverse=True)
            buf = text
            for start, end, h in marks:
                color = color_by_cat.get(h.category, "#999999")
                seg = buf[start:end]
                buf = buf[:start] + f'<span style="background:{color}">{seg}</span>' + buf[end:]
            html_parts.append(f"<div>{buf}</div>")
        return "<br/>".join(html_parts)

    elif ext == ".xlsx":
        # Minimal sheet preview: just list hits with colored chips
        lines = []
        for h in chosen_hits:
            color = color_by_cat.get(h.category, "#999999")
            scope = h.context[0] if h.context else ""
            lines.append(f"<div><span style='background:{color};padding:2px 6px;border-radius:6px;margin-right:6px;'>{h.category}</span>{h.text} <em>({scope})</em></div>")
        if not lines:
            return "<div>No matches selected.</div>"
        return "<div>" + "".join(lines) + "</div>"

    return "<div>Preview not available.</div>"
