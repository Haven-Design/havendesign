import streamlit as st
import tempfile
import os
import base64
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

    # Render PDF Preview
    def show_pdf(file_path):
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600px" type="application/pdf"></iframe>'
        st.components.v1.html(pdf_display, height=620, scrolling=True)

    st.markdown("### Preview:")
    show_pdf(output_path)

    os.remove(tmp_input_path)
    os.remove(output_path)

elif uploaded_file and not selected_options:
    st.info("Please select at least one option to redact.")
