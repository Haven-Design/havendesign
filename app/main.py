# main.py
import streamlit as st
from io import BytesIO
from app.utilities.extract_text import extract_text_from_pdf
from app.utilities.redact_pdf import (
    find_redaction_matches,
    generate_preview_images,
    generate_final_pdf_bytes,
)

st.set_page_config(page_title="PDF Redactor", layout="wide")

st.title("PDF Redactor — Preview & Selective Redaction")
st.markdown(
    """
Upload a PDF, select categories to scan. Detected matches appear on the right;
click ❌ to exclude a match and the preview will update instantly.

**Preview uses slightly transparent black boxes.**  
When you download the final PDF those boxes will be fully opaque (permanent redaction).
"""
)

uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if not uploaded_file:
    st.info("Choose a PDF to get started.")
    st.stop()

pdf_bytes = uploaded_file.read()

# --- Scan options
st.sidebar.header("Scan categories")
opt_names = st.sidebar.checkbox("Names (NLP)", value=False)
opt_dates = st.sidebar.checkbox("Dates", value=True)
opt_emails = st.sidebar.checkbox("Emails", value=True)
opt_phones = st.sidebar.checkbox("Phone Numbers", value=True)
opt_addresses = st.sidebar.checkbox("Addresses", value=False)
opt_zip = st.sidebar.checkbox("ZIP Codes", value=True)
opt_all = st.sidebar.checkbox("Select All", value=False)
if opt_all:
    opt_names = opt_dates = opt_emails = opt_phones = opt_addresses = opt_zip = True

options = {
    "names": opt_names,
    "dates": opt_dates,
    "emails": opt_emails,
    "phones": opt_phones,
    "addresses": opt_addresses,
    "zipcodes": opt_zip,
}

# --- Find matches (phrase text + fitz.Rects per page)
with st.spinner("Detecting matches..."):
    matches = find_redaction_matches(pdf_bytes, options)

# session state for removed matches
if "removed_ids" not in st.session_state:
    st.session_state.removed_ids = set()

def remove_match(id_):
    st.session_state.removed_ids.add(id_)

# Build filtered matches (exclude removed ids)
filtered_matches = {}
for pageno, items in matches.items():
    filtered = [m for m in items if m["id"] not in st.session_state.removed_ids]
    if filtered:
        filtered_matches[pageno] = filtered

# Layout: preview (left) + list (right)
col_preview, col_list = st.columns([2, 1])

with col_preview:
    st.subheader("Preview (transparent redactions)")
    # Generate preview images (semi-transparent boxes baked into images)
    preview_images = generate_preview_images(pdf_bytes, filtered_matches, opacity=0.45)
    for i, img_bytes in enumerate(preview_images):
        st.image(img_bytes, caption=f"Page {i+1}", use_column_width=True)

with col_list:
    st.subheader("Detected matches")
    st.markdown("Click the ❌ next to any match to exclude it from redaction.")
    if not any(matches.values()):
        st.info("No matches detected for the chosen categories.")
    else:
        container = st.container()
        container.markdown("<div style='max-height:560px; overflow:auto;'>", unsafe_allow_html=True)
        for pageno, items in matches.items():
            for m in items:
                # show only if not removed
                if m["id"] in st.session_state.removed_ids:
                    continue
                cols = container.columns([0.8, 0.15, 0.05])
                # Phrase full text
                cols[0].markdown(f"**Page {pageno+1}:** {m['text']}")
                # small context or category not required — kept simple
                # remove button
                cols[2].button("❌", key=m["id"], on_click=remove_match, args=(m["id"],))
        container.markdown("</div>", unsafe_allow_html=True)

# Finalize and download
st.markdown("---")
st.markdown("**Final redaction:** when you click the button below we'll produce a PDF with solid black redaction boxes (permanent).")
if st.button("Generate final redacted PDF"):
    with st.spinner("Creating final redacted PDF..."):
        final_pdf_bytes = generate_final_pdf_bytes(pdf_bytes, filtered_matches)
        st.success("Final redacted PDF ready.")
        st.download_button(
            "Download Final Redacted PDF",
            final_pdf_bytes,
            file_name="redacted_output.pdf",
            mime="application/pdf",
        )
