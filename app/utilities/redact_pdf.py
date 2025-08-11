import fitz  # PyMuPDF
import re
import spacy

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
    """
    Returns dict:
    {
        page_num: [
            {"text": phrase, "rect": fitz.Rect},
            ...
        ],
        ...
    }
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    phrases_by_page = {}

    for page_num, page in enumerate(doc):
        page_text = page.get_text()
        page_phrases = []

        # Regex matches
        for key, pattern in REGEX_PATTERNS.items():
            if options.get(key):
                for match in re.finditer(pattern, page_text, flags=re.IGNORECASE):
                    phrase = match.group()
                    rects = page.search_for(phrase)
                    for r in rects:
                        page_phrases.append({"text": phrase, "rect": r})

        # NLP matches
        if any(options.get(field) for field in NLP_LABELS):
            doc_spacy = nlp(page_text)
            for ent in doc_spacy.ents:
                for field, labels in NLP_LABELS.items():
                    if options.get(field) and ent.label_ in labels:
                        phrase = ent.text
                        rects = page.search_for(phrase)
                        for r in rects:
                            page_phrases.append({"text": phrase, "rect": r})

        if page_phrases:
            phrases_by_page[page_num] = page_phrases

    return phrases_by_page


def redact_pdf(pdf_bytes, phrases_to_redact):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        page_text = page.get_text()
        for phrase in phrases_to_redact:
            text_instances = page.search_for(phrase)
            for inst in text_instances:
                # Draw a black rectangle over the phrase for redaction
                page.add_redact_annot(inst, fill=(0, 0, 0))
        page.apply_redactions()
    output_path = "redacted_output.pdf"
    doc.save(output_path)
    return output_path
