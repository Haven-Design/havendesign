import streamlit as st
import fitz  # PyMuPDF
import io
from app.utilities.extract_text import extract_text_from_pdf
from app.utilities.redact_pdf import redact_text

st.set_page_config(page_title="PDF Redactor", layout="centered")

st.title("PDF Redactor")
st.markdown("""
Drag and drop a PDF file below, or click the area to browse your files.  
Select what types of information you'd like to redact.
""")

# Hover effect for file upload
st.markdown("""
    <style>
    .stFileUploader > div:first-child {
        border: 2px dashed #ccc;
        padding: 2em;
        text-align: center;
        background-color: #f9f9f9;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    .stFileUploader > div:first-child:hover {
        background-color: #e6f7ff;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.2);
        transform: scale(1.01);
    }
    </style>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload PDF", type="pdf", label_visibility="collapsed")

def generate_pdf_preview(pdf_bytes, options):
    """Return a list of image bytes for preview."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    extracted_text = extract_text_from_pdf(pdf_bytes)
    redactions = redact_text(extracted_text, options, return_matches=True)  # Assuming redact_text can return match locations

    # Apply redactions visually
    for page_num in range(len(doc)):
        page = doc[page_num]
        if page_num in redactions:
            for rect in redactions[page_num]:
                page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()

    # Convert pages to images
    preview_images = []
    for page_num in range(len(doc)):
        pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(2, 2))  # higher res
        img_bytes = pix.tobytes("png")
        preview_images.append(img_bytes)

    return preview_images, doc

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
        preview_images, final_doc = generate_pdf_preview(pdf_bytes, selected_options)

        st.subheader("Preview of Redacted PDF")
        for img_bytes in preview_images:
            st.image(img_bytes, use_container_width=True)

        # Download final redacted PDF
        output_stream = io.BytesIO()
        final_doc.save(output_stream)
        st.download_button(
            "Download Redacted PDF",
            data=output_stream.getvalue(),
            file_name="redacted_output.pdf",
            mime="application/pdf"
        )

    else:
        st.info("Select at least one option to redact.")
