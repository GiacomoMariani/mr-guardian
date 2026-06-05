"""Typed weekly LLM review models."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WeeklyLlmReviewResult = Literal[
    "optimal",
    "on_track",
    "needs_attention",
    "at_risk",
    "blocked",
]


class WeeklyLlmReviewCreate(BaseModel):
    """Payload accepted when storing a weekly LLM review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    week_start: date
    week_end: date
    created_at: datetime | None = None
    result: WeeklyLlmReviewResult
    score: int = Field(ge=1, le=100)
    summary: str
    mr_count: int = Field(ge=0)
    developer_count: int = Field(ge=0)
    ticket_count: int = Field(ge=0)
    approved_ticket_count: int = Field(ge=0)
    observed_ticket_count: int = Field(ge=0)
    blocking_review_count: int = Field(ge=0)
    high_risk_review_count: int = Field(ge=0)
    warning_review_count: int = Field(ge=0)
    info_review_count: int = Field(ge=0)
    top_risks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    provider: str
    model: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    currency: str = "USD"

    @field_validator("summary", "provider", "model")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        """Trim and reject empty text fields."""
        clean_value = value.strip()
        if not clean_value:
            msg = "Field must not be empty."
            raise ValueError(msg)
        return clean_value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        """Normalize and validate a three-letter currency code."""
        clean_value = value.strip().upper()
        if len(clean_value) != 3 or not clean_value.isalpha():
            msg = "Currency must be a three-letter code."
            raise ValueError(msg)
        return clean_value

    @field_validator("top_risks", "recommended_actions")
    @classmethod
    def validate_text_items(cls, value: list[str]) -> list[str]:
        """Trim and reject empty list items."""
        clean_items: list[str] = []
        for item in value:
            clean_item = item.strip()
            if not clean_item:
                msg = "List items must not be empty."
                raise ValueError(msg)
            clean_items.append(clean_item)
        return clean_items

    @model_validator(mode="after")
    def validate_week_and_tokens(self) -> "WeeklyLlmReviewCreate":
        """Validate weekly boundaries and token totals."""
        if self.week_start.weekday() != 0:
            msg = "week_start must be a Monday."
            raise ValueError(msg)
        if self.week_end.weekday() != 6:
            msg = "week_end must be a Sunday."
            raise ValueError(msg)
        if self.week_end <= self.week_start:
            msg = "week_end must be after week_start."
            raise ValueError(msg)
        if (
            self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens is not None
            and self.total_tokens < self.input_tokens + self.output_tokens
        ):
            msg = "total_tokens must be at least input_tokens plus output_tokens."
            raise ValueError(msg)
        return self


class WeeklyLlmReviewRecord(BaseModel):
    """A stored weekly LLM review."""

    model_config = ConfigDict(frozen=True)

    weekly_review_id: int
    week_start: date
    week_end: date
    created_at: datetime
    result: WeeklyLlmReviewResult
    score: int = Field(ge=1, le=100)
    summary: str
    mr_count: int = Field(ge=0)
    developer_count: int = Field(ge=0)
    ticket_count: int = Field(ge=0)
    approved_ticket_count: int = Field(ge=0)
    observed_ticket_count: int = Field(ge=0)
    blocking_review_count: int = Field(ge=0)
    high_risk_review_count: int = Field(ge=0)
    warning_review_count: int = Field(ge=0)
    info_review_count: int = Field(ge=0)
    top_risks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    provider: str
    model: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    currency: str = "USD"


def weekly_llm_review_payload_schema() -> dict[str, Any]:
    """Return the JSON schema for manual weekly LLM review payloads."""
    schema = WeeklyLlmReviewCreate.model_json_schema()
    schema["x-storage-notes"] = {
        "created_at": (
            "Optional on ingestion. When omitted, MR Guardian stores the current "
            "UTC timestamp."
        ),
        "weekly_review_id": "Assigned by SQLite after the weekly review is stored.",
        "week_start": "Must be a Monday.",
        "week_end": "Must be the following Sunday.",
        "score": "LLM-calculated weekly assessment from 1 to 100.",
        "estimated_cost_usd": (
            "Estimated provider cost for generating this weekly review; token "
            "counts remain the primary usage metric."
        ),
    }
    return schema
