import streamlit as st
import base64
import io
import fitz  # PyMuPDF
from app.utilities.redact_pdf import (
    find_redaction_phrases,
    redact_pdf_bytes,
)
from pathlib import Path

# --- Config ---
st.set_page_config(page_title="PDF Redactor", layout="wide")

# Categories (label -> key)
REDACTION_CATEGORIES = {
    "Emails": "emails",
    "Phone Numbers": "phones",
    "Dates": "dates",
    "Names (NLP)": "names",
    "Addresses": "addresses",
    "Zip Codes": "zip_codes",
    "Social Security Numbers (SSN)": "ssn",
    "Credit Card Numbers": "credit_cards",
    "Passport Numbers": "passport",
    "Driver's License Numbers": "drivers_license",
    "IP Addresses": "ip_addresses",
    "VINs (Vehicle ID)": "vin",
    "Bank Account Numbers": "bank_accounts",
}

# helper
def pdf_bytes_to_iframe(pdf_bytes, width="100%", height=800):
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    return f'<iframe src="data:application/pdf;base64,{b64}" width="{width}" height="{height}" type="application/pdf"></iframe>'

# convert upload to PDF bytes (supports pdf, png/jpg/jpeg, txt)
def to_pdf_bytes(uploaded_file):
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    if name.endswith(".pdf"):
        return data
    # images -> single-page PDF
    if name.endswith((".png", ".jpg", ".jpeg")):
        img_doc = fitz.open(stream=data, filetype="png" if name.endswith(".png") else "jpg")
        # create single page pdf with the image
        pdf_doc = fitz.open()
        rect = fitz.Rect(0, 0, img_doc[0].width, img_doc[0].height)
        page = pdf_doc.new_page(width=rect.width, height=rect.height)
        page.insert_image(rect, stream=data)
        pdf_bytes = pdf_doc.tobytes()
        pdf_doc.close()
        img_doc.close()
        return pdf_bytes
    # txt -> simple PDF rendering
    if name.endswith(".txt"):
        txt = data.decode("utf-8", errors="ignore")
        # create simple PDF
        pdf_doc = fitz.open()
        # use default page size
        page = pdf_doc.new_page()
        text = txt
        page.insert_text((72, 72), text)
        pdf_bytes = pdf_doc.tobytes()
        pdf_doc.close()
        return pdf_bytes
    # other types (docx) not converted here
    raise ValueError("Unsupported file type. Use PDF, PNG, JPG, JPEG, or TXT.")

# --- App UI ---
st.title("🔒 Redactor API — Streamlit UI")

uploaded_file = st.file_uploader("Upload PDF / image / txt", type=["pdf", "png", "jpg", "jpeg", "txt"])
if not uploaded_file:
    st.info("Upload a PDF, image (PNG/JPG), or TXT to begin. (DOCX not supported automatically.)")
    st.stop()

# convert to PDF bytes
try:
    pdf_bytes = to_pdf_bytes(uploaded_file)
except Exception as e:
    st.error(f"Could not convert uploaded file: {e}")
    st.stop()

# initialize session state
if "selected_categories" not in st.session_state:
    st.session_state.selected_categories = []
if "custom_regex_list" not in st.session_state:
    st.session_state.custom_regex_list = []
if "manual_phrases" not in st.session_state:
    st.session_state.manual_phrases = []
if "highlights" not in st.session_state:
    st.session_state.highlights = {}
if "selected_phrases" not in st.session_state:
    st.session_state.selected_phrases = set()
if "select_all_categories" not in st.session_state:
    st.session_state.select_all_categories = False
if "scan_done" not in st.session_state:
    st.session_state.scan_done = False

st.markdown("---")

# --- Category selection UI ---
st.markdown("## 1) Choose categories to detect")
cols = st.columns(3)
for i, (label, key) in enumerate(REDACTION_CATEGORIES.items()):
    with cols[i % 3]:
        checked = key in st.session_state.selected_categories
        new_val = st.checkbox(label, value=checked, key=f"cat_{key}")
        if new_val and key not in st.session_state.selected_categories:
            st.session_state.selected_categories.append(key)
        elif (not new_val) and key in st.session_state.selected_categories:
            st.session_state.selected_categories.remove(key)

# single Select All toggle
if st.button("Toggle Select All Categories"):
    if len(st.session_state.selected_categories) < len(REDACTION_CATEGORIES):
        st.session_state.selected_categories = list(REDACTION_CATEGORIES.values())
        st.session_state.select_all_categories = True
    else:
        st.session_state.selected_categories = []
        st.session_state.select_all_categories = False

