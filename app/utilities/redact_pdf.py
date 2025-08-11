import fitz  # PyMuPDF
import re
import spacy

# Load NLP model once
nlp = spacy.load("en_core_web_sm")

# Regex patterns for sensitive info with new categories added
REGEX_PATTERNS = {
    "emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b",
    "phones": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "dates": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    "zip_codes": r"\b\d{5}(?:-\d{4})?\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_cards": r"\b(?:\d[ -]*?){13,16}\b",
    "passport": r"\b[A-PR-WYa-pr-wy][1-9]\d\s?\d{4}[1-9]\b",  # very crude example pattern
    "drivers_license": r"\b[A-Z]{1,2}\d{4,6}\b",  # simplified example for US states
    "addresses": r"\d{1,5}\s\w+(\s\w+){0,5}",  # crude address pattern
}

# NLP entity labels
NLP_LABELS = {
    "names": ["PERSON"],
    "addresses": ["GPE", "LOC", "FAC"],
    "dates": ["DATE"],
}

def find_redaction_phrases(pdf_bytes, options):
    """
    Returns dictionary: {page_num: [ {"text": phrase, "rect": fitz.Rect}, ... ], ...}
    'options' is a dict mapping category keys to booleans for whether to search them.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    matches = {}

    for page_num, page in enumerate(doc):
        page_text = page.get_text()
        page_matches = []

        # Regex matches per enabled category
        for key, pattern in REGEX_PATTERNS.items():
            if options.get(key, False):
                for match in re.finditer(pattern, page_text, flags=re.IGNORECASE):
                    phrase = match.group()
                    # Get rects for phrase
                    rects = page.search_for(phrase)
                    for rect in rects:
                        page_matches.append({"text": phrase, "rect": rect})

        # NLP matches
        if any(options.get(field, False) for field in NLP_LABELS.keys()):
            doc_spacy = nlp(page_text)
            for ent in doc_spacy.ents:
                for field, labels in NLP_LABELS.items():
                    if options.get(field, False) and ent.label_ in labels:
                        phrase = ent.text
                        rects = page.search_for(phrase)
                        for rect in rects:
                            page_matches.append({"text": phrase, "rect": rect})

        if page_matches:
            matches[page_num] = page_matches

    return matches


def redact_pdf(pdf_bytes, highlights, excluded_phrases=None):
    """
    Redacts all phrases in highlights except those in excluded_phrases.
    Returns redacted PDF bytes.
    """
    if excluded_phrases is None:
        excluded_phrases = set()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_num, page_matches in highlights.items():
        page = doc[page_num]
        for match in page_matches:
            phrase = match["text"]
            if phrase in excluded_phrases:
                continue  # skip redacting this phrase

            rect = match["rect"]
            # Use a transparent gray fill with red border on hover effect (Streamlit can't do hover in PDF, so just normal redaction here)
            fill = (0.5, 0.5, 0.5, 0.3)  # RGBA grey fill (will appear as solid in PDF viewer)
            # Add redact annotation (PyMuPDF doesn’t support border color in add_redact_annot, so no border here)
            page.add_redact_annot(rect, fill=fill)

        page.apply_redactions()

    output = doc.tobytes()
    doc.close()
    return output
