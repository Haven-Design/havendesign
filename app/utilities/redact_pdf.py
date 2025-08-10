import fitz
import re
import uuid
from io import BytesIO
from .extract_text import extract_text_from_pdf

def find_redaction_matches(pdf_bytes, options):
    words_by_page = extract_text_from_pdf(pdf_bytes)
    matches = {}

    patterns = []
    if options.get("names"):
        patterns.append(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b")
    if options.get("dates"):
        patterns.append(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?)\b")
    if options.get("emails"):
        patterns.append(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}")
    if options.get("phones"):
        patterns.append(r"\b(?:\+?\d{1,2}\s?)?(?:\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})\b")
    if options.get("addresses"):
        patterns.append(r"\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Lane|Ln)\b")
    if options.get("zipcodes"):
        patterns.append(r"\b\d{5}(?:-\d{4})?\b")

    combined_pattern = re.compile("|".join(patterns), re.IGNORECASE) if patterns else None

    for page_num, words in words_by_page.items():
        matches[page_num] = []
        if not combined_pattern:
            continue
        for w in words:
            x0, y0, x1, y1, text, *_ = w
            if combined_pattern.search(text):
                matches[page_num].append({
                    "id": str(uuid.uuid4()),
                    "rect": fitz.Rect(x0, y0, x1, y1),
                    "text": text
                })

    return matches

def apply_redactions(pdf_bytes, matches, opacity=1.0):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num, page_matches in matches.items():
        for m in page_matches:
            shape = doc[page_num].new_shape()
            shape.draw_rect(m["rect"])
            shape.finish(fill=(0, 0, 0), color=None)
            shape.commit(opacity=opacity)
    preview_images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = BytesIO(pix.tobytes("png"))
        preview_images.append(img_bytes)
    final_pdf = BytesIO()
    doc.save(final_pdf)
    final_pdf.seek(0)
    return preview_images, final_pdf
