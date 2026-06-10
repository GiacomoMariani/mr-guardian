from datetime import datetime, timezone

from mr_guardian.models.history import ReviewRunRecord, TriggeredRuleStat
from mr_guardian.reporting.history import render_clear_history_result, render_review_history


def test_renders_empty_review_history() -> None:
    report = render_review_history([])

    assert "MR Guardian Review History" in report
    assert "No review runs have been stored yet." in report


def test_renders_review_history_table() -> None:
    report = render_review_history(
        [
            ReviewRunRecord(
                review_id=1,
                timestamp=datetime(2026, 5, 22, 10, 30, tzinfo=timezone.utc),
                review_scope="local-all-policies",
                branch_name="feature/history",
                mr_id="42",
                commit_sha="abc123",
                policy_version=1,
                risk="warning",
                blocking_count=0,
                high_count=0,
                warning_count=1,
                info_count=0,
                changed_file_count=3,
                changed_line_count=12,
                triggered_rule_ids=["PYTHON-PRINT-001"],
                generated_review_report="## MR Guardian Review\n",
            )
        ],
        most_triggered_rules=[TriggeredRuleStat(rule_id="PYTHON-PRINT-001", trigger_count=3)],
    )

    assert "ID  Timestamp" in report
    assert "local-all-policies" in report
    assert "feature/history" in report
    assert "PYTHON-PRINT-001" in report
    assert "Most Triggered Rules" in report
    assert "Count" in report


def test_renders_clear_history_result() -> None:
    assert render_clear_history_result(2) == "Removed 2 review run(s)."
