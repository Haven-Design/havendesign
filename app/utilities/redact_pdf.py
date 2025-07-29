import fitz  # PyMuPDF
import tempfile
import os

def redact_pdf(input_path, options):
    doc = fitz.open(input_path)

    redaction_terms = {
        "names": ["John Doe", "Jane Smith"],
        "dates": ["01/01/2023", "February 20, 2022"],
        "phone": ["123-456-7890", "(987) 654-3210"],
        "email": ["example@email.com", "test.user@example.com"],
    }

    for page in doc:
        found = False  # Track if any redactions were added
        for option in options:
            for term in redaction_terms.get(option, []):
                text_instances = page.search_for(term)
                for inst in text_instances:
                    page.add_redact_annot(inst, fill=(0, 0, 0))
                    found = True
        if found:
            page.apply_redactions()  # Apply only if needed

    # Safely create output file
    fd, output_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(output_path, deflate=True, clean=True)
    doc.close()
    return output_path
