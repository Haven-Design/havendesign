import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
from app.utilities.extract_text import extract_text_from_pdf
from app.utilities.redact_pdf import find_redaction_matches, apply_redactions

st.set_page_config(page_title="PDF Redactor", layout="centered")

st.title("PDF Redactor")
st.markdown("""
Drag and drop a PDF file below, or click to browse.  
Select the types of information to scan, then review and choose which matches to redact.
""")

# Custom CSS for uploader hover effect
st.markdown("""
    <style>
    .stFileUploader > div:first-child {
        border: 2px dashed #ccc;
        padding: 2em;
        text-align: center;
        background-color: #f9f9f9;
        transition: all 0.3s ease;
        cursor: pointer;
        border-radius: 10px;
    }
    .stFileUploader > div:first-child:hover {
        background-color: #e6f7ff;
        box-shadow: 0 0 20px rgba(0,0,0,0.2);
        transform: scale(1.01);
    }
    </style>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload PDF", type="pdf", label_visibility="collapsed")

if uploaded_file:
    pdf_bytes = uploaded_file.read()

    st.subheader("Step 1 – Select Categories to Scan")
    col1, col2 = st.columns(2)

    with col1:
        redact_names = st.checkbox("Names")
        redact_dates = st.checkbox("Dates")
        redact_emails = st.checkbox("Emails")
    with col2:
        redact_phone = st.checkbox("Phone Numbers")
        redact_addresses = st.checkbox("Addresses")
        redact_all = st.checkbox("Select All")

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
        st.subheader("Step 2 – Review Detected Matches")
        matches_by_page = find_redaction_matches(pdf_bytes, selected_options)

        user_choices = {}
        for page_num, matches in matches_by_page.items():
            phrases = [m["phrase"] for m in matches]
            default_selection = phrases.copy()  # preselect all
            chosen = st.multiselect(
                f"Page {page_num + 1} Matches:",
                options=phrases,
                default=default_selection,
                key=f"page_{page_num}_matches"
            )
            user_choices[page_num] = chosen

        if st.button("Apply Redactions"):
            preview_images, final_doc = apply_redactions(pdf_bytes, matches_by_page, user_choices)

            st.subheader("Step 3 – Preview")
            for img_bytes in preview_images:
                st.image(img_bytes)

            st.download_button(
                "Download Redacted PDF",
                final_doc,
                file_name="redacted_output.pdf",
                mime="application/pdf"
            )
    else:
        st.info("Select at least one category to scan.")
