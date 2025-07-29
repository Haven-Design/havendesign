import os
import tempfile
import streamlit as st
from utilities.redact_pdf import redact_pdf
import base64

st.title("PDF Redactor")

uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")

options = [
    "Emails",
    "Phone Numbers",
    "Dates",
    "Names",
    "SSNs",
    "Addresses",
    "Credit Cards"
]

selected_options = st.multiselect("Select what to redact", options, default=options)

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_input:
        tmp_input.write(uploaded_file.read())
        tmp_input_path = tmp_input.name

    if st.button("Redact PDF"):
        with st.spinner("Redacting..."):
            output_path = redact_pdf(tmp_input_path, selected_options)

            if output_path and os.path.exists(output_path):
                # Read redacted file as bytes
                with open(output_path, "rb") as f:
                    redacted_bytes = f.read()

                # Download button
                st.download_button(
                    label="Download Redacted PDF",
                    data=redacted_bytes,
                    file_name="redacted_output.pdf",
                    mime="application/pdf"
                )

                # Inline viewer
                pdf_base64 = base64.b64encode(redacted_bytes).decode("utf-8")
                pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_base64}" width="700" height="1000" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
            else:
                st.error("Redaction failed or output file not found.")
