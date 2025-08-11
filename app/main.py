import streamlit as st
import base64
from utilities.redact_pdf import redact_pdf, find_redaction_phrases

REDACTION_CATEGORIES = {
    "emails": "Emails",
    "phones": "Phone Numbers",
    "dates": "Dates",
    "addresses": "Addresses",
    "names": "Names",
    "zip_codes": "Zip Codes",
    "credit_cards": "Credit Card Numbers",
}

def main():
    st.set_page_config(page_title="PDF Redactor", layout="wide")
    st.title("PDF Redactor")

    if "pdf_bytes" not in st.session_state:
        st.session_state.pdf_bytes = None
    if "highlights" not in st.session_state:
        st.session_state.highlights = None
    if "excluded_phrases" not in st.session_state:
        st.session_state.excluded_phrases = set()
    if "selected_categories" not in st.session_state:
        st.session_state.selected_categories = []

    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

    if uploaded_file:
        pdf_bytes = uploaded_file.read()
        st.session_state.pdf_bytes = pdf_bytes

        st.markdown("### Select categories to redact:")
        all_categories = list(REDACTION_CATEGORIES.keys())

        selected = st.multiselect(
            "Categories",
            options=[REDACTION_CATEGORIES[c] for c in all_categories],
            default=[],
            key="category_multiselect"
        )

        selected_keys = [key for key, label in REDACTION_CATEGORIES.items() if label in selected]
        st.session_state.selected_categories = selected_keys

        if st.button("Scan for redacted phrases"):
            if not selected_keys:
                st.warning("Please select at least one category to scan.")
            else:
                options = {cat: (cat in selected_keys) for cat in REDACTION_CATEGORIES.keys()}
                highlights = find_redaction_phrases(pdf_bytes, options)
                if not highlights:
                    st.warning("No redaction phrases found.")
                    st.session_state.highlights = None
                    st.session_state.excluded_phrases = set()
                else:
                    st.session_state.highlights = highlights
                    st.session_state.excluded_phrases = set()
                st.experimental_rerun()

    if st.session_state.pdf_bytes and st.session_state.highlights:
        highlights = st.session_state.highlights
        excluded = st.session_state.excluded_phrases

        st.markdown("---")
        st.markdown("### Preview and manage redactions:")

        col1, col2 = st.columns([3, 2])

        with col1:
            st.markdown("**PDF Preview with redactions (hover over highlights):**")

            redacted_pdf_bytes = redact_pdf(
                st.session_state.pdf_bytes,
                highlights,
                excluded
            )

            b64 = base64.b64encode(redacted_pdf_bytes).decode()
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)

        with col2:
            st.markdown("**Redacted Phrases (click to exclude/include):**")

            phrase_keys = []
            for page_num in highlights:
                for i, match in enumerate(highlights[page_num]):
                    phrase = match["text"]
                    key = f"{page_num}_{i}_{phrase}"
                    phrase_keys.append(key)

            container_height = 500
            container_style = f"overflow-y: auto; height: {container_height}px; border: 1px solid #ddd; padding: 5px;"

            st.markdown(f'<div style="{container_style}"><table style="width:100%"><tr>', unsafe_allow_html=True)
            half = (len(phrase_keys) + 1) // 2

            for col_i in range(2):
                st.markdown("<td style='vertical-align: top;'>", unsafe_allow_html=True)
                for idx in range(col_i * half, min(len(phrase_keys), (col_i + 1) * half)):
                    key = phrase_keys[idx]
                    included = key not in excluded
                    label = key.split("_", 2)[2]
                    checkbox = st.checkbox(
                        label,
                        value=included,
                        key=f"exclude_{key}"
                    )
                    if checkbox and key in excluded:
                        excluded.remove(key)
                    elif not checkbox and key not in excluded:
                        excluded.add(key)
                st.markdown("</td>", unsafe_allow_html=True)
            st.markdown("</tr></table></div>", unsafe_allow_html=True)

            st.session_state.excluded_phrases = excluded

        st.markdown("---")
        if st.button("Clear All Selections"):
            st.session_state.excluded_phrases = set()
            st.experimental_rerun()

if __name__ == "__main__":
    main()
