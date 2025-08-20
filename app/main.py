import os
import io
import base64
import tempfile
from typing import List, Set, Dict

import pandas as pd
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
if "hits_editor_version" not in st.session_state:
    st.session_state.hits_editor_version = 0  # bump to reset table selection
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}

# handy aliases
hits = st.session_state.hits
selected_hit_ids = st.session_state.selected_hit_ids

# temp workspace
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

# callback to set all parameter checkboxes BEFORE they are instantiated
def _select_all_params():
    for key in redaction_parameters.values():
        st.session_state[f"param_{key}"] = True

# put the button above the checkboxes so its on_click runs first in the rerun
st.button("Select All Parameters", on_click=_select_all_params)

col1, col2 = st.columns(2)
selected_params: List[str] = []

for i, (label, key) in enumerate(redaction_parameters.items()):
    target_col = col1 if i % 2 == 0 else col2
    with target_col:
        default_val = bool(st.session_state.get(f"param_{key}", False))
        if st.checkbox(label, key=f"param_{key}", value=default_val):
            selected_params.append(key)

custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type phrase and press Enter")
if custom_phrase:
    selected_params.append(custom_phrase)

# -----------------------
# Scan
# -----------------------
if st.button("Scan for Redacted Phrases") and uploaded_file and selected_params:
    if st.session_state.input_path:
        hits[:] = extract_text_and_positions(st.session_state.input_path, selected_params) or []
        # select ALL by default after scanning
        st.session_state.id_to_hit.clear()
        selected_hit_ids.clear()
        for idx, h in enumerate(hits):
            hid = h.page * 1_000_000 + idx
            st.session_state.id_to_hit[hid] = h
            selected_hit_ids.add(hid)

        # reset table widget so defaults reflect current selection
        st.session_state.hits_editor_version += 1

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

        # Color markers (emoji squares) for each category
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

        # build table rows
        rows = []
        for idx, h in enumerate(hits):
            hid = h.page * 1_000_000 + idx
            rows.append({
                "id": hid,
                "Include": (hid in selected_hit_ids),
                "Mark": DOT.get(h.category, "⬛"),
                "Category": h.category,
                "Phrase": h.text,
                "Page": h.page + 1,
            })

        df = pd.DataFrame(rows).sort_values(["Category", "Page", "Phrase"]).reset_index(drop=True)

        # deselect-all button (single, per your spec)
        if st.button("Deselect All Phrases"):
            selected_hit_ids.clear()
            st.session_state.hits_editor_version += 1  # force reset

        # editable table with built-in scroll
        edited = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            height=420,
            key=f"hits_editor_{st.session_state.hits_editor_version}",
            column_config={
                "Include": st.column_config.CheckboxColumn("Include", help="Toggle to include / exclude this phrase"),
                "Mark": st.column_config.TextColumn(""),
                "Category": st.column_config.TextColumn("Type"),
                "Phrase": st.column_config.TextColumn("Phrase"),
                "Page": st.column_config.NumberColumn("Page"),
                "id": None,  # hide id column from display
            }
        )

        # update selection from editor
        try:
            new_selected = set(edited.loc[edited["Include"], "id"].astype(int).tolist())
        except Exception:
            new_selected = set()
        st.session_state.selected_hit_ids = new_selected

    with right_col:
        st.markdown("### Preview")
        if st.session_state.input_path:
            # create preview (colored, semi-transparent)
            selected_hits = [st.session_state.id_to_hit[i] for i in st.session_state.selected_hit_ids]
            out_bytes = redact_pdf_with_hits(st.session_state.input_path, selected_hits, preview_mode=True)

            # show preview
            b64_pdf = base64.b64encode(out_bytes).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="520px"></iframe>',
                unsafe_allow_html=True,
            )

            # download button (black-filled, burned-in)
            final_bytes = redact_pdf_with_hits(st.session_state.input_path, selected_hits, preview_mode=False)
            st.download_button("Download PDF", data=final_bytes, file_name="redacted.pdf")
