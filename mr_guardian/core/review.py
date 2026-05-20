"""Review orchestration entry points."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ReviewRequest(BaseModel):
    """Inputs needed to run a merge request review."""

    model_config = ConfigDict(frozen=True)

    base: str
    policy_path: Path


class ReviewResult(BaseModel):
    """Result of a merge request review."""

    model_config = ConfigDict(frozen=True)

    risk: str
    message: str


def review_merge_request(request: ReviewRequest) -> ReviewResult:
    """Run the review engine and return a placeholder result."""
    _ = request
    return ReviewResult(
        risk="Unknown",
        message="No rules have been implemented yet.",
    )

