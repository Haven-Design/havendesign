import re
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter

def redact_text(text, redact_names, redact_addresses, redact_dates):
    if redact_names:
        text = re.sub(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", "[REDACTED NAME]", text)
    if redact_addresses:
        text = re.sub(r"\d{1,5}\s\w+\s(?:Street|St|Avenue|Ave|Rd|Road|Blvd|Lane|Ln|Drive|Dr)\b", "[REDACTED ADDRESS]", text)
    if redact_dates:
        text = re.sub(r"\b(?:\d{1,2}[/-])?\d{1,2}[/-]\d{2,4}\b", "[REDACTED DATE]", text)
        text = re.sub(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b", "[REDACTED DATE]", text)
    return text

def redact_pdf(pdf_bytes, pages_to_redact, redact_names, redact_addresses, redact_dates):
    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if i in pages_to_redact:
            redacted_text = redact_text(text, redact_names, redact_addresses, redact_dates)
            page.clear_text()
            page.add_text(redacted_text)  # This may require external lib if you're adding visual overlays
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
