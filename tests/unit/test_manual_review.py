import json
from pathlib import Path

import pytest

from mr_guardian.core.manual_review import (
    ManualReviewJsonError,
    ManualReviewValidationError,
    load_manual_review_payload,
    manual_review_to_review_run,
    store_manual_review_file,
)
from mr_guardian.storage import ReviewHistoryStore


def valid_payload() -> dict[str, object]:
    return {
        "review_scope": "manual-review",
        "branch_name": "feature/manual-review",
        "title": "TK-234 Manual review",
        "developer_id": "Test Reviewer",
        "policy_version": 1,
        "risk": "high",
        "findings": [
            {
                "rule_id": "PYTHON-PRINT-001",
                "severity": "warning",
                "message": "print calls should be replaced with logging.",
                "source": "manual-review#PYTHON-PRINT-001",
                "evaluation": "coding",
                "rule_type": "deterministic",
                "file_path": "mr_guardian/example.py",
                "line_number": 4,
            },
            {
                "rule_id": "MR-META-001",
                "severity": "high",
                "message": "Manual review found missing release notes.",
                "source": "manual-review#MR-META-001",
                "evaluation": "mr_structure",
                "rule_type": "deterministic",
                "file_path": None,
                "line_number": None,
            },
        ],
        "evaluations": [
            {
                "evaluation": "coding",
                "risk": "warning",
                "counts": {
                    "blocking": 0,
                    "high": 0,
                    "warning": 1,
                    "info": 0,
                },
                "triggered_rule_ids": ["PYTHON-PRINT-001"],
            },
            {
                "evaluation": "mr_structure",
                "risk": "high",
                "counts": {
                    "blocking": 0,
                    "high": 1,
                    "warning": 0,
                    "info": 0,
                },
                "triggered_rule_ids": ["MR-META-001"],
            },
        ],
        "changed_file_count": 2,
        "changed_line_count": 8,
        "generated_review_report": "## Manual Review\n\nReviewer notes.",
        "mr_id": "42",
        "commit_sha": "abc123",
    }


def write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    payload_path = tmp_path / "manual-review.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload_path


def test_loads_valid_manual_review_json(tmp_path: Path) -> None:
    payload_path = write_payload(tmp_path, valid_payload())

    payload = load_manual_review_payload(payload_path)

    assert payload.review_scope == "manual-review"
    assert payload.branch_name == "feature/manual-review"
    assert len(payload.findings) == 2
    assert payload.findings[0].file_path == Path("mr_guardian/example.py")


def test_recomputes_counts_and_triggered_rules_from_findings(tmp_path: Path) -> None:
    payload = load_manual_review_payload(write_payload(tmp_path, valid_payload()))

    review_run = manual_review_to_review_run(payload)

    assert review_run.risk == "high"
    assert review_run.high_count == 1
    assert review_run.warning_count == 1
    assert review_run.ticket_key == "TK-234"
    assert review_run.review_score == 80
    assert review_run.triggered_rule_ids == ["PYTHON-PRINT-001", "MR-META-001"]


def test_stores_valid_manual_review(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    payload_path = write_payload(tmp_path, valid_payload())

    record = store_manual_review_file(payload_path, database_path=database_path)
    store = ReviewHistoryStore(database_path)
    stored_record = store.review_run(record.review_id)
    store.close()

    assert stored_record is not None
    assert stored_record.review_id == 1
    assert stored_record.review_scope == "manual-review"
    assert stored_record.branch_name == "feature/manual-review"
    assert stored_record.developer_id == "Test Reviewer"
    assert stored_record.ticket_key == "TK-234"
    assert stored_record.review_score == 80
    assert stored_record.triggered_rule_ids == ["PYTHON-PRINT-001", "MR-META-001"]
    assert len(stored_record.findings) == 2
    assert stored_record.findings[0].rule_id == "PYTHON-PRINT-001"
    assert stored_record.findings[0].file_path == Path("mr_guardian/example.py")
    assert stored_record.evaluations[0].evaluation == "coding"
    assert stored_record.evaluations[0].risk == "warning"
    assert stored_record.evaluations[1].evaluation == "mr_structure"
    assert stored_record.evaluations[1].risk == "high"
    assert stored_record.generated_review_report == "## Manual Review\n\nReviewer notes."


def test_rejects_invalid_json_syntax(tmp_path: Path) -> None:
    payload_path = tmp_path / "manual-review.json"
    payload_path.write_text("{", encoding="utf-8")

    with pytest.raises(ManualReviewJsonError, match="Invalid JSON"):
        load_manual_review_payload(payload_path)


def test_rejects_missing_required_fields(tmp_path: Path) -> None:
    payload = valid_payload()
    payload.pop("branch_name")

    with pytest.raises(ManualReviewValidationError, match="branch_name"):
        load_manual_review_payload(write_payload(tmp_path, payload))


def test_rejects_risk_that_does_not_match_findings(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["risk"] = "none"

    with pytest.raises(ManualReviewValidationError, match="does not match findings risk"):
        load_manual_review_payload(write_payload(tmp_path, payload))


def test_rejects_inconsistent_evaluation_summaries(tmp_path: Path) -> None:
    payload = valid_payload()
    evaluations = payload["evaluations"]
    assert isinstance(evaluations, list)
    first_evaluation = evaluations[0]
    assert isinstance(first_evaluation, dict)
    first_evaluation["triggered_rule_ids"] = []

    with pytest.raises(ManualReviewValidationError, match="triggered_rule_ids"):
        load_manual_review_payload(write_payload(tmp_path, payload))
