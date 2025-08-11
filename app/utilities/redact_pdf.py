import fitz  # PyMuPDF
import re
import spacy

# Load English NLP model (download with: python -m spacy download en_core_web_sm)
nlp = spacy.load("en_core_web_sm")

# Regex for common sensitive info
REGEX_PATTERNS = {
    "names": r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b",  # Simplified name pattern
    "dates": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    "emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b",
    "phones": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "addresses": r"\d{1,5}\s\w+\s\w+",  # Simple street address pattern
    # add more patterns if needed
}

def find_redaction_matches(pdf_bytes, options):
    """
    Returns dict: { page_num: [ { 'phrase': str, 'rect': fitz.Rect }, ... ] }
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    matches = {}

    for page_num, page in enumerate(doc):
        words = page.get_text("words")  # list of tuples: (x0, y0, x1, y1, word, block_no, line_no, word_no)
        text = page.get_text()
        page_matches = []

        # Compile regex patterns for selected options
        patterns = []
        for key, enabled in options.items():
            if enabled and key in REGEX_PATTERNS:
                patterns.append(REGEX_PATTERNS[key])
        combined_pattern = re.compile("|".join(patterns), re.IGNORECASE) if patterns else None

        # Find matches by regex
        if combined_pattern:
            for match in combined_pattern.finditer(text):
                matched_text = match.group()
                # Find word rectangles overlapping this match
                matched_rects = []
                for w in words:
                    word_rect = fitz.Rect(w[:4])
                    word_text = w[4]
                    # If word inside matched text region by char index approximation
                    # We'll check if word is inside match span text:
                    if matched_text.lower() in word_text.lower() or word_text.lower() in matched_text.lower():
                        matched_rects.append(word_rect)
                if matched_rects:
                    # Merge rects to one rectangle
                    union_rect = matched_rects[0]
                    for r in matched_rects[1:]:
                        union_rect |= r
                    page_matches.append({"phrase": matched_text, "rect": union_rect})

        # NLP-based name detection if names selected
        if options.get("names", False):
            doc_nlp = nlp(text)
            for ent in doc_nlp.ents:
                if ent.label_ == "PERSON":
                    # find rects for entity text
                    ent_rects = []
                    for w in words:
                        word_rect = fitz.Rect(w[:4])
                        if ent.text.lower() in w[4].lower() or w[4].lower() in ent.text.lower():
                            ent_rects.append(word_rect)
                    if ent_rects:
                        union_rect = ent_rects[0]
                        for r in ent_rects[1:]:
                            union_rect |= r
                        page_matches.append({"phrase": ent.text, "rect": union_rect})

        matches[page_num] = page_matches

    return matches


def redact_pdf_bytes(pdf_bytes, matches, exclude_phrases=set()):
    """
    Apply black box redactions on matched phrases except those excluded.
    Return redacted PDF bytes.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num, page_matches in matches.items():
        page = doc[page_num]
        for match in page_matches:
            phrase = match["phrase"]
            rect = match["rect"]
            if phrase not in exclude_phrases:
                page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()
    out_pdf = doc.write()
    doc.close()
    return out_pdf
