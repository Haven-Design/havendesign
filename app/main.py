"""
main.py (v1.4.3)

Focus: stable UI + scrollable results (left) and preview (right) same height.
Parent checkboxes control children. Child widget states drive the selected set.
A "Select / Deselect All (Results)" button sits at the bottom of the results.
"""

import os
import base64
from typing import List, Dict, Set

import streamlit as st

from utilities.extract_text import extract_text_and_positions, CATEGORY_LABELS, Hit
from utilities.redact_pdf import redact_pdf_with_hits, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("Redactor-API (v1.4.3)")

RESULT_HEIGHT_PX = 600

# -----------------------
# Session defaults
# -----------------------
st.session_state.setdefault("file_bytes", None)
st.session_state.setdefault("ext", ".pdf")
st.session_state.setdefault("hits", [])  # List[Hit]
st.session_state.setdefault("id_to_hit", {})  # Dict[int, Hit]
st.session_state.setdefault("selected_hit_ids", set())  # Set[int]
st.session_state.setdefault("collapsed", {})  # Dict[str, bool]

# -----------------------
# Upload
# -----------------------
uploaded_file = st.file_uploader("Upload PDF/DOCX/TXT", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()
    _, ext = os.path.splitext(uploaded_file.name)
    st.session_state.ext = ext.lower()
    # reset any previous scan results (keep user choices separate)
    st.session_state.hits = []
    st.session_state.id_to_hit = {}
    st.session_state.selected_hit_ids = set()
    st.session_state.collapsed = {}

# -----------------------
# Category selection (scan parameters)
# -----------------------
st.subheader("Select categories to scan (for the next Scan)")
category_keys = list(CATEGORY_LABELS.keys())
cols = st.columns(2)
for i, k in enumerate(category_keys):
    if f"param_{k}" not in st.session_state:
        st.session_state[f"param_{k}"] = False
    with cols[i % 2]:
        st.checkbox(CATEGORY_LABELS[k], key=f"param_{k}")

custom_phrase = st.text_input("Custom phrase (optional)")

# -----------------------
# Scan
# -----------------------
if st.button("Scan for Redacted Phrases") and st.session_state.file_bytes:
    # build list of categories to search
    sel = [k for k in category_keys if st.session_state.get(f"param_{k}", False)]
    if custom_phrase and custom_phrase.strip():
        sel.append("custom")

    found = extract_text_and_positions(st.session_state.file_bytes, st.session_state.ext, sel, custom_phrase if custom_phrase else None)

    # sort by page then start (None -> large)
    found.sort(key=lambda h: (h.page, h.start if getattr(h, "start", None) is not None else 1_000_000))

    # store hits and stable integer ids
    st.session_state.hits = found
    st.session_state.id_to_hit = {i: h for i, h in enumerate(found)}
    # default: all selected
    st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())

    # init collapsed states for categories present
    for k in category_keys:
        st.session_state.collapsed.setdefault(k, False)

