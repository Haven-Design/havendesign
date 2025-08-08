import re
import spacy
import fitz  # PyMuPDF

# Load NLP model (ensure to run: python -m spacy download en_core_web_sm once)
nlp = spacy.load("en_core_web_sm")

# Regex patterns for sensitive data
REGEX_PATTERNS = {
    "emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b",
    "phones": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "dates": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    "names": None,  # Will use NLP for names
    "addresses": None  # Will use NLP for GPE and LOC
}

# NLP labels mapped to keys
NLP_LABELS = {
    "names": ["PERSON"],
    "addresses": ["GPE", "LOC"]
}

def redact_text(text, options, return_matches=False):
    """
    Redact the text based on options.
    If return_matches=True, also returns dict of page_num -> list of fitz.Rect for matches.

    options keys: 'names', 'dates', 'emails', 'phones', 'addresses' (all bool)
    """
    redacted_text = text
    matches = {}

    # We'll mock page_num = 0 since plain text extraction doesn't preserve pages
    page_num = 0
    matches[page_num] = []

    # Collect all matches positions (simulate with spans in text)
    # Because we don’t have page-based coordinate info here,
    # For preview, we’ll treat redacted area as full page to draw black boxes.
    # But for demonstration, let's just return empty rectangles so preview can draw something.

    # Redact regex-based patterns
    for key in ['emails', 'phones', 'dates']:
        if options.get(key):
            pattern = REGEX_PATTERNS[key]
            if pattern:
                redacted_text = re.sub(pattern, "[REDACTED]", redacted_text, flags=re.IGNORECASE)

    # Redact NLP entities for names and addresses
    if options.get("names") or options.get("addresses"):
        doc = nlp(redacted_text)
        for ent in reversed(doc.ents):  # reversed to avoid messing up offsets on replacements
            if options.get("names") and ent.label_ in NLP_LABELS.get("names", []):
                redacted_text = redacted_text[:ent.start_char] + "[REDACTED]" + redacted_text[ent.end_char:]
            elif options.get("addresses") and ent.label_ in NLP_LABELS.get("addresses", []):
                redacted_text = redacted_text[:ent.start_char] + "[REDACTED]" + redacted_text[ent.end_char:]

    # For preview: since we lack real bounding boxes in extracted text,
    # generate a black box covering the whole page to simulate redaction preview
    # This is a fallback — ideally you'd get coordinates from PDF text extraction.
    if return_matches:
        # Dummy rectangle covering the entire page area (for preview only)
        # In practice, better to use fitz.Page.rect or similar.
        matches[page_num].append(fitz.Rect(0, 0, 595, 842))  # A4 page size in points approx

        return redacted_text, matches

    return redacted_text
