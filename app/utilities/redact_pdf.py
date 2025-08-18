import os
import tempfile
import base64
import streamlit as st
import streamlit.components.v1 as components
from typing import List, Set
from utilities.extract_text import extract_text_and_positions, Hit
from utilities.redact_pdf import redact_pdf_with_hits, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("PDF Redactor Tool")

# -----------------------
# Session state init
# -----------------------
if "hits" not in st.session_state:
    st.session_state["hits"] = []
if "selected_hit_ids" not in st.session_state:
    st.session_state["selected_hit_ids"] = set()

hits: List[Hit] = st.session_state["hits"]
selected_hit_ids: Set[int] = st.session_state["selected_hit_ids"]

# -----------------------
# File upload
# -----------------------
temp_dir = tempfile.mkdtemp()
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

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

# Checkbox groups
for i, (label, key) in enumerate(redaction_parameters.items()):
    if i % 2 == 0:
        with col1:
            if st.checkbox(label, key=f"param_{key}"):
                selected_params.append(key)
    else:
        with col2:
            if st.checkbox(label, key=f"param_{key}"):
                selected_params.append(key)

# Select All Parameters button
if st.button("Select All Parameters"):
    for key in redaction_parameters.values():
        st.session_state[f"param_{key}"] = True

# Custom phrase
custom_phrase = st.text_input("Add a custom phrase to redact", placeholder="Type phrase and press Enter")
if custom_phrase:
    selected_params.append(custom_phrase)

# -----------------------
# Scan PDF
# -----------------------
if st.button("Scan for Redacted Phrases") and uploaded_file:
    input_path = os.path.join(temp_dir, "input.pdf")
    with open(input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    hits[:] = extract_text_and_positions(input_path, selected_params) or []
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

        for idx, hit in enumerate(hits):
            hit_id = hit.page * 1_000_000 + idx
            checked = hit_id in selected_hit_ids
            color = CATEGORY_COLORS.get(hit.category, "#000000")
            label = f"<span style='color:{color};'>[{hit.category}] {hit.text} (p{hit.page+1})</span>"

            if st.checkbox(label, key=f"hit_{hit_id}", value=checked, unsafe_allow_html=True):
                selected_hit_ids.add(hit_id)
            else:
                selected_hit_ids.discard(hit_id)

        st.markdown("</div>", unsafe_allow_html=True)

        # Build preview PDF
        preview_pdf_path = os.path.join(temp_dir, "preview.pdf")
        input_path = os.path.join(temp_dir, "input.pdf")
        hits_to_redact = [
            hit for idx, hit in enumerate(hits)
            if (hit.page * 1_000_000 + idx) in selected_hit_ids
        ]
        redact_pdf_with_hits(input_path, hits_to_redact, preview_pdf_path, preview_mode=True)

        with open(preview_pdf_path, "rb") as f:
            st.download_button("Download PDF", f, file_name="redacted.pdf")

    with right_col:
        st.markdown("### Preview")
        with open(preview_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="500px"></iframe>',
            unsafe_allow_html=True,
        )
