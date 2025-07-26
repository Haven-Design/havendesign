import streamlit as st
import fitz  # PyMuPDF
import io
import re

# --------------------
# Sidebar
# --------------------
st.sidebar.title("Redaction Settings")

# Pattern checkboxes
redact_ssn = st.sidebar.checkbox("Social Security Numbers")
redact_dates = st.sidebar.checkbox("Dates")
redact_names = st.sidebar.checkbox("Names")
redact_emails = st.sidebar.checkbox("Email Addresses")
redact_phones = st.sidebar.checkbox("Phone Numbers")
redact_cc = st.sidebar.checkbox("Credit Card Numbers")
redact_all = st.sidebar.checkbox("Select All")

if redact_all:
    redact_ssn = redact_dates = redact_names = redact_emails = redact_phones = redact_cc = True

# --------------------
# Main App
# --------------------
st.title("PDF Redactor")

uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")

custom_terms = st.text_area("Custom Terms to Redact (comma or newline separated)", height=100)

if uploaded_file and st.button("Redact and Preview"):

    # Load the PDF
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Collect all search terms
    terms = []

    if custom_terms:
        for line in custom_terms.splitlines():
            terms.extend([term.strip() for term in line.split(",") if term.strip()])

    # Define regex patterns
    patterns = []

    if redact_ssn:
        patterns.append(r"\b\d{3}-\d{2}-\d{4}\b")
    if redact_dates:
        patterns.append(r"\b(?:\d{1,2}[/-])?\d{1,2}[/-]\d{2,4}\b")  # Dates like 01/01/2020 or 1-1-20
    if redact_names:
        terms.extend(["John", "Emily"])  # Add more names as needed
    if redact_emails:
        patterns.append(r"\b[\w.-]+@[\w.-]+\.\w+\b")
    if redact_phones:
        patterns.append(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
    if redact_cc:
        patterns.append(r"\b(?:\d[ -]*?){13,16}\b")

    # Go through all pages and apply redactions
    for page in doc:
        # Search for literal terms
        for term in terms:
            matches = page.search_for(term, flags=fitz.TEXT_DEHYPHENATE | fitz.TEXT_IGNORECASE)
            for match in matches:
                page.add_redact_annot(match, fill=(0, 0, 0))

        # Search for regex patterns
        text = page.get_text()
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                matched_text = match.group()
                rects = page.search_for(matched_text)
                for rect in rects:
                    page.add_redact_annot(rect, fill=(0, 0, 0))

    # Apply redactions
    doc.apply_redactions()

    # Save redacted PDF to buffer
    redacted_pdf_bytes = io.BytesIO()
    doc.save(redacted_pdf_bytes)
    doc.close()

    st.success("Redaction complete!")
    st.download_button(
        label="Download Redacted PDF",
        data=redacted_pdf_bytes.getvalue(),
        file_name="redacted_output.pdf",
        mime="application/pdf"
    )

    # Optional: Preview
    st.subheader("Preview")
    st.info("Preview shows first 2 pages of redacted PDF.")
    preview_doc = fitz.open(stream=redacted_pdf_bytes.getvalue(), filetype="pdf")
    for page in preview_doc[:2]:
        pix = page.get_pixmap()
        st.image(pix.tobytes("png"))
    preview_doc.close()
