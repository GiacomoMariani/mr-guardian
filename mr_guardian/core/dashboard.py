"""Dashboard data preparation for review history."""

from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from mr_guardian.models.history import ReviewRunRecord, TriggeredRuleStat
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
    finally:
        store.close()

    return prepare_dashboard_data(
        recent_reviews=recent_reviews,
        most_triggered_rules=most_triggered_rules,
    )


def prepare_dashboard_data(
    *,
    recent_reviews: list[ReviewRunRecord],
    most_triggered_rules: list[TriggeredRuleStat],
) -> DashboardData:
    """Prepare manager-facing metrics from review history records."""
    return DashboardData(
        recent_reviews=recent_reviews,
        risk_counts=_risk_counts(recent_reviews),
        most_triggered_rules=most_triggered_rules,
        trend_points=_trend_points(recent_reviews),
        ai_code_risk_frequency=_ai_code_risk_frequency(recent_reviews),
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
