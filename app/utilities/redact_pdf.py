import fitz  # PyMuPDF
import re
import spacy

# Load English NLP model (make sure to have run: python -m spacy download en_core_web_sm)
nlp = spacy.load("en_core_web_sm")

REGEX_PATTERNS = {
    "emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b",
    "phones": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "dates": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    "credit_cards": r"\b(?:\d[ -]*?){13,16}\b",
    "zip_codes": r"\b\d{5}(?:-\d{4})?\b"
}

NLP_LABELS = {
    "names": ["PERSON"],
    "addresses": ["GPE", "LOC"],
    "dates": ["DATE"],
}

def find_redaction_matches(pdf_bytes, selected_fields):
    """Find all redaction matches with bounding boxes by page.

    Returns a dict: {page_num: [(rect, phrase), ...], ...}
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    matches = {}

    for page_num, page in enumerate(doc):
        text_instances = []
        text = page.get_text("text")
        matches[page_num] = []

        # Regex matches
        for field in selected_fields:
            if selected_fields[field]:
                pattern = REGEX_PATTERNS.get(field)
                if pattern:
                    for match in re.finditer(pattern, text, re.IGNORECASE):
                        # Find all rects for this match text
                        areas = page.search_for(match.group())
                        for rect in areas:
                            matches[page_num].append((rect, match.group()))

        # NLP matches
        if any(selected_fields.get(k, False) for k in NLP_LABELS.keys()):
            doc_spacy = nlp(text)
            for ent in doc_spacy.ents:
                for field in selected_fields:
                    if selected_fields[field] and field in NLP_LABELS:
                        if ent.label_ in NLP_LABELS[field]:
                            areas = page.search_for(ent.text)
                            for rect in areas:
                                matches[page_num].append((rect, ent.text))

    return matches


def redact_pdf(input_pdf_bytes, selected_fields, output_path, custom_text=None):
    """Redact and save PDF."""
    doc = fitz.open(stream=input_pdf_bytes, filetype="pdf")

    # Find phrases to redact
    matches = find_redaction_matches(input_pdf_bytes, selected_fields)

    for page_num, rects_phrases in matches.items():
        page = doc[page_num]
        for rect, _phrase in rects_phrases:
            page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()

    doc.save(output_path)
    doc.close()
