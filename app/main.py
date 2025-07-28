import streamlit as st
import fitz  # PyMuPDF
import io
import re
from PIL import Image

st.set_page_config(page_title="PDF Redactor", layout="centered")
st.title("🔐 PDF Redactor")

st.markdown("Redact sensitive information like names, emails, and dates from your PDF.")

uploaded_file = st.file_uploader("Upload a PDF", type="pdf")

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    st.subheader("Preview PDF")
    pdf_to_images = []
    for page in doc:
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        pdf_to_images.append(img)

    for i, image in enumerate(pdf_to_images):
        st.image(image.resize((600, 800)), caption=f"Page {i + 1}", use_container_width=True)

    st.subheader("Choose What to Redact")
    redact_names = st.checkbox("Names (e.g., John Smith)")
    redact_emails = st.checkbox("Email Addresses")
    redact_dates = st.checkbox("Dates (e.g., July 8, 2023)")

    if st.button("Redact PDF"):
        with st.spinner("Redacting..."):
            name_pattern = r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"
            email_pattern = r"[\w\.-]+@[\w\.-]+"
            date_patterns = [
                r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:\s+\d{1,2})(?:,\s*\d{4})?',
                r'\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:,\s*\d{4})?'
            ]

            for page in doc:
                text = page.get_text()
                if redact_names:
                    for match in re.findall(name_pattern, text):
                        for inst in page.search_for(match):
                            page.add_redact_annot(inst, fill=(0, 0, 0))
                if redact_emails:
                    for match in re.findall(email_pattern, text):
                        for inst in page.search_for(match):
                            page.add_redact_annot(inst, fill=(0, 0, 0))
                if redact_dates:
                    for pattern in date_patterns:
                        for match in re.findall(pattern, text):
                            for inst in page.search_for(match):
                                page.add_redact_annot(inst, fill=(0, 0, 0))

            doc.apply_redactions()
            redacted_bytes = doc.write()

            st.success("Redaction complete!")
            st.download_button("Download Redacted PDF", redacted_bytes, file_name="redacted.pdf", mime="application/pdf")
