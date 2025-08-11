import streamlit as st
import fitz
from io import BytesIO
import base64
from app.utilities.redact_pdf import find_redaction_phrases, redact_pdf
import os

st.set_page_config(page_title="PDF Redactor", layout="centered")

if "uploaded_pdf" not in st.session_state:
    st.session_state.uploaded_pdf = None
if "phrases" not in st.session_state:
    st.session_state.phrases = {}
if "redact_selections" not in st.session_state:
    st.session_state.redact_selections = {}

st.title("PDF Redaction Tool")

uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    st.session_state.uploaded_pdf = pdf_bytes

if st.session_state.uploaded_pdf:
    # Options for redaction types
    redact_options = {
        "emails": st.checkbox("Emails", value=True),
        "phones": st.checkbox("Phone Numbers", value=True),
        "dates": st.checkbox("Dates", value=True),
        "addresses": st.checkbox("Addresses", value=True),
        "names": st.checkbox("Names", value=True),
    }

    # Find phrases if not found yet or options changed
    if not st.session_state.phrases or st.button("Refresh Phrases"):
        st.session_state.phrases = find_redaction_phrases(st.session_state.uploaded_pdf, redact_options)
        # Reset selections (default all included)
        st.session_state.redact_selections = {}
        for page_num, phrases in st.session_state.phrases.items():
            for i, phrase in enumerate(phrases):
                key = f"{page_num}_{i}"
                st.session_state.redact_selections[key] = True  # True means include for redaction

    if st.session_state.phrases:
        st.subheader("Redaction Phrases")
        # List phrases with radio buttons Include/Exclude
        for page_num, phrases in st.session_state.phrases.items():
            st.markdown(f"### Page {page_num + 1}")
            for i, phrase in enumerate(phrases):
                key = f"{page_num}_{i}"
                selection = st.radio(
                    label=phrase["text"],
                    options=["Include", "Exclude"],
                    index=0 if st.session_state.redact_selections.get(key, True) else 1,
                    key=key,
                    horizontal=True,
                )
                st.session_state.redact_selections[key] = (selection == "Include")

        # Show PDF preview with highlights on included phrases
        st.subheader("PDF Preview (highlighted phrases to redact)")

        def render_highlighted_pdf(pdf_bytes, phrases, selections):
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num, ph_list in phrases.items():
                page = doc[page_num]
                for i, ph in enumerate(ph_list):
                    key = f"{page_num}_{i}"
                    if selections.get(key):
                        rect = ph["rect"]
                        highlight = page.add_highlight_annot(rect)
                        highlight.update()
            output = BytesIO()
            doc.save(output)
            doc.close()
            output.seek(0)
            return output.read()

        preview_pdf = render_highlighted_pdf(st.session_state.uploaded_pdf, st.session_state.phrases, st.session_state.redact_selections)
        b64 = base64.b64encode(preview_pdf).decode()
        pdf_display = f'<iframe src="data:application/pdf;base64,{b64}" width="700" height="800" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)

        if st.button("Redact and Download"):
            # Prepare phrases to redact based on selections
            phrases_to_redact = {}
            for page_num, ph_list in st.session_state.phrases.items():
                filtered = []
                for i, ph in enumerate(ph_list):
                    key = f"{page_num}_{i}"
                    if st.session_state.redact_selections.get(key):
                        filtered.append(ph)
                if filtered:
                    phrases_to_redact[page_num] = filtered

            # Save uploaded pdf to temp file
            tmp_path = "temp_input.pdf"
            with open(tmp_path, "wb") as f:
                f.write(st.session_state.uploaded_pdf)

            output_path = redact_pdf(tmp_path, phrases_to_redact)
            with open(output_path, "rb") as f:
                redacted_pdf = f.read()

            # Clean up temp files
            os.remove(tmp_path)
            os.remove(output_path)

            st.download_button(
                label="Download Redacted PDF",
                data=redacted_pdf,
                file_name="redacted_output.pdf",
                mime="application/pdf"
            )
