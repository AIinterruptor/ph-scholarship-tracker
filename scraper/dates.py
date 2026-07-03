import re

from dateutil import parser as dateutil_parser

_DEADLINE_PATTERNS = [
    r"closes?\s+on\s+([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})",
    r"deadline\s*:?\s*([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})",
    r"on\s+or\s+before\s+([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})",
    r"until\s+([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})",
]


def extract_deadline(text: str, reference_date: str) -> tuple:
    if not text:
        return None, ""

    for pattern in _DEADLINE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            continue
        raw = match.group(1)
        try:
            parsed = dateutil_parser.parse(raw, fuzzy=False)
        except (ValueError, OverflowError):
            continue
        return parsed.date().isoformat(), raw

    return None, ""
