import os
import io
import base64
import tempfile
import streamlit as st
from typing import List, Set
from utilities.extract_text import extract_text_and_positions, Hit, CATEGORY_LABELS
from utilities.redact_pdf import redact_pdf_with_hits, save_masked_file, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("PDF / Document Redactor Tool")

# --- Session State Setup ---
if "params" not in st.session_state:
    st.session_state.params = {k: True for k in CATEGORY_LABELS.keys()}
if "custom_phrases" not in st.session_state:
    st.session_state.custom_phrases: List[str] = []
if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit = {}
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()
if "input_path" not in st.session_state:
    st.session_state.input_path = None
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None

# --- File Uploader ---
uploaded_file = st.file_uploader("Upload a PDF, DOCX, or TXT file", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.read()
    ext = os.path.splitext(uploaded_file.name)[1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(st.session_state.file_bytes)
        st.session_state.input_path = tmp.name

    # --- Parameter Checkboxes (2-column layout) ---
    col1, col2 = st.columns(2)
    for i, (key, label) in enumerate(CATEGORY_LABELS.items()):
        target = col1 if i % 2 == 0 else col2
        st.session_state.params[key] = target.checkbox(
            label, value=st.session_state.params[key], key=f"param_{key}"
        )

    # --- Custom Phrases ---
    custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type a phrase and hit Enter")
    if custom_phrase:
        if custom_phrase not in st.session_state.custom_phrases:
            st.session_state.custom_phrases.append(custom_phrase)

    if st.session_state.custom_phrases:
        st.write("Custom phrases to redact:")
        st.write(", ".join(st.session_state.custom_phrases))

    # --- Scan Button ---
    if st.button("Scan for Redacted Phrases"):
        hits = extract_text_and_positions(
            st.session_state.input_path,
            st.session_state.params,
            st.session_state.custom_phrases,
        )
        st.session_state.hits = hits
        st.session_state.id_to_hit = {hit.page * 1_000_000 + i: hit for i, hit in enumerate(hits)}
        st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())

    # --- Results ---
    if st.session_state.hits:
        st.subheader("Redacted Phrases")
        left_col, right_col = st.columns([1, 2])

        with left_col:
            if st.button("Deselect All"):
                st.session_state.selected_hit_ids.clear()
            if st.button("Select All"):
                st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())

            hits_html = "<div style='max-height:400px; overflow-y:scroll; padding:5px;'>"
            for hid, hit in st.session_state.id_to_hit.items():
                color = CATEGORY_COLORS.get(hit.category, "#000000")
                checked = "checked" if hid in st.session_state.selected_hit_ids else ""
                hits_html += (
                    f"<div style='margin-bottom:4px;'>"
                    f"<input type='checkbox' id='chk_{hid}' {checked}> "
                    f"<label for='chk_{hid}' style='color:{color}; font-weight:500;'>"
                    f"{hit.text}</label></div>"
                )
            hits_html += "</div>"
            st.markdown(hits_html, unsafe_allow_html=True)

            if st.session_state.input_path and st.session_state.selected_hit_ids:
                hits_to_redact = [st.session_state.id_to_hit[i] for i in st.session_state.selected_hit_ids]
                if ext == ".pdf":
                    out_bytes = redact_pdf_with_hits(st.session_state.input_path, hits_to_redact, preview_mode=False)
                else:
                    out_bytes = save_masked_file(st.session_state.file_bytes, ext, hits_to_redact)
                st.download_button("Click to Download", data=out_bytes, file_name=f"redacted{ext}")

        with right_col:
            st.subheader("Preview")
            if st.session_state.selected_hit_ids:
                hits_to_redact = [st.session_state.id_to_hit[i] for i in st.session_state.selected_hit_ids]
                preview_bytes = redact_pdf_with_hits(st.session_state.input_path, hits_to_redact, preview_mode=True)
                b64 = base64.b64encode(preview_bytes).decode()
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600"></iframe>',
                    unsafe_allow_html=True,
                )
