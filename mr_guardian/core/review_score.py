"""Deterministic review scoring."""

from mr_guardian.models.review import FindingCounts

BLOCKING_PENALTY = 35
HIGH_PENALTY = 15
WARNING_PENALTY = 5
INFO_PENALTY = 1


def calculate_review_score(
    *,
    blocking_count: int,
    high_count: int,
    warning_count: int,
    info_count: int,
) -> int:
    """Calculate a stable review score from finding severity counts."""
    raw_score = (
        100
        - (blocking_count * BLOCKING_PENALTY)
        - (high_count * HIGH_PENALTY)
        - (warning_count * WARNING_PENALTY)
        - (info_count * INFO_PENALTY)
    )
    return max(0, min(100, raw_score))


def calculate_review_score_from_counts(counts: FindingCounts) -> int:
    """Calculate a stable review score from a finding count model."""
    return calculate_review_score(
        blocking_count=counts.blocking,
        high_count=counts.high,
        warning_count=counts.warning,
        info_count=counts.info,
    )
