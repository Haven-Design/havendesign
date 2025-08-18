import re
import fitz  # PyMuPDF

# Category regex patterns + colors for preview
patterns = {
    "email": (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}", "#1f77b4"),
    "phone": (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "#ff7f0e"),
    "credit_card": (r"\b(?:\d[ -]*?){13,16}\b", "#2ca02c"),
    "ssn": (r"\b\d{3}-\d{2}-\d{4}\b", "#d62728"),
    "drivers_license": (r"\b[A-Z0-9]{6,12}\b", "#9467bd"),
    "date": (r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "#8c564b"),
    "address": (r"\b\d{1,5}\s\w+(\s\w+){1,4}\b", "#e377c2"),
    "name": (r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", "#7f7f7f"),
    "ip_address": (r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "#bcbd22"),
    "bank_account": (r"\b\d{9,12}\b", "#17becf"),
    "vin": (r"\b[A-HJ-NPR-Z0-9]{17}\b", "#17a589"),
}

def extract_text_and_positions(pdf_path, selected_params):
    doc = fitz.open(pdf_path)
    found_phrases = []
    positions_by_category = []

    for page_num, page in enumerate(doc):
        text = page.get_text("text")

        for category in selected_params:
            if category in patterns:
                regex, color = patterns[category]
                for match in re.finditer(regex, text):
                    phrase = match.group(0)
                    found_phrases.append((phrase, category))

                    areas = page.search_for(phrase)
                    for rect in areas:
                        positions_by_category.append((page_num, rect, color, category))

            else:  # Custom phrase
                for match in re.finditer(re.escape(category), text, re.IGNORECASE):
                    phrase = match.group(0)
                    found_phrases.append((phrase, "custom"))
                    areas = page.search_for(phrase)
                    for rect in areas:
                        positions_by_category.append((page_num, rect, "#000000", "custom"))

    doc.close()
    return found_phrases, positions_by_category
