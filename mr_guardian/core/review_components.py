"""Feed individual review components into an existing stored review run.

Each helper validates the target review ID, opens the history store, and maps a
missing review to :class:`ReviewComponentNotFoundError` so the API layer can return
a 404. List feeds are idempotent: re-feeding replaces the prior set for that review
(see ``ReviewHistoryStore.replace_*``). Parent counts/score on ``review_runs`` are
never recomputed here — the caller owns them via the review-creation payload.
"""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeVar

from mr_guardian.models.history import ReviewPolicySummary, ReviewRunRecord
from mr_guardian.models.review import (
    Finding,
    LlmDeveloperProfile,
    LlmReviewSummary,
    LlmRuleMetric,
    ReviewEvaluation,
)
from mr_guardian.storage import ReviewHistoryStore

T = TypeVar("T")


class ReviewComponentError(Exception):
    """Base error for review component feeds."""


class ReviewComponentNotFoundError(ReviewComponentError):
    """Raised when the target review run does not exist."""


def _run(
    review_id: int,
    database_path: str | Path,
    operation: Callable[[ReviewHistoryStore], T],
) -> T:
    if review_id < 1:
        msg = "Review ID must be a positive integer."
        raise ValueError(msg)

    store = ReviewHistoryStore(database_path)
    try:
        try:
            return operation(store)
        except KeyError as exc:
            msg = f"Review {review_id} was not found."
            raise ReviewComponentNotFoundError(msg) from exc
    finally:
        store.close()


def feed_review_findings(
    *,
    review_id: int,
    findings: Sequence[Finding],
    database_path: str | Path,
) -> ReviewRunRecord:
    """Replace the findings stored for one review run."""
    return _run(
        review_id,
        database_path,
        lambda store: store.replace_findings(review_id=review_id, findings=findings),
    )


def feed_review_triggered_rules(
    *,
    review_id: int,
    rule_ids: Sequence[str],
    database_path: str | Path,
) -> ReviewRunRecord:
    """Replace the triggered-rule IDs stored for one review run."""
    return _run(
        review_id,
        database_path,
        lambda store: store.replace_triggered_rules(
            review_id=review_id,
            rule_ids=rule_ids,
        ),
    )


def feed_review_evaluations(
    *,
    review_id: int,
    evaluations: Sequence[ReviewEvaluation],
    database_path: str | Path,
) -> ReviewRunRecord:
    """Replace the evaluation summaries stored for one review run."""
    return _run(
        review_id,
        database_path,
        lambda store: store.replace_evaluations(
            review_id=review_id,
            evaluations=evaluations,
        ),
    )


def feed_review_policy_summaries(
    *,
    review_id: int,
    policy_summaries: Sequence[ReviewPolicySummary],
    database_path: str | Path,
) -> ReviewRunRecord:
    """Replace the policy summaries stored for one review run."""
    return _run(
        review_id,
        database_path,
        lambda store: store.replace_policy_summaries(
            review_id=review_id,
            policy_summaries=policy_summaries,
        ),
    )


def feed_review_llm_metrics(
    *,
    review_id: int,
    metrics: Sequence[LlmRuleMetric],
    database_path: str | Path,
) -> ReviewRunRecord:
    """Replace the LLM rule metrics stored for one review run."""
    return _run(
        review_id,
        database_path,
        lambda store: store.replace_llm_metrics(review_id=review_id, metrics=metrics),
    )


def set_review_llm_summary(
    *,
    review_id: int,
    llm_summary: LlmReviewSummary,
    database_path: str | Path,
) -> ReviewRunRecord:
    """Attach (or overwrite) the LLM review summary for one review run."""
    return _run(
        review_id,
        database_path,
        lambda store: store.set_llm_summary(
            review_id=review_id,
            llm_summary=llm_summary,
        ),
    )


def set_review_developer_profile(
    *,
    review_id: int,
    developer_profile: LlmDeveloperProfile,
    database_path: str | Path,
) -> ReviewRunRecord:
    """Attach (or overwrite) the developer profile snapshot for one review run."""
    return _run(
        review_id,
        database_path,
        lambda store: store.update_developer_profile(
            review_id=review_id,
            developer_profile=developer_profile,
        ),
    )
