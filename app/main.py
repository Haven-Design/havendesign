import streamlit as st
import base64
from app.utilities.redact_pdf import redact_pdf, find_redaction_phrases

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

    # Initialize session state variables
    if "pdf_bytes" not in st.session_state:
        st.session_state.pdf_bytes = None
    if "highlights" not in st.session_state:
        st.session_state.highlights = None
    if "excluded_phrases" not in st.session_state:
        st.session_state.excluded_phrases = set()
    if "selected_categories" not in st.session_state:
        st.session_state.selected_categories = []
    if "select_all_categories" not in st.session_state:
        st.session_state.select_all_categories = False

    # File upload
    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    if uploaded_file:
        pdf_bytes = uploaded_file.read()
        st.session_state.pdf_bytes = pdf_bytes

        st.markdown("### Select categories to redact:")

        # Select All checkbox
        def toggle_select_all():
            if st.session_state.select_all_categories:
                st.session_state.selected_categories = list(REDACTION_CATEGORIES.keys())
            else:
                st.session_state.selected_categories = []

        st.checkbox(
            "Select All",
            key="select_all_categories",
            on_change=toggle_select_all
        )

        # Category checkboxes
        for key, label in REDACTION_CATEGORIES.items():
            checked = key in st.session_state.selected_categories
            new_val = st.checkbox(label, value=checked, key=f"cat_{key}")
            if new_val and key not in st.session_state.selected_categories:
                st.session_state.selected_categories.append(key)
            elif not new_val and key in st.session_state.selected_categories:
                st.session_state.selected_categories.remove(key)

        # Sync select_all_categories based on individual selections
        if len(st.session_state.selected_categories) == len(REDACTION_CATEGORIES):
            if not st.session_state.select_all_categories:
                st.session_state.select_all_categories = True
        else:
            if st.session_state.select_all_categories:
                st.session_state.select_all_categories = False

        # Scan button
        if st.button("Scan for redacted phrases"):
            if not st.session_state.selected_categories:
                st.warning("Please select at least one category to scan.")
            else:
                options = {cat: (cat in st.session_state.selected_categories) for cat in REDACTION_CATEGORIES.keys()}
                highlights = find_redaction_phrases(pdf_bytes, options)
                if not highlights:
                    st.warning("No redaction phrases found.")
                    st.session_state.highlights = None
                    st.session_state.excluded_phrases = set()
                else:
                    st.session_state.highlights = highlights
                    st.session_state.excluded_phrases = set()
                # No rerun, UI will update next interaction

    # If we have highlights, show preview and phrase list
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
            st.markdown("**Redacted Phrases (uncheck to exclude):**")

            phrase_keys = []
            for page_num in highlights:
                for i, match in enumerate(highlights[page_num]):
                    phrase = match["text"]
                    key = f"{page_num}_{i}_{phrase}"
                    phrase_keys.append(key)

            container_height = 500
            container_style = (
                f"overflow-y: auto; height: {container_height}px; border: 1px solid #ddd; padding: 5px;"
            )

            # Two column layout inside the container
            half = (len(phrase_keys) + 1) // 2

            st.markdown(f'<div style="{container_style}"><table style="width:100%"><tr>', unsafe_allow_html=True)
            for col_i in range(2):
                st.markdown("<td style='vertical-align: top;'>", unsafe_allow_html=True)
                for idx in range(col_i * half, min(len(phrase_keys), (col_i + 1) * half)):
                    key = phrase_keys[idx]
                    included = key not in excluded
                    label = key.split("_", 2)[2]
                    checked = st.checkbox(label, value=included, key=f"phrase_{key}")
                    if checked and key in excluded:
                        excluded.remove(key)
                    elif not checked and key not in excluded:
                        excluded.add(key)
                st.markdown("</td>", unsafe_allow_html=True)
            st.markdown("</tr></table></div>", unsafe_allow_html=True)

            st.session_state.excluded_phrases = excluded

        st.markdown("---")
        if st.button("Clear All Exclusions"):
            st.session_state.excluded_phrases = set()

if __name__ == "__main__":
    main()
