import os
import io
import tempfile
import base64
import streamlit as st
import streamlit.components.v1 as components
from typing import List, Set
from utilities.extract_text import extract_text_and_positions, Hit, CATEGORY_PRIORITY
from utilities.redact_pdf import redact_pdf_with_hits, save_masked_file, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("PDF & Document Redactor Tool")

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
uploaded_file = st.file_uploader("Upload a file", type=["pdf", "docx", "txt", "csv"])
if uploaded_file:
    st.session_state["file_bytes"] = uploaded_file.getvalue()
    st.session_state["file_ext"] = os.path.splitext(uploaded_file.name)[1].lower()

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
# Scan file
# -----------------------
if st.button("Scan for Redacted Phrases") and uploaded_file:
    ext = st.session_state["file_ext"]
    input_path = os.path.join(temp_dir, f"input{ext}")
    with open(input_path, "wb") as f:
        f.write(st.session_state["file_bytes"])

    hits[:] = extract_text_and_positions(input_path, selected_params) or []
    selected_hit_ids.clear()

    components.html(
        """<script>
            setTimeout(function(){
                document.getElementById("results-section").scrollIntoView({behavior: "smooth"});
            }, 300);
        </script>""",
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

        if st.button("Deselect All"):
            selected_hit_ids.clear()

        for idx, hit in enumerate(hits):
            hit_id = hit.page * 1_000_000 + idx
            checked = hit_id in selected_hit_ids or not selected_hit_ids
            color = CATEGORY_COLORS.get(hit.category, "#000000")
            label_html = f"<span style='color:{color}'>[{hit.category}] {hit.text} (p{hit.page+1})</span>"
            if st.checkbox(label_html, key=f"hit_{hit_id}", value=checked):
                selected_hit_ids.add(hit_id)
            else:
                selected_hit_ids.discard(hit_id)

        st.markdown("</div>", unsafe_allow_html=True)

        ext = st.session_state.get("file_ext", "")
        file_bytes = st.session_state.get("file_bytes", b"")

        if st.button("Download Redacted File"):
            if ext == ".pdf":
                input_path = os.path.join(temp_dir, "input.pdf")
                with open(input_path, "wb") as f:
                    f.write(file_bytes)

                hits_to_redact = [hit for idx, hit in enumerate(hits)
                                  if (hit.page * 1_000_000 + idx) in selected_hit_ids]
                out_bytes = redact_pdf_with_hits(input_path, hits_to_redact, preview_mode=False)
                st.download_button("Click to Download", data=out_bytes, file_name="redacted.pdf")
            else:
                hits_to_redact = [hit for idx, hit in enumerate(hits)
                                  if (hit.page * 1_000_000 + idx) in selected_hit_ids]
                out_bytes = save_masked_file(file_bytes, st.session_state["file_ext"], hits_to_redact)
                st.download_button("Click to Download", data=out_bytes,
                                   file_name=f"redacted{ext}")

    with right_col:
        st.markdown("### Preview")
        ext = st.session_state.get("file_ext", "")

        if ext == ".pdf":
            preview_pdf_path = os.path.join(temp_dir, "preview.pdf")
            hits_to_redact = [hit for idx, hit in enumerate(hits)
                              if (hit.page * 1_000_000 + idx) in selected_hit_ids]
            redact_pdf_with_hits(input_path, hits_to_redact, preview_pdf_path, preview_mode=True)
            with open(preview_pdf_path, "rb") as f:
                b64_pdf = base64.b64encode(f.read()).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="500px"></iframe>',
                unsafe_allow_html=True,
            )
        else:
            text_preview = save_masked_file(st.session_state["file_bytes"], ext, hits)
            st.text_area("Preview", text_preview.decode("utf-8"), height=500)
