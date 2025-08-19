import os
import tempfile
import base64
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from typing import List, Set

from utilities.extract_text import extract_text_and_positions, Hit, CATEGORY_PRIORITY
from utilities.redact_pdf import redact_pdf_with_hits, save_masked_file

st.set_page_config(layout="wide")
st.title("PDF Redactor Tool")

# -----------------------
# Session state init
# -----------------------
if "hits" not in st.session_state:
    st.session_state["hits"] = []
if "selected_hit_ids" not in st.session_state:
    st.session_state["selected_hit_ids"] = set()
if "file_bytes" not in st.session_state:
    st.session_state["file_bytes"] = None
if "input_path" not in st.session_state:
    st.session_state["input_path"] = None

hits: List[Hit] = st.session_state["hits"]
selected_hit_ids: Set[int] = st.session_state["selected_hit_ids"]

# -----------------------
# File upload
# -----------------------
temp_dir = tempfile.mkdtemp()
uploaded_file = st.file_uploader("Upload a document", type=["pdf", "txt", "csv", "docx"])

if uploaded_file:
    st.session_state["file_bytes"] = uploaded_file.getvalue()
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext == ".pdf":
        input_path = os.path.join(temp_dir, "input.pdf")
        with open(input_path, "wb") as f:
            f.write(st.session_state["file_bytes"])
        st.session_state["input_path"] = input_path

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
col1, col2 = st.columns(2)
selected_params: List[str] = []

for i, (label, key) in enumerate(redaction_parameters.items()):
    if i % 2 == 0:
        with col1:
            if st.checkbox(label, key=f"param_{key}"):
                selected_params.append(key)
    else:
        with col2:
            if st.checkbox(label, key=f"param_{key}"):
                selected_params.append(key)

custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type phrase and press Enter")
if custom_phrase:
    selected_params.append(custom_phrase)

# -----------------------
# Scan PDF
# -----------------------
if st.button("Scan for Redacted Phrases") and uploaded_file and selected_params:
    if st.session_state["input_path"]:
        hits[:] = extract_text_and_positions(st.session_state["input_path"], selected_params) or []
        selected_hit_ids.clear()

        # Scroll to results
        components.html(
            """
            <script>
                setTimeout(function(){
                    document.getElementById("results-section").scrollIntoView({behavior: "smooth"});
                }, 300);
            </script>
            """,
            height=0,
        )

# -----------------------
# Display results & preview
# -----------------------
if hits:
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("<div id='results-section'></div>", unsafe_allow_html=True)
        st.markdown("### Redacted Phrases")

        # Category to emoji square
        DOT = {
            "email": "🟥", "phone": "🟩", "credit_card": "🟦", "ssn": "🟨",
            "drivers_license": "🟧", "date": "🟪", "address": "🟩",
            "name": "🟪", "ip_address": "🟦", "bank_account": "🟧",
            "vin": "🟫", "custom": "⬜",
        }

        rows = []
        id_to_hit = {}
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

        df = pd.DataFrame(rows).sort_values(by=["Category", "Phrase"]).set_index("id")
        st.session_state.id_to_hit = id_to_hit

        # Scroll box style
        st.markdown(
            """
            <style>
            .scroll-box {
                max-height: 400px;
                overflow-y: auto;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div class='scroll-box'>", unsafe_allow_html=True)

        # Deselect all button
        if st.button("Deselect All Phrases"):
            selected_hit_ids.clear()

        # Individual checkboxes
        for idx, row in df.iterrows():
            checked = idx in selected_hit_ids
            label = f"{row['Mark']} {row['Phrase']} (p{row['Page']})"
            if st.checkbox(label, key=f"hit_{idx}", value=checked):
                selected_hit_ids.add(idx)
            else:
                selected_hit_ids.discard(idx)

        st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        st.markdown("### Preview")
        if st.session_state["input_path"]:
            preview_pdf_path = os.path.join(temp_dir, "preview.pdf")
            hits_to_redact = [st.session_state.id_to_hit[i] for i in selected_hit_ids]
            out_bytes = redact_pdf_with_hits(st.session_state["input_path"], hits_to_redact, preview_mode=True)
            with open(preview_pdf_path, "wb") as f:
                f.write(out_bytes)

            b64_pdf = base64.b64encode(out_bytes).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="500px"></iframe>',
                unsafe_allow_html=True,
            )

        # Download
        if st.session_state["file_bytes"]:
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            hits_to_redact = [st.session_state.id_to_hit[i] for i in selected_hit_ids]

            if ext == ".pdf":
                out_bytes = redact_pdf_with_hits(st.session_state["input_path"], hits_to_redact, preview_mode=False)
                st.download_button("Click to Download", data=out_bytes, file_name="redacted.pdf")
            else:
                out_bytes = save_masked_file(st.session_state["file_bytes"], ext, hits_to_redact)
                st.download_button("Click to Download", data=out_bytes, file_name=f"redacted{ext}")
