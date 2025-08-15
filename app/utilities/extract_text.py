import re

# Define colors for each category (ADA-compliant high-contrast)
CATEGORY_COLORS = {
    "Emails": "#FF5733",             # Bright orange-red
    "Phone Numbers": "#2ECC71",      # Green
    "Credit Cards": "#3498DB",       # Blue
    "SSNs": "#9B59B6",               # Purple
    "Driver's Licenses": "#E67E22",  # Orange
    "VIN Numbers": "#1ABC9C",        # Teal
    "Bank Account Numbers": "#E74C3C", # Red
    "IP Addresses": "#F1C40F",       # Yellow
    "Dates": "#34495E"               # Dark blue-gray
}

# Exclusive regex patterns (order matters — first match wins)
CATEGORY_PATTERNS = [
    ("Emails", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("Credit Cards", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
    ("SSNs", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("Phone Numbers", re.compile(r"\b(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("Driver's Licenses", re.compile(r"\b[A-Z]{1}\d{7}\b")),
    ("VIN Numbers", re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")),
    ("Bank Account Numbers", re.compile(r"\b\d{9,12}\b")),
    ("IP Addresses", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")),
    ("Dates", re.compile(r"\b(?:\d{1,2}[-/]){2}\d{2,4}\b"))
]

def extract_sensitive_data(text):
    """
    Extract sensitive data based on predefined patterns.
    Returns a dictionary {category: [(match, start, end), ...]}
    """
    found_data = {cat: [] for cat, _ in CATEGORY_PATTERNS}

    used_spans = set()
    for category, pattern in CATEGORY_PATTERNS:
        for match in pattern.finditer(text):
            span = match.span()
            if any(start < span[1] and end > span[0] for (start, end) in used_spans):
                continue
            found_data[category].append((match.group(), span[0], span[1]))
            used_spans.add(span)

    return found_data
