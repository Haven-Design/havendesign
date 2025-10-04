import os
import base64
import tempfile
from typing import List, Set, Dict

import streamlit as st
import streamlit.components.v1 as components

from utilities.extract_text import extract_text_and_positions, Hit
from utilities.redact_pdf import redact_pdf_with_hits
from components.redacted_list_component import redacted_list

st.set_page_config(layout="wide")
st.title("PDF Redactor Tool")

# -----------------------
# Session state init
# -----------------------
if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}

hits = st.session_state.hits
selected_hit_ids = st.session_state.selected_hit_ids
id_to_hit = st.session_state.id_to_hit
temp_dir = tempfile.mkdtemp()

# -----------------------
# File upload
# -----------------------
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()

# -----------------------
# Redaction parameters
# -----------------------
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

st.subheader("Select Redaction Parameters")

def _toggle_all():
    current = any(st.session_state.get(f"param_{key}", False) for key in redaction_parameters.values())
    for key in redaction_parameters.values():
        st.session_state[f"param_{key}"] = not current

st.button("Select/Deselect All Parameters", on_click=_toggle_all)

col1, col2 = st.columns(2)
selected_params: List[str] = []

for i, (label, key) in enumerate(redaction_parameters.items()):
    target_col = col1 if i % 2 == 0 else col2
    with target_col:
        if f"param_{key}" not in st.session_state:
            st.session_state[f"param_{key}"] = False
        if st.checkbox(label, key=f"param_{key}"):
            selected_params.append(key)

custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type phrase and press Enter")
if custom_phrase:
    selected_params.append(custom_phrase)

# -----------------------
# Scan
# -----------------------
if st.button("Scan for Redacted Phrases") and uploaded_file and selected_params:
    hits.clear()
    id_to_hit.clear()
    selected_hit_ids.clear()

    new_hits = extract_text_and_positions(st.session_state.file_bytes, ".pdf", selected_params) or []
    hits.extend(new_hits)

    for idx, h in enumerate(hits):
        hid = h.page * 1_000_000 + idx
        id_to_hit[hid] = h
        selected_hit_ids.add(hid)

# -----------------------
# Results & Preview
# -----------------------
if hits:
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("### Redacted Phrases")

        # Build data for React component
        phrases_data: Dict[str, List[dict]] = {}
        category_colors = {
            "email": "#e63946",
            "phone": "#2a9d8f",
            "credit_card": "#264653",
            "ssn": "#f4a261",
            "drivers_license": "#e76f51",
            "date": "#457b9d",
            "address": "#8d99ae",
            "name": "#6a4c93",
            "ip_address": "#118ab2",
            "bank_account": "#073b4c",
            "vin": "#8338ec",
            "custom": "#adb5bd",
        }

        for hid, h in id_to_hit.items():
            color = category_colors.get(h.category, "#000000")
            if h.category not in phrases_data:
                phrases_data[h.category] = []
            phrases_data[h.category].append({
                "id": hid,
                "text": h.text,
                "page": h.page + 1,
                "color": color,
                "selected": hid in selected_hit_ids,
            })

        updated_state = redacted_list(phrases_data, key="redacted-ui")

        if updated_state:
            # Reset and update selected_hit_ids based on React component
            selected_hit_ids.clear()
            for cat, phrases in updated_state.items():
                for p in phrases:
                    if p.get("selected", False):
                        selected_hit_ids.add(p["id"])

        if st.session_state.file_bytes:
            selected_hits = [id_to_hit[i] for i in selected_hit_ids]
            final_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=False)
            st.download_button("Download PDF", data=final_bytes, file_name="redacted.pdf")

    with right_col:
        st.markdown("### Preview")
        if st.session_state.file_bytes:
            selected_hits = [id_to_hit[i] for i in selected_hit_ids]
            out_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=True)
            b64_pdf = base64.b64encode(out_bytes).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="520px"></iframe>',
                unsafe_allow_html=True,
            )
