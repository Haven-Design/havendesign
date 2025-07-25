import streamlit as st
import fitz  # PyMuPDF
import re
import os

st.set_page_config(page_title="PDF Redactor", layout="wide")

st.title("🔍 PDF Redactor Tool")

# Upload PDF
uploaded_file = st.file_uploader("Upload a PDF", type="pdf")

# Search terms input
search_terms = st.text_area(
    "Enter search terms (one per line):",
    height=150,
    placeholder="Example:\nSocial Security Number\nConfidential\nJohn Doe"
)

if uploaded_file and search_terms:
    # Save uploaded PDF to temp file
    temp_file_path = os.path.join("temp_uploaded.pdf")
    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.read())

    # Load PDF
    doc = fitz.open(temp_file_path)

    # Extract text from all pages
    all_text = ""
    page_texts = []
    for page in doc:
        text = page.get_text()
        page_texts.append(text)
        all_text += text + "\n"

    # Search for terms
    terms = [term.strip() for term in search_terms.splitlines() if term.strip()]
    patterns = [(re.escape(term), term) for term in terms]

    match_data = []
    for i, text in enumerate(page_texts):
        for pattern, original_term in patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                snippet = text[max(0, match.start() - 30): match.end() + 30].replace('\n', ' ')
                match_data.append({
                    "page": i,
                    "term": original_term,
                    "context": snippet,
                })

    if match_data:
        st.write("### 🔎 Found Matches:")
        selected_to_redact = []
        for match in match_data:
            key = f"{match['page']}-{match['term']}-{match['context'][:20]}"
            if st.checkbox(f"Page {match['page'] + 1}: '{match['term']}' in \"...{match['context']}...\"", key=key):
                selected_to_redact.append((match['term'], match['page']))

        if selected_to_redact:
            if st.button("Redact and Download"):
                # Redact selected matches
                for term, page_num in selected_to_redact:
                    page = doc[page_num]
                    text_instances = page.search_for(term, flags=fitz.TEXT_DEHYPHENATE | fitz.TEXT_IGNORECASE)
                    for inst in text_instances:
                        page.add_redact_annot(inst, fill=(0, 0, 0))
                    page.apply_redactions()

                redacted_path = "redacted_output.pdf"
                doc.save(redacted_path)
                with open(redacted_path, "rb") as f:
                    st.download_button("📥 Download Redacted PDF", f, file_name="redacted.pdf")

                doc.close()
                os.remove(temp_file_path)
                os.remove(redacted_path)
    else:
        st.info("No matches found.")
elif uploaded_file and not search_terms:
    st.warning("Please enter at least one search term.")
