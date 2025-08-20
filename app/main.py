import os
import io
import base64
import tempfile
from typing import List, Set, Dict

import streamlit as st
import streamlit.components.v1 as components

from utilities.extract_text import extract_text_and_positions, Hit
from utilities.redact_pdf import redact_pdf_with_hits, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("PDF Redactor Tool")

# -----------------------
# Session state init
# -----------------------
if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()
if "input_path" not in st.session_state:
    st.session_state.input_path = None
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}

hits = st.session_state.hits
selected_hit_ids = st.session_state.selected_hit_ids
temp_dir = tempfile.mkdtemp()

# -----------------------
# File upload
# -----------------------
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()
    input_path = os.path.join(temp_dir, "input.pdf")
    with open(input_path, "wb") as f:
        f.write(st.session_state.file_bytes)
    st.session_state.input_path = input_path

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

def _select_all_params():
    for key in redaction_parameters.values():
        st.session_state[f"param_{key}"] = True

st.button("Select All Parameters", on_click=_select_all_params)

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
    if st.session_state.input_path:
        # clear old hits
        hits.clear()
        st.session_state.id_to_hit.clear()
        selected_hit_ids.clear()

        new_hits = extract_text_and_positions(st.session_state.input_path, selected_params) or []
        hits.extend(new_hits)

        for idx, h in enumerate(hits):
            hid = h.page * 1_000_000 + idx
            st.session_state.id_to_hit[hid] = h
            selected_hit_ids.add(hid)

        components.html(
            """
            <script>
                setTimeout(function(){
                    const el = document.getElementById("results-section");
                    if (el) el.scrollIntoView({behavior: "smooth"});
                }, 300);
            </script>
            """,
            height=0,
        )

# -----------------------
# Results & Preview
# -----------------------
if hits:
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("<div id='results-section'></div>", unsafe_allow_html=True)
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
            selected_hit_ids.clear()

        # scrollable phrases list
        phrases_md = ""
        for idx, h in enumerate(hits):
            hid = h.page * 1_000_000 + idx
            checked = hid in selected_hit_ids
            dot = DOT.get(h.category, "⬛")
            phrase_line = f"{dot} [p{h.page+1}] **{h.category}**: {h.text}"
            if st.checkbox(phrase_line, key=f"hit_{hid}", value=checked):
                selected_hit_ids.add(hid)
            else:
                selected_hit_ids.discard(hid)

        # Download button here (under phrases list)
        if st.session_state.input_path:
            selected_hits = [st.session_state.id_to_hit[i] for i in selected_hit_ids]
            final_bytes = redact_pdf_with_hits(st.session_state.input_path, selected_hits, preview_mode=False)
            st.download_button("Download PDF", data=final_bytes, file_name="redacted.pdf")

    with right_col:
        st.markdown("### Preview")
        if st.session_state.input_path:
            selected_hits = [st.session_state.id_to_hit[i] for i in selected_hit_ids]
            out_bytes = redact_pdf_with_hits(st.session_state.input_path, selected_hits, preview_mode=True)

            b64_pdf = base64.b64encode(out_bytes).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="520px"></iframe>',
                unsafe_allow_html=True,
            )
