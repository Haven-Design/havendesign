import io
import os
import base64
import streamlit as st

from app.utilities.extract_text import (
    CATEGORY_DEFS,
    DEFAULT_CATEGORY_KEYS,
    detect_matches_in_pdf,
    build_summary_counts,
)
from app.utilities.redact_pdf import (
    make_preview_pdf,
    apply_redactions_pdf,
)

st.set_page_config(page_title="PDF Redactor", layout="wide")

# ---------- Session State ----------
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

if "selected_categories" not in st.session_state:
    # start with nothing selected until user toggles Select All
    st.session_state.selected_categories = set()

if "custom_regex" not in st.session_state:
    st.session_state.custom_regex = ""

if "detected_items" not in st.session_state:
    # list of dicts: {id, page, phrase, rects, category}
    st.session_state.detected_items = []

if "included_item_ids" not in st.session_state:
    st.session_state.included_item_ids = set()  # which items are included for redaction


# ---------- Helpers ----------
def b64_pdf(pdf_bytes: bytes) -> str:
    return base64.b64encode(pdf_bytes).decode("ascii")


def render_pdf_viewer(pdf_bytes: bytes, height: int = 620):
    if not pdf_bytes:
        return
    data = b64_pdf(pdf_bytes)
    html = f"""
    <iframe
        src="data:application/pdf;base64,{data}"
        style="width:100%; height:{height}px; border:1px solid #e5e7eb; border-radius:10px;"
    ></iframe>
    """
    st.markdown(html, unsafe_allow_html=True)


# ============ STEP 1: Upload & Choose Detection ============
st.markdown("## 1) Upload a PDF, choose what to redact, then scan")

colA, colB = st.columns([1, 1])

with colA:
    uploaded = st.file_uploader("Upload PDF", type=["pdf"], key="pdf_upload")
    if uploaded:
        st.session_state.pdf_bytes = uploaded.read()

    # Category toggles (no sidebar)
    st.markdown("#### Detection categories")
    # Single "Select All" toggle
    all_selected_now = st.checkbox(
        "Select All",
        value=(len(st.session_state.selected_categories) == len(CATEGORY_DEFS)),
        help="Toggle all detection categories on or off.",
        key="toggle_all_categories"
    )

    # If user changed the Select All checkbox, reflect it
    if all_selected_now and len(st.session_state.selected_categories) != len(CATEGORY_DEFS):
        st.session_state.selected_categories = set(CATEGORY_DEFS.keys())
    elif not all_selected_now and len(st.session_state.selected_categories) == len(CATEGORY_DEFS):
        st.session_state.selected_categories = set()

    # Show grid-ish of checkboxes (3 columns) in-page
    cat_cols = st.columns(3)
    for i, (key, meta) in enumerate(CATEGORY_DEFS.items()):
        col = cat_cols[i % 3]
        checked = key in st.session_state.selected_categories
        new_val = col.checkbox(
            meta["label"],
            value=checked,
            key=f"cat_{key}",
            help=meta["help"],
        )
        if new_val and key not in st.session_state.selected_categories:
            st.session_state.selected_categories.add(key)
        if (not new_val) and key in st.session_state.selected_categories:
            st.session_state.selected_categories.remove(key)

    # Custom patterns (below the category checkboxes)
    st.markdown("#### Custom patterns (optional)")
    st.caption("Enter one or more regular expressions (one per line). Press **Enter** to commit. "
               "These will be **added** to detection.")
    st.session_state.custom_regex = st.text_area(
        "Custom regex (one per line)",
        value=st.session_state.custom_regex or "",
        height=120,
        key="custom_regex_area",
        placeholder=r"(?:\bCONFIDENTIAL\b)|(?:\bINTERNAL USE ONLY\b)|(?:\bSECRET\b)"
    )

    can_scan = (
        st.session_state.pdf_bytes is not None
        and (len(st.session_state.selected_categories) > 0 or st.session_state.custom_regex.strip())
    )

    scan_clicked = st.button("Scan for redacted phrases", type="primary", disabled=not can_scan)
    if scan_clicked:
        items = detect_matches_in_pdf(
            st.session_state.pdf_bytes,
            selected_keys=list(st.session_state.selected_categories),
            custom_regex_text=st.session_state.custom_regex,
        )
        st.session_state.detected_items = items
        # Default: everything included (pre-checked behavior)
        st.session_state.included_item_ids = {it["id"] for it in items}

