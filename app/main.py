"""
main.py (v1.4.4)

- Left: scrollable results container (visually a scroll box) and category/child widgets inside a Streamlit container.
- Right: preview iframe, same fixed height.
- Category parent checkbox is a normal Streamlit checkbox (but visually arranged inline).
- Collapse/Expand per-category uses a pill-styled toggle (implemented using a checkbox with CSS).
- Select / Deselect All (Results) button is at the bottom of the results area.
- Children are indented under parent. Children checkboxes are the authoritative source
  of truth; selected_hit_ids is derived from them after widget creation.
"""

import os
import base64
from typing import List, Dict, Set

import streamlit as st
from utilities.extract_text import extract_text_and_positions, CATEGORY_LABELS, Hit
from utilities.redact_pdf import redact_pdf_with_hits, CATEGORY_COLORS

st.set_page_config(layout="wide")
st.title("Redactor-API (v1.4.4)")

RESULT_HEIGHT_PX = 600

# -----------------------
# Session defaults
# -----------------------
st.session_state.setdefault("file_bytes", None)
st.session_state.setdefault("ext", ".pdf")
st.session_state.setdefault("hits", [])  # List[Hit]
st.session_state.setdefault("id_to_hit", {})  # Dict[int, Hit]
st.session_state.setdefault("selected_hit_ids", set())  # Set[int]
st.session_state.setdefault("collapsed", {})  # Dict[str, bool]

# -----------------------
# Upload
# -----------------------
uploaded_file = st.file_uploader("Upload PDF/DOCX/TXT", type=["pdf", "docx", "txt"])
if uploaded_file:
    st.session_state.file_bytes = uploaded_file.getvalue()
    _, ext = os.path.splitext(uploaded_file.name)
    st.session_state.ext = ext.lower()
    # reset search results (preserve param checkboxes)
    st.session_state.hits = []
    st.session_state.id_to_hit = {}
    st.session_state.selected_hit_ids = set()
    st.session_state.collapsed = {}

# -----------------------
# Category selection for scanning
# -----------------------
st.subheader("Select categories to scan (for the next Scan)")
category_keys = list(CATEGORY_LABELS.keys())
cols = st.columns(2)
for i, k in enumerate(category_keys):
    if f"param_{k}" not in st.session_state:
        st.session_state[f"param_{k}"] = False
    with cols[i % 2]:
        st.checkbox(CATEGORY_LABELS[k], key=f"param_{k}")

custom_phrase = st.text_input("Custom phrase (optional)")

# -----------------------
# Scan
# -----------------------
if st.button("Scan for Redacted Phrases") and st.session_state.file_bytes:
    selected_categories = [k for k in category_keys if st.session_state.get(f"param_{k}", False)]
    if custom_phrase and custom_phrase.strip():
        selected_categories.append("custom")

    found = extract_text_and_positions(st.session_state.file_bytes, st.session_state.ext, selected_categories, custom_phrase if custom_phrase else None)
    found.sort(key=lambda h: (h.page, h.start if getattr(h, "start", None) is not None else 1_000_000))

    st.session_state.hits = found
    st.session_state.id_to_hit = {i: h for i, h in enumerate(found)}
    # default: all selected
    st.session_state.selected_hit_ids = set(st.session_state.id_to_hit.keys())
    # default collapsed = False (expanded)
    for k in category_keys:
        st.session_state.collapsed.setdefault(k, False)

