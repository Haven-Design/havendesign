# app/utilities/redact_pdf.py
import fitz  # PyMuPDF
import re
import os
import uuid

def redact_pdf(file_path, redaction_types, custom_inputs):
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        print(f"Error opening PDF file: {e}")
        return None

    if "all" in redaction_types:
        redaction_types = ["names", "emails", "phones", "dates", "ssns"]

    patterns = []

    if "names" in redaction_types:
        patterns.append((r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", "[REDACTED NAME]"))
    if "emails" in redaction_types:
        patterns.append((r"\b[\w.-]+?@\w+?\.\w+?\b", "[REDACTED EMAIL]"))
    if "phones" in redaction_types:
        patterns.append((r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "[REDACTED PHONE]"))
    if "dates" in redaction_types:
        patterns.append((r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "[REDACTED DATE]"))
        patterns.append((r"\b\d{4}-\d{2}-\d{2}\b", "[REDACTED DATE]"))
    if "ssns" in redaction_types:
        patterns.append((r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED SSN]"))

    for term in custom_inputs:
        if term:
            patterns.append((re.escape(term), "[REDACTED CUSTOM]"))

    try:
        for page in doc:
            text = page.get_text()
            for pattern, replacement in patterns:
                matches = list(re.finditer(pattern, text))
                for match in matches:
                    inst = page.search_for(match.group())
                    for rect in inst:
                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        page.insert_text(rect.tl, replacement, fontsize=8, color=(1, 1, 1))
            page.apply_redactions()

        redacted_filename = f"redacted_{uuid.uuid4()}.pdf"
        redacted_path = os.path.join(os.path.dirname(file_path), redacted_filename)
        doc.save(redacted_path)
        doc.close()
        return redacted_path

    except Exception as e:
        print(f"Error during redaction: {e}")
        return None