with colB:
    st.markdown("#### Preview (auto-updates)")
    if st.session_state.pdf_bytes and st.session_state.detected_items:
        preview = make_preview_pdf(
            st.session_state.pdf_bytes,
            [it for it in st.session_state.detected_items if it["id"] in st.session_state.included_item_ids],
        )
        render_pdf_viewer(preview, height=650)
    else:
        st.info("Upload a PDF, select categories (or add custom regex), and click **Scan for redacted phrases** to see the preview.")


# ============ STEP 2: Found Phrases (Left) | Preview (Right) ============
if st.session_state.pdf_bytes and st.session_state.detected_items:
    st.markdown("---")
    st.markdown("## 2) Review found phrases and download")

    left, right = st.columns([1, 1])

    with left:
        # Summary at top, small text
        counts = build_summary_counts(st.session_state.detected_items)
        st.caption("Summary of detected items (by category): " + " · ".join(
            f"{CATEGORY_DEFS[k]['label']}: {counts.get(k,0)}" for k in CATEGORY_DEFS.keys()
        ))

        st.markdown("#### Found phrases")
        # Scrollable area with checkboxes: pre-selected
        # Group items by category to show colored labels
        # Make it a fixed-height container via HTML/CSS
        st.markdown(
            """
            <div style="max-height: 380px; overflow-y: auto; padding-right: 6px; border: 1px solid #e5e7eb; border-radius: 8px;">
            """,
            unsafe_allow_html=True
        )

        # Render lists per category (color dot + label)
        for cat_key, meta in CATEGORY_DEFS.items():
            cat_items = [it for it in st.session_state.detected_items if it["category"] == cat_key]
            if not cat_items:
                continue

            color_hex = meta["color_hex"]
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:8px; margin:10px 0 4px 4px;">
                    <div style="width:12px; height:12px; border-radius:50%; background:{color_hex};"></div>
                    <div style="font-weight:600;">{meta["label"]} ({len(cat_items)})</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            for it in cat_items:
                checked = it["id"] in st.session_state.included_item_ids
                new_val = st.checkbox(
                    f'Page {it["page"] + 1}: “{it["phrase"]}”',
                    value=checked,
                    key=f"include_{it['id']}",
                )
                if new_val and it["id"] not in st.session_state.included_item_ids:
                    st.session_state.included_item_ids.add(it["id"])
                if (not new_val) and it["id"] in st.session_state.included_item_ids:
                    st.session_state.included_item_ids.remove(it["id"])

        # close the scroll container
        st.markdown("</div>", unsafe_allow_html=True)

        # One button: Download PDF
        st.markdown(" ")
        if st.session_state.included_item_ids:
            final_pdf = apply_redactions_pdf(
                st.session_state.pdf_bytes,
                [it for it in st.session_state.detected_items if it["id"] in st.session_state.included_item_ids],
            )
            st.download_button(
                "Download PDF",
                data=final_pdf,
                file_name="redacted.pdf",
                mime="application/pdf",
                type="primary",
            )
        else:
            st.warning("No items selected to redact. Check items above or redo Scan with different categories.")

    with right:
        st.markdown("#### Live preview (reflects selections)")
        if st.session_state.included_item_ids:
            preview = make_preview_pdf(
                st.session_state.pdf_bytes,
                [it for it in st.session_state.detected_items if it["id"] in st.session_state.included_item_ids],
            )
            render_pdf_viewer(preview, height=760)
        else:
            st.info("Select some items on the left to see a preview.")


# Footer / tiny help
st.markdown("---")
st.caption("Tip: Use **custom regex** for project-specific terms (case-insensitive by default).")
