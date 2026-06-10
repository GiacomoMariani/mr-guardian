"""Full history-reset orchestration."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mr_guardian.storage import ReviewHistoryStore


class HistoryResetResult(BaseModel):
    """Counts of data removed by a full reset."""

    model_config = ConfigDict(frozen=True)

    status: Literal["reset"] = "reset"
    reviews: int
    weekly_reviews: int
    developer_reviews: int
    eta_notes: int


def reset_all_history(*, database_path: str | Path) -> HistoryResetResult:
    """Delete all stored data (reviews, weekly + developer reviews, ETA notes) and return counts."""
    store = ReviewHistoryStore(database_path)
    try:
        counts = store.reset_all()
    finally:
        store.close()
    return HistoryResetResult(
        reviews=counts["reviews"],
        weekly_reviews=counts["weekly_reviews"],
        developer_reviews=counts["developer_reviews"],
        eta_notes=counts["eta_notes"],
    )
