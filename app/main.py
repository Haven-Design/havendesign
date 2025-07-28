import streamlit as st
import fitz  # PyMuPDF
import re
from io import BytesIO

st.set_page_config(page_title="PDF Redactor", layout="wide")

st.title("PDF Redactor")

uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

# Checkbox options
st.subheader("Select the types of data to redact:")
select_all = st.checkbox("Select All")

option_names = {
    "Names": r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",
    "SSNs": r"\b\d{3}-\d{2}-\d{4}\b",
    "Emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "Phone Numbers": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "Dates": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})\b",
}

# Keep track of selected types
selected_options = {
    label: st.checkbox(label, value=select_all)
    for label in option_names
}

custom_terms_input = st.text_input("Custom terms to redact (comma separated)")

if st.button("Redact PDF") and uploaded_file:
    try:
        file_bytes = uploaded_file.read()
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")

        # Build redaction pattern list
        patterns = []

        for label, selected in selected_options.items():
            if selected:
                patterns.append(option_names[label])

        # Add custom terms
        if custom_terms_input.strip():
            custom_terms = [term.strip() for term in custom_terms_input.split(",")]
            for term in custom_terms:
                # Escape special characters unless it's a regex
                if not re.match(r"^[\[\]\\^$.|?*+(){}]", term):
                    term = re.escape(term)
                patterns.append(fr"\b{term}\b")

        combined_pattern = "|".join(patterns)
        regex = re.compile(combined_pattern, re.IGNORECASE)

        redacted_pdf = fitz.open()

        progress_bar = st.progress(0, text="Redacting...")

        for page_num, page in enumerate(pdf_doc):
            text_instances = regex.finditer(page.get_text())
            for match in text_instances:
                rects = page.search_for(match.group(), quads=True)
                for rect in rects:
                    page.add_redact_annot(rect.rect, fill=(0, 0, 0))
            page.apply_redactions()
            redacted_pdf.insert_pdf(pdf_doc, from_page=page_num, to_page=page_num)
            progress_bar.progress((page_num + 1) / len(pdf_doc), text=f"Redacting page {page_num + 1}")

        # Save redacted PDF to memory
        redacted_bytes = redacted_pdf.write()

        st.success("Redaction complete!")

        # Show preview of the first page
        st.subheader("Preview:")
        preview_page = redacted_pdf.load_page(0)
        pix = preview_page.get_pixmap(matrix=fitz.Matrix(2, 2))
        st.image(pix.tobytes("png"), use_column_width=True)

        st.download_button("Download Redacted PDF", data=redacted_bytes, file_name="redacted.pdf")

    except Exception as e:
        st.error("Something went wrong during redaction.")
        st.exception(e)
