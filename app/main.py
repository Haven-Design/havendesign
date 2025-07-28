import streamlit as st
from PyPDF2 import PdfReader
from pdf2image import convert_from_bytes
from io import BytesIO
from utilities.redact_pdf import redact_pdf
import base64

st.set_page_config(page_title="PDF Redactor", layout="wide")
st.title("🔒 PDF Redactor")

if "pdf_bytes" not in st.session_state:
    st.session_state["pdf_bytes"] = None
if "selected_pages" not in st.session_state:
    st.session_state["selected_pages"] = []
if "redacted_pdf_bytes" not in st.session_state:
    st.session_state["redacted_pdf_bytes"] = None

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file:
    st.session_state["pdf_bytes"] = uploaded_file.read()
    reader = PdfReader(BytesIO(st.session_state["pdf_bytes"]))
    total_pages = len(reader.pages)

    st.markdown("### Select pages to redact")
    cols = st.columns([0.1, 0.9])
    with cols[0]:
        select_all = st.checkbox("All", key="select_all")
    with cols[1]:
        selected = st.multiselect(
            "", [f"Page {i+1}" for i in range(total_pages)],
            default=[f"Page {i+1}" for i in range(total_pages)] if st.session_state["selected_pages"] == [] else st.session_state["selected_pages"]
        )
    st.session_state["selected_pages"] = selected

    # Show preview
    st.markdown("### PDF Preview")
    images = convert_from_bytes(st.session_state["pdf_bytes"])
    for i, image in enumerate(images):
        if f"Page {i+1}" in st.session_state["selected_pages"]:
            st.image(image, caption=f"Page {i+1}", use_container_width=True)

    # Redaction options
    st.markdown("### Redaction Options")
    st.session_state["redact_names"] = st.checkbox("Redact Names")
    st.session_state["redact_addresses"] = st.checkbox("Redact Addresses")
    st.session_state["redact_dates"] = st.checkbox("Redact Dates")

    # Perform redaction
    if st.session_state["redacted_pdf_bytes"] is None:
        if st.button("Redact PDF"):
            with st.spinner("Redacting PDF..."):
                selected_indices = [int(p.split(" ")[1]) - 1 for p in st.session_state["selected_pages"]]
                st.session_state["redacted_pdf_bytes"] = redact_pdf(
                    pdf_bytes=st.session_state["pdf_bytes"],
                    pages_to_redact=selected_indices,
                    redact_names=st.session_state["redact_names"],
                    redact_addresses=st.session_state["redact_addresses"],
                    redact_dates=st.session_state["redact_dates"]
                )
                st.success("PDF redacted successfully.")

    # Show download if redaction is done
    if st.session_state["redacted_pdf_bytes"]:
        st.download_button(
            label="Download PDF",
            data=st.session_state["redacted_pdf_bytes"],
            file_name="redacted.pdf",
            mime="application/pdf"
        )
