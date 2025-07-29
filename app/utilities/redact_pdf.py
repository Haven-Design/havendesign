import fitz  # PyMuPDF
import re
import os
import tempfile
from typing import List

def redact_pdf(input_path: str, selected_redactions: List[str]) -> str:
    doc = fitz.open(input_path)

    patterns = {
        "Names": re.compile(r"(?i)(john doe|jane doe|alice smith|bob jones)"),
        "Phone Numbers": re.compile(r"(\+?\d{1,2}[\s.-]?)?(\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}"),
        "Email Addresses": re.compile(r"[\w\.-]+@[\w\.-]+"),
        "Dates": re.compile(r"\b(?:\d{1,2}[/-]){2}\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b"),
        "Social Security Numbers": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "Credit Card Numbers": re.compile(r"(?:\d[ -]*?){13,16}"),
        "IP Addresses": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    }

    for page in doc:
        text = page.get_text()
        for redaction_type in selected_redactions:
            pattern = patterns.get(redaction_type)
            if not pattern:
                continue
            for match in pattern.finditer(text):
                areas = page.search_for(match.group())
                for area in areas:
                    page.add_redact_annot(area, fill=(0, 0, 0))

    doc.apply_redactions()

    fd, output_path = tempfile.mkstemp(suffix="_redacted.pdf")
    os.close(fd)
    doc.save(output_path)
    doc.close()
    return output_path