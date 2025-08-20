import os
import base64
import tempfile
import streamlit as st
from typing import List, Set
from utilities.extract_text import extract_text_and_positions, Hit
from utilities.redact_pdf import redact_pdf_with_hits, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("PDF Redactor Tool")

# Temporary working directory
temp_dir = tempfile.mkdtemp()

# Initialize state
if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit = {}
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()
if "input_path" not in st.session_state:
    st.session_state.input_path = None

# Parameters
redaction_parameters = {
    "Email Addresses": "email",
    "Phone Numbers": "phone",
    "Credit Card Numbers": "credit_card",
    "Social Security Numbers": "ssn",
    "Driver's Licenses": "drivers_license",
    "Dates": "date",
    "Addresses": "address",
    "Names": "name",
    "IP Addresses": "ip_address",
    "Bank Account Numbers": "bank_account",
    "VIN Numbers": "vin",
}

# Select All for parameters
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Select All Parameters"):
        for label, key in redaction_parameters.items():
            st.session_state[f"param_{key}"] = True

st.subheader("Select Redaction Parameters")
c1, c2 = st.columns(2)
selected_params = []
for i, (label, key) in enumerate(redaction_parameters.items()):
    with (c1 if i % 2 == 0 else c2):
        if st.checkbox(label, key=f"param_{key}"):
            selected_params.append(key)

# Custom phrase
custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type phrase and press Enter")
if custom_phrase:
    selected_params.append(custom_phrase)

# File uploader
uploaded_file = st.file_uploader("Upload a document", type=["pdf", "txt", "docx"])
ext = None
if uploaded_file:
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    st.session_state.input_path = os.path.join(temp_dir, "input" + ext)
    with open(st.session_state.input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

# Scan button
if st.button("Scan for Redacted Phrases") and uploaded_file and selected_params:
    try:
        hits = extract_text_and_positions(st.session_state.input_path, selected_params)
        st.session_state.hits = hits
        st.session_state.id_to_hit = {h.page * 1_000_000 + i: h for i, h in enumerate(hits)}
        st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())
    except Exception as e:
        st.error(f"Error scanning: {e}")

# Results & Preview
if st.session_state.hits:
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("### Redacted Phrases")

        DOT = {
            "email": "🟥",
            "phone": "🟩",
            "credit_card": "🟦",
            "ssn": "🟨",
            "drivers_license": "🟧",
            "date": "🟪",
            "address": "🟩",
            "name": "🟪",
            "ip_address": "🟦",
            "bank_account": "🟧",
            "vin": "🟫",
            "custom": "⬜",
        }

        if st.button("Deselect All Phrases"):
            st.session_state.selected_hit_ids.clear()

        st.markdown(
            """
            <style>
            .scroll-box {
                max-height: 300px;
                overflow-y: scroll;
                padding: 0.5rem;
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: #fafafa;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="scroll-box">', unsafe_allow_html=True)

        for idx, h in enumerate(st.session_state.hits):
            hid = h.page * 1_000_000 + idx
            checked = hid in st.session_state.selected_hit_ids
            dot = DOT.get(h.category, "⬛")
            phrase_line = f"{dot} **{h.category}**: {h.text}"
            if st.checkbox(phrase_line, key=f"hit_{hid}", value=checked):
                st.session_state.selected_hit_ids.add(hid)
            else:
                st.session_state.selected_hit_ids.discard(hid)

        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.input_path:
            selected_hits = [st.session_state.id_to_hit[i] for i in st.session_state.selected_hit_ids]
            final_bytes = redact_pdf_with_hits(st.session_state.input_path, selected_hits, preview_mode=False)
            st.download_button("Download PDF", data=final_bytes, file_name="redacted.pdf")

    with right_col:
        st.markdown("### Preview")
        if st.session_state.input_path:
            preview_hits = [st.session_state.id_to_hit[i] for i in st.session_state.selected_hit_ids]
            preview_bytes = redact_pdf_with_hits(st.session_state.input_path, preview_hits, preview_mode=True)
            b64_pdf = base64.b64encode(preview_bytes).decode("utf-8")
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="600px"></iframe>', unsafe_allow_html=True)
