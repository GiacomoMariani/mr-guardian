"""Core helpers for externally supplied biweekly developer LLM reviews."""

from pathlib import Path
from typing import Any

from mr_guardian.models.developer_review import (
    DeveloperLlmReviewCreate,
    DeveloperLlmReviewRecord,
    developer_llm_review_payload_schema,
)
from mr_guardian.storage import ReviewHistoryStore


def store_developer_llm_review_payload(
    payload: DeveloperLlmReviewCreate,
    *,
    database_path: str | Path,
) -> DeveloperLlmReviewRecord:
    """Validate and store one biweekly developer LLM review payload."""
    store = ReviewHistoryStore(database_path)
    try:
        return store.store_developer_llm_review(payload)
    finally:
        store.close()


def load_latest_developer_llm_review(
    database_path: str | Path,
    *,
    developer_id: str,
) -> DeveloperLlmReviewRecord | None:
    """Load the latest stored biweekly developer LLM review for one developer."""
    store = ReviewHistoryStore(database_path)
    try:
        return store.latest_developer_llm_review(developer_id)
    finally:
        store.close()


def load_recent_developer_llm_reviews(
    database_path: str | Path,
    *,
    developer_id: str | None = None,
    limit: int = 20,
) -> list[DeveloperLlmReviewRecord]:
    """Load stored biweekly developer LLM reviews, most recent first."""
    store = ReviewHistoryStore(database_path)
    try:
        return store.recent_developer_llm_reviews(developer_id=developer_id, limit=limit)
    finally:
        store.close()


def load_developer_llm_review(
    database_path: str | Path,
    developer_review_id: int,
) -> DeveloperLlmReviewRecord | None:
    """Load one stored biweekly developer LLM review by ID, or None if it does not exist."""
    store = ReviewHistoryStore(database_path)
    try:
        return store.find_developer_llm_review(developer_review_id)
    finally:
        store.close()


def manual_developer_llm_review_payload_schema() -> dict[str, Any]:
    """Return the JSON schema for manual biweekly developer LLM review ingestion."""
    return developer_llm_review_payload_schema()
