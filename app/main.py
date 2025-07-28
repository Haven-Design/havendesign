import streamlit as st
import tempfile
import os
from utilities.redact_pdf import redact_pdf

st.set_page_config(page_title="PDF Redactor", layout="wide")

st.title("PDF Redactor")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

st.markdown("### Select what to redact:")

options = [
    "Names",
    "Addresses",
    "Dates",
    "Phone Numbers",
    "Numbers",
    "SSNs",
    "Credit Card Numbers",
]

all_selected = st.checkbox("Select All")

if all_selected:
    selected_options = options
else:
    selected_options = [opt for opt in options if st.checkbox(opt)]

if uploaded_file and selected_options:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_input:
        tmp_input.write(uploaded_file.read())
        tmp_input_path = tmp_input.name

    with st.spinner("Redacting PDF..."):
        output_path = redact_pdf(tmp_input_path, selected_options)

    with open(output_path, "rb") as f:
        st.download_button(
            label="Download Redacted PDF",
            data=f,
            file_name="redacted.pdf",
            mime="application/pdf"
        )

    st.markdown("### Preview:")
    st.pdf(output_path, use_container_width=True)

    os.remove(tmp_input_path)
    os.remove(output_path)
elif uploaded_file and not selected_options:
    st.info("Please select at least one option to redact.")
