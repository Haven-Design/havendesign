import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
import base64
from app.utilities.extract_text import extract_text_from_pdf
from app.utilities.redact_pdf import find_redaction_phrases, redact_pdf
import os

st.set_page_config(page_title="PDF Redactor", layout="centered")

def highlight_rects(page, rects, color=(1, 0, 0), fill_opacity=0.3, stroke_opacity=0.8):
    for rect in rects:
        highlight = page.add_highlight_annot(rect)
        highlight.set_colors(stroke=color, fill=color)
        highlight.set_opacity(fill_opacity)
        highlight.update()

def render_pdf_with_highlights(pdf_bytes, highlights, excluded_phrases):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num, page in enumerate(doc):
        rects_to_highlight = []
        for match in highlights.get(page_num, []):
            phrase = match["text"]
            if phrase in excluded_phrases:
                continue
            rects_to_highlight.append(match["rect"])

        # Add transparent grey highlight for all included phrases
        for rect in rects_to_highlight:
            annot = page.add_rect_annot(rect)
            annot.set_colors(stroke=(1, 1, 0), fill=(0.5, 0.5, 0.5))  # yellow stroke, grey fill
            annot.set_opacity(0.3)
            annot.update()
    pdf_stream = BytesIO()
    doc.save(pdf_stream)
    pdf_stream.seek(0)
    return pdf_stream.read()

def main():
    st.title("PDF Redactor")

    # Step 1: Choose categories
    st.sidebar.header("Select redaction categories to scan")
    options = {
        "emails": st.sidebar.checkbox("Emails", value=True),
        "phones": st.sidebar.checkbox("Phone numbers", value=True),
        "dates": st.sidebar.checkbox("Dates", value=True),
        "addresses": st.sidebar.checkbox("Addresses", value=True),
        "names": st.sidebar.checkbox("Names", value=True),
    }

    uploaded_file = st.file_uploader("Upload PDF file", type=["pdf"])

    if uploaded_file is None:
        st.info("Upload a PDF file to start redacting.")
        return

    pdf_bytes = uploaded_file.read()

    # Step 2: Find phrases to redact
    highlights = find_redaction_phrases(pdf_bytes, options)

    if not highlights:
        st.warning("No redaction phrases found for the selected categories.")
        return

    # Build phrase list with page numbers for uniqueness
    phrases_set = {}
    for page_num, matches in highlights.items():
        for m in matches:
            key = f"{page_num}_{m['text']}"
            phrases_set[key] = m['text']

    # Session state for excluded phrases
    if "excluded_phrases" not in st.session_state:
        st.session_state.excluded_phrases = set()

    st.sidebar.header("Redacted Phrases")
    # Scrollable two-column layout
    phrases_list = list(phrases_set.items())
    col1, col2 = st.sidebar.columns(2)

    for i, (key, phrase) in enumerate(phrases_list):
        checkbox_key = f"exclude_{key}"
        checked = checkbox_key in st.session_state.excluded_phrases
        if i % 2 == 0:
            with col1:
                exclude = st.checkbox(phrase, key=checkbox_key, value=checked)
        else:
            with col2:
                exclude = st.checkbox(phrase, key=checkbox_key, value=checked)
        if exclude:
            st.session_state.excluded_phrases.add(checkbox_key)
        else:
            st.session_state.excluded_phrases.discard(checkbox_key)

    excluded_phrases = {key.split("exclude_")[1] for key in st.session_state.excluded_phrases}

    # Step 3: Show PDF preview with highlights
    preview_bytes = render_pdf_with_highlights(pdf_bytes, highlights, excluded_phrases)
    b64 = base64.b64encode(preview_bytes).decode("utf-8")
    pdf_display = f'<iframe src="data:application/pdf;base64,{b64}" width="700" height="900" style="border: none;"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

    # Step 4: Redact and download
    if st.button("Download Redacted PDF"):
        output_pdf = redact_pdf(pdf_bytes, highlights, excluded_phrases)
        st.success("Redacted PDF ready for download!")
        st.download_button(
            label="Download Redacted PDF",
            data=output_pdf,
            file_name="redacted_output.pdf",
            mime="application/pdf",
        )

if __name__ == "__main__":
    main()
