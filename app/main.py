import pytesseract
from PIL import Image
import os
import subprocess
import shutil

# --- CONFIGURE PATHS HERE ---
# Path to Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\CrKegley\OneDrive - Jenzabar, Inc\Documents\Z-Personal Projects\Redactor-API\Tesseract-OCR\tesseract.exe"

# Path to ImageMagick executable
MAGICK_PATH = r"C:\Users\CrKegley\OneDrive - Jenzabar, Inc\Documents\Z-Personal Projects\Redactor-API\ImageMagick-7.1.2-Q16-HDRI\magick.exe"

# Path to your PDF file
PDF_PATH = r"C:\Users\CrKegley\OneDrive - Jenzabar, Inc\Documents\Z-Personal Projects\Redactor-API\app\samples\test.pdf"


def convert_pdf_to_images(pdf_path, output_folder):
    """Convert a PDF into individual image files using ImageMagick."""
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)  # Clean out old images
    os.makedirs(output_folder, exist_ok=True)

    output_pattern = os.path.join(output_folder, "page-%d.png")

    cmd = [
        MAGICK_PATH,
        "-density", "300",  # High quality
        pdf_path,
        "-quality", "100",
        output_pattern
    ]

    subprocess.run(cmd, check=True)


def ocr_image(image_path):
    """Run OCR on an image and return the extracted text."""
    text = pytesseract.image_to_string(Image.open(image_path))
    return text


def process_pdf(pdf_path):
    """Convert PDF to images and run OCR on each."""
    images_folder = "temp_images"
    convert_pdf_to_images(pdf_path, images_folder)

    all_text = ""
    for filename in sorted(os.listdir(images_folder)):
        if filename.lower().endswith(".png"):
            image_path = os.path.join(images_folder, filename)
            text = ocr_image(image_path)
            all_text += f"\n--- {filename} ---\n{text}"

    return all_text


if __name__ == "__main__":
    extracted_text = process_pdf(PDF_PATH)
    print(extracted_text)
