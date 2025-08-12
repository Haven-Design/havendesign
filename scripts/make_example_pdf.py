# scripts/make_example_pdf.py
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pathlib import Path

output = Path("redaction_example.pdf")
lines = [
    "Redaction Example Document",
    "--------------------------",
    "Name: John Doe",
    "Another Name: Jane A. Smith",
    "Email: test.email+alias@example.com",
    "Secondary Email: user123@sub.domain.org",
    "Phone: (555) 123-4567",
    "Alternate Phone: +1 555-987-6543",
    "Date: 12/31/2023",
    "Date verbose: January 5, 2024",
    "Address: 123 Main Street, Springfield",
    "Zip Code: 90210",
    "SSN: 123-45-6789",
    "Credit Card: 4111 1111 1111 1111",
    "Alternate CC: 5500-0000-0000-0004",
    "Passport: C12345678",
    "Driver's License: D1234567",
    "IP Address: 192.168.0.1",
    "VIN: 1HGCM82633A004352",
    "Bank Account: 123456789012",
    "Custom phrase: CONFIDENTIAL_PROJECT_X",
    "End of examples."
]

c = canvas.Canvas(str(output), pagesize=letter)
w, h = letter
y = h - 50
c.setFont("Helvetica", 12)
for line in lines:
    c.drawString(50, y, line)
    y -= 18
    if y < 50:
        c.showPage()
        c.setFont("Helvetica", 12)
        y = h - 50
c.save()
print(f"Saved {output.resolve()}")
