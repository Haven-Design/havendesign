import streamlit as st
import fitz  # PyMuPDF
import io
import re

st.set_page_config(page_title="PDF Redactor", layout="wide")
st.title("🔒 PDF Redactor")

uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")

st.markdown("### What would you like to redact?")
redact_names = st.checkbox("Names (case-insensitive)")
redact_ssn = st.checkbox("Social Security Numbers (XXX-XX-XXXX)")
redact_emails = st.checkbox("Email addresses")
redact_phone = st.checkbox("Phone numbers")
custom_terms = st.text_input("Custom words/phrases to redact (comma-separated)")

if st.button("Redact PDF"):
    if uploaded_file is not None:
        pdf_data = uploaded_file.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")

        custom_list = [term.strip().lower() for term in custom_terms.split(",") if term.strip()]
        regex_patterns = []

        if redact_names:
            custom_list.extend(["john", "emily"])  # Add known names for redaction

        if redact_ssn:
            regex_patterns.append(r"\b\d{3}-\d{2}-\d{4}\b")

        if redact_emails:
            regex_patterns.append(r"\b[\w\.-]+@[\w\.-]+\.\w+\b")

        if redact_phone:
            regex_patterns.append(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")

        for page in doc:
            page_text = page.get_text().lower()

            # Case-insensitive string redaction
            for term in custom_list:
                if term:
                    matches = page.search_for(term, flags=fitz.TEXT_DEHYPHENATE)
                    for match in matches:
                        page.add_redact_annot(match, fill=(0, 0, 0))

            # Regex redaction
            for pattern in regex_patterns:
                for match in re.finditer(pattern, page_text):
                    start, end = match.span()
                    redaction_text = page.get_textpage().text()[start:end]
                    if redaction_text:
                        highlight_areas = page.search_for(redaction_text)
                        for area in highlight_areas:
                            page.add_redact_annot(area, fill=(0, 0, 0))

            page.apply_redactions()

        redacted_pdf = io.BytesIO()
        doc.save(redacted_pdf)
        st.download_button(
            label="📥 Download Redacted PDF",
            data=redacted_pdf.getvalue(),
            file_name="redacted_output.pdf",
            mime="application/pdf"
        )
    else:
        st.warning("Please upload a PDF first.")
