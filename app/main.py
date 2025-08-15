import os
import tempfile
import base64
import streamlit as st
import streamlit.components.v1 as components
from utilities.extract_text import extract_text_and_positions, CATEGORY_COLORS
from utilities.redact_pdf import redact_pdf_with_positions

# Temporary directory
temp_dir = tempfile.mkdtemp()

st.set_page_config(layout="wide")
st.title("PDF Redactor Tool")

# File uploader
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

# Redaction categories (with colors from extract_text.py)
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

# Selection state
if "selected_params" not in st.session_state:
    st.session_state.selected_params = list(redaction_parameters.values())

# Deselect All toggle
deselect_all = st.checkbox("Deselect All", value=False)
if deselect_all:
    st.session_state.selected_params = []
else:
    st.session_state.selected_params = list(redaction_parameters.values())

# Checkboxes for each parameter
for label, key in redaction_parameters.items():
    checked = key in st.session_state.selected_params
    if st.checkbox(f"{label}", value=checked):
        if key not in st.session_state.selected_params:
            st.session_state.selected_params.append(key)
    else:
        if key in st.session_state.selected_params:
            st.session_state.selected_params.remove(key)

# Custom phrase
custom_phrase = st.text_input("Custom phrase to redact", placeholder="Type and press Enter")
if custom_phrase and custom_phrase not in st.session_state.selected_params:
    st.session_state.selected_params.append(custom_phrase)

# Scan button
if st.button("Scan for Redacted Phrases") and uploaded_file:
    input_path = os.path.join(temp_dir, "input.pdf")
    with open(input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    try:
        found_phrases, positions = extract_text_and_positions(input_path, st.session_state.selected_params)

        components.html("""
            <script>
                setTimeout(function(){
                    document.getElementById("results-section").scrollIntoView({behavior: "smooth"});
                }, 300);
            </script>
        """, height=0)

        left_col, right_col = st.columns([1, 1])
        with left_col:
            st.markdown("<div id='results-section'></div>", unsafe_allow_html=True)
            st.markdown("### Redacted Phrases")
            st.markdown("""
                <style>
                .scroll-box {
                    max-height: 400px;
                    overflow-y: auto;
                    padding: 8px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    background-color: #f9f9f9;
                }
                .color-chip {
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border-radius: 2px;
                    margin-right: 8px;
                }
                </style>
            """, unsafe_allow_html=True)

            if found_phrases:
                phrase_html = "<div class='scroll-box'>"
                for phrase, category in found_phrases:
                    color = CATEGORY_COLORS.get(category, "#000000")
                    phrase_html += f"<div><span class='color-chip' style='background-color:{color}'></span>{phrase}</div>"
                phrase_html += "</div>"
                st.markdown(phrase_html, unsafe_allow_html=True)
            else:
                st.write("No matches found.")

            preview_pdf_path = os.path.join(temp_dir, "preview.pdf")
            redact_pdf_with_positions(input_path, positions, preview_pdf_path, preview_mode=True)

            with open(preview_pdf_path, "rb") as f:
                st.download_button("Download PDF", f, file_name="redacted.pdf")

        with right_col:
            st.markdown("### Preview")
            with open(preview_pdf_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode("utf-8")
            pdf_display = f"""
                <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500"></iframe>
            """
            st.markdown(pdf_display, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error processing PDF: {e}")
