# app/utilities/redact_pdf.py
import fitz
import re
from typing import Dict, List
from io import BytesIO

# try spaCy for names
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None

# Regex patterns for categories
REGEX_PATTERNS = {
    "emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b",
    "phones": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "dates": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    "addresses": r"\d{1,5}\s\w+(\s\w+){0,5}",
    "zip_codes": r"\b\d{5}(?:-\d{4})?\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_cards": r"\b(?:\d[ -]*?){13,16}\b",
    "passport": r"\b[A-PR-WY][0-9][0-9][A-Z0-9]{5}\b",
    "drivers_license": r"\b[A-Z]{1,2}\d{6,8}\b",
    "ip_addresses": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "vin": r"\b([A-HJ-NPR-Z0-9]{17})\b",
    "bank_accounts": r"\b\d{9,18}\b",
}

NLP_LABELS = {
    "names": ["PERSON"],
    "addresses": ["GPE", "LOC", "FAC"],
    "dates": ["DATE"],
}

def find_redaction_phrases(pdf_bytes: bytes, options: Dict[str, bool], custom_regex_list: List[str] = None):
    """
    Scan PDF (text-based pages or image-inserted pages) and return dict:
    { category_key: [ {"text": phrase, "page": pnum, "rect": rect}, ... ], ... }
    """
    if custom_regex_list is None:
        custom_regex_list = []

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    highlights = {}

    for pnum in range(len(doc)):
        page = doc[pnum]
        # get text; for pages that are images inserted, get_text() may return text if we rendered text earlier,
        # otherwise it returns empty string. That's okay because for images we rely on OCR earlier when constructing PDF if needed.
        text = page.get_text()

        # regex categories
        for cat_key, pattern in REGEX_PATTERNS.items():
            if not options.get(cat_key, False):
                continue
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                phrase = m.group()
                rects = page.search_for(phrase)
                for rect in rects:
                    highlights.setdefault(cat_key, [])
                    highlights[cat_key].append({"text": phrase, "page": pnum, "rect": rect})

        # NLP-based detection (names etc.)
        if nlp:
            for field, labels in NLP_LABELS.items():
                if not options.get(field, False):
                    continue
                doc_spacy = nlp(text)
                for ent in doc_spacy.ents:
                    if ent.label_ in labels:
                        phrase = ent.text
                        rects = page.search_for(phrase)
                        for rect in rects:
                            highlights.setdefault(field, [])
                            highlights[field].append({"text": phrase, "page": pnum, "rect": rect})

        # custom regexes
        for regex_str in custom_regex_list:
            try:
                cre = re.compile(regex_str)
            except re.error:
                continue
            for m in cre.finditer(text):
                phrase = m.group()
                rects = page.search_for(phrase)
                for rect in rects:
                    highlights.setdefault("custom_regex", [])
                    highlights["custom_regex"].append({"text": phrase, "page": pnum, "rect": rect})

    doc.close()
    return highlights

def redact_pdf_bytes(pdf_bytes: bytes, highlights: dict, excluded_phrases: set):
    """
    Apply redactions for all matches in highlights except those in excluded_phrases.
    Returns PDF bytes with applied redactions.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Add redact annots
    for cat, matches in highlights.items():
        for match in matches:
            phrase = match["text"]
            if phrase in excluded_phrases:
                continue
            pnum = match["page"]
            rect = match["rect"]
            page = doc[pnum]
            # Add solid black redaction
            page.add_redact_annot(rect, fill=(0,0,0))

    # Apply redactions on each page
    for page in doc:
        page.apply_redactions()

    out_bytes = doc.tobytes()
    doc.close()
    return out_bytes
