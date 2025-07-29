import fitz  # PyMuPDF
import os
import tempfile


def redact_pdf(input_path, selected_options):
    doc = fitz.open(input_path)

    # Define your redaction logic here based on selected_options
    # For example, redact SSNs
    if "SSN" in selected_options:
        for page in doc:
            text_instances = page.search_for(r"\d{3}-\d{2}-\d{4}")
            for inst in text_instances:
                page.add_redact_annot(inst, fill=(0, 0, 0))
    
    # Add more conditions for other options if needed
    # if "PHONE" in selected_options:
    #     ...

    # Apply redactions
    doc.apply_redactions()

    # Use mkstemp to safely create an output path
    fd, output_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)  # Important: Close the file descriptor so PyMuPDF can write to it

    doc.save(output_path)
    doc.close()

    return output_path
