import fitz  # PyMuPDF
import re
import spacy

# Load NLP model once
nlp = spacy.load("en_core_web_sm")

# Regex patterns for sensitive info, add zip codes and credit cards here
REGEX_PATTERNS = {
    "emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b",
    "phones": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "dates": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    "addresses": r"\d{1,5}\s\w+(\s\w+){0,5}",  # crude address pattern
    "zip_codes": r"\b\d{5}(-\d{4})?\b",
    "credit_cards": r"\b(?:\d[ -]*?){13,16}\b",
}

NLP_LABELS = {
    "names": ["PERSON"],
    "addresses": ["GPE", "LOC", "FAC"],
    "dates": ["DATE"],
}


def find_redaction_phrases(pdf_bytes, options):
    """
    Return dict: {page_num: [ {"text": phrase, "rect": fitz.Rect}, ... ], ...}
    options is dict like {'emails': True, 'phones': False, ...}
    """
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
                    # Find rectangles for this phrase on the page
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


def redact_pdf(pdf_bytes, highlights, excluded_keys):
    """
    Returns bytes of PDF with redactions applied.
    highlights: dict {page_num: [ {"text": phrase, "rect": fitz.Rect}, ... ], ...}
    excluded_keys: set of keys of phrases to exclude from redaction
    Keys format: "pageNum_index_phrase"
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_num, matches in highlights.items():
        page = doc[page_num]
        for i, match in enumerate(matches):
            key = f"{page_num}_{i}_{match['text']}"
            if key in excluded_keys:
                continue  # Skip this phrase redaction

            # Draw transparent grey rectangle with red border on match rect
            rect = match["rect"]
            highlight_color = (1, 0, 0)  # Red border
            fill_color = (0.5, 0.5, 0.5, 0.3)  # Transparent grey fill (last value is alpha)

            # Draw a filled rectangle with transparency
            page.add_redact_annot(rect, fill=fill_color, stroke=highlight_color, width=1)

        # Apply redactions on page
        page.apply_redactions()

    output_bytes = doc.write()
    doc.close()
    return output_bytes
