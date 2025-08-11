import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
from utilities.extract_text import extract_text_from_pdf
from utilities.redact_pdf import find_redaction_matches

st.set_page_config(page_title="PDF Redactor", layout="centered")

st.title("PDF Redactor")
st.markdown("""
Drag and drop a PDF file below, or click the area to browse your files. Select what types of information you'd like to redact.
""")

# CSS hover effect for file uploader area
st.markdown("""
    <style>
    .stFileUploader > div:first-child {
        border: 2px dashed #ccc;
        padding: 2em;
        text-align: center;
        background-color: #f9f9f9;
        transition: all 0.3s ease;
        cursor: pointer;
        border-radius: 10px;
    }
    .stFileUploader > div:first-child:hover {
        background-color: #e6f7ff;
        box-shadow: 0 0 20px rgba(0,0,0,0.2);
        transform: scale(1.01);
    }
    </style>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload PDF", type="pdf", label_visibility="collapsed")

if uploaded_file:
    pdf_bytes = uploaded_file.read()

    st.subheader("Select Information to Redact")

    col1, col2 = st.columns(2)

    with col1:
        redact_names = st.checkbox("Names")
        redact_dates = st.checkbox("Dates")
        redact_emails = st.checkbox("Emails")
    with col2:
        redact_phone = st.checkbox("Phone Numbers")
        redact_addresses = st.checkbox("Addresses")
        redact_all = st.checkbox("Select All")

    if redact_all:
        redact_names = redact_dates = redact_emails = redact_phone = redact_addresses = True

    selected_options = {
        "names": redact_names,
        "dates": redact_dates,
        "emails": redact_emails,
        "phones": redact_phone,
        "addresses": redact_addresses
    }

    if any(selected_options.values()):
        matches = find_redaction_matches(pdf_bytes, selected_options)

        if matches:
            st.subheader("Detected Phrases for Redaction (check to exclude)")

            if "removed_phrases" not in st.session_state:
                st.session_state.removed_phrases = set()

            phrases_to_show = []
            for page_num, phrases in matches.items():
                for phrase_info in phrases:
                    phrase_text = phrase_info["text"]
                    key = f"{page_num}_{phrase_text}"
                    if key not in st.session_state.removed_phrases:
                        phrases_to_show.append((key, phrase_text))

            for key, phrase_text in phrases_to_show:
                exclude = st.checkbox(phrase_text, key=key)
                if exclude:
                    st.session_state.removed_phrases.add(key)
                elif key in st.session_state.removed_phrases:
                    st.session_state.removed_phrases.remove(key)

            filtered_matches = {}
            for page_num, phrases in matches.items():
                filtered = []
                for phrase_info in phrases:
                    phrase_text = phrase_info["text"]
                    key = f"{page_num}_{phrase_text}"
                    if key not in st.session_state.removed_phrases:
                        filtered.append(phrase_info)
                if filtered:
                    filtered_matches[page_num] = filtered

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            # Draw black rectangles for filtered phrases
            for page_num, page in enumerate(doc):
                page_matches = filtered_matches.get(page_num, [])
                for match in page_matches:
                    rect = match["rect"]
                    page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0))

            preview_images = []
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img_bytes = BytesIO(pix.tobytes("png"))
                preview_images.append(img_bytes)

            st.subheader("Preview of Redacted PDF")
            for img_bytes in preview_images:
                st.image(img_bytes)

            final_pdf = BytesIO()
            doc.save(final_pdf)
            final_pdf.seek(0)

            st.download_button(
                label="Download Redacted PDF",
                data=final_pdf,
                file_name="redacted_output.pdf",
                mime="application/pdf",
            )
        else:
            st.info("No matching phrases found to redact.")
    else:
        st.info("Select at least one type of information to redact.")
else:
    st.info("Please upload a PDF file.")
