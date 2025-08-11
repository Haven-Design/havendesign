import streamlit as st
import fitz
from io import BytesIO
import base64

from utilities.redact_pdf import find_redaction_phrases, redact_pdf

st.set_page_config(page_title="PDF Redactor", layout="wide")

# Options with labels and keys to pass to redact logic
REDACT_OPTIONS = {
    "emails": "Emails",
    "phones": "Phone numbers",
    "dates": "Dates",
    "names": "Names",
    "addresses": "Addresses",
    "zip_codes": "Zip Codes",
    "credit_cards": "Credit Cards"
}

def checkbox_select_all(label, options_dict):
    """Render a master checkbox to select/deselect all, then individual checkboxes."""
    st.markdown(f"### Select categories to redact:")
    select_all = st.checkbox("Select All", value=True, key="select_all_categories")

    selected = {}
    for key, val in options_dict.items():
        if select_all:
            selected[key] = st.checkbox(val, value=True, key=f"cat_{key}")
        else:
            selected[key] = st.checkbox(val, value=False, key=f"cat_{key}")
    return selected


def main():
    st.title("PDF Redactor")

    if "pdf_bytes" not in st.session_state:
        st.session_state.pdf_bytes = None
    if "highlights" not in st.session_state:
        st.session_state.highlights = {}
    if "excluded_phrases" not in st.session_state:
        st.session_state.excluded_phrases = set()
    if "selected_categories" not in st.session_state:
        st.session_state.selected_categories = {key: True for key in REDACT_OPTIONS}

    uploaded_file = st.file_uploader("Upload PDF file", type=["pdf"])

    if uploaded_file is not None:
        pdf_bytes = uploaded_file.read()
        st.session_state.pdf_bytes = pdf_bytes

        # Select categories to redact
        selected_categories = checkbox_select_all("Categories", REDACT_OPTIONS)
        st.session_state.selected_categories = selected_categories

        if st.button("Scan for redacted phrases"):
            # Only scan for categories selected True
            options_to_scan = {k: v for k, v in selected_categories.items() if v}
            if not options_to_scan:
                st.warning("Please select at least one category to scan for.")
            else:
                highlights = find_redaction_phrases(pdf_bytes, options_to_scan)
                if not highlights:
                    st.warning("No redaction phrases found for selected categories.")
                else:
                    st.session_state.highlights = highlights
                    st.session_state.excluded_phrases = set()

                    st.experimental_rerun()

    # After scanning phrases, show preview + redacted phrases
    if st.session_state.pdf_bytes and st.session_state.highlights:

        highlights = st.session_state.highlights
        excluded = st.session_state.excluded_phrases

        # Flatten phrases for checkbox list and keys
        phrases_list = []
        phrase_keys = []
        for page_num, matches in highlights.items():
            for i, match in enumerate(matches):
                key = f"{page_num}_{i}_{match['text']}"
                phrases_list.append(match['text'])
                phrase_keys.append(key)

        # Layout preview + redacted phrases side-by-side
        col1, col2 = st.columns([3, 2])

        with col1:
            st.markdown("### PDF Preview with Redactions (hover highlights in red)")

            redacted_pdf_bytes = redact_pdf(
                st.session_state.pdf_bytes,
                highlights,
                excluded
            )
            # Render PDF preview as image pages
            preview_images = []
            doc = fitz.open(stream=redacted_pdf_bytes, filetype="pdf")
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                img_bytes = pix.tobytes("png")
                preview_images.append(img_bytes)
            doc.close()

            for i, img_bytes in enumerate(preview_images):
                st.image(img_bytes, caption=f"Page {i + 1}")

        with col2:
            st.markdown("### Click phrases to exclude from redaction")

            # Add scrollable container with CSS for two columns
            container_style = """
                <style>
                .scrollbox {
                    max-height: 400px;
                    overflow-y: auto;
                    display: flex;
                    flex-wrap: wrap;
                }
                .phrase {
                    width: 48%;
                    margin-bottom: 4px;
                }
                </style>
            """
            st.markdown(container_style, unsafe_allow_html=True)

            # Show checkboxes for all phrases
            st.markdown('<div class="scrollbox">', unsafe_allow_html=True)
            new_excluded = set()
            for key, phrase in zip(phrase_keys, phrases_list):
                checked = key in excluded
                # Checkbox means "Exclude from redaction" (checked = excluded)
                if st.checkbox(phrase, value=checked, key=f"phrase_{key}"):
                    new_excluded.add(key)
            st.markdown('</div>', unsafe_allow_html=True)

            # Update excluded phrases in session_state
            if new_excluded != excluded:
                st.session_state.excluded_phrases = new_excluded
                st.experimental_rerun()

if __name__ == "__main__":
    main()
