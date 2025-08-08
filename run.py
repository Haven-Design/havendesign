import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
from app.utilities.extract_text import extract_text_from_pdf
from app.utilities.redact_pdf import redact_text

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


def generate_pdf_preview_with_boxes(pdf_bytes, options):
    """Generate a preview of the PDF with black box redactions."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    extracted_text = extract_text_from_pdf(pdf_bytes)

    # Get text matches for redaction
    matches = redact_text(extracted_text, options, return_matches=True)

    # Apply black boxes
    for page_num, page in enumerate(doc):
        page_matches = matches.get(page_num, [])
        for rect in page_matches:
            page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0))

    # Convert each page to PNG bytes for preview
    preview_images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = BytesIO(pix.tobytes("png"))
        preview_images.append(img_bytes)

    # Save the final redacted PDF
    final_pdf = BytesIO()
    doc.save(final_pdf)
    final_pdf.seek(0)

    return preview_images, final_pdf


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

    # Select All behavior
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
        preview_images, final_doc = generate_pdf_preview_with_boxes(pdf_bytes, selected_options)

        st.subheader("Preview of Redacted PDF")
        for img_bytes in preview_images:
            st.image(img_bytes)

        st.download_button(
            "Download Redacted PDF",
            final_doc,
            file_name="redacted_output.pdf",
            mime="application/pdf"
        )
    else:
        st.info("Select at least one option to redact.")
