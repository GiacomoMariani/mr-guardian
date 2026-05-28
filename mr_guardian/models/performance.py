"""Typed developer performance models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeveloperActivity(BaseModel):
    """Recent activity summary for one developer."""

    model_config = ConfigDict(frozen=True)

    developer_id: str
    last_review_at: datetime
    review_request_count: int = Field(ge=0)
    average_score: float | None = None


class TicketPerformanceSummary(BaseModel):
    """Review performance for one ticket."""

    model_config = ConfigDict(frozen=True)

    ticket_key: str
    mr_request_count: int = Field(ge=0)
    first_request_at: datetime
    last_request_at: datetime
    total_review_days: float = Field(ge=0)
    assumed_deployed_at: datetime
    average_score: float


class DeveloperPerformanceSummary(BaseModel):
    """Developer performance across a lookback window."""

    model_config = ConfigDict(frozen=True)

    developer_id: str
    start_at: datetime
    end_at: datetime
    review_request_count: int = Field(ge=0)
    average_score: float | None = None
    tickets: list[TicketPerformanceSummary]
