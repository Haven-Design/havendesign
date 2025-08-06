import streamlit as st
from utilities.redact_pdf import redact_pdf
import os
import uuid
from pdf2image import convert_from_path

# Create necessary folders if not present
os.makedirs("uploaded_files", exist_ok=True)
os.makedirs("redacted_files", exist_ok=True)

st.set_page_config(page_title="PDF Redactor", layout="centered")
st.title("📄 PDF Redactor")

st.write("Upload a PDF, select what you want to redact, and download a redacted version.")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

# 🔧 Use individual checkboxes
st.subheader("Select what to redact:")
redact_fields = ["Name", "Date", "Email", "Phone", "Address", "Credit Card", "SSN"]
selected = []
for field in redact_fields:
    if st.checkbox(field, value=True):
        selected.append(field)

custom_input = st.text_input("Custom text to redact (optional)")

if uploaded_file:
    file_id = str(uuid.uuid4())
    input_path = os.path.join("uploaded_files", f"{file_id}_{uploaded_file.name}")
    output_path = os.path.join("redacted_files", f"redacted_{file_id}.pdf")

    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    st.success("✅ PDF uploaded successfully!")

    if st.button("Redact PDF"):
        st.write("🔧 Starting redaction...")

        redact_pdf(input_path, selected, output_path, custom_input)
        st.success("✅ Redaction complete.")

        # 🔍 Preview first page using pdf2image
        try:
            st.subheader("Preview (Page 1):")
            images = convert_from_path(output_path, first_page=1, last_page=1)
            for img in images:
                st.image(img, use_container_width=True)

            # 📥 Offer download
            with open(output_path, "rb") as f:
                st.download_button(
                    label="📥 Download Redacted PDF",
                    data=f,
                    file_name=f"redacted_{uploaded_file.name}",
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"⚠️ Error generating preview: {str(e)}\n\nMake sure Poppler is installed and in PATH.")
