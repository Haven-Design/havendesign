import os
import io
import base64
import tempfile
from typing import List, Dict

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from utilities.extract_text import extract_text_and_positions, Hit
from utilities.redact_pdf import redact_pdf_with_hits, save_masked_file, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("PDF & Document Redactor Tool")

# -----------------------
# Session state
# -----------------------
if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}
if "hit_df" not in st.session_state:
    st.session_state.hit_df = pd.DataFrame()
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = b""
if "file_ext" not in st.session_state:
    st.session_state.file_ext = ""
if "input_path" not in st.session_state:
    st.session_state.input_path = ""

temp_dir = tempfile.mkdtemp()

# -----------------------
# Upload
# -----------------------
uploaded_file = st.file_uploader("Upload a file", type=["pdf", "docx", "txt", "csv"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()
    st.session_state.file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    st.session_state.input_path = os.path.join(temp_dir, f"input{st.session_state.file_ext}")
    with open(st.session_state.input_path, "wb") as f:
        f.write(st.session_state.file_bytes)

# -----------------------
# Params (with Select All)
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

def _select_all_params():
    for k in redaction_parameters.values():
        st.session_state[f"param_{k}"] = True

st.subheader("Select Redaction Parameters")
st.caption("Tip: Click **Select All Parameters** to quickly enable everything.")
st.button("Select All Parameters", on_click=_select_all_params)

selected_params: List[str] = []
col1, col2 = st.columns(2)
for i, (label, key) in enumerate(redaction_parameters.items()):
    target_col = col1 if i % 2 == 0 else col2
    with target_col:
        if st.checkbox(label, key=f"param_{key}", value=st.session_state.get(f"param_{key}", False)):
            selected_params.append(key)

custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type phrase and press Enter")
if custom_phrase:
    selected_params.append(custom_phrase)

# -----------------------
# Scan
# -----------------------
if st.button("Scan for Redacted Phrases") and st.session_state.input_path and selected_params:
    hits = extract_text_and_positions(st.session_state.input_path, selected_params) or []
    st.session_state.hits = hits

    rows = []
    id_to_hit = {}
    # color dots for categories (emoji so they render reliably)
    DOT = {
        "email": "🟥", "phone": "🟩", "credit_card": "🟦", "ssn": "🟨",
        "drivers_license": "🟧", "date": "🟪", "address": "🟩",
        "name": "🩷", "ip_address": "🟦", "bank_account": "🟠",
        "vin": "🟫", "custom": "⬜",
    }
    for idx, h in enumerate(hits):
        hit_id = h.page * 1_000_000 + idx
        id_to_hit[hit_id] = h
        rows.append({
            "id": hit_id,
            "Include": True,
            "Mark": DOT.get(h.category, "⬛"),
            "Category": h.category,
            "Phrase": h.text,
            "Page": h.page + 1,
        })
    df = pd.DataFrame(rows).set_index("id")
    st.session_state.id_to_hit = id_to_hit
    st.session_state.hit_df = df

    components.html(
        """<script>
            setTimeout(function(){
              const n = document.getElementById("results-section");
              if (n) n.scrollIntoView({behavior: "smooth"});
            }, 250);
        </script>""",
        height=0,
    )

# -----------------------
# Results & preview
# -----------------------
if not st.session_state.hits:
    st.stop()

left_col, right_col = st.columns([1, 1])

with left_col:
    st.markdown("<div id='results-section'></div>", unsafe_allow_html=True)
    st.subheader("Redacted Phrases")

    # Deselect All (apply BEFORE rendering the editor)
    if st.button("Deselect All"):
        if not st.session_state.hit_df.empty:
            st.session_state.hit_df["Include"] = False

    # Scrollable, editable list
    edited = st.data_editor(
        st.session_state.hit_df,
        num_rows="fixed",
        use_container_width=True,
        height=420,
        hide_index=True,
        column_config={
            "Include": st.column_config.CheckboxColumn("Include"),
            "Mark": st.column_config.TextColumn(" ", width="small"),
            "Category": st.column_config.TextColumn("Type"),
            "Phrase": st.column_config.TextColumn("Phrase"),
            "Page": st.column_config.NumberColumn("Pg"),
        },
        disabled=["Mark", "Category", "Phrase", "Page"],
    )
    st.session_state.hit_df = edited

    ext = st.session_state.file_ext
    if st.button("Download Redacted File"):
        selected_ids = edited.index[edited["Include"]].tolist()
        hits_to_redact = [st.session_state.id_to_hit[i] for i in selected_ids]

        if ext == ".pdf":
            out_bytes = redact_pdf_with_hits(
                st.session_state.input_path, hits_to_redact, preview_mode=False
            )
            st.download_button("Click to Download", data=out_bytes, file_name="redacted.pdf")
        else:
            out_bytes = save_masked_file(st.session_state.file_bytes, ext, hits_to_redact)
            st.download_button("Click to Download", data=out_bytes, file_name=f"redacted{ext}")

with right_col:
    st.subheader("Preview")

    ext = st.session_state.file_ext
    selected_ids = st.session_state.hit_df.index[st.session_state.hit_df["Include"]].tolist()
    hits_to_preview = [st.session_state.id_to_hit[i] for i in selected_ids]

    if ext == ".pdf":
        preview_bytes = redact_pdf_with_hits(
            st.session_state.input_path, hits_to_preview, preview_mode=True
        )
        b64_pdf = base64.b64encode(preview_bytes).decode("utf-8")
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="520px"></iframe>',
            unsafe_allow_html=True,
        )
    else:
        masked = save_masked_file(st.session_state.file_bytes, ext, hits_to_preview)
        st.text_area("Masked Preview", masked.decode("utf-8"), height=520)
