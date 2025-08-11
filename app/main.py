import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
import base64

from utilities.extract_text import extract_text_from_pdf
from utilities.redact_pdf import find_redaction_phrases, redact_pdf

# Options available for redaction categories and labels
ALL_OPTIONS = {
    "emails": "Emails",
    "phones": "Phone Numbers",
    "dates": "Dates",
    "names": "Names",
    "addresses": "Addresses",
    "zip_codes": "Zip Codes",
    "credit_cards": "Credit Card Numbers",
}

# Add regex for zip codes and credit cards in redact_pdf.py accordingly

def main():
    st.set_page_config(page_title="PDF Redactor", layout="wide")

    st.title("PDF Redactor")

    # Upload PDF file
    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    if not uploaded_file:
        st.info("Please upload a PDF file to get started.")
        return

    pdf_bytes = uploaded_file.read()

    # Initialize session state for options and highlights
    if "redact_options" not in st.session_state:
        st.session_state.redact_options = {key: False for key in ALL_OPTIONS}
    if "highlights" not in st.session_state:
        st.session_state.highlights = {}
    if "excluded_phrases" not in st.session_state:
        st.session_state.excluded_phrases = set()
    if "pdf_bytes" not in st.session_state or st.session_state.pdf_bytes != pdf_bytes:
        st.session_state.pdf_bytes = pdf_bytes
        st.session_state.highlights = {}
        st.session_state.excluded_phrases = set()
        st.session_state.redact_options = {key: False for key in ALL_OPTIONS}

    st.subheader("Select what to redact")

    col_opts1, col_opts2 = st.columns(2)
    with col_opts1:
        for key in list(ALL_OPTIONS.keys())[:len(ALL_OPTIONS)//2]:
            st.session_state.redact_options[key] = st.checkbox(
                ALL_OPTIONS[key], value=st.session_state.redact_options[key], key=f"opt_{key}"
            )
    with col_opts2:
        for key in list(ALL_OPTIONS.keys())[len(ALL_OPTIONS)//2:]:
            st.session_state.redact_options[key] = st.checkbox(
                ALL_OPTIONS[key], value=st.session_state.redact_options[key], key=f"opt_{key}"
            )

    select_all = st.button("Select All")
    if select_all:
        for key in st.session_state.redact_options.keys():
            st.session_state.redact_options[key] = True

    deselect_all = st.button("Deselect All")
    if deselect_all:
        for key in st.session_state.redact_options.keys():
            st.session_state.redact_options[key] = False

    if st.button("Scan for redacted phrases"):
        options = st.session_state.redact_options
        if not any(options.values()):
            st.warning("Please select at least one category to scan for redaction.")
        else:
            highlights = find_redaction_phrases(pdf_bytes, options)
            if not highlights:
                st.warning("No redaction phrases found with selected options.")
                st.session_state.highlights = {}
                st.session_state.excluded_phrases = set()
            else:
                st.session_state.highlights = highlights
                st.session_state.excluded_phrases = set()

    if st.session_state.highlights:
        st.subheader("Redacted Phrases and Preview")

        # Flatten phrases with unique keys for checkboxes
        phrases_to_show = []
        for page_num, matches in st.session_state.highlights.items():
            for i, match in enumerate(matches):
                phrase = match["text"]
                key = f"{page_num}_{i}_{phrase}"
                phrases_to_show.append((key, phrase))

        # Layout: Preview on left, phrase list on right
        preview_col, phrases_col = st.columns([3, 1])

        with phrases_col:
            st.markdown("**Exclude phrases from redaction:**")
            # Scroll container with two columns
            scroll_height = 350
            container = st.container()
            container.markdown(
                f"""
                <style>
                .scroll-container {{
                    height: {scroll_height}px;
                    overflow-y: auto;
                    border: 1px solid #ccc;
                    padding: 8px;
                    display: flex;
                    flex-wrap: wrap;
                }}
                .phrase-checkbox {{
                    width: 48%;
                    margin-bottom: 6px;
                }}
                </style>
                """,
                unsafe_allow_html=True,
            )

            # Use st.checkbox inside the styled div
            phrases_html = '<div class="scroll-container">'
            # Generate unique keys for each checkbox and label
            for key, phrase_text in phrases_to_show:
                checked = key not in st.session_state.excluded_phrases
                # We'll show checkbox with label, but checkbox disables if phrase excluded
                # Use st.checkbox with key inside phrases_col to keep state
                pass
            phrases_html += "</div>"
            st.markdown(phrases_html, unsafe_allow_html=True)

            # Because we cannot inject checkboxes directly in custom html,
            # we will use Streamlit checkboxes with a two-column layout instead:

            # Let's do this better: Two columns with checkboxes inside phrases_col:
            phrase_chunks = [phrases_to_show[i : i + (len(phrases_to_show)+1)//2] for i in range(0, len(phrases_to_show), (len(phrases_to_show)+1)//2)]
            col1, col2 = st.columns(2)
            for col, chunk in zip([col1, col2], phrase_chunks):
                with col:
                    for key, phrase_text in chunk:
                        checked = key not in st.session_state.excluded_phrases
                        cb = st.checkbox(phrase_text, value=checked, key=f"exclude_{key}")
                        if cb:
                            if key in st.session_state.excluded_phrases:
                                st.session_state.excluded_phrases.remove(key)
                        else:
                            st.session_state.excluded_phrases.add(key)

        with preview_col:
            st.markdown("**PDF Preview with redactions:**")

            # Generate a redacted PDF preview with current excluded phrases
            redacted_pdf_bytes = redact_pdf(
                st.session_state.pdf_bytes,
                st.session_state.highlights,
                st.session_state.excluded_phrases,
            )

            # Display PDF preview as embedded base64 PDF (in iframe)
            b64_pdf = base64.b64encode(redacted_pdf_bytes).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="700" style="border: none;"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.info("Select categories and click 'Scan for redacted phrases' to see redactions.")

if __name__ == "__main__":
    main()
