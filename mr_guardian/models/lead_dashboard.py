"""Typed technical-lead dashboard models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mr_guardian.models.history import ReviewRunRecord
from mr_guardian.models.policy import EvaluationDimension
from mr_guardian.models.review import FindingCounts, RiskLevel

TrendDirection = Literal["improving", "declining", "stable", "insufficient_data"]


class LeadRepeatedRule(BaseModel):
    """Repeated triggered rule for one developer."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    review_run_count: int = Field(ge=0)
    latest_review_at: datetime


class LeadEvaluationSummary(BaseModel):
    """Evaluation-dimension summary for one developer."""

    model_config = ConfigDict(frozen=True)

    evaluation: EvaluationDimension
    review_count: int = Field(ge=0)
    average_score: float | None = None
    counts: FindingCounts


class LeadTicketAttemptSummary(BaseModel):
    """Ticket-level review attempt summary for one developer."""

    model_config = ConfigDict(frozen=True)

    ticket_key: str
    review_attempt_count: int = Field(ge=0)
    first_review_at: datetime
    latest_review_at: datetime
    assumed_deployed_at: datetime
    is_approved: bool = False
    approved_at: datetime | None = None
    attempts_to_approval: int | None = Field(default=None, ge=0)
    average_score: float
    latest_risk: RiskLevel


class LeadDeveloperSummary(BaseModel):
    """Technical lead summary for one developer."""

    model_config = ConfigDict(frozen=True)

    developer_id: str
    review_request_count: int = Field(ge=0)
    ticket_count: int = Field(ge=0)
    average_attempts_per_ticket: float = Field(ge=0)
    approved_ticket_count: int = Field(ge=0)
    average_attempts_to_approval: float | None = None
    average_score: float | None = None
    total_estimated_cost_usd: float | None = None
    total_tokens: int | None = None
    currency: str = "USD"
    latest_review_at: datetime
    trend_direction: TrendDirection
    multi_attempt_ticket_count: int = Field(ge=0)
    repeated_rule_count: int = Field(ge=0)
    unlinked_review_count: int = Field(ge=0)
    tickets: list[LeadTicketAttemptSummary]
    repeated_rules: list[LeadRepeatedRule]
    evaluation_summaries: list[LeadEvaluationSummary]


class LeadDashboardSummary(BaseModel):
    """Technical lead dashboard data for a review-history window."""

    model_config = ConfigDict(frozen=True)

    start_at: datetime
    end_at: datetime
    total_estimated_cost_usd: float | None = None
    total_tokens: int | None = None
    currency: str = "USD"
    developers: list[LeadDeveloperSummary]


class LeadDeveloperDetail(BaseModel):
    """Developer-focused detail page data."""

    model_config = ConfigDict(frozen=True)

    start_at: datetime
    end_at: datetime
    developer: LeadDeveloperSummary
    review_runs: list[ReviewRunRecord]
