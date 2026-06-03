"""Project-manager dashboard aggregation."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.models.history import ReviewRunRecord
from mr_guardian.models.pm_dashboard import (
    PmDashboardSummary,
    PmRecurringBlocker,
    PmTicketStatus,
    PmTicketStatusValue,
)
from mr_guardian.models.review import RiskLevel
from mr_guardian.storage import ReviewHistoryStore

RISK_PRIORITY: dict[RiskLevel, int] = {
    "none": 0,
    "info": 1,
    "warning": 2,
    "high": 3,
    "blocking": 4,
}


def load_pm_dashboard_summary(
    database_path: str | Path,
    *,
    days: int,
    end_at: datetime | None = None,
) -> PmDashboardSummary:
    """Load and prepare PM dashboard data for a recent history window."""
    resolved_end_at = end_at or datetime.now(timezone.utc)
    resolved_start_at = resolved_end_at - timedelta(days=days)
    store = ReviewHistoryStore(database_path)
    try:
        review_runs = store.review_runs_between(
            start_at=resolved_start_at,
            end_at=resolved_end_at,
        )
    finally:
        store.close()

    return prepare_pm_dashboard_summary(
        review_runs=review_runs,
        start_at=resolved_start_at,
        end_at=resolved_end_at,
    )


def prepare_pm_dashboard_summary(
    *,
    review_runs: list[ReviewRunRecord],
    start_at: datetime,
    end_at: datetime,
) -> PmDashboardSummary:
    """Prepare PM-facing ticket status and blocker metrics."""
    tickets = _ticket_statuses(review_runs)
    status_counts = _status_counts(tickets)
    total_ticket_count = len(tickets)
    pass_count = status_counts["pass"]
    non_failing_count = pass_count + status_counts["pass_with_warnings"]
    pass_rate = round((non_failing_count / total_ticket_count) * 100, 2) if tickets else 0.0
    return PmDashboardSummary(
        start_at=start_at,
        end_at=end_at,
        total_ticket_count=total_ticket_count,
        pass_count=pass_count,
        pass_with_warnings_count=status_counts["pass_with_warnings"],
        fail_count=status_counts["fail"],
        pass_rate=pass_rate,
        blocked_ticket_count=status_counts["fail"],
        unlinked_review_count=sum(1 for run in review_runs if run.ticket_key is None),
        tickets=tickets,
        recurring_blockers=_recurring_blockers(review_runs),
    )


def classify_pm_ticket_status(risk: RiskLevel) -> PmTicketStatusValue:
    """Classify a review risk into PM-facing pass/fail status."""
    if risk in {"blocking", "high"}:
        return "fail"
    if risk in {"warning", "info"}:
        return "pass_with_warnings"
    return "pass"


def _ticket_statuses(review_runs: list[ReviewRunRecord]) -> list[PmTicketStatus]:
    runs_by_ticket: dict[str, list[ReviewRunRecord]] = defaultdict(list)
    for run in review_runs:
        if run.ticket_key is not None:
            runs_by_ticket[run.ticket_key].append(run)

    statuses = [
        _ticket_status(ticket_key=ticket_key, review_runs=ticket_runs)
        for ticket_key, ticket_runs in runs_by_ticket.items()
    ]
    return sorted(
        statuses,
        key=lambda status: (status.latest_review_at, status.ticket_key),
        reverse=True,
    )


def _ticket_status(
    *,
    ticket_key: str,
    review_runs: list[ReviewRunRecord],
) -> PmTicketStatus:
    latest_run = max(review_runs, key=lambda run: (run.timestamp, run.review_id))
    final_run = _final_run(review_runs)
    status = classify_pm_ticket_status(latest_run.risk)
    return PmTicketStatus(
        ticket_key=ticket_key,
        status=status,
        latest_review_at=latest_run.timestamp,
        assumed_deployed_at=latest_run.timestamp,
        delivery_state="approved" if final_run is not None else "observed",
        approved_at=final_run.timestamp if final_run is not None else None,
        latest_risk=latest_run.risk,
        review_request_count=len(review_runs),
        average_score=_average_score(review_runs),
        blocker_reason=_blocker_reason(latest_run) if status == "fail" else None,
    )


def _final_run(review_runs: list[ReviewRunRecord]) -> ReviewRunRecord | None:
    final_runs = [run for run in review_runs if run.is_final]
    if not final_runs:
        return None
    return max(final_runs, key=lambda run: (run.timestamp, run.review_id))


def _status_counts(tickets: list[PmTicketStatus]) -> dict[PmTicketStatusValue, int]:
    return {
        "fail": sum(1 for ticket in tickets if ticket.status == "fail"),
        "pass_with_warnings": sum(
            1 for ticket in tickets if ticket.status == "pass_with_warnings"
        ),
        "pass": sum(1 for ticket in tickets if ticket.status == "pass"),
    }


def _average_score(review_runs: list[ReviewRunRecord]) -> float:
    return round(sum(run.review_score for run in review_runs) / len(review_runs), 2)


def _blocker_reason(run: ReviewRunRecord) -> str:
    severity_label = "Blocking" if run.risk == "blocking" else "High-risk"
    if run.triggered_rule_ids:
        return f"{severity_label} review risk from {', '.join(run.triggered_rule_ids[:3])}."
    if run.risk == "blocking":
        return f"Blocking review risk from {run.blocking_count} blocking finding(s)."
    return f"High review risk from {run.high_count} high finding(s)."


def _recurring_blockers(review_runs: list[ReviewRunRecord]) -> list[PmRecurringBlocker]:
    runs_by_rule: dict[str, list[ReviewRunRecord]] = defaultdict(list)
    for run in review_runs:
        if run.risk not in {"blocking", "high"}:
            continue
        for rule_id in dict.fromkeys(run.triggered_rule_ids):
            runs_by_rule[rule_id].append(run)

    recurring = [
        _recurring_blocker(rule_id=rule_id, review_runs=rule_runs)
        for rule_id, rule_runs in runs_by_rule.items()
        if _is_recurring(rule_runs)
    ]
    return sorted(
        recurring,
        key=lambda blocker: (
            RISK_PRIORITY[blocker.highest_severity_seen],
            blocker.affected_ticket_count,
            blocker.review_run_count,
            blocker.rule_id,
        ),
        reverse=True,
    )


def _recurring_blocker(
    *,
    rule_id: str,
    review_runs: list[ReviewRunRecord],
) -> PmRecurringBlocker:
    return PmRecurringBlocker(
        rule_id=rule_id,
        affected_ticket_count=len(
            {
                run.ticket_key
                for run in review_runs
                if run.ticket_key is not None
            }
        ),
        review_run_count=len(review_runs),
        highest_severity_seen=max(
            (run.risk for run in review_runs),
            key=lambda risk: RISK_PRIORITY[risk],
        ),
    )


def _is_recurring(review_runs: list[ReviewRunRecord]) -> bool:
    affected_ticket_count = len(
        {
            run.ticket_key
            for run in review_runs
            if run.ticket_key is not None
        }
    )
    return affected_ticket_count > 1 or len(review_runs) > 1
