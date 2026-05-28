"""Ticket key extraction helpers."""

import re

TICKET_KEY_PATTERN = re.compile(r"\bTK-\d+\b")


def extract_ticket_key_from_title(title: str) -> str | None:
    """Extract the first supported ticket key from an MR title."""
    match = TICKET_KEY_PATTERN.search(title)
    if match is None:
        return None
    return match.group(0)
