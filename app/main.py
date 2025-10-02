import os
import base64
import tempfile
from typing import List, Set, Dict

import streamlit as st
import streamlit.components.v1 as components

from utilities.extract_text import extract_text_and_positions, Hit, CATEGORY_LABELS
from utilities.redact_pdf import redact_pdf_with_hits, CATEGORY_COLORS

# -----------------------
# Streamlit setup
# -----------------------
st.set_page_config(layout="wide")
st.title("PDF Redactor Tool")

# -----------------------
# Session state init
# -----------------------
if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}
if "collapsed_categories" not in st.session_state:
    st.session_state.collapsed_categories: Dict[str, bool] = {}

hits = st.session_state.hits
selected_hit_ids = st.session_state.selected_hit_ids
id_to_hit = st.session_state.id_to_hit

# -----------------------
# File upload
# -----------------------
uploaded_file = st.file_uploader("Upload a file", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()
    _, ext = os.path.splitext(uploaded_file.name)
    st.session_state.ext = ext.lower()

# -----------------------
# Redaction parameters
# -----------------------
st.subheader("Select Categories to Redact")

params = []
for key in CATEGORY_LABELS.keys():
    if st.checkbox(CATEGORY_LABELS[key], key=f"param_{key}"):
        params.append(key)

custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type phrase and press Enter")
if custom_phrase:
    params.append("custom")

# -----------------------
# Scan for redactions
# -----------------------
if st.button("Scan for Redacted Phrases") and st.session_state.file_bytes and params:
    hits.clear()
    id_to_hit.clear()
    selected_hit_ids.clear()

    new_hits = extract_text_and_positions(
        st.session_state.file_bytes,
        st.session_state.ext,
        params,
        custom_phrase
    )
    hits.extend(new_hits)

    for idx, h in enumerate(hits):
        hid = h.page * 1_000_000 + idx
        id_to_hit[hid] = h
        selected_hit_ids.add(hid)

    # Reset collapsed states
    for cat in CATEGORY_LABELS.keys():
        st.session_state.collapsed_categories[cat] = False

    components.html(
        "<script>setTimeout(function(){document.getElementById('results-section').scrollIntoView({behavior:'smooth'});},300);</script>",
        height=0,
    )

# -----------------------
# Results & Preview
# -----------------------
if hits:
    left_col, right_col = st.columns([1, 2])

    with left_col:
        st.markdown("<div id='results-section'></div>", unsafe_allow_html=True)
        st.markdown("### Redacted Phrases")

        # Scrollable box
        st.markdown(
            "<div style='max-height:520px; overflow-y:auto; padding:6px; border:1px solid #ccc; border-radius:8px;'>",
            unsafe_allow_html=True
        )

        # Group by category
        grouped: Dict[str, List[tuple]] = {}
        for idx, h in enumerate(hits):
            grouped.setdefault(h.category, []).append((idx, h))

        for cat, cat_hits in grouped.items():
            color = CATEGORY_COLORS.get(cat, "#000000")
            collapsed = st.session_state.collapsed_categories.get(cat, False)

            # Category row
            cat_col1, cat_col2 = st.columns([5, 1])
            with cat_col1:
                checked_all = all((hid in selected_hit_ids) for hid, _ in [
                    (h.page * 1_000_000 + idx, h) for idx, h in cat_hits
                ])
                cat_checkbox = st.checkbox(
                    f"**{CATEGORY_LABELS.get(cat, cat.title())}**",
                    key=f"cat_{cat}",
                    value=checked_all
                )
                st.markdown(
                    f"<style>label[for='cat_{cat}'] span {{color: {color}; font-weight: bold;}}</style>",
                    unsafe_allow_html=True,
                )

            with cat_col2:
                toggle_key = f"collapse_{cat}"
                if toggle_key not in st.session_state:
                    st.session_state[toggle_key] = False
                toggle_val = st.toggle(" ", key=toggle_key, label_visibility="collapsed")
                st.session_state.collapsed_categories[cat] = toggle_val

            # Sync category checkbox with children
            if cat_checkbox:
                for idx, h in cat_hits:
                    hid = h.page * 1_000_000 + idx
                    selected_hit_ids.add(hid)
            else:
                for idx, h in cat_hits:
                    hid = h.page * 1_000_000 + idx
                    selected_hit_ids.discard(hid)

            # Child phrases
            if not st.session_state.collapsed_categories[cat]:
                for idx, h in cat_hits:
                    hid = h.page * 1_000_000 + idx
                    checked = hid in selected_hit_ids
                    phrase_line = f"{h.text} _(p{h.page+1})_"
                    if st.checkbox(phrase_line, key=f"hit_{hid}", value=checked):
                        selected_hit_ids.add(hid)
                    else:
                        selected_hit_ids.discard(hid)

        st.markdown("</div>", unsafe_allow_html=True)

        # Download button
        if st.session_state.file_bytes:
            selected_hits = [id_to_hit[i] for i in selected_hit_ids]
            final_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=False)
            st.download_button("Download Redacted PDF", data=final_bytes, file_name="redacted.pdf")

    with right_col:
        st.markdown("### Preview")
        if st.session_state.file_bytes:
            selected_hits = [id_to_hit[i] for i in selected_hit_ids]
            out_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=True)

            b64_pdf = base64.b64encode(out_bytes).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="520px"></iframe>',
                unsafe_allow_html=True,
            )
