import os
import io
import base64
import tempfile
import streamlit as st
from typing import List

from utilities.extract_text import (
    Hit,
    CATEGORY_LABELS,
    CATEGORY_COLORS,
    extract_hits_from_file,
)
from utilities.redact_pdf import (
    make_preview_pdf_with_colored_overlays,
    make_final_blackfilled_pdf,
    mask_text_like_file,
    CATEGORY_COLORS,
)

st.set_page_config(layout="wide")
st.title("PDF / TXT / DOCX Redactor Tool")

temp_dir = tempfile.mkdtemp()

if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit = {}
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids = set()
if "input_path" not in st.session_state:
    st.session_state.input_path = None
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None

# --- Redaction Parameters ---
st.subheader("Select Redaction Parameters")
col1, col2 = st.columns(2)

if "params" not in st.session_state:
    st.session_state.params = {key: False for key in CATEGORY_LABELS.keys()}

col1.button("Select All", on_click=lambda: st.session_state.params.update({k: True for k in st.session_state.params}))
col2.button("Deselect All", on_click=lambda: st.session_state.params.update({k: False for k in st.session_state.params}))

for i, (label, key) in enumerate(CATEGORY_LABELS.items()):
    target = col1 if i % 2 == 0 else col2
    st.session_state.params[key] = target.checkbox(
        label, value=st.session_state.params[key], key=f"param_{key}"
    )

custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type phrase and press Enter")
if custom_phrase:
    st.session_state.params[custom_phrase] = True

# --- Scan button ---
uploaded_file = st.file_uploader("Upload a file", type=["pdf", "txt", "docx"])
if st.button("Scan for Redacted Phrases") and uploaded_file:
    file_bytes = uploaded_file.getvalue()
    st.session_state.file_bytes = file_bytes
    ext = os.path.splitext(uploaded_file.name)[1].lower()

    if ext == ".pdf":
        input_path = os.path.join(temp_dir, "input.pdf")
        with open(input_path, "wb") as f:
            f.write(file_bytes)
        st.session_state.input_path = input_path
        hits = extract_hits_from_file(input_path, [k for k, v in st.session_state.params.items() if v])
    else:
        hits = extract_hits_from_file(io.BytesIO(file_bytes), [k for k, v in st.session_state.params.items() if v])

    # Deduplicate hits
    unique = {}
    for h in hits:
        key = (h.page, h.text, tuple(h.rect) if h.rect else None)
        if key not in unique:
            unique[key] = h
    hits = list(unique.values())

    st.session_state.hits = hits
    st.session_state.id_to_hit = {i: hit for i, hit in enumerate(hits)}
    st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())

# --- Results Section ---
if st.session_state.hits:
    st.markdown("### Redacted Phrases")

    left, right = st.columns([1, 2])

    with left:
        if st.button("Deselect All Phrases"):
            st.session_state.selected_hit_ids.clear()

        st.markdown(
            """
            <style>
            .scroll-box {
                max-height: 400px;
                overflow-y: auto;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        phrases_html = "<div class='scroll-box'>"
        for idx, hit in st.session_state.id_to_hit.items():
            checked = idx in st.session_state.selected_hit_ids
            color = CATEGORY_COLORS.get(hit.category, "#000000")
            cb = st.checkbox(
                f"{hit.text} (page {hit.page+1})",
                value=checked,
                key=f"hit_{idx}",
            )
            if cb:
                st.session_state.selected_hit_ids.add(idx)
            else:
                st.session_state.selected_hit_ids.discard(idx)

            phrases_html += f"<div style='color:{color}; margin-bottom:4px;'>{hit.text}</div>"

        phrases_html += "</div>"
        st.markdown(phrases_html, unsafe_allow_html=True)

        # Download button
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        selected_ids = st.session_state.selected_hit_ids
        hits_to_redact = [st.session_state.id_to_hit[i] for i in selected_ids]

        if ext == ".pdf":
            out_bytes = make_final_blackfilled_pdf(
                st.session_state["file_bytes"], hits_to_redact
            )
            st.download_button("Download Redacted PDF", data=out_bytes, file_name="redacted.pdf")
        else:
            out_bytes = mask_text_like_file(
                st.session_state["file_bytes"], ext, hits_to_redact
            )
            fname = "redacted" + ext
            st.download_button("Download Redacted File", data=out_bytes, file_name=fname)

    with right:
        st.markdown("### Preview")
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext == ".pdf":
            selected_ids = st.session_state.selected_hit_ids
            hits_to_redact = [st.session_state.id_to_hit[i] for i in selected_ids]
            preview_bytes = make_preview_pdf_with_colored_overlays(
                st.session_state["file_bytes"], hits_to_redact
            )
            b64_pdf = base64.b64encode(preview_bytes).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="500px"></iframe>',
                unsafe_allow_html=True,
            )
        else:
            st.write("Preview available only for PDF files.")
