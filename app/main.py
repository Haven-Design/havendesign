import streamlit as st
from utilities.redact_pdf import PDFRedactor
import fitz  # PyMuPDF
import base64
import os

st.set_page_config(layout="wide")

st.title("🔒 PDF Redactor")

# Sidebar
st.sidebar.header("Redaction Settings")

redaction_options = {
    "Names": False,
    "Emails": False,
    "Phone Numbers": False,
    "Dates": False,
    "Addresses": False,
    "Organizations": False,
    "SSNs": False,
    "Credit Card Numbers": False,
}

select_all = st.sidebar.checkbox("Select All")

for key in redaction_options:
    redaction_options[key] = st.sidebar.checkbox(key, value=select_all)

# File uploader
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    doc = PDFRedactor(pdf_bytes)
    doc.set_redaction_targets(redaction_options)

    st.subheader("📄 Preview")
    preview_tabs = st.tabs([f"Page {i+1}" for i in range(doc.page_count())])

    preview_images = doc.get_preview_images()
    for i, tab in enumerate(preview_tabs):
        with tab:
            st.image(preview_images[i], use_column_width=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔍 Redact PDF"):
            try:
                doc.apply_redactions()
                st.success("Redaction applied successfully.")
            except Exception as e:
                st.error(f"Redaction failed: {str(e)}")

    with col2:
        if doc.redacted_pdf:
            b64 = base64.b64encode(doc.redacted_pdf).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="redacted.pdf">📥 Download Redacted PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
