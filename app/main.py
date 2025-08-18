import os
import tempfile
import base64
import streamlit as st
import streamlit.components.v1 as components
from utilities.extract_text import extract_text_and_positions
from utilities.redact_pdf import redact_pdf_with_positions

# Temporary directory for previews
temp_dir = tempfile.mkdtemp()

# UI Title
st.title("PDF Redactor Tool")

# File uploader
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

# Parameter list for redactions
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

# Checkbox UI (default unchecked)
st.subheader("Select Redaction Parameters")
col1, col2 = st.columns(2)
selected_params = []
checkbox_states = {}

for i, (label, key) in enumerate(redaction_parameters.items()):
    if i % 2 == 0:
        with col1:
            state = st.checkbox(label, value=False, key=key)
    else:
        with col2:
            state = st.checkbox(label, value=False, key=key)
    checkbox_states[key] = state
    if state:
        selected_params.append(key)

# Select All button
if st.button("Select All"):
    for key in redaction_parameters.values():
        st.session_state[key] = True

# Extra custom phrase input
custom_phrase = st.text_input(
    "Add a custom phrase to redact",
    placeholder="Type phrase and press Enter"
)
if custom_phrase:
    selected_params.append(custom_phrase)

# Scan button
if st.button("Scan for Redacted Phrases") and uploaded_file:
    # Save uploaded PDF temporarily
    input_path = os.path.join(temp_dir, "input.pdf")
    with open(input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    try:
        # Extract matches and positions
        found_phrases, positions_by_category = extract_text_and_positions(
            input_path, selected_params
        )

        # Inject auto-scroll to results section
        components.html("""
            <script>
                setTimeout(function(){
                    document.getElementById("results-section").scrollIntoView({behavior: "smooth"});
                }, 300);
            </script>
        """, height=0)

        # Layout: Left list, Right preview
        left_col, right_col = st.columns([1, 1])

        with st.container():
            st.markdown("<div id='results-section'></div>", unsafe_allow_html=True)

            # Left: Scrollable list
            with left_col:
                st.markdown("### Found Phrases")

                if found_phrases:
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
                        .phrase-email { color: #1f77b4; }
                        .phrase-phone { color: #ff7f0e; }
                        .phrase-credit_card { color: #2ca02c; }
                        .phrase-ssn { color: #d62728; }
                        .phrase-drivers_license { color: #9467bd; }
                        .phrase-date { color: #8c564b; }
                        .phrase-address { color: #e377c2; }
                        .phrase-name { color: #7f7f7f; }
                        .phrase-ip_address { color: #bcbd22; }
                        .phrase-bank_account { color: #17becf; }
                        .phrase-vin { color: #17a589; }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )

                    formatted_phrases = [
                        f"<div class='phrase-{cat}'>{phrase}</div>"
                        for phrase, cat in found_phrases
                    ]
                    st.markdown(
                        "<div class='scroll-box'>" + "<br>".join(formatted_phrases) + "</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.write("No matches found.")

                # Download button always visible
                preview_pdf_path = os.path.join(temp_dir, "preview.pdf")
                redact_pdf_with_positions(input_path, positions_by_category, preview_pdf_path, preview=True)
                with open(preview_pdf_path, "rb") as f:
                    st.download_button("Download PDF", f, file_name="redacted.pdf")

            # Right: Preview
            with right_col:
                st.markdown("### Preview")
                with open(preview_pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500px"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error processing PDF: {e}")
