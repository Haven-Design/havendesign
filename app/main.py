import streamlit as st
import os
import tempfile
from utilities.extract_text import extract_text_with_positions
from utilities.redact_pdf import redact_pdf_with_positions

# Streamlit page config
st.set_page_config(page_title="PDF Redactor", layout="wide")

# Sidebar checkboxes for sensitive info
st.sidebar.header("Redaction Options")
patterns = {
    "Email Addresses": r"[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+",
    "Phone Numbers": r"\b\d{3}[-.\s]??\d{3}[-.\s]??\d{4}\b",
    "Credit Card Numbers": r"\b(?:\d[ -]*?){13,16}\b",
    "Social Security Numbers": r"\b\d{3}-\d{2}-\d{4}\b",
    "Driver's Licenses": r"\b[A-Z]{1,2}\d{6,8}\b",
}
selected_patterns = {name: st.sidebar.checkbox(name) for name in patterns.keys()}

# File uploader
uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")

# Custom phrase input
custom_phrase = st.text_input("Add a custom phrase to redact:")
custom_phrases = st.session_state.get("custom_phrases", [])

if st.button("Add Phrase"):
    if custom_phrase.strip():
        custom_phrases.append(custom_phrase.strip())
        st.session_state["custom_phrases"] = custom_phrases

# Show list of phrases
st.write("### Redacted Phrases:")
for phrase in custom_phrases:
    st.write(f"- {phrase}")

# Process PDF when file is uploaded
if uploaded_file:
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, uploaded_file.name)
    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    # Extract text & positions
    positions = extract_text_with_positions(
        input_path,
        [patterns[k] for k, v in selected_patterns.items() if v],
        custom_phrases
    )

    # Show preview
    st.write("### Preview")
    preview_pdf_path = os.path.join(temp_dir, "preview.pdf")
    redact_pdf_with_positions(input_path, positions, preview_pdf_path)
    with open(preview_pdf_path, "rb") as f:
        st.download_button("Download PDF", f, file_name="redacted.pdf")

