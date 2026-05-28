from pathlib import Path

from mr_guardian.core.review import ReviewResult
from mr_guardian.core.review_history import store_review_result
from mr_guardian.models.review import EngineReviewResult, FindingCounts
from mr_guardian.models.review_input import ReviewInput


def test_store_review_result_extracts_ticket_key_from_title_only(tmp_path: Path) -> None:
    result = ReviewResult(
        base_ref="feature/TK-999-branch",
        policy_directory=tmp_path,
        policy_results=[],
        developer_id="Test User",
        review_input=ReviewInput(
            base_ref="main",
            title="TK-234 Add validation",
            description="References TK-888 in the description.",
            changed_files=[],
        ),
        engine_result=EngineReviewResult(
            risk="none",
            findings=[],
            counts=FindingCounts(),
        ),
    )

    record = store_review_result(
        result,
        report="## MR Guardian Review\n",
        database_path=tmp_path / "history.sqlite",
        review_scope="local-all-policies",
    )

    assert record.ticket_key == "TK-234"


def test_store_review_result_does_not_extract_ticket_from_branch_or_description(
    tmp_path: Path,
) -> None:
    result = ReviewResult(
        base_ref="feature/TK-999-branch",
        policy_directory=tmp_path,
        policy_results=[],
        developer_id="Test User",
        review_input=ReviewInput(
            base_ref="main",
            title="Add validation",
            description="References TK-888 in the description.",
            changed_files=[],
        ),
        engine_result=EngineReviewResult(
            risk="none",
            findings=[],
            counts=FindingCounts(),
        ),
    )

    record = store_review_result(
        result,
        report="## MR Guardian Review\n",
        database_path=tmp_path / "history.sqlite",
        review_scope="local-all-policies",
    )

    assert record.ticket_key is None
