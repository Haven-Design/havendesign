import re
import fitz
import docx
import io
from typing import List

class Hit:
    def __init__(self, page, rect, text, category):
        self.page = page
        self.rect = rect
        self.text = text
        self.category = category

CATEGORY_LABELS = {
    "email": "Emails",
    "phone": "Phone Numbers",
    "ssn": "SSNs",
    "credit_card": "Credit Cards",
    "drivers_license": "Driver's License",
    "name": "Names",
    "custom": "Custom Phrases"
}

CATEGORY_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "drivers_license": r"\b[A-Z0-9]{5,12}\b",
    "name": r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b",
}

CATEGORY_COLORS = {
    "email": "#FFA07A",
    "phone": "#87CEEB",
    "ssn": "#FFD700",
    "credit_card": "#FF69B4",
    "drivers_license": "#ADFF2F",
    "name": "#9370DB",
    "custom": "#D3D3D3"
}

def extract_text_and_positions(file_bytes, ext, params, custom_phrase):
    hits: List[Hit] = []

    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_num, page in enumerate(doc):
            blocks = page.get_text("blocks")
            for block in blocks:
                text = block[4]
                for category, pattern in CATEGORY_PATTERNS.items():
                    if params.get(category, False):
                        for match in re.finditer(pattern, text):
                            hits.append(Hit(page_num, block[:4], match.group(), category))
                if custom_phrase:
                    for match in re.finditer(re.escape(custom_phrase), text, flags=re.IGNORECASE):
                        hits.append(Hit(page_num, block[:4], match.group(), "custom"))

    elif ext == ".docx":
        doc = docx.Document(io.BytesIO(file_bytes))
        for para in doc.paragraphs:
            text = para.text
            for category, pattern in CATEGORY_PATTERNS.items():
                if params.get(category, False):
                    for match in re.finditer(pattern, text):
                        hits.append(Hit(0, None, match.group(), category))
            if custom_phrase:
                for match in re.finditer(re.escape(custom_phrase), text, flags=re.IGNORECASE):
                    hits.append(Hit(0, None, match.group(), "custom"))

    elif ext == ".txt":
        text = file_bytes.decode("utf-8")
        for category, pattern in CATEGORY_PATTERNS.items():
            if params.get(category, False):
                for match in re.finditer(pattern, text):
                    hits.append(Hit(0, None, match.group(), category))
        if custom_phrase:
            for match in re.finditer(re.escape(custom_phrase), text, flags=re.IGNORECASE):
                hits.append(Hit(0, None, match.group(), "custom"))

    return hits
