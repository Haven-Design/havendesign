# app/utilities/extract_text.py
import fitz
from io import BytesIO
from PIL import Image
import pytesseract
from docx import Document
import tempfile
import os

def pdf_bytes_from_text_lines(lines, page_size=(595, 842)):
    """
    Create a simple PDF bytes from a list of text lines (for .txt or docx content).
    page_size default is roughly A4/letter points.
    """
    doc = fitz.open()
    # set simple page with top margin and write text
    fontsize = 11
    margin = 72
    line_height = fontsize + 2
    page_w, page_h = page_size
    page = doc.new_page(width=page_w, height=page_h)
    y = margin
    for line in lines:
        if y + line_height > page_h - margin:
            page = doc.new_page(width=page_w, height=page_h)
            y = margin
        page.insert_text((margin, y), line, fontsize=fontsize)
        y += line_height
    out = doc.tobytes()
    doc.close()
    return out

def image_bytes_to_pdf_bytes(image_bytes):
    """
    Insert image into a PDF page sized to the image, return PDF bytes.
    """
    img = Image.open(BytesIO(image_bytes))
    width, height = img.size
    pdf_doc = fitz.open()
    page = pdf_doc.new_page(width=width, height=height)
    # insert image as full-page
    page.insert_image(page.rect, stream=image_bytes)
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()
    return pdf_bytes

def docx_to_pdf_bytes(docx_bytes):
    """
    Extract text from docx and render to PDF bytes (text-based).
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    tmp.write(docx_bytes)
    tmp.close()
    doc = Document(tmp.name)
    paragraphs = []
    for p in doc.paragraphs:
        paragraphs.append(p.text)
    os.unlink(tmp.name)
    return pdf_bytes_from_text_lines(paragraphs)

def convert_upload_to_pdf_bytes(uploaded_file):
    """
    Accepts uploaded_file (Streamlit UploadedFile) and returns PDF bytes.
    Supports: pdf, png/jpg/jpeg, txt, docx.
    """
    fname = uploaded_file.name.lower()
    data = uploaded_file.read()
    if fname.endswith(".pdf"):
        return data
    if fname.endswith((".png", ".jpg", ".jpeg")):
        # return PDF bytes with image as a page
        return image_bytes_to_pdf_bytes(data)
    if fname.endswith(".txt"):
        try:
            txt = data.decode("utf-8", errors="ignore")
        except Exception:
            txt = str(data)
        lines = txt.splitlines()
        return pdf_bytes_from_text_lines(lines)
    if fname.endswith(".docx"):
        return docx_to_pdf_bytes(data)
    raise ValueError("Unsupported file type. Allowed: pdf, png/jpg/jpeg, txt, docx.")
