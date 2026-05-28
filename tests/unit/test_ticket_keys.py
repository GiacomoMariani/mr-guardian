from mr_guardian.core.ticket_keys import extract_ticket_key_from_title


def test_extracts_ticket_key_from_mr_title() -> None:
    assert extract_ticket_key_from_title("TK-234 Add inventory validation") == "TK-234"


def test_extracts_first_ticket_key_from_mr_title() -> None:
    assert extract_ticket_key_from_title("TK-234 follow-up for TK-235") == "TK-234"


def test_does_not_extract_ticket_key_from_non_matching_text() -> None:
    assert extract_ticket_key_from_title("MRG-234 Add inventory validation") is None
