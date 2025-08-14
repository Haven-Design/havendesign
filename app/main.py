import os
import io
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from pytesseract import Output

# -----------------------------
# Optional: Hard-wire Tesseract if bundled locally in your project
# Example: r"C:\Users\<you>\...\Redactor-API\Tesseract-OCR\tesseract.exe"
TESSERACT_PATH = None  # set to a full path string if you bundled it
if TESSERACT_PATH and os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
# -----------------------------

st.set_page_config(page_title="PDF Redactor", layout="wide")

# ADA-friendly high-contrast colors (approx WCAG AA contrast on light background)
CATEGORY_COLORS = {
    "Emails": (0, 92, 175),          # deep blue
    "Phones": (0, 138, 0),           # dark green
    "SSN": (176, 0, 32),             # dark red
    "Credit Cards": (120, 0, 120),   # deep purple
    "Dates": (153, 81, 0),           # brown
    "ZIP Codes": (0, 112, 143),      # teal
    "Addresses": (90, 90, 0),        # olive
    "Names": (0, 0, 0),              # black (high contrast)
    "Custom": (128, 0, 0),           # maroon
}

# Reasonable default regexes
REGEX_PATTERNS = {
    "Emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "Phones": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "Credit Cards": r"\b(?:\d[ -]*?){13,19}\b",
    "Dates": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b",
    "ZIP Codes": r"\b\d{5}(?:-\d{4})?\b",
    "Addresses": r"\b\d{1,6}\s+[A-Za-z0-9.\-]+\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Ct|Court)\b",
    # "Names": (left to OCR/heuristic below)
}

# Heuristic for "Names": capitalized words that are not at sentence start only if OCR gives proper spacing
def is_potential_name(token: str) -> bool:
    if not token:
        return False
    if len(token) < 2:
        return False
    # Starts with uppercase, followed by lowercase letters, and not all caps
    return token[0].isupper() and (token[1:].islower() or token[1:].isalpha())

@dataclass
class Box:
    page: int
    x: float
    y: float
    w: float
    h: float
    text: str
    category: str
    id: str  # unique id

def _rgba(fill_rgb, alpha: float = 0.25):
    r, g, b = fill_rgb
    a = int(alpha * 255)
    return (r, g, b, a)

def render_page_image(doc: fitz.Document, page_index: int, zoom: float = 2.0) -> Image.Image:
    """Render a PDF page to a PIL image using PyMuPDF."""
    page = doc.load_page(page_index)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img

def ocr_page(image: Image.Image) -> Dict[str, List]:
    """Run Tesseract OCR on a PIL image, returning image_to_data dict."""
    return pytesseract.image_to_data(image, output_type=Output.DICT)

