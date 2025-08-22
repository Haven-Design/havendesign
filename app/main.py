import os
import io
import base64
import tempfile
import html
from typing import List, Dict, Set, Tuple

import streamlit as st

from utilities.extract_text import (
    extract_text_and_positions,
    Hit,
    CATEGORY_LABELS,
    CATEGORY_COLORS,
)
from utilities.redact_pdf import redact_pdf_with_hits, save_masked_file

st.set_page_config(layout="wide")
st.title("Redactor-API — PDF / DOCX / TXT")

# -----------------------
# Session state
# -----------------------
def _reset_scan_state():
    st.session_state.hits = []
    st.session_state.id_to_hit = {}
    st.session_state.selected_hit_ids = set()
    st.session_state.hit_keys = []  # stable ordering for UI rows

if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None
if "file_name" not in st.session_state:
    st.session_state.file_name = None
if "ext" not in st.session_state:
    st.session_state.ext = None
if "input_pdf_path" not in st.session_state:
    st.session_state.input_pdf_path = None

if "params" not in st.session_state:
    st.session_state.params = {k: False for k in CATEGORY_LABELS.keys()}

if "hits" not in st.session_state:
    st.session_state.hits: List[Hit] = []
if "id_to_hit" not in st.session_state:
    st.session_state.id_to_hit: Dict[int, Hit] = {}
if "selected_hit_ids" not in st.session_state:
    st.session_state.selected_hit_ids: Set[int] = set()
if "hit_keys" not in st.session_state:
    st.session_state.hit_keys: List[int] = []

