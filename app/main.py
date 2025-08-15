import base64
import io
import os
import tempfile
from typing import Dict, List

import streamlit as st
import streamlit.components.v1 as components

from utilities.extract_text import (
    CATEGORY_PATTERNS,
    CATEGORY_PRIORITY,
    CATEGORY_COLORS_HEX,
    CATEGORY_COLORS_RGB,
    extract_text_and_positions,           # returns list[dict]: {id, page, text, rect, category}
)
from utilities.redact_pdf import (
    build_preview_pdf,                    # colored rectangles (non-destructive)
    redact_pdf_with_positions,            # true redaction (black boxes)
)

st.set_page_config(page_title="PDF Redactor", layout="wide")

# -----------------------------
# Session State (idempotent)
# -----------------------------
if "uploaded_pdf_bytes" not in st.session_state:
    st.session_state.uploaded_pdf_bytes = None
if "found_items" not in st.session_state:
    st.session_state.found_items = []     # list[dict] from extractor
if "selected_item_ids" not in st.session_state:
    st.session_state.selected_item_ids = set()
if "last_preview_pdf" not in st.session_state:
    st.session_state.last_preview_pdf = None
if "scan_done" not in st.session_state:
    st.session_state.scan_done = False
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = tempfile.mkdtemp()

# -----------------------------
# Small helpers
# -----------------------------
def _b64_pdf(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

def _render_pdf_iframe(file_path: str, height: int = 600):
    b64 = _b64_pdf(file_path)
    components.html(
        f"""
        <iframe
          src="data:application/pdf;base64,{b64}"
          width="100%"
          height="{height}px"
          style="border:1px solid #ddd;border-radius:6px;"
        ></iframe>
        """,
        height=height + 8,
        scrolling=False,
    )

def _regen_preview(input_pdf_path: str):
    """Regenerate preview using the currently selected items."""
    selected = [it for it in st.session_state.found_items if it["id"] in st.session_state.selected_item_ids]
    if not selected:
        # Build a "blank" preview (just original PDF) so user still sees something
        out_path = os.path.join(st.session_state.temp_dir, "preview.pdf")
        with open(out_path, "wb") as f:
            f.write(open(input_pdf_path, "rb").read())
        st.session_state.last_preview_pdf = out_path
        return

    out_path = os.path.join(st.session_state.temp_dir, "preview.pdf")
    build_preview_pdf(
        input_pdf_path,
        selected,
        out_path,
        color_map=CATEGORY_COLORS_RGB
    )
    st.session_state.last_preview_pdf = out_path

def _select_all_found(toggle_on: bool):
    if toggle_on:
        st.session_state.selected_item_ids = {it["id"] for it in st.session_state.found_items}
    else:
        st.session_state.selected_item_ids = set()

# -----------------------------
# UI — Header & Upload
# -----------------------------
st.title("PDF Redactor Tool")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
if uploaded is not None:
    st.session_state.uploaded_pdf_bytes = uploaded.getvalue()

# -----------------------------
# Category selection (left half)
# -----------------------------
st.subheader("Choose What To Detect")

# Categories grid + single toggle
cat_cols = st.columns(3)
with cat_cols[0]:
    st.markdown("**Built-in categories**")
with cat_cols[1]:
    select_all_categories = st.toggle("Select All", value=True, key="select_all_categories_toggle")
with cat_cols[2]:
    st.write("")  # spacer

# Determine initial checkbox default from the toggle
default_checked = True if select_all_categories else False

# render category checkboxes in two columns
left_cat_col, right_cat_col = st.columns(2)
selected_categories: List[str] = []

cat_items = list(CATEGORY_PATTERNS.keys())
half = (len(cat_items) + 1) // 2
for i, cat in enumerate(cat_items):
    label = cat.replace("_", " ").title()
    column = left_cat_col if i < half else right_cat_col
    with column:
        if st.checkbox(label, value=default_checked, key=f"cat_{cat}"):
            selected_categories.append(cat)

# Custom regex (under categories, before scan)
custom_regex = st.text_area(
    "Custom regex (optional)",
    placeholder=r"Enter one regex per line, e.g.\n(?i)\bproject\s+codename\b\n\d{4}-\d{4}-\d{4}-\d{4}",
    height=80
)

# -----------------------------
# Scan for Phrases
# -----------------------------
scan_col_l, scan_col_r = st.columns([1, 3])
with scan_col_l:
    scan_clicked = st.button("Scan for Redacted Phrases", type="primary", use_container_width=True)
with scan_col_r:
    st.caption("Tip: keep categories selected; phrases will load below and the preview appears on the right. You can toggle phrases and the preview will update automatically.")

input_pdf_path = None
if st.session_state.uploaded_pdf_bytes:
    input_pdf_path = os.path.join(st.session_state.temp_dir, "input.pdf")
    with open(input_pdf_path, "wb") as fw:
        fw.write(st.session_state.uploaded_pdf_bytes)

if scan_clicked:
    if not st.session_state.uploaded_pdf_bytes:
        st.warning("Please upload a PDF first.")
    elif not selected_categories and not custom_regex.strip():
        st.warning("Please choose at least one category or supply custom regex.")
    else:
        # Extract text & positions
        found_items = extract_text_and_positions(
            input_pdf_path,
            selected_categories,
            custom_patterns=[line.strip() for line in custom_regex.splitlines() if line.strip()]
        )

        # Persist
        st.session_state.found_items = found_items
        # Default: everything checked
        st.session_state.selected_item_ids = {it["id"] for it in found_items}
        st.session_state.scan_done = True

        # Build initial preview
        _regen_preview(input_pdf_path)

        # Smooth scroll to results
        components.html(
            """
            <script>
              setTimeout(function(){
                var el = document.getElementById("results-anchor");
                if (el) el.scrollIntoView({behavior: "smooth", block:"start"});
              }, 150);
            </script>
            """,
            height=0
        )

# -----------------------------
# Results + Preview (side-by-side)
# -----------------------------
if st.session_state.scan_done and st.session_state.found_items:
    st.markdown("<div id='results-anchor'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)

    with left:
        st.markdown("### Redacted Phrases")
        st.caption("Summary: Each item is pre-selected. Deselect to exclude from redaction. (Scroll list)")

        # Select All toggle for FOUND phrases
        toggle_found = st.toggle("Select All Phrases", value=True, key="toggle_found_all")
        _select_all_found(toggle_found)

        # Scrollable list with checkboxes, grouped by category color
        st.markdown(
            """
            <style>
              .phrase-box { max-height: 460px; overflow-y: auto; border:1px solid #ddd; border-radius:8px; padding:8px; background:#fafafa; }
              .pill { display:inline-block; padding:2px 6px; border-radius:999px; font-size:11px; margin-left:6px; }
            </style>
            """,
            unsafe_allow_html=True
        )

        # Group by category to show color labels
        from collections import defaultdict
        grouped: Dict[str, List[dict]] = defaultdict(list)
        for it in st.session_state.found_items:
            grouped[it["category"]].append(it)

        # Build UI
        changed = False
        with st.container():
            st.markdown("<div class='phrase-box'>", unsafe_allow_html=True)
            for cat in CATEGORY_PRIORITY:
                if cat not in grouped:
                    continue
                hex_color = CATEGORY_COLORS_HEX.get(cat, "#777777")
                st.write(f"**{cat.replace('_',' ').title()}**", unsafe_allow_html=True)
                for it in grouped[cat]:
                    label = f"{it['text']} (p.{it['page']+1})"
                    key = f"item_{it['id']}"
                    # default from session
                    default_val = it["id"] in st.session_state.selected_item_ids
                    val = st.checkbox(
                        label,
                        value=default_val,
                        key=key,
                    )
                    # colored pill indication
                    st.markdown(
                        f"<span class='pill' style='background:{hex_color}22;border:1px solid {hex_color};color:#222;'> {cat} </span>",
                        unsafe_allow_html=True,
                    )
                    if val and it["id"] not in st.session_state.selected_item_ids:
                        st.session_state.selected_item_ids.add(it["id"])
                        changed = True
                    elif (not val) and it["id"] in st.session_state.selected_item_ids:
                        st.session_state.selected_item_ids.remove(it["id"])
                        changed = True
            st.markdown("</div>", unsafe_allow_html=True)

        # If any checkbox changed, regenerate preview
        if changed and input_pdf_path:
            _regen_preview(input_pdf_path)

        # Single download button under list
        if st.session_state.selected_item_ids:
            # Build the FINAL redacted PDF on click
            with open(input_pdf_path, "rb") as _:
                pass  # ensure exists
            final_btn = st.button("Download PDF", type="primary", use_container_width=True)
            if final_btn:
                # Final redaction into a BytesIO so user downloads once
                buf = io.BytesIO()
                tmp_out = os.path.join(st.session_state.temp_dir, "final_redacted.pdf")
                selected = [it for it in st.session_state.found_items if it["id"] in st.session_state.selected_item_ids]
                redact_pdf_with_positions(
                    input_pdf_path,
                    selected,
                    tmp_out_path=tmp_out
                )
                with open(tmp_out, "rb") as fr:
                    st.download_button(
                        label="Download PDF",
                        data=fr.read(),
                        file_name="redacted.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        else:
            st.info("No phrases selected. Use the checkboxes above to include items.")

    with right:
        st.markdown("### Preview")
        if st.session_state.last_preview_pdf and os.path.exists(st.session_state.last_preview_pdf):
            _render_pdf_iframe(st.session_state.last_preview_pdf, height=640)
        else:
            st.write("Run a scan to preview.")
