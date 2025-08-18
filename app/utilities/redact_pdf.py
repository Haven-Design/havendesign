import fitz
from typing import List
from utilities.extract_text import Hit

CATEGORY_PATTERNS: dict[str, str] = {
    "email": "#FF6B6B",
    "phone": "#6BCB77",
    "credit_card": "#4D96FF",
    "ssn": "#FFD93D",
    "drivers_license": "#FF8C42",
    "date": "#9D4EDD",
    "address": "#00C49A",
    "name": "#FF1493",
    "ip_address": "#1E90FF",
    "bank_account": "#FF4500",
    "vin": "#008B8B",
    "custom": "#A9A9A9",
}

# Colors for duplicate occurrences
DUPLICATE_COLORS: list[str] = [
    "#000000",  # first occurrence
    "#FFA500",  # second occurrence
    "#FF1493",  # third occurrence
    "#00CED1",  # fourth occurrence
    "#8A2BE2",  # fifth occurrence
]

def get_duplicate_color(category: str, count: int) -> str:
    """
    Returns a color for previewing duplicate occurrences.
    """
    if count <= 1:
        return CATEGORY_PATTERNS.get(category, "#000000")
    return DUPLICATE_COLORS[(count - 2) % len(DUPLICATE_COLORS)]

def redact_pdf_with_hits(input_pdf: str, hits: List[Hit], output_pdf: str, preview_mode: bool = False) -> None:
    """
    Redacts or previews redactions on a PDF using Hit objects.
    Duplicates are previewed with custom colors.
    """
    doc = fitz.open(input_pdf)

    for hit in hits:
        page = doc[hit["page"]]
        if preview_mode:
            color: str = get_duplicate_color(hit["category"], hit["count"])
            width: int = 2 if hit["count"] == 1 else 3
            page.draw_rect(hit["rect"], color=fitz.utils.getColor(color), fill=None, width=width)
        else:
            page.add_redact_annot(hit["rect"], fill=(0, 0, 0))

    if not preview_mode:
        doc.apply_redactions()

    doc.save(output_pdf)
    doc.close()
