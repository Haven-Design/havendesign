import streamlit as st
from app.utilities.extract_text import extract_text_from_pdf
from app.utilities.redact_pdf import redact_text

st.set_page_config(page_title="PDF Redactor", layout="centered")

st.title("PDF Redactor")
st.markdown("""
Drag and drop a PDF file below, or click the area to browse your files. Select what types of information you'd like to redact.
""")

# Upload file section
uploaded_file = st.file_uploader("Upload PDF", type="pdf", label_visibility="collapsed")

# Hover effect for file upload area
st.markdown("""
    <style>
    .stFileUploader > div:first-child {
        border: 2px dashed #ccc;
        padding: 2em;
        text-align: center;
        background-color: #f9f9f9;
        transition: background-color 0.3s ease;
        cursor: pointer;
    }
    .stFileUploader > div:first-child:hover {
        background-color: #e6f7ff;
    }
    </style>
""", unsafe_allow_html=True)

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    extracted_text = extract_text_from_pdf(pdf_bytes)

    st.subheader("Select Information to Redact")
    col1, col2 = st.columns(2)

    with col1:
        redact_names = st.checkbox("Names")
        redact_dates = st.checkbox("Dates")
        redact_emails = st.checkbox("Emails")
    with col2:
        redact_phone = st.checkbox("Phone Numbers")
        redact_addresses = st.checkbox("Addresses")
        redact_all = st.checkbox("Select All")

    # Handle "Select All" behavior
    if redact_all:
        redact_names = redact_dates = redact_emails = redact_phone = redact_addresses = True

    selected_options = {
        "names": redact_names,
        "dates": redact_dates,
        "emails": redact_emails,
        "phones": redact_phone,
        "addresses": redact_addresses
    }

    if any(selected_options.values()):
        redacted_text = redact_text(extracted_text, selected_options)
        st.subheader("Redacted Text")
        st.text_area("", redacted_text, height=300)

        st.download_button("Download Redacted Text", redacted_text, file_name="redacted_output.txt")
    else:
        st.info("Select at least one option to redact.")
