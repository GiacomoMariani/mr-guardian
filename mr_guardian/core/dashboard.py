"""Dashboard data preparation for review history."""

from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from mr_guardian.models.history import ReviewRunRecord, TriggeredRuleStat
from mr_guardian.models.performance import DeveloperActivity
from mr_guardian.models.review import RiskLevel
from mr_guardian.storage import ReviewHistoryStore


class RiskCount(BaseModel):
    """Count of stored review runs for one risk level."""

    model_config = ConfigDict(frozen=True)

    risk: RiskLevel
    count: int


class TrendPoint(BaseModel):
    """Daily aggregate of review history counts."""

    model_config = ConfigDict(frozen=True)

    date: str
    blocking_count: int
    warning_count: int


class DashboardData(BaseModel):
    """Prepared review history data for dashboards."""

    model_config = ConfigDict(frozen=True)

    recent_reviews: list[ReviewRunRecord]
    risk_counts: list[RiskCount]
    most_triggered_rules: list[TriggeredRuleStat]
    trend_points: list[TrendPoint]
    ai_code_risk_frequency: int
    developer_activity: list[DeveloperActivity]


def load_dashboard_data(
    database_path: str | Path,
    *,
    recent_limit: int = 50,
    rule_limit: int = 10,
) -> DashboardData:
    """Load and prepare dashboard data from review history storage."""
    store = ReviewHistoryStore(database_path)
    try:
        recent_reviews = store.recent_review_runs(limit=recent_limit)
        most_triggered_rules = store.most_triggered_rules(limit=rule_limit)
        developer_activity = store.developer_activity()
    finally:
        store.close()

    return prepare_dashboard_data(
        recent_reviews=recent_reviews,
        most_triggered_rules=most_triggered_rules,
        developer_activity=developer_activity,
    )


def prepare_dashboard_data(
    *,
    recent_reviews: list[ReviewRunRecord],
    most_triggered_rules: list[TriggeredRuleStat],
    developer_activity: list[DeveloperActivity] | None = None,
) -> DashboardData:
    """Prepare manager-facing metrics from review history records."""
    return DashboardData(
        recent_reviews=recent_reviews,
        risk_counts=_risk_counts(recent_reviews),
        most_triggered_rules=most_triggered_rules,
        trend_points=_trend_points(recent_reviews),
        ai_code_risk_frequency=_ai_code_risk_frequency(recent_reviews),
        developer_activity=developer_activity or _developer_activity(recent_reviews),
    )


def _risk_counts(review_runs: list[ReviewRunRecord]) -> list[RiskCount]:
    counts = Counter(run.risk for run in review_runs)
    risk_order: tuple[RiskLevel, ...] = ("blocking", "high", "warning", "info", "none")
    return [RiskCount(risk=risk, count=counts[risk]) for risk in risk_order]


def _trend_points(review_runs: list[ReviewRunRecord]) -> list[TrendPoint]:
    by_date: dict[str, dict[str, int]] = {}
    for run in review_runs:
        date_key = run.timestamp.date().isoformat()
        counts = by_date.setdefault(date_key, {"blocking": 0, "warning": 0})
        counts["blocking"] += run.blocking_count
        counts["warning"] += run.warning_count

    return [
        TrendPoint(
            date=date_key,
            blocking_count=counts["blocking"],
            warning_count=counts["warning"],
        )
        for date_key, counts in sorted(by_date.items())
    ]


def _ai_code_risk_frequency(review_runs: list[ReviewRunRecord]) -> int:
    return sum(
        1
        for run in review_runs
        if any(rule_id.startswith("AI-CODE") for rule_id in run.triggered_rule_ids)
    )


def _developer_activity(review_runs: list[ReviewRunRecord]) -> list[DeveloperActivity]:
    latest_by_developer: dict[str, ReviewRunRecord] = {}
    runs_by_developer: dict[str, list[ReviewRunRecord]] = {}
    for run in review_runs:
        runs_by_developer.setdefault(run.developer_id, []).append(run)
        current_latest = latest_by_developer.get(run.developer_id)
        if current_latest is None or run.timestamp > current_latest.timestamp:
            latest_by_developer[run.developer_id] = run

    activity = [
        DeveloperActivity(
            developer_id=developer_id,
            last_review_at=latest_by_developer[developer_id].timestamp,
            review_request_count=len(developer_runs),
            average_score=round(
                sum(run.review_score for run in developer_runs) / len(developer_runs),
                2,
            ),
        )
        for developer_id, developer_runs in runs_by_developer.items()
    ]
    return sorted(
        activity,
        key=lambda item: (item.last_review_at, item.developer_id),
        reverse=True,
    )
