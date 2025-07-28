import re
import fitz  # PyMuPDF
from io import BytesIO

class PDFRedactor:
    def __init__(self, pdf_bytes):
        self.original_pdf = pdf_bytes
        self.doc = fitz.open("pdf", pdf_bytes)
        self.redacted_pdf = None
        self.patterns = {}
        self.targets = {}

    def page_count(self):
        return len(self.doc)

    def set_redaction_targets(self, targets):
        self.targets = targets
        self.patterns.clear()

        if targets.get("Names"):
            self.patterns["Names"] = r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b"
        if targets.get("Emails"):
            self.patterns["Emails"] = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        if targets.get("Phone Numbers"):
            self.patterns["Phone Numbers"] = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        if targets.get("Dates"):
            self.patterns["Dates"] = r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"
        if targets.get("Addresses"):
            self.patterns["Addresses"] = r"\d{1,5}\s\w+(\s\w+)*\s(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b"
        if targets.get("Organizations"):
            self.patterns["Organizations"] = r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*\s(?:Inc|LLC|Ltd|Corporation|Corp|Company|Co)\b"
        if targets.get("SSNs"):
            self.patterns["SSNs"] = r"\b\d{3}-\d{2}-\d{4}\b"
        if targets.get("Credit Card Numbers"):
            self.patterns["Credit Card Numbers"] = r"\b(?:\d[ -]*?){13,16}\b"

    def get_preview_images(self):
        previews = []
        for page in self.doc:
            pix = page.get_pixmap()
            previews.append(pix.tobytes("png"))
        return previews

    def apply_redactions(self):
        if not self.patterns:
            return

        for page in self.doc:
            text = page.get_text("text")
            for label, pattern in self.patterns.items():
                for match in re.finditer(pattern, text):
                    matched_text = match.group()
                    areas = page.search_for(matched_text)
                    for area in areas:
                        page.add_redact_annot(area, fill=(0, 0, 0))
            page.apply_redactions()

        output = BytesIO()
        self.doc.save(output)
        self.redacted_pdf = output.getvalue()
