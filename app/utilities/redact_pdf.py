import fitz  # PyMuPDF
import tempfile
import os


def redact_pdf(input_path, options):
    doc = fitz.open(input_path)

    # Redact keywords on every page
    for page in doc:
        for option in options:
            redactions = page.search_for(option)
            for rect in redactions:
                page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()

    # Save to a temporary file
    fd, output_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)  # Close the file descriptor to avoid 'Permission denied' on Windows

    try:
        doc.save(output_path, deflate=True, clean=True)
    except Exception as e:
        print(f"Error saving PDF: {e}")
        raise
    finally:
        doc.close()

    return output_path
