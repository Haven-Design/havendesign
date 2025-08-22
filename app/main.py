import os
import io
import base64
import tempfile
from typing import List, Dict, Set, Tuple

import streamlit as st

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
    # all categories default to False
    st.session_state.params: Dict[str, bool] = {k: False for k in CATEGORY_LABELS.keys()}

if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()

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

    # Select All button — set first, then trigger a rerun so checkboxes show as checked immediately
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
        # Deduplicate by (page, start, end, category, text) when available; fall back to (page, text, category)
        uniq: Dict[Tuple, Hit] = {}
        for h in hits:
            key = (
                h.page,
                getattr(h, "start", None),
                getattr(h, "end", None),
                h.category,
                h.text,
            )
            if key[1] is None:  # no offsets for DOCX/TXT
                key = (h.page, h.text, h.category)
            uniq[key] = h

        st.session_state.hits = list(uniq.values())
        st.session_state.id_to_hit = {i: h for i, h in enumerate(st.session_state.hits)}
        st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())

# -----------------------
# Results & Preview
# -----------------------
if st.session_state.hits:
    left, right = st.columns([1, 1])

    with left:
        st.markdown("### Redacted Phrases")
        st.caption("Uncheck any phrase to exclude it from the preview and download.")

        if st.button("Deselect All Phrases"):
            st.session_state.selected_hit_ids.clear()

        # Scrollable list of phrases with real Streamlit checkboxes (so they sync state)
        # We'll group by category for color-coding badges
        st.markdown(
            """
            <style>
            .scrollbox {max-height: 360px; overflow-y: auto; border: 1px solid #ddd; padding: 8px; border-radius: 8px; background: #fafafa;}
            .pill {display:inline-block; padding:2px 6px; border-radius:999px; font-size:12px; margin-right:6px;}
            </style>
            """,
            unsafe_allow_html=True,
        )
        with st.container():
            st.markdown("<div class='scrollbox'>", unsafe_allow_html=True)
            for i, h in st.session_state.id_to_hit.items():
                color = CATEGORY_COLORS.get(h.category, "#cccccc")
                pill = f"<span class='pill' style='background:{color}33;border:1px solid {color};'>{h.category}</span>"
                label_html = f"{pill} [p{(h.page + 1) if h.page is not None else 1}] {h.text}"
                # Use checkbox per-hit; toggling updates selection immediately
                checked = i in st.session_state.selected_hit_ids
                new_val = st.checkbox(
                    label=label_html,
                    value=checked,
                    key=f"hit_{i}",
                    help=f"{CATEGORY_LABELS.get(h.category, h.category)}",
                )
                if new_val:
                    st.session_state.selected_hit_ids.add(i)
                else:
                    st.session_state.selected_hit_ids.discard(i)
            st.markdown("</div>", unsafe_allow_html=True)

        # Download buttons under list
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
        if st.session_state.ext == ".pdf" and st.session_state.input_pdf_path:
            # live PDF preview
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
            # For DOCX/TXT, show a masked text preview
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
