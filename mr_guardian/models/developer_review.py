"""Typed biweekly developer LLM review models."""

from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DeveloperLlmReviewResult = Literal[
    "optimal",
    "on_track",
    "needs_attention",
    "at_risk",
    "blocked",
]

# A Monday start plus 13 days lands on the second Sunday — a fixed 2-week window.
PERIOD_LENGTH_DAYS = 13


class DeveloperLlmReviewCreate(BaseModel):
    """Payload accepted when storing a biweekly developer LLM review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    developer_id: str
    period_start: date
    period_end: date
    created_at: datetime | None = None
    result: DeveloperLlmReviewResult
    score: int = Field(ge=1, le=100)
    summary: str
    review_request_count: int = Field(ge=0)
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

    @field_validator("developer_id", "summary", "provider", "model")
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
    def validate_period_and_tokens(self) -> "DeveloperLlmReviewCreate":
        """Validate the 2-week period boundaries and token totals."""
        if self.period_start.weekday() != 0:
            msg = "period_start must be a Monday."
            raise ValueError(msg)
        if self.period_end != self.period_start + timedelta(days=PERIOD_LENGTH_DAYS):
            msg = "period_end must be the Sunday 13 days after period_start (a 2-week window)."
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


class DeveloperLlmReviewRecord(BaseModel):
    """A stored biweekly developer LLM review."""

    model_config = ConfigDict(frozen=True)

    developer_review_id: int
    developer_id: str
    period_start: date
    period_end: date
    created_at: datetime
    result: DeveloperLlmReviewResult
    score: int = Field(ge=1, le=100)
    summary: str
    review_request_count: int = Field(ge=0)
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


def developer_llm_review_payload_schema() -> dict[str, Any]:
    """Return the JSON schema for manual biweekly developer LLM review payloads."""
    schema = DeveloperLlmReviewCreate.model_json_schema()
    schema["x-storage-notes"] = {
        "created_at": (
            "Optional on ingestion. When omitted, MR Guardian stores the current UTC timestamp."
        ),
        "developer_review_id": "Assigned by SQLite after the review is stored.",
        "period_start": "Must be a Monday.",
        "period_end": "Must be the Sunday 13 days after period_start (a 2-week window).",
        "score": "LLM-calculated developer assessment from 1 to 100.",
        "estimated_cost_usd": (
            "Estimated provider cost for generating this developer review; token counts "
            "remain the primary usage metric."
        ),
    }
    return schema