def find_regex_hits(text: str, patterns: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Return list of (category, matched_text) for each regex hit found in text."""
    hits = []
    for cat, pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            hits.append((cat, m.group()))
    return hits

def assemble_boxes_from_ocr(ocr: Dict[str, List], page_idx: int,
                            active_categories: List[str],
                            custom_patterns: List[str]) -> List[Box]:
    """Map OCR tokens to category matches; return bounding boxes for matched tokens."""
    boxes: List[Box] = []
    n = len(ocr["text"])
    # Build page-level plaintext to catch multi-token regex (like CC numbers split by spaces)
    # Also keep token -> bbox map for back-mapping.
    tokens = []
    spans = []  # (start,end)
    bboxes = []  # (x,y,w,h)
    cursor = 0
    for i in range(n):
        txt = ocr["text"][i] or ""
        if txt.strip() == "":
            continue
        x, y, w, h = ocr["left"][i], ocr["top"][i], ocr["width"][i], ocr["height"][i]
        # Normalize whitespace between tokens as single space
        if tokens:
            cursor += 1  # space
        start = cursor
        cursor += len(txt)
        end = cursor
        tokens.append(txt)
        spans.append((start, end))
        bboxes.append((x, y, w, h))
    page_text = " ".join(tokens)

    # Build patterns list (category, pattern)
    patterns: List[Tuple[str, str]] = []
    for cat in active_categories:
        if cat == "Names":
            continue  # handled heuristically below
        pat = REGEX_PATTERNS.get(cat)
        if pat:
            patterns.append((cat, pat))
    for idx, pat in enumerate(custom_patterns):
        if pat.strip():
            patterns.append(("Custom", pat.strip()))

    # 1) Regex-based matches (map matched substring back to token boxes by span overlap)
    for cat, pat in patterns:
        for m in re.finditer(pat, page_text, flags=re.IGNORECASE):
            ms, me = m.span()
            # collect all token bboxes that overlap [ms, me)
            merged_rect = None
            merged_text_parts = []
            for (ts, te), (x, y, w, h), tok in zip(spans, bboxes, tokens):
                if te <= ms or ts >= me:
                    continue
                # expand merged rect
                if merged_rect is None:
                    merged_rect = [x, y, x + w, y + h]
                else:
                    merged_rect[0] = min(merged_rect[0], x)
                    merged_rect[1] = min(merged_rect[1], y)
                    merged_rect[2] = max(merged_rect[2], x + w)
                    merged_rect[3] = max(merged_rect[3], y + h)
                merged_text_parts.append(tok)
            if merged_rect:
                bx, by, ex, ey = merged_rect
                boxes.append(Box(
                    page=page_idx,
                    x=bx, y=by, w=ex - bx, h=ey - by,
                    text=m.group(),
                    category=cat,
                    id=f"p{page_idx}-rx-{ms}-{me}-{cat}"
                ))

    # 2) Name heuristic (token-level)
    if "Names" in active_categories:
        for i, tok in enumerate(tokens):
            if is_potential_name(tok):
                x, y, w, h = bboxes[i]
                boxes.append(Box(
                    page=page_idx, x=x, y=y, w=w, h=h,
                    text=tok, category="Names",
                    id=f"p{page_idx}-nm-{i}"
                ))

    return boxes

def draw_preview(image: Image.Image, boxes: List[Box], selected_ids: set,
                 legend: Dict[str, Tuple[int,int,int]]) -> Image.Image:
    """Overlay semi-transparent gray fills with colored outlines for selected boxes."""
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    for b in boxes:
        if b.id not in selected_ids:
            continue
        color = legend.get(b.category, (0, 0, 0))
        fill = _rgba((128, 128, 128), 0.25)  # semi-transparent gray
        # rectangle coords
        x0, y0 = int(b.x), int(b.y)
        x1, y1 = int(b.x + b.w), int(b.y + b.h)
        # fill
        odraw.rectangle([x0, y0, x1, y1], fill=fill, outline=color, width=3)

    out = Image.alpha_composite(image, overlay)

    # Legend badge
    badgelines = []
    for cat, rgb in legend.items():
        badgelines.append((cat, rgb))
    # draw legend in a small panel
    d = ImageDraw.Draw(out)
    pad = 8
    bx, by = pad, pad
    # header
    legend_w = 260
    legend_h = 20 + 18 * len(badgelines) + 10
    d.rectangle([bx, by, bx + legend_w, by + legend_h], fill=(255, 255, 255, 200), outline=(0, 0, 0, 200), width=1)
    d.text((bx + 8, by + 6), "Legend", fill=(0, 0, 0))
    cy = by + 26
    for label, rgb in badgelines:
        # color swatch + label
        d.rectangle([bx + 8, cy, bx + 28, cy + 12], fill=rgb + (255,), outline=(0, 0, 0))
        d.text((bx + 36, cy - 2), label, fill=(0, 0, 0))
        cy += 18

    return out.convert("RGB")

def save_redacted_pdf(original_pdf_bytes: bytes, selected_boxes: List[Box]) -> bytes:
    """Apply actual redactions to the PDF using PyMuPDF and return new bytes."""
    doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
    # Group boxes per page
    page_map: Dict[int, List[Box]] = {}
    for b in selected_boxes:
        page_map.setdefault(b.page, []).append(b)

    for pno, items in page_map.items():
        page = doc.load_page(pno)
        # add redact annots
        for b in items:
            rect = fitz.Rect(b.x, b.y, b.x + b.w, b.y + b.h)
            page.add_redact_annot(rect, fill=(0, 0, 0))  # final output: solid black
        page.apply_redactions()

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    out.seek(0)
    return out.read()

# ------------------------------------------------------------------------------------
# UI & State
# ------------------------------------------------------------------------------------

if "doc_bytes" not in st.session_state:
    st.session_state.doc_bytes = None
if "doc_images" not in st.session_state:
    st.session_state.doc_images = {}  # page -> PIL image
if "ocr" not in st.session_state:
    st.session_state.ocr = {}  # page -> pytesseract data dict
if "boxes" not in st.session_state:
    st.session_state.boxes = []  # all Box across pages
if "selected_ids" not in st.session_state:
    st.session_state.selected_ids = set()
if "scan_done" not in st.session_state:
    st.session_state.scan_done = False
if "active_categories" not in st.session_state:
    st.session_state.active_categories = []
if "custom_terms" not in st.session_state:
    st.session_state.custom_terms = ""

st.title("PDF Redactor (ADA-friendly preview)")

# Step 1: Upload
uploaded = st.file_uploader("Upload a PDF", type=["pdf"])

# Step 2: Category checkboxes + Select All + custom terms box (only after upload)
if uploaded is not None and st.session_state.doc_bytes is None:
    st.session_state.doc_bytes = uploaded.read()
    # clear previous
    st.session_state.doc_images.clear()
    st.session_state.ocr.clear()
    st.session_state.boxes.clear()
    st.session_state.selected_ids.clear()
    st.session_state.scan_done = False

if st.session_state.doc_bytes:
    st.subheader("What to scan for")
    cols = st.columns(4)
    base_categories = list(CATEGORY_COLORS.keys())
    # We’ll offer checkboxes for all except "Custom" (that’s driven by input)
    offered_categories = [c for c in base_categories if c != "Custom"]

    # Single Select All toggle
    if "select_all_toggle" not in st.session_state:
        st.session_state.select_all_toggle = False

    with cols[0]:
        st.session_state.select_all_toggle = st.checkbox("Select All", value=False, help="Toggle all categories")

    # Render checkboxes honoring the select-all toggle
    per_col = (len(offered_categories) + 3) // 4
    chosen = set(st.session_state.active_categories)
    for j, cat in enumerate(offered_categories):
        col = cols[j // per_col]
        default_val = st.session_state.select_all_toggle or (cat in chosen)
        val = col.checkbox(cat, value=default_val, key=f"cat_{cat}")
        if val:
            chosen.add(cat)
        else:
            chosen.discard(cat)

    # Update active categories
    st.session_state.active_categories = sorted(list(chosen))

    # Custom terms/regex box (under checkboxes)
    st.text_input(
        "Custom terms or regex (comma-separated). Example: Acme Corp,(?i)confidential",
        key="custom_terms",
        value=st.session_state.custom_terms or "",
        help="You can add plain words or full regex patterns. We’ll match them case-insensitively unless your regex overrides it."
    )

    # Step 3: Scan button
    if st.button("Scan for redacted phrases"):
        # Build doc / images / OCR once
        doc = fitz.open(stream=st.session_state.doc_bytes, filetype="pdf")
        try:
            # render and OCR
            total_pages = doc.page_count
            st.session_state.doc_images.clear()
            st.session_state.ocr.clear()
            st.session_state.boxes.clear()
            st.session_state.selected_ids.clear()

            active = st.session_state.active_categories[:]
            custom_patterns = [s.strip() for s in (st.session_state.custom_terms or "").split(",") if s.strip()]

            progress = st.progress(0.0, text="Scanning pages…")
            for p in range(total_pages):
                img = render_page_image(doc, p, zoom=2.0)
                st.session_state.doc_images[p] = img
                ocr = ocr_page(img)
                st.session_state.ocr[p] = ocr
                page_boxes = assemble_boxes_from_ocr(ocr, p, active, custom_patterns)
                st.session_state.boxes.extend(page_boxes)
                progress.progress((p + 1) / total_pages, text=f"Scanning page {p+1}/{total_pages}…")
            progress.empty()

            # Pre-select everything
            st.session_state.selected_ids = {b.id for b in st.session_state.boxes}
            st.session_state.scan_done = True
        finally:
            doc.close()

# Step 4: Preview + phrases list after scan
if st.session_state.scan_done:
    # Split layout
    col_preview, col_list = st.columns([3, 2])

    # Right column: Scrollable phrases with summary at top (small text)
    with col_list:
        st.markdown("##### Found Phrases (click to exclude/include)")
        # Summary small text
        total = len(st.session_state.boxes)
        by_cat: Dict[str, int] = {}
        for b in st.session_state.boxes:
            by_cat[b.category] = by_cat.get(b.category, 0) + 1
        summary = " • ".join(f"{k}: {v}" for k, v in sorted(by_cat.items()))
        st.caption(f"Summary — total: {total} • {summary}" if total else "Summary — no phrases found")

        # Select all phrases toggle
        if "phrases_all_toggle" not in st.session_state:
            st.session_state.phrases_all_toggle = True  # initially all selected

        st.session_state.phrases_all_toggle = st.checkbox(
            "Select All Phrases",
            value=len(st.session_state.selected_ids) == len(st.session_state.boxes),
            help="Toggle all individual phrases below."
        )

        if st.session_state.phrases_all_toggle:
            st.session_state.selected_ids = {b.id for b in st.session_state.boxes}
        else:
            # if user untoggles, do not force-clear; allow individual control
            pass

        # Group phrases by page with a scroll container
        with st.container(height=360):
            # Sort by page, then category, then text
            sorted_boxes = sorted(st.session_state.boxes, key=lambda b: (b.page, b.category, b.text.lower()))
            current_page = None
            for b in sorted_boxes:
                if b.page != current_page:
                    current_page = b.page
                    st.markdown(f"**Page {current_page + 1}**")

                # individual checkbox reflecting selection
                color = CATEGORY_COLORS.get(b.category, (0, 0, 0))
                color_hex = "#{:02x}{:02x}{:02x}".format(*color)
                label = f"{b.category}: `{b.text}`"
                key = f"ph_{b.id}"
                checked = b.id in st.session_state.selected_ids
                new_state = st.checkbox(label, value=checked, key=key, help="Uncheck to exclude from redaction")
                # If user toggled
                if new_state and b.id not in st.session_state.selected_ids:
                    st.session_state.selected_ids.add(b.id)
                elif (not new_state) and (b.id in st.session_state.selected_ids):
                    st.session_state.selected_ids.remove(b.id)
                # tiny color swatch
                st.markdown(f"<div style='height:4px;background:{color_hex};margin:-10px 0 8px 0;'></div>", unsafe_allow_html=True)

    # Left column: dynamic preview (rebuilds image overlays for currently selected IDs)
    with col_preview:
        # User can pick a page to preview
        doc = fitz.open(stream=st.session_state.doc_bytes, filetype="pdf")
        total_pages = doc.page_count
        page_to_show = st.number_input("Preview Page", min_value=1, max_value=total_pages, value=1, step=1)
        doc.close()

        # Filter boxes for this page
        page_idx = page_to_show - 1
        page_boxes = [b for b in st.session_state.boxes if b.page == page_idx]
        # Render
        base_img = st.session_state.doc_images[page_idx]
        img_with_boxes = draw_preview(base_img.copy(), page_boxes, st.session_state.selected_ids, CATEGORY_COLORS)
        st.image(img_with_boxes, use_container_width=True, caption="Live Preview (semi-transparent gray fill + colored outlines)")

        # Download (apply true redactions to all selected boxes across all pages)
        if st.button("Download Redacted PDF"):
            chosen_boxes = [b for b in st.session_state.boxes if b.id in st.session_state.selected_ids]
            if not chosen_boxes:
                st.warning("Nothing selected to redact.")
            else:
                try:
                    pdf_bytes = save_redacted_pdf(st.session_state.doc_bytes, chosen_boxes)
                    st.download_button("Save file", data=pdf_bytes, file_name="redacted.pdf", mime="application/pdf")
                except Exception as e:
                    st.error(f"Failed to create redacted PDF: {e}")

else:
    if st.session_state.doc_bytes:
        st.info("Choose categories and/or enter custom terms, then click **Scan for redacted phrases**.")
    else:
        st.info("Upload a PDF to get started.")
