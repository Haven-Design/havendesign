import fitz  # PyMuPDF
import spacy
import re
import tempfile
from typing import List

nlp = spacy.load("en_core_web_sm")

# Regex patterns for sensitive info
date_pattern = r"\b(?:\d{1,2}[/-])?(?:\d{1,2}[/-])?\d{2,4}\b"
phone_pattern = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
credit_card_pattern = r"\b(?:\d[ -]*?){13,16}\b"
number_pattern = r"\b\d{5,}\b"

# Map UI labels to internal tags
option_to_entity = {
    "Names": "PERSON",
    "Addresses": "GPE",
    "Dates": "DATE",
    "Phone Numbers": "PHONE",
    "SSNs": "SSN",
    "Credit Card Numbers": "CC",
    "Numbers": "NUMBER"
}


def get_matches(text: str, enabled_entities: List[str]) -> List[dict]:
    doc = nlp(text)
    matches = []

    for ent in doc.ents:
        if ent.label_ in enabled_entities:
            matches.append({"text": ent.text, "start": ent.start_char, "end": ent.end_char})

    if "DATE" in enabled_entities:
        for match in re.finditer(date_pattern, text):
            matches.append({"text": match.group(), "start": match.start(), "end": match.end()})

    if "PHONE" in enabled_entities:
        for match in re.finditer(phone_pattern, text):
            matches.append({"text": match.group(), "start": match.start(), "end": match.end()})

    if "SSN" in enabled_entities:
        for match in re.finditer(ssn_pattern, text):
            matches.append({"text": match.group(), "start": match.start(), "end": match.end()})

    if "CC" in enabled_entities:
        for match in re.finditer(credit_card_pattern, text):
            matches.append({"text": match.group(), "start": match.start(), "end": match.end()})

    if "NUMBER" in enabled_entities:
        for match in re.finditer(number_pattern, text):
            matches.append({"text": match.group(), "start": match.start(), "end": match.end()})

    return matches


def redact_pdf(input_path: str, selected_options: List[str]) -> str:
    enabled_entities = [option_to_entity[opt] for opt in selected_options if opt in option_to_entity]

    doc = fitz.open(input_path)

    for page in doc:
        blocks = page.get_text("blocks")
        for b in blocks:
            text = b[4]
            matches = get_matches(text, enabled_entities)

            for match in matches:
                rects = page.search_for(match["text"])
                for rect in rects:
                    page.add_redact_annot(rect, fill=(0, 0, 0))

        page.apply_redactions()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_output:
        doc.save(tmp_output.name)
        output_path = tmp_output.name

    doc.close()
    return output_path
