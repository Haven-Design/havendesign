import os
import fitz
import streamlit as st
from utilities.extract_text import extract_sensitive_data, CATEGORY_COLORS
from utilities.redact_pdf import redact_pdf_with_positions

st.set_page_config(layout="wide")

st.title("📄 PDF Redactor")

uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file:
    input_path = os.path.join("temp_uploaded.pdf")
    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    if st.button("🔍 Scan for Redacted Phrases"):
        with st.spinner("Scanning PDF..."):
            doc = fitz.open(input_path)
            all_text = ""
            page_texts = []
            for page_num in range(len(doc)):
                text = doc[page_num].get_text()
                page_texts.append(text)
                all_text += text + "\n"
            doc.close()

            found_data = extract_sensitive_data(all_text)

        st.write("---")
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("Found Phrases")
            st.markdown(
                """
                <style>
                .scroll-box {
                    max-height: 400px;
                    overflow-y: auto;
                    padding-right: 10px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

            selected_positions = []
            with st.container():
                st.markdown('<div class="scroll-box">', unsafe_allow_html=True)
                for category, matches in found_data.items():
                    if matches:
                        cat_color = CATEGORY_COLORS.get(category, "#000000")
                        st.markdown(f"**<span style='color:{cat_color}'>{category}</span>**", unsafe_allow_html=True)
                        for match, start, end in matches:
                            if st.checkbox(match, value=True, key=f"{category}-{match}-{start}"):
                                for page_num, text in enumerate(page_texts):
                                    idx = text.find(match)
                                    if idx != -1:
                                        inst = fitz.open(input_path)[page_num].search_for(match)
                                        for rect in inst:
                                            selected_positions.append((page_num, rect, category))
                st.markdown('</div>', unsafe_allow_html=True)

            if st.button("📥 Download PDF"):
                preview_pdf_path = "redacted_preview.pdf"
                redact_pdf_with_positions(input_path, selected_positions, preview_pdf_path)
                with open(preview_pdf_path, "rb") as f:
                    st.download_button("Download PDF", f, file_name="redacted.pdf")

        with col2:
            st.subheader("Preview")
            preview_pdf_path = "redacted_preview.pdf"
            if os.path.exists(preview_pdf_path):
                st.pdf(preview_pdf_path)
