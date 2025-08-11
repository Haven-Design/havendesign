import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
import base64
from utilities.extract_text import extract_text_from_pdf
from utilities.redact_pdf import find_redaction_phrases, redact_pdf

st.set_page_config(page_title="PDF Redactor", layout="wide")

SENSITIVE_CATEGORIES = {
    "emails": "Emails",
    "phones": "Phone numbers",
    "dates": "Dates",
    "addresses": "Addresses",
    "names": "Names",
    "zip_codes": "Zip Codes",
    "credit_cards": "Credit Card Numbers",
}

def render_pdf_with_highlights(pdf_bytes, highlights, excluded_phrases):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num, page in enumerate(doc):
        for match in highlights.get(page_num, []):
            phrase = match["text"]
            if phrase in excluded_phrases:
                continue
            rect = match["rect"]
            annot = page.add_rect_annot(rect)
            annot.set_colors(stroke=(1, 1, 0), fill=(0.5, 0.5, 0.5))  # Yellow border, grey fill
            annot.set_opacity(0.3)
            annot.update()
    pdf_stream = BytesIO()
    doc.save(pdf_stream)
    pdf_stream.seek(0)
    return pdf_stream.read()

def main():
    st.title("PDF Redactor")

    uploaded_file = st.file_uploader("Upload PDF file", type=["pdf"])
    if uploaded_file is None:
        st.info("Please upload a PDF file to continue.")
        return

    pdf_bytes = uploaded_file.read()

    st.subheader("Select categories to redact")

    if "select_all" not in st.session_state:
        st.session_state.select_all = False

    def toggle_select_all():
        st.session_state.select_all = not st.session_state.select_all

    col_toggle, _ = st.columns([1, 5])
    with col_toggle:
        if st.button("Select All" if not st.session_state.select_all else "Deselect All"):
            toggle_select_all()

    options = {}
    for key, label in SENSITIVE_CATEGORIES.items():
        checked = st.session_state.select_all
        options[key] = st.checkbox(label, value=checked, key=f"opt_{key}")

    if st.button("Scan for redacted phrases"):
        if not any(options.values()):
            st.warning("Please select at least one category to scan for redaction.")
            return

        highlights = find_redaction_phrases(pdf_bytes, options)

        if not highlights:
            st.warning("No redaction phrases found with selected options.")
            return

        st.session_state.highlights = highlights
        st.session_state.pdf_bytes = pdf_bytes
        st.session_state.excluded_phrases = set()
        st.experimental_rerun()

    if "highlights" in st.session_state and "pdf_bytes" in st.session_state:
        highlights = st.session_state.highlights
        pdf_bytes = st.session_state.pdf_bytes

        phrase_keys = []
        phrase_texts = []
        for page_num, matches in highlights.items():
            for m in matches:
                # Unique key based on page, phrase text, and rect coords
                key = f"{page_num}_{m['text']}_{int(m['rect'].x0)}_{int(m['rect'].y0)}"
                phrase_keys.append(key)
                phrase_texts.append(m['text'])

        if "excluded_phrases" not in st.session_state:
            st.session_state.excluded_phrases = set()

        col1, col2 = st.columns([2, 1])

        with col2:
            st.subheader("Redacted Phrases (check to EXCLUDE)")
            st.markdown(
                """
                <style>
                .scroll-box {
                    max-height: 400px;
                    overflow-y: auto;
                    border: 1px solid #ddd;
                    padding: 8px;
                }
                .checkbox-grid {
                    column-count: 2;
                    column-gap: 20px;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            container = st.container()
            with container:
                st.markdown('<div class="scroll-box checkbox-grid">', unsafe_allow_html=True)
                for key, phrase in zip(phrase_keys, phrase_texts):
                    checked = key in st.session_state.excluded_phrases
                    exclude = st.checkbox(phrase, value=checked, key=key)
                    if exclude:
                        st.session_state.excluded_phrases.add(key)
                    else:
                        st.session_state.excluded_phrases.discard(key)
                st.markdown('</div>', unsafe_allow_html=True)

        excluded_phrases = {k.split("_", 1)[1] for k in st.session_state.excluded_phrases}

        with col1:
            st.subheader("PDF Preview with Highlights")
            preview_pdf = render_pdf_with_highlights(pdf_bytes, highlights, excluded_phrases)
            b64 = base64.b64encode(preview_pdf).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64}" width="700" height="900" style="border:none;"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)

        if st.button("Download Redacted PDF"):
            output_pdf = redact_pdf(pdf_bytes, highlights, excluded_phrases)
            st.success("Redacted PDF ready!")
            st.download_button(
                label="Download PDF",
                data=output_pdf,
                file_name="redacted_output.pdf",
                mime="application/pdf",
            )


if __name__ == "__main__":
    main()
