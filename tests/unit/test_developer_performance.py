from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.core.developer_performance import (
    load_developer_performance_summary,
    summarize_developer_performance,
)
from mr_guardian.models.history import ReviewRunCreate
from mr_guardian.models.review import RiskLevel
from mr_guardian.storage import ReviewHistoryStore


def make_review_run(
    *,
    developer_id: str = "Jane Developer",
    ticket_key: str | None = "TK-234",
    timestamp: datetime,
    risk: RiskLevel = "warning",
) -> ReviewRunCreate:
    return ReviewRunCreate(
        review_scope="gitlab-webhook",
        branch_name="refs/remotes/origin/main",
        developer_id=developer_id,
        ticket_key=ticket_key,
        mr_id="42",
        policy_version=1,
        risk=risk,
        blocking_count=1 if risk == "blocking" else 0,
        high_count=1 if risk == "high" else 0,
        warning_count=1 if risk == "warning" else 0,
        info_count=1 if risk == "info" else 0,
        changed_file_count=2,
        changed_line_count=12,
        triggered_rule_ids=["RULE-001"] if risk != "none" else [],
        generated_review_report="## MR Guardian Review\n",
        timestamp=timestamp,
    )


def test_summarizes_developer_performance_by_ticket() -> None:
    first_request = datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc)
    second_request = first_request + timedelta(days=2, hours=12)
    third_request = first_request + timedelta(days=4)
    store = ReviewHistoryStore(":memory:")
    first_record = store.store_review_run(
        make_review_run(ticket_key="TK-234", timestamp=first_request, risk="warning")
    )
    second_record = store.store_review_run(
        make_review_run(ticket_key="TK-234", timestamp=second_request, risk="high")
    )
    third_record = store.store_review_run(
        make_review_run(ticket_key="TK-999", timestamp=third_request, risk="none")
    )
    store.close()

    summary = summarize_developer_performance(
        review_runs=[first_record, second_record, third_record],
        developer_id="Jane Developer",
        start_at=first_request - timedelta(days=1),
        end_at=third_request + timedelta(days=1),
    )

    ticket = next(item for item in summary.tickets if item.ticket_key == "TK-234")
    assert summary.review_request_count == 3
    assert summary.average_score == 93.33
    assert ticket.mr_request_count == 2
    assert ticket.first_request_at == first_request
    assert ticket.last_request_at == second_request
    assert ticket.assumed_deployed_at == second_request
    assert ticket.total_review_days == 2.5
    assert ticket.average_score == 90


def test_load_developer_performance_summary_filters_by_developer_and_days(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 5, 25, 10, 0, tzinfo=timezone.utc)
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    expected_record = store.store_review_run(
        make_review_run(timestamp=now - timedelta(days=1), ticket_key="TK-234")
    )
    store.store_review_run(
        make_review_run(timestamp=now - timedelta(days=10), ticket_key="TK-999")
    )
    store.store_review_run(
        make_review_run(
            developer_id="Other Developer",
            timestamp=now - timedelta(days=1),
            ticket_key="TK-888",
        )
    )
    store.close()

    summary = load_developer_performance_summary(
        tmp_path / "history.sqlite",
        developer_id="Jane Developer",
        days=7,
        end_at=now,
    )

    assert summary.review_request_count == 1
    assert summary.tickets[0].ticket_key == "TK-234"
    assert summary.tickets[0].last_request_at == expected_record.timestamp
