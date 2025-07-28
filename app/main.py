import streamlit as st
import fitz  # PyMuPDF
import re
import io

# ---------- CONFIG ---------- #
st.set_page_config(page_title="PDF Redactor", layout="centered")

# ---------- HELPER FUNCTIONS ---------- #
def find_matches(text, patterns):
    matches = []
    for pattern in patterns:
        matches.extend(re.finditer(pattern, text, re.IGNORECASE))
    return matches

def redact_pdf(pdf_file, patterns):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    for page in doc:
        text = page.get_text("text")
        matches = find_matches(text, patterns)
        for match in matches:
            matched_text = match.group()
            areas = page.search_for(matched_text)
            for area in areas:
                page.add_redact_annot(area, fill=(0, 0, 0))
        page.apply_redactions()
    output = io.BytesIO()
    doc.save(output)
    return output

# ---------- REGEX PATTERNS ---------- #
regex_patterns = {
    "Names": r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "Phone": r"\b(?:\+?1\s*[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "Address": r"\d{1,5}\s[\w\s]{2,30}(?:Street|St|Rd|Road|Avenue|Ave|Boulevard|Blvd|Ln|Lane|Drive|Dr)\.?",
    "Dates": r"\b(?:\d{1,2}[/-])?\d{1,2}[/-]\d{2,4}\b|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}"
}

# ---------- UI ---------- #
st.title("📄 PDF Redactor")
st.markdown("Upload a PDF and choose which types of information to redact.")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file:
    # Display checkboxes
    st.subheader("🔎 What do you want to redact?")
    select_all = st.checkbox("All")
    selected = {}
    for key in regex_patterns:
        selected[key] = st.checkbox(key, value=select_all)

    selected_patterns = [regex_patterns[k] for k, v in selected.items() if v]

    # Redact button
    if st.button("Redact PDF"):
        if not selected_patterns:
            st.warning("Please select at least one type of information to redact.")
        else:
            with st.spinner("Redacting... Please wait."):
                try:
                    redacted = redact_pdf(uploaded_file, selected_patterns)
                    st.success("Redaction complete! ✅")

                    # Preview PDF
                    st.subheader("🔍 Preview")
                    base64_pdf = redacted.getvalue()
                    st.download_button("📥 Download Redacted PDF", data=base64_pdf, file_name="redacted.pdf")

                    # Show preview in viewer
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf.encode("base64").decode()}" width="700" height="1000" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Something went wrong during redaction.\n\n{e}")

