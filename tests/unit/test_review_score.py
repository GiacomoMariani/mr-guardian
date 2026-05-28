from mr_guardian.core.review_score import calculate_review_score


def test_calculates_review_score_from_severity_counts() -> None:
    score = calculate_review_score(
        blocking_count=1,
        high_count=1,
        warning_count=2,
        info_count=3,
    )

    assert score == 37


def test_review_score_is_clamped_between_zero_and_one_hundred() -> None:
    assert calculate_review_score(
        blocking_count=0,
        high_count=0,
        warning_count=0,
        info_count=0,
    ) == 100
    assert calculate_review_score(
        blocking_count=10,
        high_count=10,
        warning_count=10,
        info_count=10,
    ) == 0
