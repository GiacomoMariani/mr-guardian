"""Core helpers for externally supplied weekly LLM reviews."""

from pathlib import Path
from typing import Any

from mr_guardian.models.weekly_review import (
    WeeklyLlmReviewCreate,
    WeeklyLlmReviewRecord,
    weekly_llm_review_payload_schema,
)
from mr_guardian.storage import ReviewHistoryStore


def store_weekly_llm_review_payload(
    payload: WeeklyLlmReviewCreate,
    *,
    database_path: str | Path,
) -> WeeklyLlmReviewRecord:
    """Validate and store one weekly LLM review payload."""
    store = ReviewHistoryStore(database_path)
    try:
        return store.store_weekly_llm_review(payload)
    finally:
        store.close()


def load_latest_weekly_llm_review(
    database_path: str | Path,
) -> WeeklyLlmReviewRecord | None:
    """Load the latest stored weekly LLM review."""
    store = ReviewHistoryStore(database_path)
    try:
        return store.latest_weekly_llm_review()
    finally:
        store.close()


def manual_weekly_llm_review_payload_schema() -> dict[str, Any]:
    """Return the JSON schema for manual weekly LLM review ingestion."""
    return weekly_llm_review_payload_schema()
