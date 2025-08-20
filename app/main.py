import os
import io
import base64
import tempfile
import streamlit as st
from typing import List
from utilities.extract_text import extract_text_and_positions, Hit, CATEGORY_LABELS
from utilities.redact_pdf import redact_pdf_with_hits, save_masked_file, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("PDF Redactor Tool")

# Initialize session state
if "params" not in st.session_state:
    st.session_state.params = {k: False for k in CATEGORY_LABELS.keys()}
if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit = {}
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids = set()
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None
if "file_name" not in st.session_state:
    st.session_state.file_name = None
if "input_path" not in st.session_state:
    st.session_state.input_path = None

uploaded_file = st.file_uploader("Upload a file (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.read()
    st.session_state.file_name = uploaded_file.name
    ext = os.path.splitext(uploaded_file.name)[1].lower()

    if ext == ".pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(st.session_state.file_bytes)
            st.session_state.input_path = tmp.name

# --- Select redaction parameters ---
if uploaded_file:
    st.subheader("Select Redaction Parameters")
    col1, col2 = st.columns(2)
    for i, (key, label) in enumerate(CATEGORY_LABELS.items()):   # FIXED order
        target = col1 if i % 2 == 0 else col2
        st.session_state.params[key] = target.checkbox(
            label, value=st.session_state.params[key], key=f"param_{key}"
        )

    if st.button("Select All Parameters"):
        for key in CATEGORY_LABELS.keys():
            st.session_state.params[key] = True

    # Custom phrase input
    custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type phrase here")
    if custom_phrase:
        st.session_state.params["custom"] = True

    # Scan button
    if st.button("Scan for Redacted Phrases"):
        hits = extract_text_and_positions(st.session_state.file_bytes, ext, st.session_state.params, custom_phrase)
        unique_hits = {(h.page, h.rect, h.text, h.category): h for h in hits}  # dedup
        st.session_state.hits = list(unique_hits.values())
        st.session_state.id_to_hit = {i: h for i, h in enumerate(st.session_state.hits)}
        st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())

# --- Redacted phrases list ---
if st.session_state.hits:
    st.subheader("Redacted Phrases")

    if st.button("Deselect All Phrases"):
        st.session_state.selected_hit_ids.clear()

    with st.container():
        st.markdown(
            """
            <style>
            .scroll-box {
                max-height: 250px;
                overflow-y: auto;
                border: 1px solid #ddd;
                padding: 6px;
                border-radius: 6px;
                background: #fafafa;
            }
            .hit-item {
                padding: 3px 6px;
                margin: 2px 0;
                border-radius: 4px;
                font-size: 14px;
                font-family: monospace;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        html_hits = ["<div class='scroll-box'>"]
        for i, hit in st.session_state.id_to_hit.items():
            checked = i in st.session_state.selected_hit_ids
            color = CATEGORY_COLORS.get(hit.category, "#cccccc")
            hit_label = f"{hit.text}"
            checkbox_html = f"""
                <div class="hit-item" style="background:{color}30;border:1px solid {color};">
                    <input type="checkbox" id="hit_{i}" {'checked' if checked else ''} 
                        onclick="fetch('/_update', {{method:'POST',body:'{i}'}})">
                    <label for="hit_{i}">{hit_label} (page {hit.page+1})</label>
                </div>
            """
            html_hits.append(checkbox_html)
        html_hits.append("</div>")
        st.markdown("".join(html_hits), unsafe_allow_html=True)

    selected_ids = list(st.session_state.selected_hit_ids)
    hits_to_redact = [st.session_state.id_to_hit[i] for i in selected_ids]

    # Preview
    if st.session_state.input_path and hits_to_redact:
        with tempfile.TemporaryDirectory() as temp_dir:
            preview_pdf_path = os.path.join(temp_dir, "preview.pdf")
            redact_pdf_with_hits(st.session_state.input_path, hits_to_redact, preview_pdf_path, preview_mode=True)
            with open(preview_pdf_path, "rb") as f:
                b64_pdf = base64.b64encode(f.read()).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="500"></iframe>',
                unsafe_allow_html=True,
            )

    # Download
    st.subheader("Download Redacted File")
    if ext == ".pdf":
        if st.button("Download PDF"):
            out_bytes = redact_pdf_with_hits(
                st.session_state.input_path, hits_to_redact, preview_mode=False
            )
            st.download_button(
                "Click to Download",
                data=out_bytes,
                file_name="redacted.pdf",
                mime="application/pdf",
            )
    else:
        if st.button("Download File"):
            out_bytes = save_masked_file(st.session_state.file_bytes, ext, hits_to_redact)
            st.download_button(
                "Click to Download",
                data=out_bytes,
                file_name=f"redacted{ext}",
                mime="application/octet-stream",
            )
