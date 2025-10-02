import base64
import tempfile
from typing import List, Set, Dict

import streamlit as st
import streamlit.components.v1 as components

from utilities.extract_text import extract_text_and_positions, Hit, CATEGORY_LABELS
from utilities.redact_pdf import redact_pdf_with_hits, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("Document Redactor Tool")

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
    hits.clear()
    id_to_hit.clear()
    selected_hit_ids.clear()

    new_hits = extract_text_and_positions(
        st.session_state.file_bytes,
        ".pdf",
        selected_params,
        custom_phrase if custom_phrase else None
    ) or []

    for idx, h in enumerate(new_hits):
        hid = h.page * 1_000_000 + idx
        id_to_hit[hid] = h
        selected_hit_ids.add(hid)
        hits.append(h)

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

        # CSS
        st.markdown(
            """
            <style>
            .scroll-box {
                max-height: 520px;
                overflow-y: auto;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 8px;
            }
            .cat-header {
                display: flex;
                align-items: center;
                font-weight: bold;
                margin-top: 6px;
                margin-bottom: 2px;
            }
            .cat-square {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                margin-right: 6px;
            }
            .phrase-item {
                margin-left: 24px;
                margin-bottom: 4px;
                font-size: 0.95em;
            }
            .phrase-meta {
                font-size: 0.8em;
                color: #666;
                margin-left: 6px;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        with st.container():
            st.markdown('<div class="scroll-box">', unsafe_allow_html=True)

            # Group hits by category
            category_groups: Dict[str, List[tuple]] = {}
            for hid, h in id_to_hit.items():
                category_groups.setdefault(h.category, []).append((hid, h))

            for cat, items in category_groups.items():
                color = CATEGORY_COLORS.get(cat, "#000")

                # Category checkbox
                cat_key = f"cat_{cat}"
                all_checked = all(hid in selected_hit_ids for hid, _ in items)
                cat_box = st.checkbox(
                    f"{CATEGORY_LABELS.get(cat, cat)}",
                    key=cat_key,
                    value=all_checked
                )

                # Styled header row
                st.markdown(
                    f"""
                    <div class="cat-header">
                        <span class="cat-square" style="background:{color};"></span>
                        <span style="color:{color};">{CATEGORY_LABELS.get(cat, cat)}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Child phrases
                for hid, h in sorted(items, key=lambda x: (x[1].page, x[1].bbox[1] if x[1].bbox else 0)):
                    phrase_key = f"hit_{hid}"
                    checked = hid in selected_hit_ids if cat_box else False
                    if st.checkbox(f"{h.text} (p.{h.page+1})", key=phrase_key, value=checked):
                        selected_hit_ids.add(hid)
                    else:
                        selected_hit_ids.discard(hid)

            st.markdown('</div>', unsafe_allow_html=True)

        # Download button
        if st.session_state.file_bytes:
            selected_hits = [id_to_hit[i] for i in selected_hit_ids]
            final_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected_hits, preview_mode=False)
            st.download_button("Download Redacted PDF", data=final_bytes, file_name="redacted.pdf")

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
