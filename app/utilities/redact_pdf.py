import fitz  # PyMuPDF

# Demo keyword sets – expand these later with real logic or regex
KEYWORDS = {
    "Name": ["John", "Jane", "Doe"],
    "Email": ["example@", ".com", "email"],
    "Phone": ["123", "555", "-"],
    "Address": ["Street", "St.", "Ave", "Road"],
    "Credit Card": ["4111", "5500", "Visa", "Mastercard"],
    "SSN": ["123-", "456-", "789-"],
    "Date": ["2023", "2024", "Jan", "Feb", "Aug"]
}

def redact_pdf(input_path, selected_fields, output_path, custom_text=None):
    doc = fitz.open(input_path)

    for page in doc:
        text_instances = []

        for field in selected_fields:
            for keyword in KEYWORDS.get(field, []):
                matches = page.search_for(keyword)
                text_instances.extend(matches)

        if custom_text:
            matches = page.search_for(custom_text, hit_max=50)
            text_instances.extend(matches)

        for inst in text_instances:
            page.add_redact_annot(inst, fill=(0, 0, 0))

        page.apply_redactions()

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
