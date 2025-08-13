import streamlit as st
import requests
import pdfplumber
import os

# Set your API URL
API_URL = "https://redactor-api-url-here"  # Replace with actual Redactor API endpoint

st.set_page_config(page_title="PDF Redactor", layout="wide")

st.title("PDF Redactor")
st.write("Upload a PDF and redact sensitive information using the Redactor API.")

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded_file is not None:
    st.success(f"Uploaded: {uploaded_file.name}")
    
    if st.button("Process PDF"):
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                extracted_text = ""
                for page in pdf.pages:
                    extracted_text += page.extract_text() or ""
            
            if not extracted_text.strip():
                st.error("No text found in the PDF.")
            else:
                st.info("Sending text to Redactor API...")
                response = requests.post(
                    API_URL,
                    json={"text": extracted_text}
                )

                if response.status_code == 200:
                    result = response.json()
                    redacted_text = result.get("redacted_text", "")
                    
                    st.subheader("Redacted Text Output")
                    st.text_area("Result", redacted_text, height=400)
                else:
                    st.error(f"API request failed: {response.status_code} - {response.text}")

        except Exception as e:
            st.error(f"Error processing PDF: {e}")
