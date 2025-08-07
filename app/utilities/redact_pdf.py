import fitz  # PyMuPDF
import re
import spacy
import pdfplumber

# Load English NLP model (only needs to be downloaded once via: python -m spacy download en_core_web_sm)
nlp = spacy.load("en_core_web_sm")

# Regex patterns for common sensitive info
REGEX_PATTERNS = {
    "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b",
    "Phone": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "Date": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    "Credit Card": r"\b(?:\d[ -]*?){13,16}\b"
}

# NLP entity labels mapped to fields
NLP_LABELS = {
    "Name": ["PERSON"],
    "Address": ["GPE", "LOC"],
    "Date": ["DATE"]
}


def get_phrases_to_redact(text, selected_fields, custom_text=None):
    found_phrases = set()

    # Use regex
    for field in selected_fields:
        pattern = REGEX_PATTERNS.get(field)
        if pattern:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            found_phrases.update(matches)

    # Use NLP
    if any(f in NLP_LABELS for f in selected_fields):
        doc = nlp(text)
        for ent in doc.ents:
            for field in selected_fields:
                if field in NLP_LABELS and ent.label_ in NLP_LABELS[field]:
                    found_phrases.add(ent.text)

    # Add custom text
    if custom_text and len(custom_text.strip()) > 2:
        found_phrases.add(custom_text.strip())

    return list(found_phrases)


def redact_text(text, selected_fields, custom_text=None):
    """Redacts sensitive phrases from plain text using the same rules as PDF redaction."""
    phrases = get_phrases_to_redact(text, selected_fields, custom_text)
    redacted_text = text
    for phrase in phrases:
        # Replace with [REDACTED] preserving phrase length for realism (optional)
        redacted_text = re.sub(re.escape(phrase), "[REDACTED]", redacted_text, flags=re.IGNORECASE)
    return redacted_text


def redact_pdf(input_path, selected_fields, output_path, custom_text=None):
    doc = fitz.open(input_path)

    with pdfplumber.open(input_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            phrases = get_phrases_to_redact(text, selected_fields, custom_text)
            if not phrases:
                continue

            fitz_page = doc[i]
            for phrase in phrases:
                try:
                    matches = fitz_page.search_for(phrase)
                    for m in matches:
                        fitz_page.add_redact_annot(m, fill=(0, 0, 0))
                except Exception:
                    continue

            fitz_page.apply_redactions()

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