# -----------------------
# Results + Preview (side by side; same height)
# -----------------------
if st.session_state.hits:
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("<h3>Redacted Phrases</h3>", unsafe_allow_html=True)

        # Styles - keep conservative and safe
        st.markdown(
            f"""
            <style>
            .left-scroll {{
                max-height: {RESULT_HEIGHT_PX}px;
                overflow-y: auto;
                padding: 8px;
                border: 1px solid #e6e6e6;
                border-radius: 8px;
                background: #fff;
            }}
            .cat-row {{
                display:flex;
                align-items:center;
                gap:8px;
                padding:6px 4px;
            }}
            .cat-label {{
                font-weight:700;
            }}
            .child-item {{
                margin-left:28px;
                padding:4px 2px;
            }}
            .select-all-btn {{
                margin-top:8px;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

        # open scroll container
        st.markdown('<div class="left-scroll">', unsafe_allow_html=True)

        # group hits by category, preserving the order they were found
        grouped: Dict[str, List[int]] = {}
        for idx, h in st.session_state.id_to_hit.items():
            grouped.setdefault(h.category, []).append(idx)

        # iterate in the order of categories that exist (user-friendly: use CATEGORY_LABELS order)
        for cat in category_keys:
            if cat not in grouped:
                continue
            idxs = grouped[cat]
            color = CATEGORY_COLORS.get(cat, "#111111")

            # compute default parent state (all children selected?)
            default_parent = all(st.session_state.get(f"hit_{i}", (i in st.session_state.selected_hit_ids)) for i in idxs)
            parent_key = f"cat_chk_{cat}"
            # set default before widget instantiation (avoids race warnings)
            st.session_state.setdefault(parent_key, default_parent)
            # parent checkbox: no visible label (we will render the colored label separately)
            _ = st.checkbox(" ", key=parent_key, label_visibility="collapsed")
            parent_val = st.session_state[parent_key]

            # render the category label (colored & bold) next to the checkbox
            st.markdown(f'<div class="cat-row"><div style="color:{color};font-weight:700">{CATEGORY_LABELS.get(cat,cat)}</div></div>', unsafe_allow_html=True)

            # collapse toggle (simple checkbox used as toggle; label visible as "Collapse")
            collapse_key = f"collapse_{cat}"
            st.session_state.setdefault(collapse_key, st.session_state.collapsed.get(cat, False))
            _ = st.checkbox("Collapse", key=collapse_key)  # label visible (user can see)
            st.session_state.collapsed[cat] = st.session_state[collapse_key]

            # sync parent -> children BEFORE creating child widgets
            if parent_val:
                for i in idxs:
                    st.session_state[f"hit_{i}"] = True
            else:
                for i in idxs:
                    # only set default if not present to avoid overwriting recent user interaction
                    st.session_state.setdefault(f"hit_{i}", False)

            # render children (indented)
            if not st.session_state.collapsed[cat]:
                for i in idxs:
                    h = st.session_state.id_to_hit[i]
                    child_key = f"hit_{i}"
                    # ensure default exists before creating the widget
                    st.session_state.setdefault(child_key, (i in st.session_state.selected_hit_ids))
                    # create the checkbox (label is the phrase + small page meta)
                    checkbox_label = f"{h.text}  (p{h.page+1})"
                    _ = st.checkbox(checkbox_label, key=child_key)
            # end category

        # bottom: Select / Deselect All for the results (affects all child checkboxes)
        def toggle_select_deselect_all_results():
            all_ids = list(st.session_state.id_to_hit.keys())
            if not all_ids:
                return
            # if all hit_x keys True -> deselect all; else select all
            if all(st.session_state.get(f"hit_{i}", False) for i in all_ids):
                for i in all_ids:
                    st.session_state[f"hit_{i}"] = False
            else:
                for i in all_ids:
                    st.session_state[f"hit_{i}"] = True

        st.button("Select / Deselect All (Results)", on_click=toggle_select_deselect_all_results)

        # close scroll container
        st.markdown('</div>', unsafe_allow_html=True)

        # AFTER all widgets created: derive selected_hit_ids from child widget states (stable source of truth)
        new_selected: Set[int] = set()
        for key, val in st.session_state.items():
            if key.startswith("hit_"):
                try:
                    idx = int(key.split("_", 1)[1])
                except Exception:
                    continue
                if val:
                    new_selected.add(idx)
        st.session_state.selected_hit_ids = new_selected

        # Download (destructive black-box)
        if st.button("Download Redacted PDF"):
            selected = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
            out = redact_pdf_with_hits(st.session_state.file_bytes, selected, preview_mode=False)
            st.download_button("Save redacted.pdf", data=out, file_name="redacted.pdf")

    # Right column: preview (same height)
    with right_col:
        st.markdown("<h3>Preview</h3>", unsafe_allow_html=True)
        selected = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
        if selected:
            preview_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected, preview_mode=True)
            b64 = base64.b64encode(preview_bytes).decode("utf-8")
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{RESULT_HEIGHT_PX}px"></iframe>', unsafe_allow_html=True)
        else:
            st.info("No phrases selected — select items on the left to preview.")
