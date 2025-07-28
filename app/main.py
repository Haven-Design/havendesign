import fitz  # PyMuPDF
import re
import spacy
from typing import List

# Load spaCy model with NER	nlp = spacy.load("en_core_web_sm")

# Regular expressions for pattern-based detection
PATTERNS = {
    "PHONE": re.compile(r"(\+?\d{1,2}[\s-]?)?(\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CREDIT_CARD": re.compile(r"(?:\d[ -]*?){13,16}"),
    "DATE": re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2}, \d{4})\b")
}

# Entity labels to look for from spaCy
ENTITY_LABELS = {
    "PERSON": "PERSON",
    "GPE": "GPE",
    "DATE": "DATE",
    "ORG": "ORG",
    "LOC": "LOC",
    "ADDRESS": "ADDRESS"
}

def find_sensitive_data(text: str, redact_types: List[str]) -> List[str]:
    sensitive = set()
    doc = nlp(text)

    # Named Entity Recognition
    if any(k in redact_types for k in ENTITY_LABELS):
        for ent in doc.ents:
            if ent.label_ in redact_types:
                sensitive.add(ent.text.strip())

    # Regex-based matches
    if "PHONE" in redact_types:
        sensitive.update(PATTERNS["PHONE"].findall(text))
    if "SSN" in redact_types:
        sensitive.update(PATTERNS["SSN"].findall(text))
    if "CREDIT_CARD" in redact_types:
        sensitive.update(PATTERNS["CREDIT_CARD"].findall(text))
    if "DATE" in redact_types:
        sensitive.update(PATTERNS["DATE"].findall(text))

    # Normalize and clean
    return [s for s in sensitive if s.strip() != ""]

def redact_pdf(input_path: str, output_path: str, redact_types: List[str]) -> None:
    doc = fitz.open(input_path)

    for page in doc:
        text = page.get_text()
        sensitive_items = find_sensitive_data(text, redact_types)

        for item in sensitive_items:
            text_instances = page.search_for(item, quads=True)
            for inst in text_instances:
                page.add_redact_annot(inst.rect, fill=(0, 0, 0))

        page.apply_redactions()

    doc.save(output_path)
    doc.close()
