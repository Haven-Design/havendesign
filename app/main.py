"""
main.py (v1.4.1)

Fixes:
- Select All now toggles (selects all if not all selected, otherwise deselects all).
- Parent category checkbox no longer writes directly to session_state after creation.
- Added dummy label + label_visibility='collapsed' to silence empty-label warning.
"""

import os
import base64
from typing import List, Dict, Set

import streamlit as st
import streamlit.components.v1 as components

from utilities.extract_text import extract_text_and_positions, CATEGORY_LABELS, Hit
from utilities.redact_pdf import redact_pdf_with_hits, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("Redactor-API (v1.4.1)")

# -----------------------
# Session state defaults
# -----------------------
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

# -----------------------
# Upload
# -----------------------
uploaded_file = st.file_uploader("Upload PDF/DOCX/TXT", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()
    _, ext = os.path.splitext(uploaded_file.name)
    st.session_state.ext = ext.lower()
    # reset previous scan results
    st.session_state.hits = []
    st.session_state.id_to_hit = {}
    st.session_state.selected_hit_ids = set()
    st.session_state.collapsed = {}

# -----------------------
# Category selection UI
# -----------------------
st.subheader("Select categories to scan")
cols = st.columns(2)
category_keys = list(CATEGORY_LABELS.keys())

# Select All button (toggle)
def toggle_select_all():
    if all(st.session_state.get(f"param_{k}", False) for k in category_keys):
        # all selected -> deselect all
        for k in category_keys:
            st.session_state[f"param_{k}"] = False
    else:
        # not all selected -> select all
        for k in category_keys:
            st.session_state[f"param_{k}"] = True

st.button("Select / Deselect All", on_click=toggle_select_all)

for i, k in enumerate(category_keys):
    col = cols[i % 2]
    with col:
        if f"param_{k}" not in st.session_state:
            st.session_state[f"param_{k}"] = False
        st.checkbox(CATEGORY_LABELS[k], key=f"param_{k}")

custom_phrase = st.text_input("Custom phrase (optional)")

# -----------------------
# Scan
# -----------------------
if st.button("Scan for Redacted Phrases") and st.session_state.file_bytes:
    # build categories list
    selected_categories = [k for k in category_keys if st.session_state.get(f"param_{k}", False)]
    if custom_phrase and custom_phrase.strip():
        selected_categories.append("custom")

    st.session_state.hits = []
    st.session_state.id_to_hit = {}
    st.session_state.selected_hit_ids = set()

    found = extract_text_and_positions(st.session_state.file_bytes, st.session_state.ext, selected_categories, custom_phrase if custom_phrase else None)
    found.sort(key=lambda h: (h.page, h.start if getattr(h, "start", None) is not None else 1_000_000))

    for i, h in enumerate(found):
        st.session_state.id_to_hit[i] = h
        st.session_state.hits.append(h)
        st.session_state.selected_hit_ids.add(i)

    for k in category_keys:
        st.session_state.collapsed.setdefault(k, False)

    components.html("<script>setTimeout(()=>{document.getElementById('results-section')?.scrollIntoView({behavior:'smooth'})},200)</script>", height=0)

# -----------------------
# Results & Preview
# -----------------------
if st.session_state.hits:
    left, right = st.columns([1, 1])

    with left:
        st.markdown("<div id='results-section'></div>", unsafe_allow_html=True)
        st.markdown("### Redacted Phrases")
        st.markdown("<div style='max-height:560px; overflow-y:auto; padding:8px; border:1px solid #e6e6e6; border-radius:8px;'>", unsafe_allow_html=True)

        grouped: Dict[str, List[int]] = {}
        for idx, h in st.session_state.id_to_hit.items():
            grouped.setdefault(h.category, []).append(idx)

        for cat, idx_list in grouped.items():
            color = CATEGORY_COLORS.get(cat, "#111111")
            parent_checked = all(i in st.session_state.selected_hit_ids for i in idx_list)
            cat_label = CATEGORY_LABELS.get(cat, cat)

            c1, c2, c3 = st.columns([0.06, 0.78, 0.16])
            with c1:
                # parent checkbox (dummy label with collapsed visibility)
                parent_val = st.checkbox(
                    " ",
                    key=f"cat_chk_{cat}",
                    value=parent_checked,
                    label_visibility="collapsed",
                )
            with c2:
                st.markdown(
                    f"<span style='display:inline-block;width:14px;height:14px;background:{color};border-radius:3px;margin-right:8px;vertical-align:middle;'></span>"
                    f"<span style='color:{color};font-weight:700'>{cat_label}</span>",
                    unsafe_allow_html=True,
                )
            with c3:
                if f"collapse_{cat}" not in st.session_state:
                    st.session_state[f"collapse_{cat}"] = st.session_state.collapsed.get(cat, False)
                collapse_val = st.checkbox("Collapse", key=f"collapse_{cat}", value=st.session_state[f"collapse_{cat}"])
                st.session_state.collapsed[cat] = collapse_val

            # sync parent to children
            if parent_val:
                for i in idx_list:
                    st.session_state.selected_hit_ids.add(i)
            else:
                for i in idx_list:
                    st.session_state.selected_hit_ids.discard(i)

            if not st.session_state.collapsed[cat]:
                for i in idx_list:
                    h = st.session_state.id_to_hit[i]
                    child_val = st.checkbox(f"{h.text} (p{h.page+1})", key=f"hit_{i}", value=(i in st.session_state.selected_hit_ids))
                    if child_val:
                        st.session_state.selected_hit_ids.add(i)
                    else:
                        st.session_state.selected_hit_ids.discard(i)

        st.markdown("</div>", unsafe_allow_html=True)

        if st.button("Download Redacted PDF"):
            selected_hits = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
            out_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=False)
            st.download_button("Save redacted.pdf", data=out_bytes, file_name="redacted.pdf")

    with right:
        st.markdown("### Preview")
        selected_hits = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
        if selected_hits:
            out_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=True)
            b64 = base64.b64encode(out_bytes).decode("utf-8")
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="560px"></iframe>', unsafe_allow_html=True)
        else:
            st.info("No phrases selected — select items on the left to preview.")
