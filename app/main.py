import streamlit as st
from utilities.redact_pdf import process_pdf, redact_pdf_phrases
import os
import tempfile

st.set_page_config(page_title="PDF Redactor", layout="wide")

# Session state setup
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "redacted_phrases" not in st.session_state:
    st.session_state.redacted_phrases = []
if "selected_phrases" not in st.session_state:
    st.session_state.selected_phrases = []
if "processed_pdf" not in st.session_state:
    st.session_state.processed_pdf = None

st.title("PDF Redactor Tool")

# Step 1: Upload PDF
uploaded_file = st.file_uploader("Upload your PDF", type=["pdf"])
if uploaded_file:
    st.session_state.uploaded_file = uploaded_file

# Only continue if file uploaded
if st.session_state.uploaded_file:
    # Step 2: Process PDF to detect sensitive info
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_input:
        tmp_input.write(st.session_state.uploaded_file.read())
        tmp_input_path = tmp_input.name

    detected_phrases = process_pdf(tmp_input_path)
    st.session_state.redacted_phrases = detected_phrases

    # Step 3: Selection UI
    st.subheader("Select phrases to redact")
    select_all = st.checkbox("Select All", value=True)

    if select_all:
        st.session_state.selected_phrases = detected_phrases.copy()
    else:
        st.session_state.selected_phrases = []

    # Scrollable phrase list
    with st.container():
        st.markdown(
            """
            <style>
            .scroll-box {
                max-height: 300px;
                overflow-y: auto;
                border: 1px solid #ccc;
                padding: 10px;
                background-color: transparent;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.markdown('<div class="scroll-box">', unsafe_allow_html=True)
        for phrase in detected_phrases:
            checked = select_all or (phrase in st.session_state.selected_phrases)
            if st.checkbox(phrase, value=checked, key=f"chk_{phrase}"):
                if phrase not in st.session_state.selected_phrases:
                    st.session_state.selected_phrases.append(phrase)
            else:
                if phrase in st.session_state.selected_phrases:
                    st.session_state.selected_phrases.remove(phrase)
        st.markdown('</div>', unsafe_allow_html=True)

    # Step 4: Redact button
    if st.button("Apply Redactions"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_output:
            redact_pdf_phrases(tmp_input_path, st.session_state.selected_phrases, tmp_output.name)
            st.session_state.processed_pdf = tmp_output.name
        st.rerun()

# Step 5: Show Preview and Download
if st.session_state.processed_pdf:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Preview (Redacted)")
        st.markdown(
            """
            <style>
            .highlight {
                background-color: rgba(128, 128, 128, 0.4);
                transition: background-color 0.3s;
            }
            .highlight:hover {
                background-color: yellow;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        with open(st.session_state.processed_pdf, "rb") as f:
            st.download_button("Download Redacted PDF", f, file_name="redacted.pdf")

    with col2:
        st.subheader("Redacted Phrases")
        for phrase in st.session_state.selected_phrases:
            st.markdown(f"<span class='highlight'>{phrase}</span>", unsafe_allow_html=True)
