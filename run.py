import streamlit as st
import fitz
from io import BytesIO
from app.utilities.extract_text import extract_text_from_pdf
from app.utilities.redact_pdf import find_redaction_matches, apply_redactions

st.set_page_config(page_title="PDF Redactor", layout="wide")

st.title("PDF Redactor")
st.markdown("""
Drag and drop a PDF file below, or click to browse.  
Select the types of information you'd like to redact.  
**Note:** The preview uses slightly transparent boxes.  
When you download, they will be fully opaque for permanent redaction.
""")

uploaded_file = st.file_uploader("Upload PDF", type="pdf")

def render_preview_with_highlight(preview_images, matches):
    """Render preview images with clickable/highlightable redaction boxes."""

    # We will create one div per page, and inside each div, an image plus absolute-positioned transparent overlays for each redaction box.

    html_parts = []
    for page_num, img_bytes in enumerate(preview_images):
        page_matches = matches.get(page_num, [])

        # Build overlay divs for each match rectangle with a unique id attribute
        overlays_html = ""
        for m in page_matches:
            r = m["rect"]
            # Position and size as percentages to scale on image size
            left = r.x0 / 612 * 100  # assuming 612pt width PDF (8.5 inch x 72pt)
            top = r.y0 / 792 * 100   # assuming 792pt height PDF (11 inch x 72pt)
            width = r.width / 612 * 100
            height = r.height / 792 * 100
            overlays_html += f"""
            <div class="redact-box" id="{m['id']}" 
                style="
                    position:absolute; 
                    left:{left:.2f}%; top:{top:.2f}%; 
                    width:{width:.2f}%; height:{height:.2f}%;
                    background-color: rgba(0,0,0,0.4);
                    border-radius: 3px;
                    transition: box-shadow 0.3s ease;
                "></div>
            """

        html = f"""
        <div class="page-container" style="position:relative; margin-bottom:30px; width:612px; height:792px; border: 1px solid #ccc;">
            <img src="data:image/png;base64,{img_bytes.getvalue().hex()}" style="width:100%; height:100%;"/>
            {overlays_html}
        </div>
        """
        html_parts.append(html)

    # Join pages together
    pages_html = "\n".join(html_parts)

    # The JS and CSS for hover effect linking list to boxes
    # We'll add event listeners on the list elements, to add/remove "highlight" class on the matching overlay div

    js = """
    <script>
    function setupHover() {
        document.querySelectorAll('.match-item').forEach(item => {
            item.addEventListener('mouseenter', (e) => {
                const redactId = item.dataset.redactid;
                const box = document.getElementById(redactId);
                if(box) box.classList.add('highlight');
            });
            item.addEventListener('mouseleave', (e) => {
                const redactId = item.dataset.redactid;
                const box = document.getElementById(redactId);
                if(box) box.classList.remove('highlight');
            });
        });
    }
    window.onload = setupHover;
    </script>
    """

    css = """
    <style>
    .redact-box.highlight {
        box-shadow: 0 0 8px 4px rgba(255, 0, 0, 0.7);
        background-color: rgba(255, 0, 0, 0.5) !important;
    }
    .page-container {
        position: relative;
    }
    </style>
    """

    # Return full html string
    return css + pages_html + js

if uploaded_file:
    pdf_bytes = uploaded_file.read()

    st.subheader("Select Information to Redact")
    col1, col2 = st.columns(2)
    with col1:
        redact_names = st.checkbox("Names")
        redact_dates = st.checkbox("Dates")
        redact_emails = st.checkbox("Emails")
    with col2:
        redact_phone = st.checkbox("Phone Numbers")
        redact_addresses = st.checkbox("Addresses")
        redact_zip = st.checkbox("ZIP Codes")
        redact_all = st.checkbox("Select All")

    if redact_all:
        redact_names = redact_dates = redact_emails = redact_phone = redact_addresses = redact_zip = True

    selected_options = {
        "names": redact_names,
        "dates": redact_dates,
        "emails": redact_emails,
        "phones": redact_phone,
        "addresses": redact_addresses,
        "zipcodes": redact_zip
    }

    if any(selected_options.values()):
        matches = find_redaction_matches(pdf_bytes, selected_options)

        if "removed" not in st.session_state:
            st.session_state.removed = set()

        def remove_match(match_id):
            st.session_state.removed.add(match_id)

        filtered_matches = {
            page: [m for m in rects if m["id"] not in st.session_state.removed]
            for page, rects in matches.items()
        }

        col_preview, col_list = st.columns([2, 1])

        with col_preview:
            st.subheader("Preview")
            preview_images, _ = apply_redactions(pdf_bytes, filtered_matches, opacity=0.4)
            # Render custom HTML preview with overlays & highlight
            preview_html = render_preview_with_highlight(preview_images, filtered_matches)
            st.components.v1.html(preview_html, height=850, scrolling=True)

        with col_list:
            st.subheader("Detected Matches")
            st.markdown("Click ❌ to exclude an item from redaction.")
            match_list = []
            for page_num, rects in matches.items():
                for m in rects:
                    if m["id"] not in st.session_state.removed:
                        match_list.append((page_num, m))
            if match_list:
                container = st.container()
                container.markdown("<div style='max-height:400px;overflow-y:auto;'>", unsafe_allow_html=True)
                for page_num, m in match_list:
                    # Add data-redactid for JS
                    col_a, col_b = st.columns([4, 1])
                    col_a.markdown(f'<div class="match-item" style="cursor:pointer;" data-redactid="{m["id"]}"><b>Page {page_num+1}:</b> {m["text"]}</div>', unsafe_allow_html=True)
                    col_b.button("❌", key=m["id"], on_click=remove_match, args=(m["id"],))
                container.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("No matches currently selected for redaction.")

        _, final_pdf = apply_redactions(pdf_bytes, filtered_matches, opacity=1.0)
        st.download_button(
            "Download Final Redacted PDF",
            final_pdf,
            file_name="redacted_output.pdf",
            mime="application/pdf"
        )
    else:
        st.info("Select at least one option to redact.")
