"""
main.py - Streamlit UI for Redactor-API
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
# Scan
# -----------------------
if st.button("Scan for Redacted Phrases") and st.session_state.file_bytes:
    selected_categories = [k for k in CATEGORY_LABELS.keys() if st.session_state.get(f"param_{k}", False)]
    custom = custom_phrase.strip() if custom_phrase and custom_phrase.strip() else None

    hits = extract_text_and_positions(st.session_state.file_bytes, st.session_state.ext, selected_categories + ([] if not custom else ["custom"]), custom_phrase=custom)
    # dedupe
    uniq = {}
    for h in hits:
        key = (h.page, getattr(h, "start", None), getattr(h, "end", None), h.category, h.text)
        if key[1] is None:
            key = (h.page, h.text, h.category)
        uniq[key] = h
    st.session_state.hits = list(uniq.values())
    st.session_state.id_to_hit = {i: h for i, h in enumerate(st.session_state.hits)}
    st.session_state.hit_keys = list(st.session_state.id_to_hit.keys())
    # initialize per-hit checkbox states
    for hid in st.session_state.hit_keys:
        key = f"hit_{hid}"
        if key not in st.session_state:
            st.session_state[key] = True
        st.session_state.selected_hit_ids.add(hid)

# -----------------------
# Results & Preview
# -----------------------
if st.session_state.hits:
    left, right = st.columns([1, 1])

    # map category -> hit ids
    cat_map: Dict[str, List[int]] = {}
    for hid, h in st.session_state.id_to_hit.items():
        cat_map.setdefault(h.category, []).append(hid)

    # LEFT: grouped results in a scrollbox
    with left:
        st.markdown("### Redacted Phrases")
        st.markdown(
            """
            <style>
            .results-scroll { max-height: 560px; overflow-y: auto; border:1px solid #e6e6e6; padding:8px; border-radius:8px; background:#fbfbfb; }
            .cat-header { display:flex; align-items:center; gap:8px; margin:8px 0; padding:6px; }
            .cat-label { font-weight:700; }
            .phrase-row { display:flex; align-items:center; gap:8px; padding:6px; border-radius:6px; }
            .pill { width:12px; height:12px; border-radius:50%; display:inline-block; margin-right:8px; }
            .phrase-text { font-weight:600; overflow-wrap:anywhere; }
            .page-num { color:#666; font-size:12px; margin-left:auto; }
            </style>
            """, unsafe_allow_html=True
        )

        st.markdown("<div class='results-scroll'>", unsafe_allow_html=True)

        # categories sorted by label
        for cat in sorted(cat_map.keys(), key=lambda c: CATEGORY_LABELS.get(c, c)):
            cat_label = CATEGORY_LABELS.get(cat, cat)
            cat_color = CATEGORY_COLORS.get(cat, "#888888")
            cat_key = f"cat_{cat}"

            # init category checkbox
            if cat_key not in st.session_state:
                st.session_state[cat_key] = all(st.session_state.get(f"hit_{hid}", False) for hid in cat_map[cat])

            # category header (color + label + category checkbox)
            header_cols = st.columns([0.04, 0.8, 0.16])
            with header_cols[0]:
                st.markdown(f"<div style='width:14px;height:14px;background:{cat_color};border-radius:3px;'></div>", unsafe_allow_html=True)
            with header_cols[1]:
                checked_cat = st.checkbox(f"{cat_label}", key=cat_key)
                # if user toggled category, update children
                if checked_cat:
                    for hid in cat_map[cat]:
                        st.session_state[f"hit_{hid}"] = True
                        st.session_state.selected_hit_ids.add(hid)
                else:
                    for hid in cat_map[cat]:
                        st.session_state[f"hit_{hid}"] = False
                        st.session_state.selected_hit_ids.discard(hid)
            with header_cols[2]:
                st.write("")

            # individual hits
            for hid in cat_map[cat]:
                h = st.session_state.id_to_hit[hid]
                phrase_key = f"hit_{hid}"
                if phrase_key not in st.session_state:
                    st.session_state[phrase_key] = hid in st.session_state.selected_hit_ids

                row_cols = st.columns([0.02, 0.78, 0.20])
                with row_cols[0]:
                    st.markdown(f"<div class='pill' style='background:{cat_color}'></div>", unsafe_allow_html=True)
                with row_cols[1]:
                    # NOTE: do NOT pass 'value=' here; rely on session_state for the checkbox value to avoid double-set warnings
                    checked = st.checkbox(h.text, key=phrase_key)
                    if checked:
                        st.session_state.selected_hit_ids.add(hid)
                    else:
                        st.session_state.selected_hit_ids.discard(hid)
                with row_cols[2]:
                    st.markdown(f"<div class='page-num'>p{h.page+1}</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        # destructive download
        if st.button("Download Redacted PDF"):
            selected_hits = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
            out = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=False, black_box=True)
            st.download_button("Save redacted.pdf", data=out, file_name="redacted.pdf")

    # RIGHT: preview
    with right:
        st.markdown("### Preview")
        selected_hits = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
        if selected_hits:
            preview_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=True, black_box=True)
            b64 = base64.b64encode(preview_bytes).decode("utf-8")
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="560"></iframe>', unsafe_allow_html=True)
        else:
            st.info("No phrases selected. Toggle items on the left to preview.")
