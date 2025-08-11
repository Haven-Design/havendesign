import fitz  # PyMuPDF
import re
import spacy

# Load NLP model once
nlp = spacy.load("en_core_web_sm")

REGEX_PATTERNS = {
    "emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b",
    "phones": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "dates": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    "addresses": r"\d{1,5}\s\w+(\s\w+){0,5}",
}

NLP_LABELS = {
    "names": ["PERSON"],
    "addresses": ["GPE", "LOC", "FAC"],
    "dates": ["DATE"],
}

def find_redaction_phrases(pdf_bytes, options):
    """Return dict: {page_num: [ {"text": phrase, "rect": fitz.Rect}, ... ], ...}"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    matches = {}

    for page_num, page in enumerate(doc):
        page_text = page.get_text()
        page_matches = []

        # Regex matches
        for key, pattern in REGEX_PATTERNS.items():
            if options.get(key):
                for match in re.finditer(pattern, page_text, flags=re.IGNORECASE):
                    phrase = match.group()
                    text_instances = page.search_for(phrase)
                    for inst in text_instances:
                        page_matches.append({"text": phrase, "rect": inst})

        # NLP matches
        if any(options.get(field) for field in NLP_LABELS):
            doc_spacy = nlp(page_text)
            for ent in doc_spacy.ents:
                for field, labels in NLP_LABELS.items():
                    if options.get(field) and ent.label_ in labels:
                        phrase = ent.text
                        text_instances = page.search_for(phrase)
                        for inst in text_instances:
                            page_matches.append({"text": phrase, "rect": inst})

        if page_matches:
            matches[page_num] = page_matches

    return matches

def redact_pdf(pdf_bytes, highlights, excluded_phrases):
    """Create redacted PDF bytes by drawing black rectangles over included highlights."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num, page in enumerate(doc):
        for match in highlights.get(page_num, []):
            phrase = match["text"]
            if phrase in excluded_phrases:
                continue
            rect = match["rect"]
            # Draw black rectangle over phrase area
            page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0))
    out_pdf = doc.write()
    return out_pdf
