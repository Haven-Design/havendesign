import os
import io
import base64
import tempfile
import streamlit as st
from typing import List
from utilities.extract_text import extract_text_and_positions, Hit, CATEGORY_LABELS
from utilities.redact_pdf import redact_pdf_with_hits, save_masked_file, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("PDF Redactor Tool")

if "params" not in st.session_state:
    st.session_state.params = {key: False for key in CATEGORY_LABELS.keys()}
if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit = {}
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids = set()
if "input_path" not in st.session_state:
    st.session_state.input_path = None
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None

uploaded_file = st.file_uploader("Upload file", type=["pdf", "txt", "docx"])

# --- Select redaction parameters ---
if uploaded_file:
    st.subheader("Select Redaction Parameters")
    col1, col2 = st.columns(2)
    for i, (label, key) in enumerate(CATEGORY_LABELS.items()):
        target = col1 if i % 2 == 0 else col2
        st.session_state.params[key] = target.checkbox(
            label, value=st.session_state.params[key], key=f"param_{key}"
        )

    if st.button("Select All Parameters"):
        for key in CATEGORY_LABELS.keys():
            st.session_state.params[key] = True
        st.experimental_rerun()

    custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type and press Enter")
    if custom_phrase:
        st.session_state.params["custom"] = True

    # Save file temporarily
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(uploaded_file.getvalue())
        st.session_state.input_path = tmp.name
    st.session_state.file_bytes = uploaded_file.getvalue()

    if st.button("Scan for Redacted Phrases"):
        st.session_state.hits = extract_text_and_positions(
            st.session_state.input_path, st.session_state.params, custom_phrase
        )
        st.session_state.id_to_hit = {
            h.page * 1_000_000 + idx: h for idx, h in enumerate(st.session_state.hits)
        }
        st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())
        st.experimental_rerun()

# --- Display redacted phrases and preview ---
if st.session_state.hits:
    st.subheader("Redacted Phrases & Preview")
    col1, col2 = st.columns([1, 2])

    with col1:
        if st.button("Deselect All"):
            st.session_state.selected_hit_ids = set()
            st.experimental_rerun()

        st.markdown("### Redacted Phrases")
        with st.container():
            st.markdown(
                "<div style='max-height:400px; overflow-y:auto; border:1px solid #ccc; padding:8px;'>",
                unsafe_allow_html=True,
            )
            for idx, hit in enumerate(st.session_state.hits):
                hit_id = hit.page * 1_000_000 + idx
                checked = hit_id in st.session_state.selected_hit_ids
                color = CATEGORY_COLORS.get(hit.category, "#999999")

                if st.checkbox(
                    f"{hit.text} (Page {hit.page+1})",
                    value=checked,
                    key=f"hit_{hit_id}",
                ):
                    st.session_state.selected_hit_ids.add(hit_id)
                else:
                    st.session_state.selected_hit_ids.discard(hit_id)

                st.markdown(
                    f"<span style='color:{color}; font-weight:bold;'>{hit.category}</span>",
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

        # Download button
        if ext == ".pdf":
            hits_to_redact = [st.session_state.id_to_hit[i] for i in st.session_state.selected_hit_ids]
            out_bytes = redact_pdf_with_hits(st.session_state.input_path, hits_to_redact, preview_mode=False)
            st.download_button("Click to Download", data=out_bytes, file_name="redacted.pdf")
        else:
            out_bytes = save_masked_file(st.session_state.file_bytes, ext)
            st.download_button("Click to Download", data=out_bytes, file_name=f"redacted{ext}")

    with col2:
        hits_to_redact = [st.session_state.id_to_hit[i] for i in st.session_state.selected_hit_ids]
        preview_bytes = redact_pdf_with_hits(st.session_state.input_path, hits_to_redact, preview_mode=True)
        b64_pdf = base64.b64encode(preview_bytes).decode("utf-8")
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="600px"></iframe>',
            unsafe_allow_html=True,
        )
