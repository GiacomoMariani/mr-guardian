from datetime import date

import pytest
from pydantic import ValidationError

from mr_guardian.models.weekly_review import WeeklyLlmReviewCreate


def valid_weekly_review_payload() -> dict[str, object]:
    return {
        "week_start": date(2026, 6, 1),
        "week_end": date(2026, 6, 7),
        "result": "on_track",
        "score": 84,
        "summary": "The week is on track.",
        "mr_count": 12,
        "developer_count": 4,
        "ticket_count": 7,
        "approved_ticket_count": 5,
        "observed_ticket_count": 2,
        "blocking_review_count": 1,
        "high_risk_review_count": 2,
        "warning_review_count": 3,
        "info_review_count": 4,
        "top_risks": ["High-risk reviews remain."],
        "recommended_actions": ["Resolve the remaining high-risk reviews."],
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "input_tokens": 1200,
        "output_tokens": 240,
        "total_tokens": 1440,
        "estimated_cost_usd": 0.0031,
    }


def test_validates_weekly_llm_review_payload() -> None:
    payload = WeeklyLlmReviewCreate.model_validate(valid_weekly_review_payload())

    assert payload.week_start == date(2026, 6, 1)
    assert payload.week_end == date(2026, 6, 7)
    assert payload.score == 84
    assert payload.currency == "USD"


def test_rejects_non_monday_week_start() -> None:
    payload = valid_weekly_review_payload()
    payload["week_start"] = date(2026, 6, 2)

    with pytest.raises(ValidationError, match="week_start must be a Monday"):
        WeeklyLlmReviewCreate.model_validate(payload)


def test_rejects_non_sunday_week_end() -> None:
    payload = valid_weekly_review_payload()
    payload["week_end"] = date(2026, 6, 6)

    with pytest.raises(ValidationError, match="week_end must be a Sunday"):
        WeeklyLlmReviewCreate.model_validate(payload)


def test_rejects_score_outside_supported_range() -> None:
    payload = valid_weekly_review_payload()
    payload["score"] = 0

    with pytest.raises(ValidationError):
        WeeklyLlmReviewCreate.model_validate(payload)


def test_rejects_invalid_token_total() -> None:
    payload = valid_weekly_review_payload()
    payload["total_tokens"] = 100

    with pytest.raises(ValidationError, match="total_tokens must be at least"):
        WeeklyLlmReviewCreate.model_validate(payload)


def test_rejects_invalid_result() -> None:
    payload = valid_weekly_review_payload()
    payload["result"] = "green"

    with pytest.raises(ValidationError):
        WeeklyLlmReviewCreate.model_validate(payload)
