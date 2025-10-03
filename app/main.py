"""
main.py (v1.5)

Stable UI focused on correctness:
- Parent checkbox toggles children.
- Child checkboxes are authoritative; selected set is derived after widgets are created.
- Per-category collapse implemented with native checkbox (starts expanded).
- Select / Deselect All (Results) button at the bottom.
- Preview updates reliably and download redacts exactly selected items.
"""

import os
import base64
from typing import List, Dict, Set

import streamlit as st

from utilities.extract_text import extract_text_and_positions, CATEGORY_LABELS, CATEGORY_COLORS, Hit
from utilities.redact_pdf import redact_pdf_with_hits

st.set_page_config(layout="wide")
st.title("Redactor-API (v1.5)")

RESULT_HEIGHT_PX = 600

# session defaults
st.session_state.setdefault("file_bytes", None)
st.session_state.setdefault("ext", ".pdf")
st.session_state.setdefault("hits", [])
st.session_state.setdefault("id_to_hit", {})
st.session_state.setdefault("selected_hit_ids", set())
st.session_state.setdefault("collapsed", {})

# upload
uploaded_file = st.file_uploader("Upload PDF/DOCX/TXT", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()
    _, ext = os.path.splitext(uploaded_file.name)
    st.session_state.ext = ext.lower()
    # reset previous results
    st.session_state.hits = []
    st.session_state.id_to_hit = {}
    st.session_state.selected_hit_ids = set()
    st.session_state.collapsed = {}

# selection parameters for scanning
st.subheader("Select categories to scan (for the next Scan)")
category_keys = list(CATEGORY_LABELS.keys())
cols = st.columns(2)
for i, k in enumerate(category_keys):
    if f"param_{k}" not in st.session_state:
        st.session_state[f"param_{k}"] = False
    with cols[i % 2]:
        st.checkbox(CATEGORY_LABELS[k], key=f"param_{k}")

custom_phrase = st.text_input("Custom phrase (optional)")

# scan
if st.button("Scan for Redacted Phrases") and st.session_state.file_bytes:
    selected_categories = [k for k in category_keys if st.session_state.get(f"param_{k}", False)]
    if custom_phrase and custom_phrase.strip():
        selected_categories.append("custom")

    found = extract_text_and_positions(st.session_state.file_bytes, st.session_state.ext, selected_categories, custom_phrase if custom_phrase else None)
    found.sort(key=lambda h: (h.page, h.start if getattr(h, "start", None) is not None else 1_000_000))

    st.session_state.hits = found
    st.session_state.id_to_hit = {i: h for i, h in enumerate(found)}
    # default: select all hits
    st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())
    # default: expanded
    for k in category_keys:
        st.session_state.collapsed.setdefault(k, False)

# render results + preview side-by-side
if st.session_state.hits:
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("<h3>Redacted Phrases</h3>", unsafe_allow_html=True)

        # small CSS to visually contain results and match preview height
        st.markdown(
            f"""
            <style>
            .results-box {{
                max-height: {RESULT_HEIGHT_PX}px;
                overflow-y: auto;
                padding: 8px;
                border: 1px solid #e6e6e6;
                border-radius: 8px;
                background: #fff;
            }}
            .cat-row {{ display:flex; align-items:center; gap:8px; padding:6px 2px; }}
            .cat-label {{ font-weight:700; }}
            .child-item {{ margin-left: 28px; padding: 4px 2px; }}
            .bottom-row {{ margin-top:8px; text-align:center; }}
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="results-box">', unsafe_allow_html=True)

        # group hits by category preserving order
        grouped: Dict[str, List[int]] = {}
        for idx, h in st.session_state.id_to_hit.items():
            grouped.setdefault(h.category, []).append(idx)

        # build UI by canonical category order
        for cat in category_keys:
            if cat not in grouped:
                continue
            idxs = grouped[cat]
            color = CATEGORY_COLORS.get(cat, "#111111")

            # parent checkbox key: set default BEFORE creating the checkbox
            parent_key = f"cat_chk_{cat}"
            default_parent = all(st.session_state.get(f"hit_{i}", True) for i in idxs)
            st.session_state.setdefault(parent_key, default_parent)

            # create a single-row layout for the category header:
            c1, c2, c3 = st.columns([0.06, 0.78, 0.16])
            with c1:
                # create parent checkbox (no visible label)
                _ = st.checkbox(" ", key=parent_key, label_visibility="collapsed")
            with c2:
                # colored bold label inline
                st.markdown(f'<div class="cat-row"><span class="cat-label" style="color:{color}">{CATEGORY_LABELS.get(cat,cat)}</span></div>', unsafe_allow_html=True)
            with c3:
                # collapse toggle (native checkbox used as a toggle; starts expanded)
                collapse_key = f"collapse_{cat}"
                st.session_state.setdefault(collapse_key, st.session_state.collapsed.get(cat, False))
                _ = st.checkbox("Collapse", key=collapse_key)  # visible label
                st.session_state.collapsed[cat] = st.session_state[collapse_key]

            # sync parent -> children defaults BEFORE creating child widgets
            parent_val = st.session_state[parent_key]
            if parent_val:
                for i in idxs:
                    st.session_state[f"hit_{i}"] = True
            else:
                for i in idxs:
                    st.session_state.setdefault(f"hit_{i}", False)

            # render children indented (if not collapsed)
            if not st.session_state.collapsed[cat]:
                for i in idxs:
                    h = st.session_state.id_to_hit[i]
                    child_key = f"hit_{i}"
                    st.session_state.setdefault(child_key, (i in st.session_state.selected_hit_ids))
                    # label includes small page metadata
                    label = f"{h.text}  (p{h.page+1})"
                    _ = st.checkbox(label, key=child_key)

        st.markdown("</div>", unsafe_allow_html=True)

        # bottom: Select/Deselect All (Results)
        def toggle_select_all_results():
            all_ids = list(st.session_state.id_to_hit.keys())
            if not all_ids:
                return
            if all(st.session_state.get(f"hit_{i}", False) for i in all_ids):
                for i in all_ids:
                    st.session_state[f"hit_{i}"] = False
            else:
                for i in all_ids:
                    st.session_state[f"hit_{i}"] = True

        st.button("Select / Deselect All (Results)", on_click=toggle_select_all_results)

        # after all widgets created: derive selected_hit_ids from hit_{i} keys (authoritative)
        new_selected: Set[int] = set()
        for k, v in st.session_state.items():
            if k.startswith("hit_"):
                try:
                    i = int(k.split("_", 1)[1])
                except Exception:
                    continue
                if v:
                    new_selected.add(i)
        st.session_state.selected_hit_ids = new_selected

        # download (final destructive black-box redaction)
        if st.button("Download Redacted PDF"):
            selected = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
            out = redact_pdf_with_hits(st.session_state.file_bytes, selected, preview_mode=False)
            st.download_button("Save redacted.pdf", data=out, file_name="redacted.pdf")

    # RIGHT column: preview (same height)
    with right_col:
        st.markdown("<h3>Preview</h3>", unsafe_allow_html=True)
        selected = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
        if selected:
            preview_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected, preview_mode=True)
            b64 = base64.b64encode(preview_bytes).decode("utf-8")
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{RESULT_HEIGHT_PX}px"></iframe>', unsafe_allow_html=True)
        else:
            st.info("No phrases selected — select items on the left to preview.")
