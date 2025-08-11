# app/utilities/redact_pdf.py
import fitz
import re
import uuid
from io import BytesIO
from .extract_text import extract_text_from_pdf

# Regex patterns
PATTERNS = {
    "dates": r"(?:\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b)|(?:\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b)|(?:\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?)",
    "emails": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "phones": r"(?:\+?\d{1,2}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})",
    "addresses": r"\d{1,5}\s+[A-Za-z0-9\.\-]+\s+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Lane|Ln|Drive|Dr)\b",
    "zipcodes": r"\b\d{5}(?:-\d{4})?\b",
    # Names handled optionally with simple capitalized-word pattern or NLP if available
    "names_simple": r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2}\b"
}

# Try to import spaCy for better name detection (optional)
try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
except Exception:
    _nlp = None


def _compile_patterns(options):
    pats = []
    if options.get("dates"):
        pats.append(PATTERNS["dates"])
    if options.get("emails"):
        pats.append(PATTERNS["emails"])
    if options.get("phones"):
        pats.append(PATTERNS["phones"])
    if options.get("addresses"):
        pats.append(PATTERNS["addresses"])
    if options.get("zipcodes"):
        pats.append(PATTERNS["zipcodes"])
    # names: if user opted in, we will use spaCy if available, otherwise fallback to simple regex
    if options.get("names"):
        if _nlp:
            # will use NLP separately
            pass
        else:
            pats.append(PATTERNS["names_simple"])
    if not pats:
        return None
    return re.compile("|".join(pats), re.IGNORECASE)


def find_redaction_matches(pdf_bytes, options):
    """
    Return dict: { page_num: [ { id, text, rect }, ... ] }
    Uses page.get_text('text') to find phrase matches, then page.search_for(phrase) to get Rects
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    matches = {}
    combined_re = _compile_patterns(options)

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text")
        page_matches = []

        # Regex-based matches (dates/emails/phones/zip/addresses/simple names)
        if combined_re:
            for m in combined_re.finditer(page_text):
                phrase = m.group().strip()
                if not phrase:
                    continue
                # get rectangles on this page for the exact phrase
                try:
                    rects = page.search_for(phrase, hit_max=256)
                except Exception:
                    rects = []
                for r in rects:
                    page_matches.append({"id": str(uuid.uuid4()), "text": phrase, "rect": r})

        # If names requested and spaCy available, find PERSON entities
        if options.get("names") and _nlp:
            doc_nlp = _nlp(page_text)
            for ent in doc_nlp.ents:
                if ent.label_ == "PERSON":
                    phrase = ent.text.strip()
                    try:
                        rects = page.search_for(phrase, hit_max=256)
                    except Exception:
                        rects = []
                    for r in rects:
                        page_matches.append({"id": str(uuid.uuid4()), "text": phrase, "rect": r})

        # Deduplicate by text+rect roughly (prevent identical duplicates)
        unique = []
        seen = set()
        for it in page_matches:
            key = (it["text"].lower(), round(it["rect"].x0, 1), round(it["rect"].y0, 1),
                   round(it["rect"].x1, 1), round(it["rect"].y1, 1))
            if key in seen:
                continue
            seen.add(key)
            unique.append(it)

        matches[page_num] = unique

    doc.close()
    return matches


def generate_preview_images(pdf_bytes, matches, opacity=0.45):
    """
    Returns list of BytesIO PNG images (one per page) with semi-transparent black boxes
    applied for the matches provided. The original pdf_bytes is not modified.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    # Work on a copy of doc in-memory
    preview_images = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # create a temporary shape layer and draw boxes
        for m in matches.get(page_num, []):
            r = m["rect"]
            # draw as shape with commit(opacity)
            shape = page.new_shape()
            shape.draw_rect(r)
            shape.finish(fill=(0, 0, 0), color=None)
            # commit semi-transparent
            try:
                shape.commit(opacity=opacity)
            except TypeError:
                # older PyMuPDF versions may not support opacity in commit; fall back to draw_rect + alpha later
                shape.commit()

        # render page to image (note: shapes are drawn on page, but because we're reading from original doc,
        # this only affects this in-memory doc)
        pix = page.get_pixmap(dpi=150)
        img_bytes = BytesIO(pix.tobytes("png"))
        preview_images.append(img_bytes)

        # remove drawn shapes for next loop so we don't accumulate (re-open doc for safety)
        # easiest safe path: re-open doc fresh for next page iteration
        doc.close()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # ensure closed
    try:
        doc.close()
    except Exception:
        pass

    return preview_images


def generate_final_pdf_bytes(pdf_bytes, matches):
    """
    Returns BytesIO with a final redacted PDF where each match rect is redacted (solid black).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_num in range(len(doc)):
        page = doc[page_num]
        for m in matches.get(page_num, []):
            r = m["rect"]
            try:
                page.add_redact_annot(r, fill=(0, 0, 0))
            except Exception:
                # fallback: draw a solid rectangle if add_redact_annot fails
                shape = page.new_shape()
                shape.draw_rect(r)
                shape.finish(fill=(0, 0, 0), color=None)
                shape.commit(opacity=1.0)
        # apply redactions for the page
        try:
            page.apply_redactions()
        except Exception:
            # some versions expect doc.apply_redactions()
            pass

    out = BytesIO()
    doc.save(out)
    out.seek(0)
    doc.close()
    return out.getvalue()
