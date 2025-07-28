import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF Redactor", layout="centered")

st.title("🔒 PDF Redactor")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

# Redaction options
st.sidebar.title("What do you want to redact?")
select_all = st.sidebar.checkbox("Select All")

redaction_options = {
    "Names": select_all or st.sidebar.checkbox("Names"),
    "Social Security Numbers": select_all or st.sidebar.checkbox("Social Security Numbers"),
    "Email Addresses": select_all or st.sidebar.checkbox("Email Addresses"),
    "Phone Numbers": select_all or st.sidebar.checkbox("Phone Numbers"),
    "Credit Card Numbers": select_all or st.sidebar.checkbox("Credit Card Numbers"),
    "Dates": select_all or st.sidebar.checkbox("Dates"),
    "Addresses": select_all or st.sidebar.checkbox("Addresses"),
}

custom_terms = st.text_input("Custom terms (comma-separated):")

def build_patterns(options, custom_terms):
    patterns = []

    if options.get("Names"):
        # Simple example list of names to redact
        patterns += [r"\bJohn\b", r"\bEmily\b", r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b"]

    if options.get("Social Security Numbers"):
        patterns.append(r"\b\d{3}-\d{2}-\d{4}\b")

    if options.get("Email Addresses"):
        patterns.append(r"\b[\w\.-]+@[\w\.-]+\.\w+\b")

    if options.get("Phone Numbers"):
        patterns.append(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

    if options.get("Credit Card Numbers"):
        patterns.append(r"\b(?:\d[ -]*?){13,16}\b")

    if options.get("Dates"):
        patterns.append(r"\b(?:\d{1,2}[-/th|st|nd|rd\s]*)?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/\s]?\d{2,4}\b")
        patterns.append(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b")

    if options.get("Addresses"):
        patterns.append(r"\b\d+\s+\w+\s+(Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Lane|Ln|Drive|Dr)\b")

    if custom_terms:
        terms = [term.strip() for term in custom_terms.split(",") if term.strip()]
        patterns += [re.escape(term) for term in terms]

    return patterns

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    patterns = build_patterns(redaction_options, custom_terms)

    try:
        for page in doc:
            text = page.get_text()
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matched_text = match.group()
                    areas = page.search_for(matched_text)
                    for area in areas:
                        page.add_redact_annot(area, fill=(0, 0, 0))
            page.apply_redactions()

        redacted_pdf = io.BytesIO()
        doc.save(redacted_pdf)
        st.success("Redaction complete. Download your redacted file below.")
        st.download_button("Download Redacted PDF", redacted_pdf.getvalue(), file_name="redacted.pdf")

    except Exception as e:
        st.error("Something went wrong during redaction.")
        st.exception(e)