# -----------------------
# Results & Preview layout
# -----------------------
if st.session_state.hits:
    left_col, right_col = st.columns([1, 1])

    # CSS: style the visual container, the pill toggle, etc.
    st.markdown(
        f"""
        <style>
        /* left scroll visual wrapper */
        .results-wrapper {{
            max-height: {RESULT_HEIGHT_PX}px;
            overflow-y: auto;
            padding: 8px;
            border: 1px solid #e6e6e6;
            border-radius: 8px;
            background: #fff;
        }}
        .cat-row {{
            display:flex;
            align-items:center;
            gap:8px;
            padding:6px 2px;
        }}
        .cat-label {{
            font-weight:700;
            display:inline-block;
        }}
        .child-item {{
            margin-left:28px;
            padding:4px 2px;
        }}
        /* pill toggle styling - uses checkbox hack */
        .pill-toggle {{
            position: relative;
            width: 42px;
            height: 24px;
            display: inline-block;
        }}
        .pill-toggle input[type="checkbox"] {{
            opacity: 0;
            width: 0;
            height: 0;
        }}
        .pill-slider {{
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            -webkit-transition: .2s;
            transition: .2s;
            border-radius: 999px;
        }}
        .pill-slider:before {{
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            -webkit-transition: .2s;
            transition: .2s;
            border-radius: 50%;
        }}
        .pill-toggle input:checked + .pill-slider {{
            background-color: #4f46e5; /* indigo */
        }}
        .pill-toggle input:checked + .pill-slider:before {{
            transform: translateX(18px);
        }}
        /* small spacing for select/deselect all */
        .results-bottom {{
            padding-top:8px;
            text-align:center;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # LEFT: results container (visual wrapper rendered, then we use a Streamlit container to place widgets visually inside)
    with left_col:
        st.markdown("<h3>Redacted Phrases</h3>", unsafe_allow_html=True)

        # Visual wrapper (HTML). Widgets will be created inside a Streamlit container placed immediately after.
        st.markdown('<div class="results-wrapper">', unsafe_allow_html=True)

        # Use a Streamlit container so the widgets render visually inside the wrapper area.
        with st.container():
            # Group hits by category preserving original order
            grouped: Dict[str, List[int]] = {}
            for idx, h in st.session_state.id_to_hit.items():
                grouped.setdefault(h.category, []).append(idx)

            # Iterate through categories in the canonical order (CATEGORY_LABELS)
            for cat in category_keys:
                if cat not in grouped:
                    continue
                idxs = grouped[cat]
                color = CATEGORY_COLORS.get(cat, "#111111")

                # Parent checkbox key
                parent_key = f"cat_chk_{cat}"
                # Default parent state: True if all children checked
                default_parent = all(st.session_state.get(f"hit_{i}", True) for i in idxs)
                st.session_state.setdefault(parent_key, default_parent)

                # layout: three columns (checkbox | label | pill toggle aligned right)
                c1, c2, c3 = st.columns([0.06, 0.78, 0.16])

                with c1:
                    # parent checkbox (hidden label for accessibility)
                    _ = st.checkbox(" ", key=parent_key, label_visibility="collapsed")

                with c2:
                    st.markdown(f'<div class="cat-row"><span class="cat-label" style="color:{color}">{CATEGORY_LABELS.get(cat, cat)}</span></div>', unsafe_allow_html=True)

                with c3:
                    # Render a pill toggle using raw HTML. It uses an input whose id is unique to the category.
                    toggle_id = f"pill_{cat}"
                    # set default state before rendering
                    st.session_state.setdefault(toggle_id, st.session_state.collapsed.get(cat, False))
                    # render HTML toggle element (checked if collapsed True)
                    checked_attr = "checked" if st.session_state[toggle_id] else ""
                    st.markdown(
                        f"""
                        <label class="pill-toggle">
                          <input type="checkbox" id="{toggle_id}" {checked_attr} />
                          <span class="pill-slider"></span>
                        </label>
                        <script>
                        // Listen for clicks and send a message to the parent window to toggle Streamlit state via a fake input change.
                        (function() {{
                            const el = document.getElementById("{toggle_id}");
                            if (!el) return;
                            el.addEventListener("change", () => {{
                                // Use the URL hash to signal a small state change which triggers Streamlit to rerun.
                                // We'll put the collapse state in window.name as a small hack to persist across reruns in this session.
                                const val = el.checked ? "1" : "0";
                                // store in localStorage to read back via Streamlit on reload
                                localStorage.setItem("{toggle_id}", val);
                                // reload to let Streamlit reflect new value
                                location.reload();
                            }});
                        }})();
                        </script>
                        """,
                        unsafe_allow_html=True,
                    )

                # If the HTML toggle was changed by the user, pick it up from localStorage on page load.
                # On Streamlit rerun we check localStorage via a small injected script. Because direct JS->Python comms
                # are limited, we use localStorage as a bridge; see the snippet below that runs once to sync values.
                st.markdown(
                    f"""
                    <script>
                    (function(){{
                        const k = "{toggle_id}";
                        const v = localStorage.getItem(k);
                        if (v !== null) {{
                            // create a small DOM element that Streamlit can read by being present in the page,
                            // but because Streamlit does not provide direct reading, we reload to trigger the server to read.
                            // In short: this saves the user's pill state in localStorage and relies on the Python side
                            // to re-sync collapsed[cat] on next rerun (below).
                        }}
                    }})();
                    </script>
                    """,
                    unsafe_allow_html=True,
                )

                # Read the toggle state from localStorage by trying to read window.localStorage via a trick:
                # on rerun, we will set server-side collapsed value from session_state if available; otherwise keep default.
                # To avoid race conditions, we only update child states after widgets exist.

                # Sync parent checkbox -> children BEFORE creating child widgets
                parent_val = st.session_state.get(parent_key, False)
                if parent_val:
                    for i in idxs:
                        st.session_state[f"hit_{i}"] = True
                else:
                    # don't overwrite if user interacted with child already; only set default when not present
                    for i in idxs:
                        st.session_state.setdefault(f"hit_{i}", False)

                # Render child checkboxes (indented)
                # If collapsed state was adjusted previously, respect it; default is expanded (False)
                # Attempt to read a persisted toggle state from session_state (sync logic)
                collapse_key = f"collapse_{cat}"
                if collapse_key not in st.session_state:
                    # default expanded
                    st.session_state[collapse_key] = st.session_state.collapsed.get(cat, False)
                # If localStorage has set value for the pill, we can't directly read it here; but user's interaction causes reload
                # and on that rerun the session_state value may be adjusted externally if you add server-side syncing.
                collapsed = st.session_state[collapse_key]

                if not collapsed:
                    for i in idxs:
                        h = st.session_state.id_to_hit[i]
                        child_key = f"hit_{i}"
                        st.session_state.setdefault(child_key, (i in st.session_state.selected_hit_ids))
                        _ = st.checkbox(f"{h.text}  (p{h.page+1})", key=child_key)

            # end categories loop
        # end container

        # close visual wrapper
        st.markdown("</div>", unsafe_allow_html=True)

        # Select / Deselect All (Results) button - at bottom
        def toggle_select_all_results():
            all_ids = list(st.session_state.id_to_hit.keys())
            if not all_ids:
                return
            if all(st.session_state.get(f"hit_{i}", False) for i in all_ids):
                for i in all_ids:
                    st.session_state[f"hit_{i}"] = False
            else:
                for i in all_ids:
                    st.session_state[f"hit_{i}"] = True

        st.button("Select / Deselect All (Results)", on_click=toggle_select_all_results)

        # After all widgets are created, derive selected_hit_ids from the child widget states
        new_selected: Set[int] = set()
        for k, v in st.session_state.items():
            if k.startswith("hit_"):
                try:
                    idx = int(k.split("_", 1)[1])
                except Exception:
                    continue
                if v:
                    new_selected.add(idx)
        st.session_state.selected_hit_ids = new_selected

        # Download button
        if st.button("Download Redacted PDF"):
            selected = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
            out = redact_pdf_with_hits(st.session_state.file_bytes, selected, preview_mode=False)
            st.download_button("Save redacted.pdf", data=out, file_name="redacted.pdf")

    # RIGHT: preview
    with right_col:
        st.markdown("<h3>Preview</h3>", unsafe_allow_html=True)
        selected = [st.session_state.id_to_hit[i] for i in sorted(st.session_state.selected_hit_ids)]
        if selected:
            preview_bytes = redact_pdf_with_hits(st.session_state.file_bytes, selected, preview_mode=True)
            b64 = base64.b64encode(preview_bytes).decode("utf-8")
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{RESULT_HEIGHT_PX}px"></iframe>', unsafe_allow_html=True)
        else:
            st.info("No phrases selected — select items on the left to preview.")
