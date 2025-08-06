import streamlit as st
import os
import uuid
from app.utilities.redact_pdf import redact_pdf
from pdf2image import convert_from_path
from PIL import Image
import tempfile

st.set_page_config(page_title="AI PDF Redactor", layout="centered")
st.title("🔒 AI-Powered PDF Redactor")

# Sidebar options
st.sidebar.header("Redaction Settings")
default_fields = ["Name", "Email", "Phone", "Address", "Date", "SSN", "Credit Card"]
selected = st.sidebar.multiselect("Select fields to redact:", default_fields, default=default_fields)
custom_input = st.sidebar.text_input("Custom text to redact (optional):")

uploaded_file = st.file_uploader("📄 Upload a PDF to redact", type=["pdf"])

if uploaded_file:
    # Save uploaded file temporarily
    input_path = os.path.join("uploaded_files", f"{uuid.uuid4()}_{uploaded_file.name}")
    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    output_filename = f"redacted_{os.path.basename(input_path)}"
    output_path = os.path.join("redacted_files", output_filename)

    if st.button("🔧 Redact PDF"):
        st.info("Running redaction engine...")

        try:
            redact_pdf(input_path, selected, output_path, custom_input)
            st.success("✅ Redaction complete!")

            # Convert all pages to preview images
            with tempfile.TemporaryDirectory() as temp_dir:
                images = convert_from_path(output_path, output_folder=temp_dir)
                for i, img in enumerate(images):
                    st.image(img, caption=f"Redacted Page {i + 1}", use_container_width=True)

            with open(output_path, "rb") as f:
                st.download_button(
                    label="📥 Download Redacted PDF",
                    data=f,
                    file_name=output_filename,
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"❌ Redaction failed: {str(e)}")