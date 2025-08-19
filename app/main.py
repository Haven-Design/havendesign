import os
import io
import base64
import tempfile
from typing import List, Set, Dict
import streamlit as st
import streamlit.components.v1 as components

from utilities.extract_text import (
    Hit,
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    extract_hits_for_file,
)
from utilities.redact_pdf import (
    build_pdf_preview,
    save_pdf_blackfill,
    save_docx_redacted,
    save_txt_redacted,
    save_xlsx_redacted,
)

st.set_page_config(layout="wide")
st.title("PDF / DOCX / TXT / XLSX Redactor")

# -----------------------
# session state
# -----------------------
if "hits" not in st.session_state:
    st.session_state["hits"] = []
if "selected_hit_ids" not in st.session_state:
    st.session_state["selected_hit_ids"] = set()
if "file_bytes" not in st.session_state:
    st.session_state["file_bytes"] = None
if "file_name" not in st.session_state:
    st.session_state["file_name"] = ""
if "file_ext" not in st.session_state:
    st.session_state["file_ext"] = ""
if "params_checked" not in st.session_state:
    st.session_state["params_checked"] = {}  # key->bool
if "last_preview" not in st.session_state:
    st.session_state["last_preview"] = b""
if "scan_ran" not in st.session_state:
    st.session_state["scan_ran"] = False

hits: List[Hit] = st.session_state["hits"]
selected_hit_ids: Set[int] = st.session_state["selected_hit_ids"]

temp_dir = tempfile.mkdtemp()

# -----------------------
# file upload
# -----------------------
uploaded = st.file_uploader(
    "Upload a file", type=["pdf", "docx", "txt", "xlsx"], accept_multiple_files=False
)

# -----------------------
# parameter checkboxes
# -----------------------
PARAMS = [
    ("email", "Email Addresses"),
    ("phone", "Phone Numbers"),
    ("credit_card", "Credit Card Numbers"),
    ("ssn", "Social Security Numbers"),
    ("drivers_license", "Driver's Licenses"),
    ("date", "Dates"),
    ("address", "Addresses"),
    ("name", "Names"),
    ("ip_address", "IP Addresses"),
    ("bank_account", "Bank Account Numbers"),
    ("vin", "VIN Numbers"),
]

st.subheader("Select Redaction Parameters")

c1, c2 = st.columns(2)
# Select All for parameters
param_keys = [p[0] for p in PARAMS]
if "all_params_flag" not in st.session_state:
    st.session_state["all_params_flag"] = False

def set_all(v: bool):
    for k, _label in PARAMS:
        st.session_state["params_checked"][k] = v

with c1:
    if st.button("Select All Parameters"):
        set_all(True)
with c2:
    if st.button("Deselect All Parameters"):
        set_all(False)

for i, (key, label) in enumerate(PARAMS):
    col = c1 if i % 2 == 0 else c2
    with col:
        default_val = st.session_state["params_checked"].get(key, False)
        st.session_state["params_checked"][key] = st.checkbox(
            label, value=default_val, key=f"param_{key}"
        )

custom_phrase = st.text_input(
    "Add a custom phrase (press Enter to add)", placeholder="e.g., Project Falcon"
)
selected_params = [k for k, v in st.session_state["params_checked"].items() if v]
if custom_phrase.strip():
    selected_params.append(custom_phrase.strip())

# -----------------------
# scan
# -----------------------
def do_scan():
    st.session_state["scan_ran"] = False
    if not uploaded:
        st.warning("Please upload a file first.")
        return
    if not selected_params:
        st.warning("Please choose at least one parameter or add a custom phrase.")
        return

    data = uploaded.read()
    st.session_state["file_bytes"] = data
    st.session_state["file_name"] = uploaded.name
    st.session_state["file_ext"] = os.path.splitext(uploaded.name)[1].lower()

    st.session_state["hits"] = extract_hits_for_file(
        st.session_state["file_bytes"],
        st.session_state["file_ext"],
        selected_params,
    )
    st.session_state["selected_hit_ids"] = set(range(len(st.session_state["hits"])))
    st.session_state["scan_ran"] = True

    components.html(
        """
        <script>
            setTimeout(function(){
                var el = document.getElementById("results-section");
                if (el) el.scrollIntoView({behavior:"smooth"});
            }, 300);
        </script>
        """,
        height=0,
    )

if st.button("Scan for Redacted Phrases"):
    do_scan()

