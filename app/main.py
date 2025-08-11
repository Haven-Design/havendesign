import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
import base64
from utilities.redact_pdf import find_redaction_phrases, redact_pdf

import re

# Helper to encode PDF bytes to base64 for embedding preview
def pdf_to_base64(pdf_bytes):
    return base64.b64encode(pdf_bytes).decode('utf-8')

# Available redaction categories with labels & keys used in regex and NLP
REDACTION_CATEGORIES = {
    "Emails": "emails",
    "Phone Numbers": "phones",
    "Dates": "dates",
    "Names": "names",
    "Addresses": "addresses",
    "Zip Codes": "zip_codes",
    "Social Security Numbers": "ssn",
    "Credit Card Numbers": "credit_cards",
    "Passport Numbers": "passport",
    "Driver's License Numbers": "drivers_license",
}

def main():
    st.set_page_config(page_title="PDF Redactor", layout="wide")
    st.title("PDF Redactor")

    # Step 1: File upload
    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    if not uploaded_file:
        st.info("Please upload a PDF file to start redaction.")
        return

    pdf_bytes = uploaded_file.read()

    # Step 2: Select categories to scan
    st.markdown("### Select categories to detect and redact:")
    # All unchecked by default
    if "selected_categories" not in st.session_state:
        st.session_state.selected_categories = []

    cols = st.columns(3)
    # Display checkboxes in columns
    for i, (label, key) in enumerate(REDACTION_CATEGORIES.items()):
        with cols[i % 3]:
            checked = key in st.session_state.selected_categories
            new_val = st.checkbox(label, value=checked, key=key)
            if new_val and key not in st.session_state.selected_categories:
                st.session_state.selected_categories.append(key)
            elif not new_val and key in st.session_state.selected_categories:
                st.session_state.selected_categories.remove(key)

    # Buttons for select all/deselect all
    col_btn1, col_btn2, _ = st.columns([1,1,5])
    with col_btn1:
        if st.button("Select All"):
            st.session_state.selected_categories = list(REDACTION_CATEGORIES.values())
    with col_btn2:
        if st.button("Deselect All"):
            st.session_state.selected_categories = []

    # Step 3: Scan for phrases button
    if st.button("Scan for redacted phrases"):
        if not st.session_state.selected_categories:
            st.warning("Please select at least one category to scan.")
            return
        highlights = find_redaction_phrases(pdf_bytes, options={k: (k in st.session_state.selected_categories) for k in REDACTION_CATEGORIES.values()})
        if not highlights:
            st.warning("No redacted phrases found.")
            st.session_state.highlights = {}
            st.session_state.pdf_bytes = pdf_bytes
            st.session_state.excluded_phrases = set()
            return
        st.session_state.highlights = highlights
        st.session_state.pdf_bytes = pdf_bytes
        st.session_state.excluded_phrases = set()

    if "highlights" not in st.session_state or not st.session_state.highlights:
        st.info("Scan for redacted phrases after selecting categories.")
        return

    highlights = st.session_state.highlights

    # Flatten list of all detected phrases
    all_phrases = []
    for page_num, matches in highlights.items():
        for match in matches:
            all_phrases.append(match["text"])
    # Unique & sorted phrases
    all_phrases = sorted(set(all_phrases))

    # Step 4: Show list of redacted phrases with checkboxes (unchecked by default)
    st.markdown("### Detected Phrases")
    if "selected_phrases" not in st.session_state:
        st.session_state.selected_phrases = set()

    col1, col2 = st.columns([1,3])
    with col1:
        st.markdown("Select which phrases to redact:")
        # Select All / Deselect All for phrases
        if st.button("Select All Phrases"):
            st.session_state.selected_phrases = set(all_phrases)
        if st.button("Deselect All Phrases"):
            st.session_state.selected_phrases = set()

        # Phrase checkboxes with scrollable container, 2 columns
        phrase_cols = st.columns(2)
        for idx, phrase in enumerate(all_phrases):
            checked = phrase in st.session_state.selected_phrases
            col = phrase_cols[idx % 2]
            new_val = col.checkbox(phrase, value=checked, key=f"phrase_{idx}")
            if new_val and phrase not in st.session_state.selected_phrases:
                st.session_state.selected_phrases.add(phrase)
            elif not new_val and phrase in st.session_state.selected_phrases:
                st.session_state.selected_phrases.remove(phrase)

    with col2:
        # Step 5: Show PDF preview with redactions
        st.markdown("### PDF Preview with Redactions (hover to highlight)")
        if st.button("Redact and Preview"):
            # Generate preview PDF bytes with selected phrases redacted
            redacted_pdf_bytes = redact_pdf(pdf_bytes, highlights, excluded_phrases=set(all_phrases) - st.session_state.selected_phrases)
            # Show PDF preview embed
            b64_pdf = pdf_to_base64(redacted_pdf_bytes)
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="700" height="900" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            st.info("Click 'Redact and Preview' to generate preview with selected redactions.")

    # Step 6: Optionally, offer final redacted PDF download
    if "selected_phrases" in st.session_state and st.session_state.selected_phrases:
        if st.button("Download Redacted PDF"):
            redacted_pdf_bytes = redact_pdf(pdf_bytes, highlights, excluded_phrases=set(all_phrases) - st.session_state.selected_phrases)
            st.download_button(
                label="Download PDF",
                data=redacted_pdf_bytes,
                file_name="redacted_output.pdf",
                mime="application/pdf"
            )


if __name__ == "__main__":
    main()