# custom regex textarea (one per line)
st.markdown("### (Optional) Add custom regex patterns — one per line")
custom_regex_input = st.text_area("Custom regex patterns", value="\n".join(st.session_state.custom_regex_list), height=90)
st.session_state.custom_regex_list = [r.strip() for r in custom_regex_input.splitlines() if r.strip()]

st.markdown("---")

# --- Scan button ---
if st.button("Scan for redacted phrases"):
    if not st.session_state.selected_categories and not st.session_state.custom_regex_list:
        st.warning("Please choose at least one category or supply custom regex patterns.")
    else:
        with st.spinner("Scanning PDF for sensitive information..."):
            options = {k: (k in st.session_state.selected_categories) for k in REDACTION_CATEGORIES.values()}
            highlights = find_redaction_phrases(pdf_bytes, options, st.session_state.custom_regex_list)
            st.session_state.highlights = highlights
            st.session_state.scan_done = True
            # default: do not select phrases automatically (user wants unchecked by default)
            st.session_state.selected_phrases = set()
        st.success("Scan complete. Detected phrases are listed below.")

if not st.session_state.scan_done:
    st.info("After selecting categories / custom regex, click **Scan for redacted phrases**.")
    st.stop()

# --- Prepare phrase list ---
# Flatten phrases (unique) and compute summary counts
highlights = st.session_state.highlights or {}
phrase_counts_by_category = {cat: len(matches) for cat, matches in highlights.items()}
all_phrases = []
for cat, matches in highlights.items():
    for m in matches:
        all_phrases.append(m["text"])
# include manual phrases typed earlier (none by default)
manual_input = st.text_area("Add manual phrases to the detected list (one per line)", height=80, key="manual_input")
manual_phrases = [p.strip() for p in manual_input.splitlines() if p.strip()]
combined_phrases = sorted(set(all_phrases + manual_phrases))

# Summary string (small text)
summary_lines = []
for cat, count in phrase_counts_by_category.items():
    if count:
        summary_lines.append(f"{cat}: {count}")
summary_text = " • ".join(summary_lines) if summary_lines else "No detected items."

# --- Side-by-side results and preview ---
left_col, right_col = st.columns([1, 2])

with left_col:
    st.markdown("### Detected phrases")
    st.markdown(f"<small>{summary_text}</small>", unsafe_allow_html=True)

    # Select All / Deselect toggle for phrases (single button)
    if st.button("Toggle Select All Phrases"):
        if len(st.session_state.selected_phrases) < len(combined_phrases):
            st.session_state.selected_phrases = set(combined_phrases)
        else:
            st.session_state.selected_phrases = set()

    # scrollable two-column display inside the left column
    container_style = "max-height:400px; overflow-y:auto; border:1px solid #ddd; padding:8px;"
    st.markdown(f'<div style="{container_style}">', unsafe_allow_html=True)

    cols_ph = st.columns(2)
    for idx, phrase in enumerate(combined_phrases):
        chk = phrase in st.session_state.selected_phrases
        c = cols_ph[idx % 2]
        v = c.checkbox(phrase, value=chk, key=f"phrase_{idx}")
        if v and (phrase not in st.session_state.selected_phrases):
            st.session_state.selected_phrases.add(phrase)
        elif (not v) and (phrase in st.session_state.selected_phrases):
            st.session_state.selected_phrases.remove(phrase)

    st.markdown("</div>", unsafe_allow_html=True)

with right_col:
    st.markdown("### Live Preview (auto-updates when you toggle phrases)")
    # Build excluded set: phrases that user did not select are excluded from redaction (i.e., not redacted)
    excluded_phrases = set(combined_phrases) - set(st.session_state.selected_phrases)

    # Generate a preview PDF bytes with current selections (fast enough for small docs)
    with st.spinner("Generating preview..."):
        preview_bytes = redact_pdf_bytes(pdf_bytes, st.session_state.highlights, excluded_phrases)
    iframe = pdf_bytes_to_iframe(preview_bytes, width="100%", height=900)
    st.markdown(iframe, unsafe_allow_html=True)

# Final single-step action to produce downloadable PDF (same preview bytes used)
if st.button("Redact & Download PDF"):
    if not st.session_state.selected_phrases:
        st.warning("Select at least one phrase to redact before downloading.")
    else:
        with st.spinner("Creating redacted PDF..."):
            excluded_phrases = set(combined_phrases) - set(st.session_state.selected_phrases)
            final_bytes = redact_pdf_bytes(pdf_bytes, st.session_state.highlights, excluded_phrases)
        st.success("Redacted PDF ready.")
        st.download_button("Download Redacted PDF", final_bytes, file_name="redacted_output.pdf", mime="application/pdf")
