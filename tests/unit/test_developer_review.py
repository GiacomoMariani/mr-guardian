from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from mr_guardian.core.developer_review import (
    load_developer_llm_review,
    load_latest_developer_llm_review,
    load_recent_developer_llm_reviews,
    store_developer_llm_review_payload,
)
from mr_guardian.models.developer_review import DeveloperLlmReviewCreate

# A valid 2-week window: Monday 2026-06-01 .. Sunday 2026-06-14.
PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 14)


def make_payload(**overrides: Any) -> DeveloperLlmReviewCreate:
    data: dict[str, Any] = dict(
        developer_id="Jack",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        result="on_track",
        score=92,
        summary="Steady fortnight; one warning cleared.",
        review_request_count=4,
        ticket_count=3,
        approved_ticket_count=2,
        observed_ticket_count=1,
        blocking_review_count=0,
        high_risk_review_count=0,
        warning_review_count=2,
        info_review_count=3,
        top_risks=["UNITY-ODIN-FIELD-LLM-001"],
        recommended_actions=["Maintain current review hygiene."],
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=1500,
        output_tokens=300,
        total_tokens=1800,
        estimated_cost_usd=0.0011,
    )
    data.update(overrides)
    return DeveloperLlmReviewCreate(**data)


def test_valid_payload_round_trips(tmp_path: Path) -> None:
    db = tmp_path / "history.sqlite"
    record = store_developer_llm_review_payload(make_payload(), database_path=db)

    assert record.developer_review_id >= 1
    assert record.developer_id == "Jack"
    assert record.period_start == PERIOD_START
    assert record.period_end == PERIOD_END
    assert record.score == 92
    assert record.estimated_cost_usd == 0.0011
    assert record.currency == "USD"
    assert record.total_tokens == 1800
    assert record.top_risks == ["UNITY-ODIN-FIELD-LLM-001"]


def test_period_start_must_be_monday() -> None:
    with pytest.raises(ValidationError, match="Monday"):
        make_payload(period_start=date(2026, 6, 2), period_end=date(2026, 6, 15))


def test_period_end_must_be_two_weeks_after_start() -> None:
    with pytest.raises(ValidationError, match="2-week"):
        make_payload(period_end=date(2026, 6, 7))  # one week, not two


def test_total_tokens_must_cover_input_plus_output() -> None:
    with pytest.raises(ValidationError, match="total_tokens"):
        make_payload(input_tokens=1000, output_tokens=500, total_tokens=1000)


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        make_payload(phase="Beta Phase")  # not a field -> extra="forbid"


def test_latest_and_recent_per_developer(tmp_path: Path) -> None:
    db = tmp_path / "history.sqlite"
    store_developer_llm_review_payload(make_payload(developer_id="Jack"), database_path=db)
    store_developer_llm_review_payload(
        make_payload(
            developer_id="Jack",
            period_start=date(2026, 6, 15),
            period_end=date(2026, 6, 28),
            summary="Later fortnight.",
        ),
        database_path=db,
    )
    store_developer_llm_review_payload(make_payload(developer_id="Nick"), database_path=db)

    latest_jack = load_latest_developer_llm_review(db, developer_id="Jack")
    assert latest_jack is not None
    assert latest_jack.period_start == date(2026, 6, 15)

    jack_all = load_recent_developer_llm_reviews(db, developer_id="Jack")
    assert [r.period_start for r in jack_all] == [date(2026, 6, 15), date(2026, 6, 1)]

    everyone = load_recent_developer_llm_reviews(db)
    assert len(everyone) == 3

    by_id = load_developer_llm_review(db, jack_all[0].developer_review_id)
    assert by_id is not None
    assert by_id.developer_id == "Jack"
    assert load_developer_llm_review(db, 9999) is None


def test_latest_is_none_when_no_reviews(tmp_path: Path) -> None:
    db = tmp_path / "history.sqlite"
    assert load_latest_developer_llm_review(db, developer_id="Jack") is None
