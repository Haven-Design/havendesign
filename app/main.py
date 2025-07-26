import streamlit as st
import fitz  # PyMuPDF
import io
import re

st.title("PDF Redactor")

uploaded_file = st.file_uploader("Upload a PDF", type="pdf")
custom_terms = st.text_input("Custom terms to redact (comma-separated)")

# Redaction options
st.markdown("### Redaction Options")
redact_names = st.checkbox("Names", value=True)
redact_ssn = st.checkbox("Social Security Numbers", value=True)
redact_email = st.checkbox("Email Addresses", value=True)
redact_phone = st.checkbox("Phone Numbers", value=True)
redact_credit_card = st.checkbox("Credit Card Numbers", value=True)
redact_dates = st.checkbox("Dates (MM/DD/YYYY)", value=True)
redact_addresses = st.checkbox("Addresses (Street-like)", value=True)

patterns = []

if redact_ssn:
    patterns.append(r"\b\d{3}-\d{2}-\d{4}\b")
if redact_email:
    patterns.append(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
if redact_phone:
    patterns.append(r"\b(?:\+?1\s*[-.\(]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
if redact_credit_card:
    patterns.append(r"\b(?:\d[ -]*?){13,16}\b")
if redact_dates:
    patterns.append(r"\b(?:0?[1-9]|1[0-2])[\/\-\.](?:0?[1-9]|[12][0-9]|3[01])[\/\-\.](?:\d{2}|\d{4})\b")
if redact_addresses:
    patterns.append(r"\b\d{1,5}\s(?:[A-Za-z0-9]+\s){1,5}(Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct)\b")

if redact_names and custom_terms:
    names = [name.strip() for name in custom_terms.split(',')]
    patterns.extend([re.escape(name) for name in names])
elif custom_terms:
    terms = [term.strip() for term in custom_terms.split(',')]
    patterns.extend([re.escape(term) for term in terms])

if uploaded_file and st.button("Redact PDF"):
    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")

        for page in doc:
            page_text = page.get_text()
            for pattern in patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in set(matches):
                    areas = page.search_for(match, flags=fitz.TEXT_IGNORECASE)
                    for area in areas:
                        page.add_redact_annot(area, fill=(0, 0, 0))
            page.apply_redactions()

        output = io.BytesIO()
        doc.save(output)
        st.download_button("Download Redacted PDF", output.getvalue(), file_name="redacted.pdf")

    except Exception as e:
        st.error("Something went wrong during redaction.")
        st.exception(e)