# -----------------------
# results + preview
# -----------------------
if hits:
    left, right = st.columns([1, 1])

    with left:
        st.markdown("<div id='results-section'></div>", unsafe_allow_html=True)
        st.subheader("Redacted Phrases")

        # grouped by category with colors, in a scroll box
        st.markdown(
            """
            <style>
            .scroll-box {
                max-height: 420px;
                overflow-y: auto;
                padding: 8px 10px;
                border: 1px solid #ccc;
                border-radius: 8px;
                background: #fafafa;
            }
            .cat-header {
                font-weight: 600;
                margin: 8px 0 4px 0;
            }
            .pill {
                display: inline-block;
                padding: 4px 6px;
                border-radius: 6px;
                margin: 2px 0;
                font-size: 0.9rem;
                background: rgba(0,0,0,0.04);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # select/deselect all found phrases (default = all selected after a scan)
        all_checked_now = st.checkbox(
            "Select / Deselect All Found Phrases",
            value=len(selected_hit_ids) == len(hits),
            key="select_all_found",
        )
        if all_checked_now:
            selected_hit_ids.update(range(len(hits)))
        else:
            selected_hit_ids.clear()

        # render grouped
        st.markdown("<div class='scroll-box'>", unsafe_allow_html=True)
        grouped: Dict[str, List[int]] = {}
        for idx, h in enumerate(hits):
            grouped.setdefault(h.category, []).append(idx)

        for cat, idxs in grouped.items():
            color = CATEGORY_COLORS.get(cat, "#999999")
            label = CATEGORY_LABELS.get(cat, cat.title())
            st.markdown(
                f"<div class='cat-header' style='color:{color}'>{label}</div>",
                unsafe_allow_html=True,
            )
            for i in idxs:
                h = hits[i]
                checked = i in selected_hit_ids
                # just the phrase as label
                if st.checkbox(f"{h.text} (p{h.page+1})" if h.page >= 0 else h.text,
                               value=checked, key=f"hit_{i}"):
                    selected_hit_ids.add(i)
                else:
                    selected_hit_ids.discard(i)
        st.markdown("</div>", unsafe_allow_html=True)

        # save / download
        if st.session_state["file_bytes"]:
            ext = st.session_state["file_ext"]
            fname = os.path.splitext(st.session_state["file_name"])[0]
            chosen_hits = [hits[i] for i in sorted(selected_hit_ids)]

            if ext == ".pdf":
                if st.button("Download PDF"):
                    out_bytes = save_pdf_blackfill(st.session_state["file_bytes"], chosen_hits)
                    st.download_button(
                        "Click to Download",
                        data=out_bytes,
                        file_name=f"{fname}_redacted.pdf",
                        mime="application/pdf",
                    )
            elif ext == ".docx":
                if st.button("Download DOCX"):
                    out_bytes = save_docx_redacted(st.session_state["file_bytes"], chosen_hits)
                    st.download_button(
                        "Click to Download",
                        data=out_bytes,
                        file_name=f"{fname}_redacted.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
            elif ext == ".txt":
                if st.button("Download TXT"):
                    out_bytes = save_txt_redacted(st.session_state["file_bytes"], chosen_hits)
                    st.download_button(
                        "Click to Download",
                        data=out_bytes,
                        file_name=f"{fname}_redacted.txt",
                        mime="text/plain",
                    )
            elif ext == ".xlsx":
                if st.button("Download XLSX"):
                    out_bytes = save_xlsx_redacted(st.session_state["file_bytes"], chosen_hits)
                    st.download_button(
                        "Click to Download",
                        data=out_bytes,
                        file_name=f"{fname}_redacted.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

    with right:
        st.subheader("Preview")
        preview_bytes = b""
        ext = st.session_state["file_ext"]

        chosen_hits = [hits[i] for i in sorted(selected_hit_ids)]
        if ext == ".pdf":
            preview_bytes = build_pdf_preview(st.session_state["file_bytes"], chosen_hits)
            if preview_bytes:
                b64 = base64.b64encode(preview_bytes).decode("utf-8")
                components.html(
                    f"""
                    <object data="data:application/pdf;base64,{b64}" type="application/pdf" width="100%" height="600px">
                        <embed src="data:application/pdf;base64,{b64}" width="100%" height="600px"/>
                    </object>
                    """,
                    height=620,
                )
        elif ext in (".docx", ".txt", ".xlsx"):
            # simple HTML preview with colored highlights
            # We re-extract a highlighted HTML for preview
            from utilities.extract_text import build_html_preview
            html = build_html_preview(st.session_state["file_bytes"], ext, chosen_hits)
            components.html(
                f'<div style="height:600px; overflow:auto; border:1px solid #ddd; border-radius:8px; padding:12px;">{html}</div>',
                height=620,
            )
