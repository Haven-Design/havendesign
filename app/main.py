import streamlit as st
import os
from utilities.redact_pdf import redact_pdf

st.set_page_config(page_title="PDF Redactor", layout="centered")
st.title("📄 PDF Redactor")

st.markdown("""
Easily redact sensitive information from PDFs. 
Select what you'd like to redact and upload your file.
""")

# Redaction options
options = [
    "Names",
    "Phone Numbers",
    "Email Addresses",
    "Dates",
    "Social Security Numbers",
    "Credit Card Numbers",
    "IP Addresses"
]

selected_options = st.multiselect("What would you like to redact?", options, default=options)

uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file and selected_options:
    with st.spinner("Redacting PDF..."):
        tmp_path = os.path.join("temp_input.pdf")
        with open(tmp_path, "wb") as f:
            f.write(uploaded_file.read())

        output_path = redact_pdf(tmp_path, selected_options)

        with open(output_path, "rb") as f:
            redacted_data = f.read()

        st.success("✅ Redaction complete!")

        with st.expander("📄 Preview PDF", expanded=False):
            st.download_button("⬇ Download Redacted PDF", redacted_data, file_name="redacted_output.pdf")
            st.components.v1.html(f"""
                <iframe src="data:application/pdf;base64,{redacted_data.encode('base64').decode()}"
                        width="100%" height="500px" type="application/pdf"></iframe>
            """, height=500)

        os.remove(tmp_path)
        os.remove(output_path)

else:
    st.info("Please upload a PDF and select at least one redaction option.")