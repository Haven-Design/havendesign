import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
from utilities.extract_text import extract_text_from_pdf
from utilities.redact_pdf import redact_pdf, find_redaction_matches

st.set_page_config(page_title="PDF Redactor", layout="centered")

st.title("PDF Redactor")
st.markdown("""
Drag and drop a PDF file below, or click the area to browse your files. Select what types of information you'd like to redact.
""")

# Custom CSS for hover effect on file uploader
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

def generate_pdf_preview_with_boxes(pdf_bytes, selected_options, removed_phrases):
    """Generate a preview with black boxes for redacted phrases."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    matches = find_redaction_matches(pdf_bytes, selected_options)

    # Filter out removed phrases from matches
    for page_num, rects_phrases in matches.items():
        new_rects = []
        for rect, phrase in rects_phrases:
            if phrase not in removed_phrases:
                new_rects.append((rect, phrase))
        matches[page_num] = new_rects

    # Draw black boxes on matches
    for page_num, rects_phrases in matches.items():
        page = doc[page_num]
        for rect, _ in rects_phrases:
            page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0))

    # Generate preview images
    preview_images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = BytesIO(pix.tobytes("png"))
        preview_images.append(img_bytes)

    # Save final redacted PDF bytes
    output_pdf = BytesIO()
    doc.save(output_pdf)
    output_pdf.seek(0)
    return preview_images, output_pdf, matches


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
        "addresses": redact_addresses,
    }

    if any(selected_options.values()):
        # Session state to track removed phrases
        if "removed_phrases" not in st.session_state:
            st.session_state.removed_phrases = set()

        preview_images, final_pdf, matches = generate_pdf_preview_with_boxes(
            pdf_bytes, selected_options, st.session_state.removed_phrases
        )

        # Show pr
