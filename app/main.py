"""
main.py - Streamlit UI for Redactor-API

Features:
- Upload PDF/DOCX/TXT
- Select categories (Select All available)
- Scan file for matches
- Scrollable, single-height results box (grouped by category)
- Category-level and item-level checkboxes
- Preview (colored overlays) and destructive black-box download
"""

import os
import base64
import tempfile
from typing import List, Dict, Set

import streamlit as st

from utilities.extract_text import extract_text_and_positions, Hit, CATEGORY_LABELS, CATEGORY_COLORS
from utilities.redact_pdf import redact_pdf_with_hits, save_masked_file

st.set_page_config(layout="wide")
st.title("Redactor-API")

# -----------------------
# Session state
# -----------------------
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None
if "file_name" not in st.session_state:
    st.session_state.file_name = None
if "ext" not in st.session_state:
    st.session_state.ext = None

if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()
if "hit_keys" not in st.session_state:
    st.session_state.hit_keys: List[int] = []

# -----------------------
# Upload
# -----------------------
uploaded_file = st.file_uploader("Upload file", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.read()
    st.session_state.file_name = uploaded_file.name
    st.session_state.ext = os.path.splitext(uploaded_file.name)[1].lower()
    # reset previous scan state
    st.session_state.hits = []
    st.session_state.id_to_hit = {}
    st.session_state.selected_hit_ids = set()
    st.session_state.hit_keys = []

# -----------------------
# Category selection
# -----------------------
st.subheader("Categories")
# ensure keys exist in session_state for checkboxes
for key in CATEGORY_LABELS.keys():
    label_key = f"param_{key}"
    if label_key not in st.session_state:
        st.session_state[label_key] = False

def select_all_params():
    for key in CATEGORY_LABELS.keys():
        st.session_state[f"param_{key}"] = True

st.button("Select All Categories", on_click=select_all_params)

cols = st.columns(2)
for i, (key, label) in enumerate(CATEGORY_LABELS.items()):
    with cols[i % 2]:
        st.checkbox(label, key=f"param_{key}")

custom_phrase = st.text_input("Custom phrase (optional)")

# -----------------------
# Scan button
# -----------------------
if st.button("Scan for Redacted Phrases") and st.session_state.file_bytes:
    # build categories list from session_state checkboxes
    selected_categories = [k for k in CATEGORY_LABELS.keys() if st.session_state.get(f"param_{k}", False)]
    # include custom phrase flag if provided
    custom = custom_phrase.strip() if custom_phrase and custom_phrase.strip() else None

    # extract
    hits = extract_text_and_positions(st.session_state.file_bytes, st.session_state.ext, selected_categories + ([] if not custom else ["custom"]), custom_phrase=custom)
    # Deduplicate by page/start/end/text/category where available
    uniq = {}
    for h in hits:
        key = (h.page, getattr(h, "start", None), getattr(h, "end", None), h.category, h.text)
        if key[1] is None:
            # if no offsets, fallback to (page, text, category)
            key = (h.page, h.text, h.category)
        uniq[key] = h
    st.session_state.hits = list(uniq.values())
    st.session_state.id_to_hit = {i: h for i, h in enumerate(st.session_state.hits)}
    st.session_state.hit_keys = list(st.session_state.id_to_hit.keys())
    # initially select all
    st.session_state.selected_hit_ids = set(st.session_state.hit_keys)

# -----------------------
# Results panel + Preview
# -----------------------
if st.session_state.hits:
    left, right = st.columns([1, 1])

    # build category -> list mapping
    cat_map: Dict[str, List[int]] = {}
    for hid, h in st.session_state.id_to_hit.items():
        cat_map.setdefault(h.category, []).append(hid)

    # LEFT: scrollable grouped results
    with left:
        st.markdown("### Redacted Phrases")
        # inline styles for scroll box and items
        st.markdown(
            """
            <style>
            .results-scroll { max-height: 560px; overflow-y: auto; border:1px solid #e6e6e6; padding:8px; border-radius:8px; background:#fbfbfb; }
            .cat-header { display:flex; align-items:center; gap:8px; margin:6px 0; }
            .phrase-row { display:flex; align-items:center; gap:8px; padding:6px; border-radius:6px; }
            .pill { width:12px; height:12px; border-radius:50%; display:inline-block; margin-right:8px; }
            .phrase-text { font-weight:600; overflow-wrap: anywhere; }
            .page-num { color:#666; font-size:12px; margin-left:auto; }
            </style>
            """, unsafe_allow_html=True
        )

        st.markdown("<div class='results-scroll'>", unsafe_allow_html=True)

        # For consistent ordering, sort categories by label
        for cat in sorted(cat_map.keys(), key=lambda c: CATEGORY_LABELS.get(c, c)):
            cat_label = CATEGORY_LABELS.get(cat, cat)
            cat_color = CATEGORY_COLORS.get(cat, "#888888")
            # category-level checkbox
            cat_checked_key = f"cat_{cat}_checked"
            # initialize if missing
            if cat_checked_key not in st.session_state:
                st.session_state[cat_checked_key] = all(hid in st.session_state.selected_hit_ids for hid in cat_map[cat])

            cols = st.columns([0.03, 0.87, 0.10])
            with cols[0]:
                # colored square
                st.markdown(f"<div style='width:14px;height:14px;background:{cat_color};border-radius:3px;'></div>", unsafe_allow_html=True)
            with cols[1]:
                # label and category checkbox that toggles all hits in the category
                if st.checkbox(f"{cat_label}", key=cat_checked_key):
                    # check all items in category
                    for hid in cat_map[cat]:
                        st.session_state.selected_hit_ids.add(hid)
                        # ensure item-level key exists and is True
                        st.session_state.setdefault(f"hit_{hid}", True)
                else:
                    for hid in cat_map[cat]:
                        st.session_state.selected_hit_ids.discard(hid)
                        st.session_state[f"hit_{hid}"] = False
            # small spacer column (unused)
            with cols[2]:
                pass

            # list item rows (indented under category)
            for hid in cat_map[cat]:
                h = st.session_state.id_to_hit[hid]
                pill_html = f"<span class='pill' style='background:{cat_color}'></span>"
                phrase_key = f"hit_{hid}"
                if phrase_key not in st.session_state:
                    # initialize from selected_hit_ids
                    st.session_state[phrase_key] = hid in st.session_state.selected_hit_ids

                row_cols = st.columns([0.05, 0.85, 0.10])
                with row_cols[0]:
                    # small placeholder to align
                    st.write("")
                with row_cols[1]:
                    checked = st.checkbox(
                        f"{h.text}",
                        key=phrase_key,
                        value=st.session_state[phrase_key],
                        help=f"{CATEGORY_LABELS.get(h.category,h.category)} — p{h.page+1}"
                    )
                    # reflect checkbox state into selection set
                    if checked:
                        st.session_state.selected_hit_ids.add(hid)
                    else:
                        st.session_state.selected_hit_ids.discard(hid)
                with row_cols[2]:
                    st.markdown(f"<div class='page-num'>p{h.page+1}</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # Download destructive (black box)
        st.markdown("---")
        if st.button("Download Redacted PDF"):
            selected_hits = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
            # only pass hits with bbox for PDF redaction; others will be ignored for PDF
            out_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=False, black_box=True)
            st.download_button("Click to save redacted.pdf", data=out_bytes, file_name="redacted.pdf")

    # RIGHT: Preview
    with right:
        st.markdown("### Preview")
        selected_hits = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
        if selected_hits:
            preview_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=True, black_box=True)
            b64 = base64.b64encode(preview_bytes).decode("utf-8")
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="560"></iframe>', unsafe_allow_html=True)
        else:
            st.info("No phrases selected. Uncheck/Check items in the left panel to preview.")
