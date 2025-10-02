"""
main.py (v1.4.2)

- Left: scrollable category + nested phrases list (fixed height)
- Right: preview (iframe) with same height
- Category parent checkboxes are Streamlit checkboxes (no unsafe session writes)
- Collapse per-category implemented with a checkbox that visually behaves like a toggle
- Select All button toggles between all selected / all deselected
"""

import os
import base64
from typing import List, Dict, Set

import streamlit as st

from utilities.extract_text import extract_text_and_positions, CATEGORY_LABELS, CATEGORY_COLORS, Hit
from utilities.redact_pdf import redact_pdf_with_hits

st.set_page_config(layout="wide")
st.title("Redactor-API (v1.4.2)")

# Session state init
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None
if "ext" not in st.session_state:
    st.session_state.ext = ".pdf"

if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()
if "collapsed" not in st.session_state:
    st.session_state.collapsed: Dict[str, bool] = {}

# Upload
uploaded_file = st.file_uploader("Upload PDF/DOCX/TXT", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()
    _, ext = os.path.splitext(uploaded_file.name)
    st.session_state.ext = ext.lower()
    # reset previous
    st.session_state.hits = []
    st.session_state.id_to_hit = {}
    st.session_state.selected_hit_ids = set()
    st.session_state.collapsed = {}

# Category parameter checkboxes
st.subheader("Select categories to scan")
category_keys = list(CATEGORY_LABELS.keys())

def toggle_select_all():
    # if all selected -> deselect; else select all
    all_selected = all(st.session_state.get(f"param_{k}", False) for k in category_keys)
    for k in category_keys:
        st.session_state[f"param_{k}"] = not all_selected

st.button("Select / Deselect All", on_click=toggle_select_all)

cols = st.columns(2)
for i, k in enumerate(category_keys):
    if f"param_{k}" not in st.session_state:
        st.session_state[f"param_{k}"] = False
    with cols[i % 2]:
        st.checkbox(CATEGORY_LABELS[k], key=f"param_{k}")

custom_phrase = st.text_input("Custom phrase (optional)")

# Scan button
if st.button("Scan for Redacted Phrases") and st.session_state.file_bytes:
    # collect selected categories
    sel = [k for k in category_keys if st.session_state.get(f"param_{k}", False)]
    if custom_phrase and custom_phrase.strip():
        sel.append("custom")

    found = extract_text_and_positions(st.session_state.file_bytes, st.session_state.ext, sel, custom_phrase if custom_phrase else None)
    # sort by page/start
    found.sort(key=lambda h: (h.page, h.start if getattr(h, "start", None) is not None else 1_000_000))

    # store
    st.session_state.hits = found
    st.session_state.id_to_hit = {i: h for i, h in enumerate(found)}
    st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())
    for k in category_keys:
        st.session_state.collapsed.setdefault(k, False)

# UI layout: left list, right preview - same height
RESULT_HEIGHT_PX = 600
if st.session_state.hits:
    left, right = st.columns([1, 1])

    with left:
        st.markdown("<h3>Redacted Phrases</h3>", unsafe_allow_html=True)
        # CSS for scroll box & styling
        st.markdown(
            f"""
            <style>
            .left-scroll {{
                max-height: {RESULT_HEIGHT_PX}px;
                overflow-y: auto;
                padding: 8px;
                border: 1px solid #e6e6e6;
                border-radius: 8px;
                background: #ffffff;
            }}
            .cat-row {{
                display:flex;
                align-items:center;
                gap:8px;
                padding:6px 4px;
                border-bottom: 1px solid rgba(0,0,0,0.03);
            }}
            .cat-label {{
                font-weight:700;
            }}
            .child-item {{
                margin-left:28px;
                padding:4px 2px;
            }}
            .collapse-pill {{
                border-radius: 999px;
                padding:4px 10px;
                font-size:0.85em;
                background:#f0f0f0;
                cursor:pointer;
            }}
            .color-square {{
                width:14px; height:14px; border-radius:3px; display:inline-block; vertical-align:middle; margin-right:6px;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="left-scroll">', unsafe_allow_html=True)

        # group hits by category preserving order
        grouped = {}
        for idx, h in st.session_state.id_to_hit.items():
            grouped.setdefault(h.category, []).append(idx)

        for cat, idxs in grouped.items():
            color = CATEGORY_COLORS.get(cat, "#111111")
            # parent checkbox - set default in session_state before creating widget
            parent_key = f"cat_chk_{cat}"
            if parent_key not in st.session_state:
                # default: checked if all children selected
                st.session_state[parent_key] = all(i in st.session_state.selected_hit_ids for i in idxs)

            # render category row (checkbox in column 1, label in col 2, collapse in col3)
            c1, c2, c3 = st.columns([0.06, 0.78, 0.16])
            with c1:
                # collapsible hidden label to conform to accessibility; checkbox key exists in session_state
                chk_val = st.checkbox(" ", key=parent_key, label_visibility="collapsed")
            with c2:
                st.markdown(f'<span class="color-square" style="background:{color}"></span><span class="cat-label" style="color:{color}">{CATEGORY_LABELS.get(cat,cat)}</span>', unsafe_allow_html=True)
            with c3:
                collapse_key = f"collapse_{cat}"
                if collapse_key not in st.session_state:
                    st.session_state[collapse_key] = st.session_state.collapsed.get(cat, False)
                # Use a checkbox to represent collapse toggle (visually styled via CSS above); label hidden
                col_toggle = st.checkbox(" ", key=collapse_key, label_visibility="collapsed")
                st.session_state.collapsed[cat] = col_toggle

            # Sync parent checkbox -> children (do not assign session_state parent afterwards)
            if chk_val:
                for i in idxs:
                    st.session_state.selected_hit_ids.add(i)
            else:
                for i in idxs:
                    st.session_state.selected_hit_ids.discard(i)

            # children
            if not st.session_state.collapsed[cat]:
                for i in idxs:
                    h = st.session_state.id_to_hit[i]
                    child_key = f"hit_{i}"
                    if child_key not in st.session_state:
                        st.session_state[child_key] = (i in st.session_state.selected_hit_ids)
                    child_val = st.checkbox(f"{h.text} (p{h.page+1})", key=child_key)
                    # reflect child checkbox into selection set
                    if child_val:
                        st.session_state.selected_hit_ids.add(i)
                    else:
                        st.session_state.selected_hit_ids.discard(i)

        st.markdown("</div>", unsafe_allow_html=True)

        # Download button
        if st.button("Download Redacted PDF"):
            selected = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
            out = redact_pdf_with_hits(st.session_state.file_bytes, selected, preview_mode=False)
            st.download_button("Save redacted.pdf", data=out, file_name="redacted.pdf")

    with right:
        st.markdown("<h3>Preview</h3>", unsafe_allow_html=True)
        selected = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
        if selected:
            preview_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected, preview_mode=True)
            b64 = base64.b64encode(preview_bytes).decode("utf-8")
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{RESULT_HEIGHT_PX}px"></iframe>', unsafe_allow_html=True)
        else:
            st.info("No phrases selected — select items on the left to preview.")
