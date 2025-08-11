import fitz  # PyMuPDF
import re

# Regex patterns for each category
CATEGORY_PATTERNS = {
    "emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phones": r"\b(?:\+?1[-.\s]?)*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "dates": r"\b(?:\d{1,2}[-/th|st|nd|rd\s]?){1,3}\d{2,4}\b",
    "names": r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)+)\b",
    "addresses": r"\d{1,5} [\w\s]+ (?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b",
    "zip_codes": r"\b\d{5}(?:-\d{4})?\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_cards": r"\b(?:\d[ -]*?){13,16}\b",
    "passport": r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b",
    "drivers_license": r"\b[A-Z]{1,2}\d{6,8}\b",
    "ip_addresses": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "vin": r"\b([A-HJ-NPR-Z0-9]{17})\b",
    "bank_accounts": r"\b\d{9,18}\b",  # Simplified pattern; adjust as needed
}

def find_redaction_phrases(pdf_bytes, options: dict, custom_regex_list=None):
    """
    Scans the PDF text for sensitive information based on options and custom regexes.
    Returns dict: {category: [{"text": phrase, "page": page_number, "rect": rect}, ...], ...}
    """
    if custom_regex_list is None:
        custom_regex_list = []

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    highlights = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()

        # Detect category matches
        for category, enabled in options.items():
            if not enabled:
                continue
            pattern = CATEGORY_PATTERNS.get(category)
            if not pattern:
                continue
            for match in re.finditer(pattern, text, re.IGNORECASE):
                phrase = match.group()
                areas = page.search_for(phrase)
                if not areas:
                    continue
                if category not in highlights:
                    highlights[category] = []
                for rect in areas:
                    highlights[category].append({"text": phrase, "page": page_num, "rect": rect})

        # Detect custom regex matches
        for regex_str in custom_regex_list:
            try:
                regex = re.compile(regex_str)
            except re.error:
                # skip invalid regex
                continue
            for match in regex.finditer(text):
                phrase = match.group()
                areas = page.search_for(phrase)
                if not areas:
                    continue
                if "custom_regex" not in highlights:
                    highlights["custom_regex"] = []
                for rect in areas:
                    highlights["custom_regex"].append({"text": phrase, "page": page_num, "rect": rect})

    doc.close()
    return highlights


def redact_pdf(pdf_bytes, highlights, excluded_phrases):
    """
    Creates a redacted PDF bytes object applying redactions except for excluded phrases.
    Highlights phrases with semi-transparent gray box, no border.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for category, matches in highlights.items():
        for match in matches:
            phrase = match["text"]
            if phrase in excluded_phrases:
                continue
            page = doc[match["page"]]
            rect = match["rect"]
            # Use black fill with transparency to redact
            page.add_redact_annot(rect, fill=(0, 0, 0, 1))  # Solid black redact
    for page in doc:
        page.apply_redactions()
    redacted_pdf_bytes = doc.write()
    doc.close()
    return redacted_pdf_bytes
