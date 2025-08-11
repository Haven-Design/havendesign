import streamlit as st
from io import BytesIO
import fitz
from app.utilities.extract_text import extract_text_from_pdf
from app.utilities.redact_pdf import find_redaction_matches, redact_pdf_bytes

st.set_page_config(page_title="PDF Redactor", layout="centered")
st.title("PDF Redactor - Interactive Redaction Preview")

uploaded_file = st.file_uploader("Drag and drop a PDF or click to browse", type="pdf", label_visibility="visible")

if uploaded_file:
    pdf_bytes = uploaded_file.read()

    st.markdown("### Detected Phrases to Redact (select to exclude):")

    # Find all redaction matches based on all options selected for demo
    # You can add UI controls to select categories here if desired
    options = {"names": True, "dates": True, "emails": True, "phones": True, "addresses": True}
    matches = find_redaction_matches(pdf_bytes, options)

    # Flatten phrases with page number
    all_phrases = []
    for pagenum, page_matches in matches.items():
        for match in page_matches:
            all_phrases.append((pagenum, match["phrase"]))

    # Use session state to store excluded phrases
    if "excluded" not in st.session_state:
        st.session_state.excluded = set()

    cols = st.columns([0.1, 0.8, 0.1])
    with cols[0]:
        st.markdown("Exclude")
    with cols[1]:
        st.markdown("Phrase")
    with cols[2]:
        st.markdown("Page")

    # Display phrases with exclude checkboxes
    for i, (page_num, phrase) in enumerate(all_phrases):
        cols = st.columns([0.1, 0.8, 0.1])
        with cols[0]:
            checked = phrase in st.session_state.excluded
            val = st.checkbox("", value=checked, key=f"exclude_{i}")
            if val and phrase not in st.session_state.excluded:
                st.session_state.excluded.add(phrase)
            elif not val and phrase in st.session_state.excluded:
                st.session_state.excluded.remove(phrase)
        with cols[1]:
            st.write(phrase)
        with cols[2]:
            st.write(page_num + 1)

    # Show preview with translucent highlights for phrases (excluding excluded ones)
    st.markdown("### Preview (translucent highlights over phrases)")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img = pix.tobytes("png")

        # Create highlight overlays
        overlay = page.get_pixmap(alpha=True, matrix=fitz.Matrix(1.5,1.5))
        for match in matches.get(page_num, []):
            phrase = match["phrase"]
            rect = match["rect"]
            if phrase not in st.session_state.excluded:
                r = rect * 1.5  # scale rect for preview image
                # Draw semi-transparent yellow rectangle
                overlay.draw_rect(r, color=(1, 1, 0), fill=(1, 1, 0, 0.3))

        overlay_bytes = overlay.tobytes("png")

        st.image(img, caption=f"Page {page_num+1}", use_column_width=True)
        st.image(overlay_bytes, use_column_width=True)

    if st.button("Finalize Redaction and Download PDF"):
        # Redact PDF bytes excluding excluded phrases
        redacted_pdf_bytes = redact_pdf_bytes(pdf_bytes, matches, exclude_phrases=st.session_state.excluded)
        st.download_button("Download Redacted PDF", redacted_pdf_bytes, file_name="redacted_output.pdf", mime="application/pdf")
