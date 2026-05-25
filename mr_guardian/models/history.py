"""Typed review history models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from mr_guardian.models.review import RiskLevel


class ReviewRunCreate(BaseModel):
    """Data required to persist a review run."""

    model_config = ConfigDict(frozen=True)

    review_scope: str
    branch_name: str
    developer_id: str = "unknown"
    policy_version: int
    risk: RiskLevel
    blocking_count: int
    high_count: int
    warning_count: int
    info_count: int
    changed_file_count: int
    changed_line_count: int
    triggered_rule_ids: list[str]
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
    policy_version: int
    risk: RiskLevel
    blocking_count: int
    high_count: int
    warning_count: int
    info_count: int
    changed_file_count: int
    changed_line_count: int
    triggered_rule_ids: list[str]
    generated_review_report: str
    mr_id: str | None = None
    commit_sha: str | None = None


class TriggeredRuleStat(BaseModel):
    """Aggregated triggered-rule count."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    trigger_count: int
