import streamlit as st
import os
import uuid
from app.utilities.redact_pdf import redact_pdf
from pdf2image import convert_from_path
import tempfile

st.set_page_config(page_title="AI PDF Redactor", layout="wide")
st.title("🔒 AI-Powered PDF Redactor")

# Redaction Options
st.subheader("🔧 Select What to Redact")
col1, col2, col3 = st.columns(3)

with col1:
    redact_name = st.checkbox("Name", value=True)
    redact_email = st.checkbox("Email", value=True)
    redact_phone = st.checkbox("Phone", value=True)
with col2:
    redact_address = st.checkbox("Address", value=True)
    redact_date = st.checkbox("Date", value=True)
    redact_ssn = st.checkbox("SSN", value=True)
with col3:
    redact_card = st.checkbox("Credit Card", value=True)
    custom_input = st.text_input("Custom Text (optional)")

selected = []
if redact_name: selected.append("Name")
if redact_email: selected.append("Email")
if redact_phone: selected.append("Phone")
if redact_address: selected.append("Address")
if redact_date: selected.append("Date")
if redact_ssn: selected.append("SSN")
if redact_card: selected.append("Credit Card")

uploaded_file = st.file_uploader("📄 Upload a PDF to redact", type=["pdf"])

if uploaded_file:
    input_path = os.path.join("uploaded_files", f"{uuid.uuid4()}_{uploaded_file.name}")
    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    output_filename = f"redacted_{os.path.basename(input_path)}"
    output_path = os.path.join("redacted_files", output_filename)

    if st.button("🔒 Redact Now"):
        st.info("Redacting document... Please wait.")

        try:
            redact_pdf(input_path, selected, output_path, custom_input)
            st.success("✅ Redaction complete!")

            # Convert all pages to preview images
            with tempfile.TemporaryDirectory() as temp_dir:
                images = convert_from_path(output_path, output_folder=temp_dir)
                for i, img in enumerate(images):
                    st.image(img, caption=f"Page {i+1}", use_container_width=True)

            with open(output_path, "rb") as f:
                st.download_button(
                    label="📥 Download Redacted PDF",
                    data=f,
                    file_name=output_filename,
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"Redaction failed: {str(e)}")