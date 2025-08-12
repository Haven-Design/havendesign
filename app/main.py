import os
import tempfile
import shutil
import pytesseract
from pytesseract import Output
from pdf2image import convert_from_path
from PIL import Image, ImageDraw
import streamlit as st

# ---------------------------
# Configure Tesseract path (bundled)
# ---------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TESSERACT_PATH = os.path.join(os.path.dirname(BASE_DIR), "Tesseract-OCR", "tesseract.exe")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="PDF Redactor with OCR", layout="wide")
st.title("📄 PDF Redactor with OCR + Color Bounding Boxes")

st.write("Upload a PDF, search for sensitive text, and preview redactions with color-coded boxes.")

# Search terms input
search_terms = st.text_area(
    "Enter sensitive words or phrases to redact (one per line):",
    height=150
).splitlines()
search_terms = [t.strip() for t in search_terms if t.strip()]

uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_pdf and search_terms:
    # Create temp dir
    temp_dir = tempfile.mkdtemp()
    pdf_path = os.path.join(temp_dir, uploaded_pdf.name)
    with open(pdf_path, "wb") as f:
        f.write(uploaded_pdf.read())

    # Convert PDF to images
    st.info("Converting PDF pages to images...")
    images = convert_from_path(pdf_path)

    processed_images = []
    colors = ["red", "blue", "green", "orange", "purple", "cyan"]

    for page_num, img in enumerate(images, start=1):
        st.write(f"**Processing page {page_num}...**")

        # OCR with bounding box data
        ocr_data = pytesseract.image_to_data(img, output_type=Output.DICT)

        draw = ImageDraw.Draw(img)

        for i, word in enumerate(ocr_data["text"]):
            if word.strip() != "":
                for idx, term in enumerate(search_terms):
                    if term.lower() in word.lower():
                        color = colors[idx % len(colors)]
                        (x, y, w, h) = (
                            ocr_data["left"][i],
                            ocr_data["top"][i],
                            ocr_data["width"][i],
                            ocr_data["height"][i]
                        )
                        draw.rectangle([x, y, x + w, y + h], outline=color, width=3)

        processed_images.append(img)

        st.image(img, caption=f"Page {page_num} preview", use_container_width=True)

    # Download redacted PDF
    output_pdf_path = os.path.join(temp_dir, "redacted_output.pdf")
    processed_images[0].save(
        output_pdf_path, save_all=True, append_images=processed_images[1:]
    )

    with open(output_pdf_path, "rb") as f:
        st.download_button(
            label="⬇️ Download Redacted PDF",
            data=f,
            file_name="redacted_output.pdf",
            mime="application/pdf"
        )

    # Cleanup temp dir after session
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
