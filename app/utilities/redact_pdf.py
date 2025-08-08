import fitz  # PyMuPDF
from io import BytesIO
import re

# Example patterns – these can be expanded or adjusted
PATTERNS = {
    "names": r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b",
    "dates": r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    "emails": r"\b\S+@\S+\.\S+\b",
    "phones": r"\b(?:\(\d{3}\)\s*|\d{3}[-\s])\d{3}[-\s]\d{4}\b",
    "addresses": r"\b\d+\s+\w+\s+(Street|St|Avenue|Ave|Road|Rd)\b"
}

def find_redaction_matches(pdf_bytes, options):
    """Return detected phrases with coordinates, grouped by page."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    matches_by_page = {}

    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        matches_for_page = []

        for category, enabled in options.items():
            if not enabled:
                continue
            pattern = PATTERNS.get(category)
            if not pattern:
                continue

            for match in re.finditer(pattern, text):
                phrase = match.group(0)
                rects = page.search_for(phrase)
                for rect in rects:
                    matches_for_page.append({
                        "phrase": phrase,
                        "rect": rect
                    })

        if matches_for_page:
            matches_by_page[page_num] = matches_for_page

    return matches_by_page


def apply_redactions(pdf_bytes, matches_by_page, user_choices):
    """Apply black box redactions only to user-selected phrases."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_num, matches in matches_by_page.items():
        selected_phrases = user_choices.get(page_num, [])
        for match in matches:
            if match["phrase"] in selected_phrases:
                page = doc[page_num]
                page.add_redact_annot(match["rect"], fill=(0, 0, 0))

    # Apply all annotations
    for page in doc:
        page.apply_redactions()

    # Create preview images
    preview_images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = BytesIO(pix.tobytes("png"))
        preview_images.append(img_bytes)

    # Save final PDF
    final_pdf = BytesIO()
    doc.save(final_pdf)
    final_pdf.seek(0)

    return preview_images, final_pdf
