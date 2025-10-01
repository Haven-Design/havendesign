import os
import io
import base64
import tempfile
from typing import List, Set, Dict

import streamlit as st
import streamlit.components.v1 as components

from utilities.extract_text import extract_text_and_positions, Hit, CATEGORY_LABELS
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
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}

hits = st.session_state.hits
selected_hit_ids = st.session_state.selected_hit_ids
id_to_hit = st.session_state.id_to_hit

# -----------------------
# File upload
# -----------------------
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()

# -----------------------
# Redaction parameters
# -----------------------
st.subheader("Select Redaction Parameters")

def _select_all_params():
    for key in CATEGORY_LABELS.keys():
        st.session_state[f"param_{key}"] = True

st.button("Select All", on_click=_select_all_params)

col1, col2 = st.columns(2)
selected_params: List[str] = []

for i, (key, label) in enumerate(CATEGORY_LABELS.items()):
    target_col = col1 if i % 2 == 0 else col2
    with target_col:
        if f"param_{key}" not in st.session_state:
            st.session_state[f"param_{key}"] = False
        if st.checkbox(label, key=f"param_{key}"):
            selected_params.append(key)

custom_phrase = st.text_input(
    "Add a custom phrase to redact",
    placeholder="Type phrase and press Enter"
)
if custom_phrase:
    selected_params.append(custom_phrase)

# -----------------------
# Scan
# -----------------------
if st.button("Scan for Redacted Phrases") and uploaded_file and selected_params:
    # clear old hits
    hits.clear()
    id_to_hit.clear()
    selected_hit_ids.clear()

    new_hits = extract_text_and_positions(
        st.session_state.file_bytes,
        ".pdf",
        selected_params,
        custom_phrase=custom_phrase if custom_phrase else None,
    ) or []
    hits.extend(new_hits)

    for idx, h in enumerate(hits):
        hid = h.page * 1_000_000 + idx
        id_to_hit[hid] = h
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

        st.markdown(
            """
            <style>
            .scroll-box {
                max-height: 350px;
                overflow-y: auto;
                border: 1px solid #ddd;
                padding: 8px;
                border-radius: 8px;
                background: #fafafa;
            }
            .phrase-item {
                display: flex;
                align-items: center;
                margin-bottom: 6px;
                padding: 4px 6px;
                border-radius: 6px;
                background: white;
                border: 1px solid #eee;
            }
            .pill {
                display: inline-block;
                width: 14px;
                height: 14px;
                border-radius: 50%;
                margin-right: 8px;
            }
            .phrase-text {
                flex-grow: 1;
                font-weight: 500;
            }
            .page-num {
                font-size: 12px;
                color: #666;
                margin-left: 6px;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        phrases_html = "<div class='scroll-box'>"
        for idx, h in enumerate(hits):
            hid = h.page * 1_000_000 + idx
            checked = hid in selected_hit_ids
            color = CATEGORY_COLORS.get(h.category, "#000000")
            checkbox_key = f"hit_{hid}"

            # Use Streamlit checkbox for interactivity
            if st.checkbox(
                f"{h.text} (p{h.page+1})",
                key=checkbox_key,
                value=checked,
            ):
                selected_hit_ids.add(hid)
            else:
                selected_hit_ids.discard(hid)

        phrases_html += "</div>"
        st.markdown(phrases_html, unsafe_allow_html=True)

        # Download button here
        if st.session_state.file_bytes:
            selected_hits = [id_to_hit[i] for i in selected_hit_ids]
            final_bytes = redact_pdf_with_hits(
                st.session_state.file_bytes,
                selected_hits,
                preview_mode=False
            )
            st.download_button("Download Redacted PDF", data=final_bytes, file_name="redacted.pdf")

    with right_col:
        st.markdown("### Preview")
        if st.session_state.file_bytes:
            selected_hits = [id_to_hit[i] for i in selected_hit_ids]
            out_bytes = redact_pdf_with_hits(
                st.session_state.file_bytes,
                selected_hits,
                preview_mode=True
            )
            b64_pdf = base64.b64encode(out_bytes).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="520px"></iframe>',
                unsafe_allow_html=True,
            )
