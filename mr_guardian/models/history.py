"""Typed review history models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mr_guardian.models.dashboard import DashboardEtaNote
from mr_guardian.models.review import (
    Finding,
    LlmDeveloperProfile,
    LlmReviewSummary,
    LlmRuleMetric,
    ReviewEvaluation,
    RiskLevel,
)

__all__ = [
    "DashboardEtaNote",
    "ReviewPolicySummary",
    "ReviewRunCreate",
    "ReviewRunRecord",
    "TriggeredRuleStat",
    "review_run_record_schema",
]


class ReviewRunCreate(BaseModel):
    """Data required to persist a review run."""

    model_config = ConfigDict(frozen=True)

    review_scope: str
    branch_name: str
    developer_id: str = "unknown"
    ticket_key: str | None = None
    is_final: bool = False
    policy_version: int
    risk: RiskLevel
    blocking_count: int
    high_count: int
    warning_count: int
    info_count: int
    changed_file_count: int
    changed_line_count: int
    review_score: int | None = Field(default=None, ge=0, le=100)
    currency: str = "USD"
    findings: list[Finding] = Field(default_factory=list)
    triggered_rule_ids: list[str]
    evaluations: list[ReviewEvaluation] = Field(default_factory=list)
    llm_metrics: list[LlmRuleMetric] = Field(default_factory=list)
    llm_summary: LlmReviewSummary | None = None
    developer_profile: LlmDeveloperProfile | None = None
    policy_summaries: list["ReviewPolicySummary"] = Field(default_factory=list)
    generated_review_report: str
    mr_id: str | None = None
    commit_sha: str | None = None
    timestamp: datetime | None = None


class ReviewRunRecord(BaseModel):
    """A stored review run."""

    model_config = ConfigDict(frozen=True)

    review_id: int
    timestamp: datetime
    review_scope: str
    branch_name: str
    developer_id: str = "unknown"
    ticket_key: str | None = None
    is_final: bool = False
    policy_version: int
    risk: RiskLevel
    blocking_count: int
    high_count: int
    warning_count: int
    info_count: int
    changed_file_count: int
    changed_line_count: int
    review_score: int = Field(default=100, ge=0, le=100)
    estimated_cost_usd: float | None = None
    currency: str = "USD"
    findings: list[Finding] = Field(default_factory=list)
    triggered_rule_ids: list[str]
    evaluations: list[ReviewEvaluation] = Field(default_factory=list)
    llm_metrics: list[LlmRuleMetric] = Field(default_factory=list)
    llm_summary: LlmReviewSummary | None = None
    developer_profile: LlmDeveloperProfile | None = None
    policy_summaries: list["ReviewPolicySummary"] = Field(default_factory=list)
    generated_review_report: str
    mr_id: str | None = None
    commit_sha: str | None = None


class TriggeredRuleStat(BaseModel):
    """Aggregated triggered-rule count."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    trigger_count: int


class ReviewPolicySummary(BaseModel):
    """A compact summary of one evaluated policy file."""

    model_config = ConfigDict(frozen=True)

    policy_path: str
    policy_version: int
    enabled_rule_count: int
    disabled_rule_count: int


def review_run_record_schema() -> dict[str, Any]:
    """Return the JSON schema for stored review run records."""
    schema = ReviewRunRecord.model_json_schema()
    schema["x-sqlite-columns"] = [
        "review_id",
        "timestamp",
        "review_scope",
        "branch_name",
        "developer_id",
        "ticket_key",
        "is_final",
        "mr_id",
        "commit_sha",
        "policy_version",
        "risk",
        "blocking_count",
        "high_count",
        "warning_count",
        "info_count",
        "changed_file_count",
        "changed_line_count",
        "review_score",
        "estimated_cost_usd",
        "currency",
        "llm_summary",
        "llm_summary_score",
        "llm_summary_status",
        "llm_summary_provider",
        "llm_summary_model",
        "llm_summary_duration_ms",
        "llm_summary_input_tokens",
        "llm_summary_output_tokens",
        "llm_summary_total_tokens",
        "llm_summary_estimated_cost_usd",
        "llm_summary_error_message",
        "developer_profile",
        "developer_profile_status",
        "developer_profile_provider",
        "developer_profile_model",
        "developer_profile_duration_ms",
        "developer_profile_input_tokens",
        "developer_profile_output_tokens",
        "developer_profile_total_tokens",
        "developer_profile_estimated_cost_usd",
        "developer_profile_error_message",
        "developer_profile_lookback_days",
        "generated_review_report",
    ]
    schema["x-storage-notes"] = {
        "project_name": (
            "Legacy SQLite column from older history databases. Current typed records "
            "use review_scope; migrations copy project_name into review_scope."
        ),
        "nested_values": (
            "SQLite stores findings, policies, evaluations, triggered rules, and LLM "
            "metrics across related tables. Application code exposes them as typed "
            "nested objects on ReviewRunRecord."
        ),
        "llm_summary_score": (
            "Stored as a SQLite column and exposed as llm_summary.score on typed records."
        ),
        "developer_profile": (
            "Stored as SQLite columns and exposed as developer_profile on typed records."
        ),
        "estimated_cost_usd": (
            "Review-level rollup of the estimated USD cost of every LLM call in the run "
            "(per-rule metrics + summary + developer profile), recomputed from the stored "
            "per-call costs. Per-call costs live on their own rows/columns; currency "
            "defaults to USD."
        ),
    }
    return schema
