import streamlit as st
import base64
from utilities.redact_pdf import find_redaction_phrases, redact_pdf

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
    "IP Addresses": "ip_addresses",
    "Vehicle Identification Numbers (VINs)": "vin",
    "Bank Account Numbers": "bank_accounts",
}

def main():
    st.title("Advanced PDF Redactor")

    uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
    if not uploaded_file:
        st.info("Upload a PDF to get started.")
        return

    pdf_bytes = uploaded_file.read()

    if "selected_categories" not in st.session_state:
        st.session_state.selected_categories = []

    st.markdown("### Select categories to detect and redact:")
    cols = st.columns(3)
    for i, (label, key) in enumerate(REDACTION_CATEGORIES.items()):
        with cols[i % 3]:
            checked = key in st.session_state.selected_categories
            new_val = st.checkbox(label, value=checked, key=key)
            if new_val and key not in st.session_state.selected_categories:
                st.session_state.selected_categories.append(key)
            elif not new_val and key in st.session_state.selected_categories:
                st.session_state.selected_categories.remove(key)

    col1, col2, _ = st.columns([1,1,6])
    with col1:
        if st.button("✅ Select All Categories"):
            st.session_state.selected_categories = list(REDACTION_CATEGORIES.values())
    with col2:
        if st.button("❌ Deselect All Categories"):
            st.session_state.selected_categories = []

    # Custom regex input
    st.markdown("### Add custom regex patterns (one per line)")
    custom_regex_input = st.text_area("Custom regex patterns", height=100)
    custom_regex_list = [line.strip() for line in custom_regex_input.split("\n") if line.strip()]

    scan_pressed = st.button("Scan for redacted phrases")

    if scan_pressed:
        if not st.session_state.selected_categories and not custom_regex_list:
            st.warning("Select at least one category or add at least one custom regex pattern.")
            return
        with st.spinner("Scanning PDF..."):
            highlights = find_redaction_phrases(
                pdf_bytes,
                {k: k in st.session_state.selected_categories for k in REDACTION_CATEGORIES.values()},
                custom_regex_list,
            )
        if not highlights:
            st.warning("No phrases detected.")
            st.session_state.highlights = {}
            return
        st.session_state.highlights = highlights
        st.session_state.pdf_bytes = pdf_bytes
        st.session_state.selected_phrases = set()

    if "highlights" not in st.session_state or not st.session_state.highlights:
        st.info("After selecting categories and/or adding regex, click 'Scan for redacted phrases'.")
        return

    # Collect all unique phrases
    all_phrases = sorted({match["text"] for matches in st.session_state.highlights.values() for match in matches})

    # Manual custom phrase input box
    st.markdown("### Add manual phrases for redaction (one per line)")
    manual_phrases_input = st.text_area("Manual phrases", height=100)
    manual_phrases = [line.strip() for line in manual_phrases_input.split("\n") if line.strip()]

    # Combine all phrases (detected + manual)
    combined_phrases = sorted(set(all_phrases + manual_phrases))

    if "selected_phrases" not in st.session_state:
        st.session_state.selected_phrases = set()

    st.markdown("### Select phrases to redact:")

    ph_col1, ph_col2 = st.columns([1,1])
    with ph_col1:
        if st.button("✅ Select All Phrases"):
            st.session_state.selected_phrases = set(combined_phrases)
    with ph_col2:
        if st.button("❌ Deselect All Phrases"):
            st.session_state.selected_phrases = set()

    phrase_cols = st.columns(2)
    for idx, phrase in enumerate(combined_phrases):
        checked = phrase in st.session_state.selected_phrases
        col = phrase_cols[idx % 2]
        new_val = col.checkbox(phrase, value=checked, key=f"phrase_{idx}")
        if new_val and phrase not in st.session_state.selected_phrases:
            st.session_state.selected_phrases.add(phrase)
        elif not new_val and phrase in st.session_state.selected_phrases:
            st.session_state.selected_phrases.remove(phrase)

    if st.button("Redact & Download PDF"):
        if not st.session_state.selected_phrases:
            st.warning("Select at least one phrase to redact.")
        else:
            with st.spinner("Redacting PDF..."):
                redacted_bytes = redact_pdf(
                    pdf_bytes,
                    st.session_state.highlights,
                    excluded_phrases=set(combined_phrases) - st.session_state.selected_phrases,
                )

            # Summary stats
            category_counts = {}
            for cat, matches in st.session_state.highlights.items():
                count = sum(1 for m in matches if m["text"] in st.session_state.selected_phrases)
                category_counts[cat] = count

            st.markdown("### Redaction Summary")
            for cat, count in category_counts.items():
                st.write(f"- **{cat}**: {count} redacted")

            b64_pdf = base64.b64encode(redacted_bytes).decode()
            st.markdown("### Redacted PDF Preview:")
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="700" height="900"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
            st.download_button(
                "Download redacted PDF",
                redacted_bytes,
                file_name="redacted_output.pdf",
                mime="application/pdf",
            )

if __name__ == "__main__":
    main()
