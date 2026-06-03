"""Typed project-manager dashboard models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mr_guardian.models.review import RiskLevel

PmTicketStatusValue = Literal["fail", "pass_with_warnings", "pass"]
PmDeliveryState = Literal["approved", "observed"]


class PmTicketStatus(BaseModel):
    """Current PM-facing status for one ticket."""

    model_config = ConfigDict(frozen=True)

    ticket_key: str
    status: PmTicketStatusValue
    latest_review_at: datetime
    assumed_deployed_at: datetime
    delivery_state: PmDeliveryState
    approved_at: datetime | None = None
    latest_risk: RiskLevel
    review_request_count: int = Field(ge=0)
    average_score: float
    blocker_reason: str | None = None


class PmRecurringBlocker(BaseModel):
    """Recurring blocker signal across ticket-linked review history."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    affected_ticket_count: int = Field(ge=0)
    review_run_count: int = Field(ge=0)
    highest_severity_seen: RiskLevel


class PmDashboardSummary(BaseModel):
    """PM-facing delivery summary for a review-history window."""

    model_config = ConfigDict(frozen=True)

    start_at: datetime
    end_at: datetime
    total_ticket_count: int = Field(ge=0)
    pass_count: int = Field(ge=0)
    pass_with_warnings_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=100)
    blocked_ticket_count: int = Field(ge=0)
    unlinked_review_count: int = Field(ge=0)
    tickets: list[PmTicketStatus]
    recurring_blockers: list[PmRecurringBlocker]
