import streamlit as st
from app.utilities import extract_text, redact_text, download_redacted_text

st.set_page_config(page_title="Redactor API", layout="centered")
st.title("Redactor API")

st.markdown("""
<style>
    .section {
        margin-bottom: 3rem;
    }
    .file-uploader .css-1p05t8e {
        display: flex;
        justify-content: center;
    }
    .custom-textarea textarea {
        min-height: 150px;
    }
    .stDownloadButton {
        margin-top: 20px;
    }
    .preview-box {
        max-width: 700px;
        margin: 0 auto;
        padding: 1rem;
        border: 1px solid #ccc;
        border-radius: 8px;
        background-color: #f9f9f9;
    }
    .uploader-wrapper {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 2rem;
        border: 2px dashed #aaa;
        border-radius: 10px;
        background-color: #f0f0f0;
        transition: background-color 0.3s;
    }
    .uploader-wrapper:hover {
        background-color: #e0e0e0;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='uploader-wrapper'>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("", type=["pdf", "txt"], label_visibility="collapsed")
    st.markdown("""
    <p><strong>Click or drag a .pdf or .txt file to upload.</strong><br>
    Redact names, dates, genders, and custom keywords from your file.</p>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

if uploaded_file:
    text = extract_text(uploaded_file)

    st.markdown("<div class='section'>", unsafe_allow_html=True)
    st.subheader("Select what to redact:")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        redact_names = st.checkbox("Names", value=False)
    with col2:
        redact_dates = st.checkbox("Dates", value=False)
    with col3:
        redact_genders = st.checkbox("Genders", value=False)
    with col4:
        redact_custom = st.checkbox("Custom", value=False)
    with col5:
        redact_all = st.checkbox("All", value=False)

    if redact_all:
        redact_names = redact_dates = redact_genders = redact_custom = True

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section'>", unsafe_allow_html=True)
    custom_words = []
    if redact_custom:
        custom_input = st.text_area("Enter custom keywords to redact (comma separated):", key="custom", help="Type one or more keywords separated by commas.")
        if custom_input:
            custom_words = [word.strip() for word in custom_input.split(",") if word.strip()]

    if st.button("Redact"):
        redacted = redact_text(text, redact_names, redact_dates, redact_genders, custom_words)

        st.markdown("### Preview:")
        st.markdown(f"<div class='preview-box'>{redacted}</div>", unsafe_allow_html=True)

        download_btn = download_redacted_text(redacted)
        st.markdown(download_btn, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
