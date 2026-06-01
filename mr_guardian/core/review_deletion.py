"""Review history deletion orchestration."""

from pathlib import Path

from mr_guardian.storage import ReviewHistoryStore


class ReviewDeletionError(Exception):
    """Base error for review deletion failures."""


class ReviewNotFoundError(ReviewDeletionError):
    """Raised when a review cannot be found for deletion."""


def delete_stored_review(
    *,
    review_id: int,
    database_path: str | Path,
) -> int:
    """Delete one stored review from history and return its review ID."""
    if review_id < 1:
        msg = "Review ID must be a positive integer."
        raise ValueError(msg)

    store = ReviewHistoryStore(database_path)
    try:
        deleted = store.delete_review_run(review_id)
    finally:
        store.close()

    if not deleted:
        msg = f"Review {review_id} was not found."
        raise ReviewNotFoundError(msg)
    return review_id
