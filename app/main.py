import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
import base64
from app.utilities.redact_pdf import find_redaction_phrases, redact_pdf
import os

st.set_page_config(page_title="PDF Redactor", layout="centered")

def pdf_to_bytes(doc):
    return doc.write()

def render_pdf_with_highlights(pdf_bytes, highlights, phrase_to_highlight=None):
    """
    Render PDF bytes with transparent grey highlights and yellow border
    only for matches of phrase_to_highlight (if given).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num, matches in highlights.items():
        page = doc[page_num]
        for match in matches:
            phrase = match["text"]
            if phrase_to_highlight is not None and phrase != phrase_to_highlight:
                continue
            rect = match["rect"]
            highlight = page.add_highlight_annot(rect)
            highlight.set_colors(stroke=(1, 1, 0), fill=(0.5, 0.5, 0.5, 0.3))  # yellow border, transparent gray fill
            highlight.update()
    return pdf_to_bytes(doc)

def main():
    st.title("PDF Redactor")

    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
    if uploaded_file is None:
        st.info("Upload a PDF to begin.")
        return

    pdf_bytes = uploaded_file.read()
    highlights = find_redaction_phrases(pdf_bytes)
    if not highlights:
        st.warning("No redaction phrases found.")
        return

    # Extract unique phrases
    phrase_set = set()
    for matches in highlights.values():
        for match in matches:
            phrase_set.add(match["text"])
    all_phrases = sorted(list(phrase_set))

    if "selected_phrases" not in st.session_state:
        st.session_state.selected_phrases = set()

    if "hovered_phrase" not in st.session_state:
        st.session_state.hovered_phrase = None

    st.markdown("### Select phrases to redact:")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Select All"):
            st.session_state.selected_phrases = set(all_phrases)
    with col2:
        if st.button("Deselect All"):
            st.session_state.selected_phrases = set()

    # Scrollable container with 2 columns for phrases + hover detection
    scroll_style = """
        <style>
        div.phrases-scroll {
            height: 200px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 8px;
            background: #f9f9f9;
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
        }
        div.phrase-item {
            flex: 1 0 45%;  /* roughly 2 columns */
            cursor: pointer;
            padding: 4px 6px;
            border-radius: 4px;
        }
        div.phrase-item:hover {
            background-color: #e0e0e0;
        }
        </style>
    """
    st.markdown(scroll_style, unsafe_allow_html=True)

    # We'll build the phrase list as buttons that track hover via click (Streamlit can't detect hover directly)
    # So user clicks a phrase to highlight it on PDF preview, click again to unhighlight
    st.markdown('<div class="phrases-scroll">', unsafe_allow_html=True)

    # We need to show checkboxes for selection and a "highlight on click" for preview
    for phrase in all_phrases:
        cols = st.columns([0.1, 1])
        with cols[0]:
            checked = st.checkbox("", key=f"chk_{phrase}", value=phrase in st.session_state.selected_phrases)
            if checked:
                st.session_state.selected_phrases.add(phrase)
            else:
                st.session_state.selected_phrases.discard(phrase)
        with cols[1]:
            clicked = st.button(
                f"👁️ {phrase}" if phrase != st.session_state.hovered_phrase else f"❌ {phrase}",
                key=f"btn_{phrase}"
            )
            if clicked:
                if st.session_state.hovered_phrase == phrase:
                    st.session_state.hovered_phrase = None
                else:
                    st.session_state.hovered_phrase = phrase

    st.markdown('</div>', unsafe_allow_html=True)

    # Preview button - regenerates PDF preview with highlight on hovered phrase only
    if st.button("Preview Redactions"):
        if not st.session_state.selected_phrases:
            st.warning("Please select at least one phrase to redact.")
            return
        preview_bytes = render_pdf_with_highlights(
            pdf_bytes,
            highlights,
            phrase_to_highlight=st.session_state.hovered_phrase if st.session_state.hovered_phrase else None
        )
        b64 = base64.b64encode(preview_bytes).decode()
        iframe_html = f'<iframe src="data:application/pdf;base64,{b64}" width="700" height="900" type="application/pdf"></iframe>'
        st.markdown(iframe_html, unsafe_allow_html=True)

    # Download button for fully redacted PDF (all selected phrases redacted)
    if st.button("Download Redacted PDF"):
        if not st.session_state.selected_phrases:
            st.warning("Please select at least one phrase to redact.")
            return
        redacted_path = redact_pdf(pdf_bytes, list(st.session_state.selected_phrases))
        with open(redacted_path, "rb") as f:
            redacted_bytes = f.read()
        b64 = base64.b64encode(redacted_bytes).decode()
        st.markdown(
            f'<a href="data:application/pdf;base64,{b64}" download="redacted.pdf">Click here to download redacted PDF</a>',
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    main()
