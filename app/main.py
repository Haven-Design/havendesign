import os
import io
import base64
from typing import List, Set, Dict

import streamlit as st
import streamlit.components.v1 as components

from utilities.extract_text import (
    extract_text_and_positions,
    Hit,
    CATEGORY_LABELS,
    CATEGORY_COLORS,
)
from utilities.redact_pdf import redact_pdf_with_hits

st.set_page_config(layout="wide")
st.title("Redactor API Tool")

# -----------------------
# Session state init
# -----------------------
if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}
if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None
if "ext" not in st.session_state:
    st.session_state.ext = None

hits = st.session_state.hits
selected_hit_ids = st.session_state.selected_hit_ids
id_to_hit = st.session_state.id_to_hit

# -----------------------
# File upload
# -----------------------
uploaded_file = st.file_uploader("Upload a file", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()
    _, ext = os.path.splitext(uploaded_file.name)
    st.session_state.ext = ext.lower()

# -----------------------
# Redaction parameters
# -----------------------
st.subheader("Select Redaction Parameters")

params: Dict[str, bool] = {}
cols = st.columns(2)
for i, (key, label) in enumerate(CATEGORY_LABELS.items()):
    with cols[i % 2]:
        params[key] = st.checkbox(label, value=False)

# Select All button
if st.button("Select All Parameters"):
    for key in CATEGORY_LABELS.keys():
        params[key] = True

custom_phrase = st.text_input(
    "Add a custom phrase to redact",
    placeholder="Type phrase and press Enter"
)
if custom_phrase:
    params["custom"] = True
else:
    params["custom"] = False

# -----------------------
# Scan
# -----------------------
if st.button("Scan for Redacted Phrases") and uploaded_file:
    # clear old hits
    hits.clear()
    id_to_hit.clear()
    selected_hit_ids.clear()

    new_hits = extract_text_and_positions(
        st.session_state.file_bytes,
        st.session_state.ext,
        params,
        custom_phrase if custom_phrase else None,
    ) or []

    hits.extend(new_hits)

    for idx, h in enumerate(hits):
        hid = h.page * 1_000_000 + idx
        id_to_hit[hid] = h
        selected_hit_ids.add(hid)

    # always reset hit_keys so scroll bar has entries
    st.session_state.hit_keys = list(id_to_hit.keys())

    # scroll UI down to results
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

        with st.container():
            st.markdown(
                """
                <style>
                    div[data-testid="stCheckbox"] label {
                        display: flex;
                        align-items: center;
                        gap: 0.4rem;
                        padding: 0.25rem 0.5rem;
                        border-radius: 8px;
                        margin-bottom: 4px;
                    }
                </style>
                """,
                unsafe_allow_html=True,
            )

            for hid in st.session_state.hit_keys:
                h = id_to_hit[hid]
                color = CATEGORY_COLORS.get(h.category, "#ccc")
                pill = f"<span style='background:{color};color:#fff;padding:2px 6px;border-radius:6px;font-size:0.8em'>{h.category}</span>"
                phrase_label = f"{h.text} {pill} <span style='font-size:0.8em;color:#666'>(p{h.page+1})</span>"

                checked = hid in selected_hit_ids
                if st.checkbox(phrase_label, key=f"hit_{hid}", value=checked):
                    selected_hit_ids.add(hid)
                else:
                    selected_hit_ids.discard(hid)

        # Download button
        if st.session_state.file_bytes:
            selected_hits = [id_to_hit[i] for i in selected_hit_ids]
            final_bytes = redact_pdf_with_hits(
                st.session_state.file_bytes,
                selected_hits,
                preview_mode=False,
            )
            st.download_button(
                "Download Redacted File",
                data=final_bytes,
                file_name="redacted.pdf",
            )

    with right_col:
        st.markdown("### Preview")
        if st.session_state.file_bytes:
            selected_hits = [id_to_hit[i] for i in selected_hit_ids]
            out_bytes = redact_pdf_with_hits(
                st.session_state.file_bytes,
                selected_hits,
                preview_mode=True,
            )

            b64_pdf = base64.b64encode(out_bytes).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="520px"></iframe>',
                unsafe_allow_html=True,
            )
