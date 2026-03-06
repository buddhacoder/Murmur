import re

def redact_phi(text: str) -> str:
    """
    Redacts Protected Health Information (PHI) from the input text using robust fast Regex.
    Replaces phone numbers, SSNs, and dates with [P.H.I].
    """
    redacted = text

    # Phone numbers (e.g., 555-123-4567, (555) 123-4567, 1-800-123-4567)
    phone_pattern = r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'
    redacted = re.sub(phone_pattern, '[P.H.I]', redacted)

    # Social Security Numbers (e.g., 123-45-6789) and partials (e.g., 123-456)
    ssn_pattern = r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b|\b\d{3}[-\s]?\d{3,4}\b'
    redacted = re.sub(ssn_pattern, '[P.H.I]', redacted)

    # Dates (e.g., MM/DD/YYYY, YYYY-MM-DD, MM-DD-YY)
    date_pattern = r'\b(?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12][0-9]|3[01])[-/](?:\d{4}|\d{2})\b|\b(?:\d{4})[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12][0-9]|3[01])\b'
    redacted = re.sub(date_pattern, '[P.H.I]', redacted)
    
    # Common HIPAA keywords and IDs (e.g., MRN 123456)
    mrn_pattern = r'(?i)\b(?:mrn|id|account|acct)\s*(?:is\s*)?#?\s*:?\s*[a-z0-9-]{4,15}\b'
    redacted = re.sub(mrn_pattern, '[P.H.I]', redacted)

    return redacted

if __name__ == "__main__":
    sample = "Patient John Doe called today. His MRN is 9482934. His number is 555-019-2034 and his SSN is 739-486. Seen on 10/12/2023."
    print("Original:", sample)
    print("Redacted:", redact_phi(sample))
