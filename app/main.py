import os
import io
import base64
import tempfile
from typing import List, Dict, Set, Tuple

import streamlit as st
import pandas as pd

from utilities.extract_text import (
    extract_text_and_positions,
    Hit,
    CATEGORY_LABELS,
    CATEGORY_COLORS,
)
from utilities.redact_pdf import redact_pdf_with_hits, save_masked_file

st.set_page_config(layout="wide")
st.title("Redactor-API — PDF / DOCX / TXT")

# -----------------------
# Session state
# -----------------------
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes: bytes | None = None
if "file_name" not in st.session_state:
    st.session_state.file_name: str | None = None
if "ext" not in st.session_state:
    st.session_state.ext: str | None = None
if "input_pdf_path" not in st.session_state:
    st.session_state.input_pdf_path: str | None = None

if "params" not in st.session_state:
    st.session_state.params: Dict[str, bool] = {k: False for k in CATEGORY_LABELS.keys()}

if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()
if "phrases_df" not in st.session_state:
    st.session_state.phrases_df = pd.DataFrame()

# -----------------------
# Upload
# -----------------------
uploaded_file = st.file_uploader("Upload a file", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.read()
    st.session_state.file_name = uploaded_file.name
    st.session_state.ext = os.path.splitext(uploaded_file.name)[1].lower()

    # prepare a temporary pdf path if PDF
    st.session_state.input_pdf_path = None
    if st.session_state.ext == ".pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(st.session_state.file_bytes)
            st.session_state.input_pdf_path = tmp.name

# -----------------------
# Category selection
# -----------------------
if st.session_state.file_bytes:
    st.subheader("Select Categories to Redact")

    if st.button("Select All Categories"):
        for k in st.session_state.params.keys():
            st.session_state.params[k] = True
        st.rerun()

    col1, col2 = st.columns(2)
    for i, (key, label) in enumerate(CATEGORY_LABELS.items()):
        target = col1 if i % 2 == 0 else col2
        st.session_state.params[key] = target.checkbox(
            label,
            value=st.session_state.params.get(key, False),
            key=f"param_{key}",
        )

    custom_phrase = st.text_input(
        "Add a custom phrase to redact (optional)",
        placeholder="Type phrase here and press Enter",
    )

    # -----------------------
    # Scan
    # -----------------------
    if st.button("Scan for Redacted Phrases"):
        hits = extract_text_and_positions(
            st.session_state.file_bytes,
            st.session_state.ext,
            st.session_state.params,
            custom_phrase,
        )

        # Deduplicate conservatively by (page, start, end, category, text) where available
        uniq: Dict[Tuple, Hit] = {}
        for h in hits:
            key = (
                h.page,
                getattr(h, "start", None),
                getattr(h, "end", None),
                h.category,
                h.text,
            )
            if key[1] is None:
                key = (h.page, h.text, h.category)
            uniq[key] = h

        st.session_state.hits = list(uniq.values())
        st.session_state.id_to_hit = {i: h for i, h in enumerate(st.session_state.hits)}
        st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())

        # Build a scrollable, editable table (data_editor) for robust selection control
        rows = []
        for i, h in st.session_state.id_to_hit.items():
            rows.append(
                {
                    "id": i,
                    "keep": True,
                    "page": (h.page + 1) if h.page is not None else 1,
                    "category": CATEGORY_LABELS.get(h.category, h.category),
                    "text": h.text,
                }
            )
        st.session_state.phrases_df = pd.DataFrame(rows)

# -----------------------
# Results & Preview
# -----------------------
if len(st.session_state.hits) > 0:
    left, right = st.columns([1, 1])

    with left:
        st.markdown("### Redacted Phrases")

        # Legend to match preview colors
        with st.expander("Category legend", expanded=False):
            legend_cols = st.columns(3)
            items = list(CATEGORY_COLORS.items())
            for idx, (k, col) in enumerate(items):
                with legend_cols[idx % 3]:
                    st.markdown(
                        f"<div style='display:inline-block;width:12px;height:12px;background:{col};border-radius:3px;margin-right:6px;vertical-align:middle;'></div>"
                        f"<span style='vertical-align:middle;'>{CATEGORY_LABELS.get(k, k)}</span>",
                        unsafe_allow_html=True,
                    )

        btn_cols = st.columns(3)
        with btn_cols[0]:
            if st.button("Select All Phrases"):
                if not st.session_state.phrases_df.empty:
                    st.session_state.phrases_df["keep"] = True
        with btn_cols[1]:
            if st.button("Deselect All Phrases"):
                if not st.session_state.phrases_df.empty:
                    st.session_state.phrases_df["keep"] = False
        with btn_cols[2]:
            st.caption("Tip: toggle rows in the table below.")

        # Editable, scrollable selection table
        if not st.session_state.phrases_df.empty:
            edited = st.data_editor(
                st.session_state.phrases_df,
                num_rows="fixed",
                use_container_width=True,
                height=380,
                hide_index=True,
                column_config={
                    "keep": st.column_config.CheckboxColumn("keep"),
                    "page": st.column_config.NumberColumn("page", format="%d"),
                    "category": st.column_config.TextColumn("category"),
                    "text": st.column_config.TextColumn("text"),
                    "id": st.column_config.NumberColumn("id", help="internal id", width="small"),
                },
            )
            # Persist changes and rebuild selected ids from the table state
            st.session_state.phrases_df = edited.copy()
            st.session_state.selected_hit_ids = set(
                edited.loc[edited["keep"] == True, "id"].astype(int).tolist()
            )
        else:
            st.info("No phrases found with the current selection.")

        # Download
        selected_hits = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
        st.markdown("### Download")
        if st.session_state.ext == ".pdf":
            if st.session_state.input_pdf_path and selected_hits:
                out_bytes = redact_pdf_with_hits(
                    st.session_state.input_pdf_path, selected_hits, preview_mode=False
                )
                st.download_button(
                    "Download Redacted PDF",
                    data=out_bytes,
                    file_name="redacted.pdf",
                    mime="application/pdf",
                )
            else:
                st.info("Select at least one phrase to enable PDF download.")
        else:
            if selected_hits:
                out_bytes = save_masked_file(
                    st.session_state.file_bytes, st.session_state.ext, selected_hits
                )
                out_name = f"redacted{st.session_state.ext}"
                st.download_button(
                    "Download Redacted File",
                    data=out_bytes,
                    file_name=out_name,
                    mime="application/octet-stream",
                )
            else:
                st.info("Select at least one phrase to enable download.")

    with right:
        st.markdown("### Preview")
        selected_hits = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]

        if st.session_state.ext == ".pdf" and st.session_state.input_pdf_path:
            if selected_hits:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    preview_path = tmp.name
                redact_pdf_with_hits(
                    st.session_state.input_pdf_path,
                    selected_hits,
                    output_path=preview_path,
                    preview_mode=True,
                )
                with open(preview_path, "rb") as f:
                    b64_pdf = base64.b64encode(f.read()).decode("utf-8")
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="560"></iframe>',
                    unsafe_allow_html=True,
                )
            else:
                st.info("No phrases selected.")
        else:
            if st.session_state.file_bytes and selected_hits:
                masked = save_masked_file(
                    st.session_state.file_bytes, st.session_state.ext, selected_hits
                )
                try:
                    preview_text = masked.decode("utf-8")
                except Exception:
                    preview_text = "(Preview unavailable for this file type.)"
                st.text_area("Masked Preview", value=preview_text, height=560)
            else:
                st.info("No phrases selected.")
