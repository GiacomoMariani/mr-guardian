"""Review finality update orchestration."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictBool

from mr_guardian.storage import ReviewHistoryStore


class ReviewFinalityError(Exception):
    """Base error for review finality failures."""


class ReviewFinalityNotFoundError(ReviewFinalityError):
    """Raised when a review cannot be found for finality updates."""


class ReviewFinalityPayload(BaseModel):
    """Input accepted by the review finality API."""

    model_config = ConfigDict(frozen=True)

    final: StrictBool


class ReviewFinalityUpdateResult(BaseModel):
    """Result returned after updating review finality."""

    model_config = ConfigDict(frozen=True)

    status: Literal["updated"]
    review_id: int
    is_final: bool
    ticket_key: str | None
    cleared_review_ids: list[int]


def review_finality_payload_schema() -> dict[str, Any]:
    """Return the JSON schema for finality update payloads."""
    return ReviewFinalityPayload.model_json_schema()


def set_stored_review_finality(
    *,
    review_id: int,
    is_final: bool,
    database_path: str | Path,
) -> ReviewFinalityUpdateResult:
    """Set a stored review's finality flag."""
    if review_id < 1:
        msg = "Review ID must be a positive integer."
        raise ValueError(msg)

    store = ReviewHistoryStore(database_path)
    try:
        try:
            record, cleared_review_ids = store.set_review_finality(
                review_id=review_id,
                is_final=is_final,
            )
        except KeyError as exc:
            msg = f"Review {review_id} was not found."
            raise ReviewFinalityNotFoundError(msg) from exc
    finally:
        store.close()

    return ReviewFinalityUpdateResult(
        status="updated",
        review_id=record.review_id,
        is_final=record.is_final,
        ticket_key=record.ticket_key,
        cleared_review_ids=cleared_review_ids,
    )
