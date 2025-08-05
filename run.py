import streamlit as st
from app.utilities.redact_pdf import redact_pdf
import os
import uuid
from PyPDF2 import PdfReader
from pdf2image import convert_from_path

st.set_page_config(page_title="PDF Redactor", layout="centered")

st.title("📄 PDF Redactor")
st.write("Upload a PDF, select what you want to redact, and download a redacted version.")

uploaded_file = st.file_uploader("Choose a PDF", type="pdf")

redact_options = ["Name", "Date", "Email", "Phone", "Address", "Credit Card", "SSN"]
selected = st.multiselect("What do you want to redact?", options=redact_options, default=redact_options)

custom_input = st.text_input("Custom text to redact (optional)")

if uploaded_file:
    file_id = str(uuid.uuid4())
    input_path = os.path.join("uploaded_files", f"{file_id}_{uploaded_file.name}")
    output_path = os.path.join("redacted_files", f"redacted_{file_id}.pdf")

    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    st.success("PDF uploaded successfully!")

    if st.button("Redact PDF"):
        # Simulate one redaction box per selected tag on page 1
        areas = {
            "0": [  # Page 0
                {"x0": 50, "y0": 50 + i * 20, "x1": 300, "y1": 65 + i * 20}
                for i in range(len(selected))
            ]
        }

        redact_pdf(input_path, areas, output_path)

        st.success("Redaction complete.")

        # Show preview of redacted PDF
        st.subheader("Preview (first page only):")
        images = convert_from_path(output_path, first_page=1, last_page=1)
        for img in images:
            st.image(img, use_column_width=True)

        # Offer download
        with open(output_path, "rb") as f:
            st.download_button(
                label="📥 Download Redacted PDF",
                data=f,
                file_name=f"redacted_{uploaded_file.name}",
                mime="application/pdf"
            )
