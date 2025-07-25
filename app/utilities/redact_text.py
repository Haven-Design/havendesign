import re

def redact_text(text: str) -> str:
    # Redact SSNs
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED SSN]', text)

    # Redact phone numbers
    text = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '[REDACTED PHONE]', text)

    # Redact emails
    text = re.sub(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', '[REDACTED EMAIL]', text)

    # Redact dates (MM/DD/YYYY or similar)
    text = re.sub(r'\b\d{1,2}/\d{1,2}/\d{4}\b', '[REDACTED DATE]', text)

    # Redact addresses (very simple version)
    text = re.sub(r'\d{1,5}\s[\w\s]+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd)\b', '[REDACTED ADDRESS]', text, flags=re.IGNORECASE)

    # Redact names (example: John Smith)
    text = re.sub(r'\bJohn Smith\b', '[REDACTED NAME]', text)
    text = re.sub(r'\bDr\. Emily Thompson\b', '[REDACTED NAME]', text)

    return text
