import io
import fitz
from utilities.extract_text import Hit, CATEGORY_COLORS

def redact_pdf_with_hits(input_path, hits, output_path=None, preview_mode=True):
    doc = fitz.open(input_path)
    for h in hits:
        if not h.rect:
            continue
        rect = fitz.Rect(h.rect)
        color = CATEGORY_COLORS.get(h.category, "#000000")
        rgb = tuple(int(color.lstrip("#")[i:i+2], 16)/255 for i in (0, 2, 4))
        page = doc[h.page]
        if preview_mode:
            page.draw_rect(rect, color=rgb, fill=(*rgb, 0.2), width=1)
        else:
            page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()

    out = io.BytesIO()
    doc.save(out)
    doc.close()

    if output_path and preview_mode:
        with open(output_path, "wb") as f:
            f.write(out.getvalue())

    return out.getvalue()

def save_masked_file(file_bytes, ext, hits):
    if ext == ".txt":
        text = file_bytes.decode("utf-8")
        for h in hits:
            text = text.replace(h.text, "█" * len(h.text))
        return text.encode("utf-8")
    elif ext == ".docx":
        from docx import Document
        import io as sysio
        doc = Document(io.BytesIO(file_bytes))
        for para in doc.paragraphs:
            for h in hits:
                if h.text in para.text:
                    para.text = para.text.replace(h.text, "█" * len(h.text))
        output = sysio.BytesIO()
        doc.save(output)
        return output.getvalue()
    return file_bytes
