import streamlit as st
from pathlib import Path
from utilities.redact_pdf import detect_sensitive_info, redact_pdf

st.set_page_config(page_title="PDF Redactor", layout="wide")

st.title("🔒 PDF Redaction Tool")

uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

if uploaded_file:
    temp_input_path = Path("temp_input.pdf")
    with open(temp_input_path, "wb") as f:
        f.write(uploaded_file.read())

    st.subheader("Detected Sensitive Information")
    detections = detect_sensitive_info(temp_input_path)

    if not detections:
        st.info("No sensitive information found.")
    else:
        # Show table with checkboxes
        checkboxes = {}
        for page_num, text, pattern_name in detections:
            key = f"{page_num}-{text}-{pattern_name}"
            checkboxes[key] = st.checkbox(
                f"[Page {page_num+1}] ({pattern_name}) → {text}",
                value=True
            )

        # Select / Deselect All
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Select All"):
                for k in checkboxes:
                    checkboxes[k] = True
        with col2:
            if st.button("Deselect All"):
                for k in checkboxes:
                    checkboxes[k] = False

        if st.button("Redact Selected"):
            selected = [
                (p, t, n) for (p, t, n) in detections
                if checkboxes[f"{p}-{t}-{n}"]
            ]
            if not selected:
                st.warning("No items selected for redaction.")
            else:
                output_path = Path("redacted_output.pdf")
                redact_pdf(temp_input_path, selected, output_path)

                with open(output_path, "rb") as f:
                    st.download_button(
                        "Download Redacted PDF",
                        data=f,
                        file_name="redacted.pdf",
                        mime="application/pdf"
                    )
