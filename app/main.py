import streamlit as st
import os
from utilities.extract_text import extract_text_from_file
from utilities.redact_pdf import redact_pdf

# Streamlit App
st.title("📄 Redactor API - OCR Integrated")

uploaded_file = st.file_uploader("Upload a PDF, TXT, or image file", type=["pdf", "txt", "png", "jpg", "jpeg"])

if uploaded_file:
    file_path = os.path.join("uploads", uploaded_file.name)
    os.makedirs("uploads", exist_ok=True)
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.success(f"Uploaded {uploaded_file.name}")

    search_word = st.text_input("Enter word to redact")
    
    if st.button("Process File"):
        if not search_word.strip():
            st.error("Please enter a search word before processing.")
        else:
            try:
                with st.spinner("Extracting text (OCR will run automatically if needed)..."):
                    text, previews = extract_text_from_file(file_path, return_previews=True)

                if text:
                    st.subheader("Extracted Text")
                    st.text_area("Text", text, height=200)

                    st.subheader("Preview with Bounding Boxes")
                    for img in previews:
                        st.image(img, use_container_width=True)

                    # Perform redaction
                    st.subheader("Redacted PDF")
                    redacted_path = redact_pdf(file_path, search_word)
                    with open(redacted_path, "rb") as f:
                        st.download_button("Download Redacted PDF", f, file_name="redacted.pdf")

                else:
                    st.warning("No text found, even after OCR.")

            except Exception as e:
                st.error(f"Error processing file: {e}")