# -----------------------
# Upload
# -----------------------
uploaded_file = st.file_uploader("Upload a file", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.read()
    st.session_state.file_name = uploaded_file.name
    st.session_state.ext = os.path.splitext(uploaded_file.name)[1].lower()
    _reset_scan_state()

    # prepare a temporary pdf path if PDF
    st.session_state.input_pdf_path = None
    if st.session_state.ext == ".pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(st.session_state.file_bytes)
            st.session_state.input_pdf_path = tmp.name

# -----------------------
# Category selection
# -----------------------
if st.session_state.file_bytes:
    st.subheader("Select Categories to Redact")

    def select_all_categories():
        for k in st.session_state.params.keys():
            st.session_state.params[k] = True

    if st.button("Select All Categories"):
        select_all_categories()
        st.rerun()

    col1, col2 = st.columns(2)
    for i, (key, label) in enumerate(CATEGORY_LABELS.items()):
        target = col1 if i % 2 == 0 else col2
        st.session_state.params[key] = target.checkbox(
            label,
            value=st.session_state.params.get(key, False),
            key=f"param_{key}",
        )

    custom_phrase = st.text_input(
        "Add a custom phrase to redact (optional)",
        placeholder="Type phrase here and press Enter",
    )

    # -----------------------
    # Scan
    # -----------------------
    if st.button("Scan for Redacted Phrases"):
        hits = extract_text_and_positions(
            st.session_state.file_bytes,
            st.session_state.ext,
            st.session_state.params,
            custom_phrase,
        )

        # Deduplicate conservatively by (page, start, end, category, text)
        uniq: Dict[Tuple, Hit] = {}
        for h in hits:
            key = (h.page, getattr(h, "start", None), getattr(h, "end", None), h.category, h.text)
            uniq[key] = h

        st.session_state.hits = list(uniq.values())
        st.session_state.id_to_hit = {i: h for i, h in enumerate(st.session_state.hits)}
        st.session_state.hit_keys = list(st.session_state.id_to_hit.keys())

        # Initialize selection state ONCE per scan
        st.session_state.selected_hit_ids = set(st.session_state.hit_keys)
        for i in st.session_state.hit_keys:
            # create stable widget states before rendering
            st.session_state.setdefault(f"hit_{i}", True)

# -----------------------
# Results & Preview
# -----------------------
def _escape(s: str) -> str:
    return html.escape(s, quote=True)

if st.session_state.hits:
    left, right = st.columns([1, 1])

    with left:
        st.markdown("### Redacted Phrases")

        # Controls
        c1, c2, c3 = st.columns([0.33, 0.33, 0.34])
        with c1:
            if st.button("Select All Phrases"):
                for i in st.session_state.hit_keys:
                    st.session_state[f"hit_{i}"] = True
                st.session_state.selected_hit_ids = set(st.session_state.hit_keys)
                st.rerun()
        with c2:
            if st.button("Deselect All Phrases"):
                for i in st.session_state.hit_keys:
                    st.session_state[f"hit_{i}"] = False
                st.session_state.selected_hit_ids.clear()
                st.rerun()
        with c3:
            st.caption("Toggle items below. Phrase is bold, then category, then page.")

        # Styles
        st.markdown(
            """
            <style>
              .scrollbox {max-height: 420px; overflow-y: auto; border: 1px solid #e5e7eb;
                          padding: 8px 8px 2px 8px; border-radius: 10px; background: #fafafa;}
              .hit-row {display:flex; gap:10px; align-items:flex-start; margin-bottom:8px;}
              .hit-card {flex:1; border-left:6px solid var(--cat); background:#fff; border-radius:8px;
                         padding:8px 10px; box-shadow:0 1px 2px rgba(16,24,40,.06);}
              .hit-phrase {font-weight:600; line-height:1.3; margin-bottom:2px;}
              .meta {font-size:12px; opacity:0.8; display:flex; gap:10px; align-items:center;}
              .badge {display:inline-block; padding:2px 6px; border-radius:999px; border:1px solid var(--cat);
                      background: color-mix(in srgb, var(--cat) 18%, white); }
              .page {font-variant-numeric: tabular-nums;}
              .checkpad {padding-top:8px;}
            </style>
            """,
            unsafe_allow_html=True,
        )

        # Scrollable list
        st.markdown("<div class='scrollbox'>", unsafe_allow_html=True)

        new_selected = set()
        for i in st.session_state.hit_keys:
            h = st.session_state.id_to_hit[i]
            color = CATEGORY_COLORS.get(h.category, "#999999")
            phrase = _escape(h.text if len(h.text) <= 160 else h.text[:157] + "…")
            label = CATEGORY_LABELS.get(h.category, h.category)
            page = (h.page + 1) if h.page is not None else 1

            row = st.columns([0.10, 0.90])
            with row[0]:
                # IMPORTANT: don't pass value once state exists; rely on key
                checked = st.checkbox("", key=f"hit_{i}")
                if checked:
                    new_selected.add(i)
            with row[1]:
                st.markdown(
                    f"""
                    <div class="hit-row">
                      <div class="hit-card" style="--cat:{color}">
                        <div class="hit-phrase">{phrase}</div>
                        <div class="meta">
                          <span class="badge">{_escape(label)}</span>
                          <span class="page">p{page}</span>
                        </div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)

        # Persist selection derived ONLY from the checkboxes above
        st.session_state.selected_hit_ids = new_selected

        # Download
        selected_hits = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
        st.markdown("### Download")
        if st.session_state.ext == ".pdf":
            if st.session_state.input_pdf_path and selected_hits:
                out_bytes = redact_pdf_with_hits(
                    st.session_state.input_pdf_path, selected_hits, preview_mode=False
                )
                st.download_button(
                    "Download Redacted PDF",
                    data=out_bytes,
                    file_name="redacted.pdf",
                    mime="application/pdf",
                )
            else:
                st.info("Select at least one phrase to enable PDF download.")
        else:
            if selected_hits:
                out_bytes = save_masked_file(
                    st.session_state.file_bytes, st.session_state.ext, selected_hits
                )
                out_name = f"redacted{st.session_state.ext}"
                st.download_button(
                    "Download Redacted File",
                    data=out_bytes,
                    file_name=out_name,
                    mime="application/octet-stream",
                )
            else:
                st.info("Select at least one phrase to enable download.")

    with right:
        st.markdown("### Preview")
        selected_hits = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]

        if st.session_state.ext == ".pdf" and st.session_state.input_pdf_path:
            if selected_hits:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    preview_path = tmp.name
                redact_pdf_with_hits(
                    st.session_state.input_pdf_path,
                    selected_hits,
                    output_path=preview_path,
                    preview_mode=True,
                )
                with open(preview_path, "rb") as f:
                    b64_pdf = base64.b64encode(f.read()).decode("utf-8")
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="560"></iframe>',
                    unsafe_allow_html=True,
                )
            else:
                st.info("No phrases selected.")
        else:
            if st.session_state.file_bytes and selected_hits:
                masked = save_masked_file(
                    st.session_state.file_bytes, st.session_state.ext, selected_hits
                )
                try:
                    preview_text = masked.decode("utf-8")
                except Exception:
                    preview_text = "(Preview unavailable for this file type.)"
                st.text_area("Masked Preview", value=preview_text, height=560)
            else:
                st.info("No phrases selected.")
