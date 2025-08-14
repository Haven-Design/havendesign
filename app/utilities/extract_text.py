import fitz  # PyMuPDF
import re

def extract_text_with_positions(pdf_path, patterns, custom_phrases):
    doc = fitz.open(pdf_path)
    positions = []

    combined_patterns = patterns + [re.escape(phrase) for phrase in custom_phrases if phrase.strip()]
    regex = re.compile("|".join(combined_patterns), re.IGNORECASE) if combined_patterns else None

    for page_num, page in enumerate(doc):
        blocks = page.get_text("blocks")
        for block in blocks:
            text = block[4]
            if regex:
                for match in regex.finditer(text):
                    bbox = page.search_for(match.group())
                    for rect in bbox:
                        positions.append((page_num, rect))

    doc.close()
    return positions
