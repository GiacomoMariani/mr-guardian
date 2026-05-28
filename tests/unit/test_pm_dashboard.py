from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.core.pm_dashboard import (
    classify_pm_ticket_status,
    load_pm_dashboard_summary,
    prepare_pm_dashboard_summary,
)
from mr_guardian.models.history import ReviewRunCreate
from mr_guardian.models.review import RiskLevel
from mr_guardian.storage import ReviewHistoryStore


def make_review_run(
    *,
    ticket_key: str | None,
    timestamp: datetime,
    risk: RiskLevel,
    triggered_rule_ids: list[str] | None = None,
) -> ReviewRunCreate:
    rule_ids = triggered_rule_ids or (["RULE-001"] if risk != "none" else [])
    return ReviewRunCreate(
        review_scope="gitlab-webhook",
        branch_name="refs/remotes/origin/main",
        developer_id="Test Developer",
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
        triggered_rule_ids=rule_ids,
        generated_review_report="## MR Guardian Review\n",
        timestamp=timestamp,
    )


def stored_runs(*runs: ReviewRunCreate) -> list:
    store = ReviewHistoryStore(":memory:")
    try:
        return [store.store_review_run(run) for run in runs]
    finally:
        store.close()


def test_classifies_pm_ticket_status_from_latest_risk() -> None:
    assert classify_pm_ticket_status("blocking") == "fail"
    assert classify_pm_ticket_status("high") == "fail"
    assert classify_pm_ticket_status("warning") == "pass_with_warnings"
    assert classify_pm_ticket_status("info") == "pass_with_warnings"
    assert classify_pm_ticket_status("none") == "pass"


def test_pm_summary_groups_by_ticket_and_uses_latest_review_status() -> None:
    base_time = datetime(2026, 5, 25, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            ticket_key="TK-100",
            timestamp=base_time,
            risk="none",
        ),
        make_review_run(
            ticket_key="TK-100",
            timestamp=base_time + timedelta(days=1),
            risk="high",
            triggered_rule_ids=["MR-META-001"],
        ),
        make_review_run(
            ticket_key="TK-200",
            timestamp=base_time + timedelta(hours=1),
            risk="none",
        ),
        make_review_run(
            ticket_key="TK-300",
            timestamp=base_time + timedelta(hours=2),
            risk="warning",
        ),
        make_review_run(
            ticket_key=None,
            timestamp=base_time + timedelta(hours=3),
            risk="blocking",
            triggered_rule_ids=["UNLINKED-001"],
        ),
    )

    summary = prepare_pm_dashboard_summary(
        review_runs=review_runs,
        start_at=base_time - timedelta(days=1),
        end_at=base_time + timedelta(days=2),
    )

    ticket_by_key = {ticket.ticket_key: ticket for ticket in summary.tickets}
    assert summary.total_ticket_count == 3
    assert summary.pass_count == 1
    assert summary.pass_with_warnings_count == 1
    assert summary.fail_count == 1
    assert summary.blocked_ticket_count == 1
    assert summary.unlinked_review_count == 1
    assert summary.pass_rate == 66.67
    assert ticket_by_key["TK-100"].status == "fail"
    assert ticket_by_key["TK-100"].latest_risk == "high"
    assert ticket_by_key["TK-100"].review_request_count == 2
    assert ticket_by_key["TK-100"].assumed_deployed_at == base_time + timedelta(days=1)
    assert ticket_by_key["TK-100"].blocker_reason == (
        "High-risk review risk from MR-META-001."
    )


def test_pm_summary_detects_recurring_blockers_across_tickets() -> None:
    base_time = datetime(2026, 5, 25, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            ticket_key="TK-100",
            timestamp=base_time,
            risk="high",
            triggered_rule_ids=["MR-META-001"],
        ),
        make_review_run(
            ticket_key="TK-200",
            timestamp=base_time + timedelta(hours=1),
            risk="blocking",
            triggered_rule_ids=["MR-META-001"],
        ),
        make_review_run(
            ticket_key="TK-300",
            timestamp=base_time + timedelta(hours=2),
            risk="warning",
            triggered_rule_ids=["MR-META-001"],
        ),
    )

    summary = prepare_pm_dashboard_summary(
        review_runs=review_runs,
        start_at=base_time - timedelta(days=1),
        end_at=base_time + timedelta(days=1),
    )

    assert len(summary.recurring_blockers) == 1
    blocker = summary.recurring_blockers[0]
    assert blocker.rule_id == "MR-META-001"
    assert blocker.affected_ticket_count == 2
    assert blocker.review_run_count == 2
    assert blocker.highest_severity_seen == "blocking"


def test_load_pm_dashboard_summary_uses_selected_time_window(tmp_path: Path) -> None:
    now = datetime(2026, 5, 28, 10, tzinfo=timezone.utc)
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    store.store_review_run(
        make_review_run(
            ticket_key="TK-OLD",
            timestamp=now - timedelta(days=10),
            risk="blocking",
        )
    )
    store.store_review_run(
        make_review_run(
            ticket_key="TK-NEW",
            timestamp=now - timedelta(days=1),
            risk="none",
        )
    )
    store.close()

    summary = load_pm_dashboard_summary(
        tmp_path / "history.sqlite",
        days=3,
        end_at=now,
    )

    assert [ticket.ticket_key for ticket in summary.tickets] == ["TK-NEW"]
    assert summary.pass_count == 1


def test_pm_aggregation_stays_outside_streamlit() -> None:
    app_source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "classify_pm_ticket_status" not in app_source
    assert "prepare_pm_dashboard_summary" not in app_source
    assert "defaultdict" not in app_source
