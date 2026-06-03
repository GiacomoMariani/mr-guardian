"""Technical-lead dashboard aggregation."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.core.review_score import calculate_review_score_from_counts
from mr_guardian.models.history import ReviewRunRecord
from mr_guardian.models.lead_dashboard import (
    LeadDashboardSummary,
    LeadDeveloperDetail,
    LeadDeveloperSummary,
    LeadEvaluationSummary,
    LeadRepeatedRule,
    LeadTicketAttemptSummary,
    TrendDirection,
)
from mr_guardian.models.policy import EvaluationDimension
from mr_guardian.models.review import EVALUATION_ORDER, FindingCounts, ReviewEvaluation
from mr_guardian.storage import ReviewHistoryStore

TREND_MIN_REVIEW_COUNT = 4
TREND_SCORE_DELTA = 2.0


def load_lead_dashboard_summary(
    database_path: str | Path,
    *,
    days: int,
    end_at: datetime | None = None,
) -> LeadDashboardSummary:
    """Load and prepare lead dashboard data for a recent history window."""
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

    return prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=resolved_start_at,
        end_at=resolved_end_at,
    )


def load_lead_developer_detail(
    database_path: str | Path,
    *,
    developer_id: str,
    days: int,
    end_at: datetime | None = None,
) -> LeadDeveloperDetail | None:
    """Load one developer's lead dashboard detail data."""
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

    return prepare_lead_developer_detail(
        developer_id=developer_id,
        review_runs=review_runs,
        start_at=resolved_start_at,
        end_at=resolved_end_at,
    )


def prepare_lead_developer_detail(
    *,
    developer_id: str,
    review_runs: list[ReviewRunRecord],
    start_at: datetime,
    end_at: datetime,
) -> LeadDeveloperDetail | None:
    """Prepare the developer detail page data for a review-history window."""
    developer_runs = [
        run for run in review_runs if run.developer_id == developer_id
    ]
    if not developer_runs:
        return None

    sorted_runs = sorted(
        developer_runs,
        key=lambda run: (run.timestamp, run.review_id),
        reverse=True,
    )
    return LeadDeveloperDetail(
        start_at=start_at,
        end_at=end_at,
        developer=_developer_summary(
            developer_id=developer_id,
            review_runs=developer_runs,
        ),
        review_runs=sorted_runs,
    )


def prepare_lead_dashboard_summary(
    *,
    review_runs: list[ReviewRunRecord],
    start_at: datetime,
    end_at: datetime,
) -> LeadDashboardSummary:
    """Prepare technical-lead review iteration and developer trend data."""
    return LeadDashboardSummary(
        start_at=start_at,
        end_at=end_at,
        developers=_developer_summaries(review_runs),
    )


def _developer_summaries(review_runs: list[ReviewRunRecord]) -> list[LeadDeveloperSummary]:
    runs_by_developer: dict[str, list[ReviewRunRecord]] = defaultdict(list)
    for run in review_runs:
        runs_by_developer[run.developer_id].append(run)

    summaries = [
        _developer_summary(developer_id=developer_id, review_runs=developer_runs)
        for developer_id, developer_runs in runs_by_developer.items()
    ]
    return sorted(
        summaries,
        key=lambda summary: (summary.latest_review_at, summary.developer_id),
        reverse=True,
    )


def _developer_summary(
    *,
    developer_id: str,
    review_runs: list[ReviewRunRecord],
) -> LeadDeveloperSummary:
    sorted_runs = sorted(review_runs, key=lambda run: (run.timestamp, run.review_id))
    tickets = _ticket_attempts(sorted_runs)
    repeated_rules = _repeated_rules(sorted_runs)
    return LeadDeveloperSummary(
        developer_id=developer_id,
        review_request_count=len(sorted_runs),
        ticket_count=len(tickets),
        average_attempts_per_ticket=_average_attempts_per_ticket(tickets),
        approved_ticket_count=sum(1 for ticket in tickets if ticket.is_approved),
        average_attempts_to_approval=_average_attempts_to_approval(tickets),
        average_score=_average_score(sorted_runs),
        latest_review_at=sorted_runs[-1].timestamp,
        trend_direction=_trend_direction(sorted_runs),
        multi_attempt_ticket_count=sum(1 for ticket in tickets if ticket.review_attempt_count > 1),
        repeated_rule_count=len(repeated_rules),
        unlinked_review_count=sum(1 for run in sorted_runs if run.ticket_key is None),
        tickets=tickets,
        repeated_rules=repeated_rules,
        evaluation_summaries=_evaluation_summaries(sorted_runs),
    )


