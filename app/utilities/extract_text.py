import re
import io
from typing import List
import fitz  # PyMuPDF
from docx import Document

class Hit:
    def __init__(self, page: int, rect, text: str, category: str):
        self.page = page
        self.rect = rect
        self.text = text
        self.category = category

CATEGORY_LABELS = {
    "Email Addresses": "email",
    "Phone Numbers": "phone",
    "Credit Card Numbers": "credit_card",
    "Social Security Numbers": "ssn",
    "Driver's Licenses": "drivers_license",
    "Dates": "date",
    "Addresses": "address",
    "Names": "name",
    "IP Addresses": "ip_address",
    "Bank Account Numbers": "bank_account",
}

CATEGORY_COLORS = {
    "email": "#1f77b4",
    "phone": "#ff7f0e",
    "credit_card": "#2ca02c",
    "ssn": "#d62728",
    "drivers_license": "#9467bd",
    "date": "#8c564b",
    "address": "#e377c2",
    "name": "#7f7f7f",
    "ip_address": "#bcbd22",
    "bank_account": "#17becf",
}

# tightened regex
PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+?\d{1,2}\s?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "drivers_license": r"\b[A-Z0-9]{5,15}\b",
    "date": r"\b(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b",
    "address": r"\d{1,5}\s\w+(\s\w+)*",
    "name": r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b",
    "ip_address": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
    "bank_account": r"\b\d{8,17}\b",
}

def extract_hits_from_pdf(pdf_bytes: bytes, selected_params: List[str]) -> List[Hit]:
    doc = fitz.open("pdf", pdf_bytes)
    hits: List[Hit] = []
    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        for cat in selected_params:
            pattern = PATTERNS.get(cat)
            if not pattern:
                continue
            for m in re.finditer(pattern, text):
                hits.append(Hit(page_num, page.search_for(m.group(0))[0], m.group(0), cat))
    return hits

def extract_hits_from_txt(txt_bytes: bytes, selected_params: List[str]) -> List[Hit]:
    text = txt_bytes.decode("utf-8", errors="ignore")
    hits: List[Hit] = []
    for cat in selected_params:
        pattern = PATTERNS.get(cat)
        if not pattern:
            continue
        for m in re.finditer(pattern, text):
            hits.append(Hit(0, None, m.group(0), cat))
    return hits

def extract_hits_from_docx(docx_bytes: bytes, selected_params: List[str]) -> List[Hit]:
    doc = Document(io.BytesIO(docx_bytes))
    text = "\n".join(p.text for p in doc.paragraphs)
    hits: List[Hit] = []
    for cat in selected_params:
        pattern = PATTERNS.get(cat)
        if not pattern:
            continue
        for m in re.finditer(pattern, text):
            hits.append(Hit(0, None, m.group(0), cat))
    return hits

def extract_hits_from_file(file_input, selected_params: List[str]) -> List[Hit]:
    if isinstance(file_input, str) and file_input.endswith(".pdf"):
        with open(file_input, "rb") as f:
            return extract_hits_from_pdf(f.read(), selected_params)
    elif isinstance(file_input, io.BytesIO):
        return extract_hits_from_pdf(file_input.read(), selected_params)
    else:
        return []
