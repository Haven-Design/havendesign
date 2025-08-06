import streamlit as st
import os
import uuid
from app.utilities.redact_pdf import redact_pdf
from pdf2image import convert_from_path
import tempfile

st.set_page_config(page_title="PDF Redactor", layout="wide")
st.title("PDF Redactor")

uploaded_file = st.file_uploader("Upload a PDF to redact", type=["pdf"])

if uploaded_file:
    st.markdown("### Redaction Options")
    select_all = st.checkbox("Select All")

    col1, col2, col3 = st.columns(3)

    with col1:
        redact_name = st.checkbox("Name", value=select_all)
        redact_email = st.checkbox("Email", value=select_all)
    with col2:
        redact_phone = st.checkbox("Phone", value=select_all)
        redact_address = st.checkbox("Address", value=select_all)
    with col3:
        redact_date = st.checkbox("Date", value=select_all)
        redact_ssn = st.checkbox("SSN", value=select_all)
        redact_card = st.checkbox("Credit Card", value=select_all)

    custom_input = st.text_input("Custom Text (optional)")

    selected = []
    if redact_name: selected.append("Name")
    if redact_email: selected.append("Email")
    if redact_phone: selected.append("Phone")
    if redact_address: selected.append("Address")
    if redact_date: selected.append("Date")
    if redact_ssn: selected.append("SSN")
    if redact_card: selected.append("Credit Card")

    st.markdown("---")

    input_path = os.path.join("uploaded_files", f"{uuid.uuid4()}_{uploaded_file.name}")
    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    output_filename = f"redacted_{os.path.basename(input_path)}"
    output_path = os.path.join("redacted_files", output_filename)

    if st.button("Redact Now"):
        st.info("Redacting document...")

        try:
            redact_pdf(input_path, selected, output_path, custom_input)
            st.success("Redaction complete.")

            with tempfile.TemporaryDirectory() as temp_dir:
                images = convert_from_path(output_path, output_folder=temp_dir)
                for i, img in enumerate(images):
                    st.image(img, caption=f"Page {i+1}", use_container_width=True)

            with open(output_path, "rb") as f:
                st.download_button(
                    label="Download Redacted PDF",
                    data=f,
                    file_name=output_filename,
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"Redaction failed: {str(e)}")
