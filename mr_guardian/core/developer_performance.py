"""Developer performance summary preparation."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.models.history import ReviewRunRecord
from mr_guardian.models.performance import (
    DeveloperPerformanceSummary,
    TicketPerformanceSummary,
)
from mr_guardian.storage import ReviewHistoryStore

SECONDS_PER_DAY = 86_400


def load_developer_performance_summary(
    database_path: str | Path,
    *,
    developer_id: str,
    days: int,
    end_at: datetime | None = None,
) -> DeveloperPerformanceSummary:
    """Load and summarize one developer's recent review history."""
    resolved_end_at = end_at or datetime.now(timezone.utc)
    resolved_start_at = resolved_end_at - timedelta(days=days)
    store = ReviewHistoryStore(database_path)
    try:
        review_runs = store.review_runs_for_developer(
            developer_id=developer_id,
            start_at=resolved_start_at,
            end_at=resolved_end_at,
        )
    finally:
        store.close()

    return summarize_developer_performance(
        review_runs=review_runs,
        developer_id=developer_id,
        start_at=resolved_start_at,
        end_at=resolved_end_at,
    )


def summarize_developer_performance(
    *,
    review_runs: list[ReviewRunRecord],
    developer_id: str,
    start_at: datetime,
    end_at: datetime,
) -> DeveloperPerformanceSummary:
    """Summarize developer review performance from stored review runs."""
    sorted_runs = sorted(review_runs, key=lambda run: (run.timestamp, run.review_id))
    return DeveloperPerformanceSummary(
        developer_id=developer_id,
        start_at=start_at,
        end_at=end_at,
        review_request_count=len(sorted_runs),
        average_score=_average_score(sorted_runs),
        tickets=_ticket_summaries(sorted_runs),
    )


def _ticket_summaries(review_runs: list[ReviewRunRecord]) -> list[TicketPerformanceSummary]:
    runs_by_ticket: dict[str, list[ReviewRunRecord]] = defaultdict(list)
    for run in review_runs:
        if run.ticket_key is not None:
            runs_by_ticket[run.ticket_key].append(run)

    summaries = [
        _ticket_summary(ticket_key=ticket_key, review_runs=ticket_runs)
        for ticket_key, ticket_runs in runs_by_ticket.items()
    ]
    return sorted(
        summaries,
        key=lambda summary: (summary.last_request_at, summary.ticket_key),
        reverse=True,
    )


def _ticket_summary(
    *,
    ticket_key: str,
    review_runs: list[ReviewRunRecord],
) -> TicketPerformanceSummary:
    sorted_runs = sorted(review_runs, key=lambda run: (run.timestamp, run.review_id))
    first_request_at = sorted_runs[0].timestamp
    last_request_at = sorted_runs[-1].timestamp
    final_run = _final_run(sorted_runs)
    return TicketPerformanceSummary(
        ticket_key=ticket_key,
        mr_request_count=len(sorted_runs),
        first_request_at=first_request_at,
        last_request_at=last_request_at,
        total_review_days=_days_between(first_request_at, last_request_at),
        assumed_deployed_at=last_request_at,
        is_approved=final_run is not None,
        approved_at=final_run.timestamp if final_run is not None else None,
        attempts_to_approval=_attempts_to_approval(sorted_runs, final_run),
        average_score=_average_score(sorted_runs) or 0.0,
    )


def _final_run(review_runs: list[ReviewRunRecord]) -> ReviewRunRecord | None:
    final_runs = [run for run in review_runs if run.is_final]
    if not final_runs:
        return None
    return max(final_runs, key=lambda run: (run.timestamp, run.review_id))


def _attempts_to_approval(
    review_runs: list[ReviewRunRecord],
    final_run: ReviewRunRecord | None,
) -> int | None:
    if final_run is None:
        return None
    return sum(
        1
        for run in review_runs
        if (run.timestamp, run.review_id) <= (final_run.timestamp, final_run.review_id)
    )


def _average_score(review_runs: list[ReviewRunRecord]) -> float | None:
    if not review_runs:
        return None
    return round(
        sum(run.review_score for run in review_runs) / len(review_runs),
        2,
    )


def _days_between(start_at: datetime, end_at: datetime) -> float:
    elapsed_seconds = max(0.0, (end_at - start_at).total_seconds())
    return round(elapsed_seconds / SECONDS_PER_DAY, 2)
