import io
from typing import List
import fitz
from docx import Document
from docx.shared import Pt, RGBColor
from openpyxl import load_workbook, Workbook

from .extract_text import Hit, CATEGORY_COLORS

# ---------- PDF ----------
def build_pdf_preview(file_bytes: bytes, hits: List[Hit]) -> bytes:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for h in hits:
        if h.page < 0 or not h.rect:
            continue
        page = doc[h.page]
        x0, y0, x1, y1 = h.rect
        color_hex = CATEGORY_COLORS.get(h.category, "#999999")
        rgb = _hex_to_rgb(color_hex)
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=rgb, width=2, fill=None)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def save_pdf_blackfill(file_bytes: bytes, hits: List[Hit]) -> bytes:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for h in hits:
        if h.page < 0 or not h.rect:
            continue
        page = doc[h.page]
        page.add_redact_annot(fitz.Rect(*h.rect), fill=(0, 0, 0))
    doc.apply_redactions()
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()

# ---------- DOCX ----------
def save_docx_redacted(file_bytes: bytes, hits: List[Hit]) -> bytes:
    doc = Document(io.BytesIO(file_bytes))
    # build per-paragraph hits
    hit_map = {}  # pkey -> List[(start,end)]
    for h in hits:
        if h.context and str(h.context[0]).startswith("p"):
            hit_map.setdefault(h.context[0], []).extend([(h.context[1], h.context[2])])

    for pi, para in enumerate(doc.paragraphs):
        key = f"p{pi}"
        if key not in hit_map:
            continue
        ranges = sorted(hit_map[key], key=lambda x: x[0])
        if not ranges:
            continue
        text = para.text or ""
        out = []
        last = 0
        for s, e in ranges:
            s = max(0, min(len(text), s))
            e = max(0, min(len(text), e))
            if s > last:
                out.append(text[last:s])
            out.append("█" * (e - s))  # black bar
            last = e
        if last < len(text):
            out.append(text[last:])
        # replace runs with single run containing redacted content
        for _ in range(len(para.runs)):
            para.runs[0].clear()
            para.runs[0].text = ""
            para._p.remove(para.runs[0]._r)
        run = para.add_run("".join(out))
        font = run.font
        font.size = Pt(11)
        font.color.rgb = RGBColor(0, 0, 0)

    outb = io.BytesIO()
    doc.save(outb)
    return outb.getvalue()

# ---------- TXT ----------
def save_txt_redacted(file_bytes: bytes, hits: List[Hit]) -> bytes:
    s = file_bytes.decode("utf-8", errors="ignore")
    # We only know hit spans per line/scope; for simplicity, replace occurrences globally
    # Build a set of unique tokens to redact
    tokens = sorted(set(h.text for h in hits), key=len, reverse=True)
    for t in tokens:
        s = re_sub_safe(s, t, "█" * len(t))
    return s.encode("utf-8")

# ---------- XLSX ----------
def save_xlsx_redacted(file_bytes: bytes, hits: List[Hit]) -> bytes:
    wb = load_workbook(io.BytesIO(file_bytes))
    # Build per-sheet tokens
    by_sheet = {}
    for h in hits:
        if h.context:
            by_sheet.setdefault(h.context[0], set()).add(h.text)

    for ws in wb.worksheets:
        toks = by_sheet.get(ws.title, set())
        if not toks:
            continue
        for row in ws.iter_rows():
            for cell in row:
                val = str(cell.value) if cell.value is not None else None
                if not val:
                    continue
                new_val = val
                for t in sorted(toks, key=len, reverse=True):
                    new_val = new_val.replace(t, "█" * len(t))
                if new_val != val:
                    cell.value = new_val

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()

# ---------- helpers ----------
import re
def re_sub_safe(s: str, token: str, repl: str) -> str:
    # escape token for regex, do a global replace
    try:
        return re.sub(re.escape(token), repl, s)
    except Exception:
        return s.replace(token, repl)

def _hex_to_rgb(hx: str):
    hx = hx.lstrip("#")
    r = int(hx[0:2], 16) / 255.0
    g = int(hx[2:4], 16) / 255.0
    b = int(hx[4:6], 16) / 255.0
    return (r, g, b)