def _ticket_attempts(review_runs: list[ReviewRunRecord]) -> list[LeadTicketAttemptSummary]:
    runs_by_ticket: dict[str, list[ReviewRunRecord]] = defaultdict(list)
    for run in review_runs:
        if run.ticket_key is not None:
            runs_by_ticket[run.ticket_key].append(run)

    tickets = [
        _ticket_attempt(ticket_key=ticket_key, review_runs=ticket_runs)
        for ticket_key, ticket_runs in runs_by_ticket.items()
    ]
    return sorted(
        tickets,
        key=lambda ticket: (ticket.latest_review_at, ticket.ticket_key),
        reverse=True,
    )


def _ticket_attempt(
    *,
    ticket_key: str,
    review_runs: list[ReviewRunRecord],
) -> LeadTicketAttemptSummary:
    sorted_runs = sorted(review_runs, key=lambda run: (run.timestamp, run.review_id))
    latest_run = sorted_runs[-1]
    final_run = _final_run(sorted_runs)
    return LeadTicketAttemptSummary(
        ticket_key=ticket_key,
        review_attempt_count=len(sorted_runs),
        first_review_at=sorted_runs[0].timestamp,
        latest_review_at=latest_run.timestamp,
        assumed_deployed_at=latest_run.timestamp,
        is_approved=final_run is not None,
        approved_at=final_run.timestamp if final_run is not None else None,
        attempts_to_approval=_attempts_to_approval(sorted_runs, final_run),
        average_score=_average_score(sorted_runs) or 0.0,
        latest_risk=latest_run.risk,
    )


def _average_attempts_per_ticket(tickets: list[LeadTicketAttemptSummary]) -> float:
    if not tickets:
        return 0.0
    return round(
        sum(ticket.review_attempt_count for ticket in tickets) / len(tickets),
        2,
    )


def _average_attempts_to_approval(
    tickets: list[LeadTicketAttemptSummary],
) -> float | None:
    approved_attempts = [
        ticket.attempts_to_approval
        for ticket in tickets
        if ticket.attempts_to_approval is not None
    ]
    if not approved_attempts:
        return None
    return round(sum(approved_attempts) / len(approved_attempts), 2)


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


def _trend_direction(review_runs: list[ReviewRunRecord]) -> TrendDirection:
    if len(review_runs) < TREND_MIN_REVIEW_COUNT:
        return "insufficient_data"

    midpoint = len(review_runs) // 2
    first_average = _average_score(review_runs[:midpoint])
    second_average = _average_score(review_runs[midpoint:])
    if first_average is None or second_average is None:
        return "insufficient_data"

    delta = second_average - first_average
    if delta > TREND_SCORE_DELTA:
        return "improving"
    if delta < -TREND_SCORE_DELTA:
        return "declining"
    return "stable"


def _repeated_rules(review_runs: list[ReviewRunRecord]) -> list[LeadRepeatedRule]:
    runs_by_rule: dict[str, list[ReviewRunRecord]] = defaultdict(list)
    for run in review_runs:
        for rule_id in dict.fromkeys(run.triggered_rule_ids):
            runs_by_rule[rule_id].append(run)

    repeated = [
        LeadRepeatedRule(
            rule_id=rule_id,
            review_run_count=len(rule_runs),
            latest_review_at=max(run.timestamp for run in rule_runs),
        )
        for rule_id, rule_runs in runs_by_rule.items()
        if len(rule_runs) > 1
    ]
    return sorted(
        repeated,
        key=lambda rule: (rule.review_run_count, rule.latest_review_at, rule.rule_id),
        reverse=True,
    )


def _evaluation_summaries(review_runs: list[ReviewRunRecord]) -> list[LeadEvaluationSummary]:
    evaluations_by_dimension: dict[EvaluationDimension, list[ReviewEvaluation]] = {
        evaluation: [] for evaluation in EVALUATION_ORDER
    }
    for run in review_runs:
        for evaluation in run.evaluations:
            evaluations_by_dimension.setdefault(evaluation.evaluation, []).append(evaluation)

    return [
        _evaluation_summary(evaluation=dimension, evaluations=evaluations)
        for dimension, evaluations in evaluations_by_dimension.items()
        if evaluations
    ]


def _evaluation_summary(
    *,
    evaluation: EvaluationDimension,
    evaluations: list[ReviewEvaluation],
) -> LeadEvaluationSummary:
    counts = FindingCounts(
        blocking=sum(item.counts.blocking for item in evaluations),
        high=sum(item.counts.high for item in evaluations),
        warning=sum(item.counts.warning for item in evaluations),
        info=sum(item.counts.info for item in evaluations),
    )
    return LeadEvaluationSummary(
        evaluation=evaluation,
        review_count=len(evaluations),
        average_score=round(
            sum(calculate_review_score_from_counts(item.counts) for item in evaluations)
            / len(evaluations),
            2,
        ),
        counts=counts,
    )
