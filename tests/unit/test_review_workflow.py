from pathlib import Path

import pytest

from mr_guardian.core.review import ReviewRequest, review_merge_request
from mr_guardian.models.policy import Policy
from mr_guardian.models.review import EngineReviewResult, FindingCounts
from mr_guardian.models.review_input import ReviewInput


def test_review_merge_request_passes_metadata_to_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_path = tmp_path / "policy.yml"
    policy_path.write_text("version: 1\nrules: []\n", encoding="utf-8")
    captured_review_input: ReviewInput | None = None

    class FakeGitProvider:
        def __init__(self, repo_path: str | Path = ".") -> None:
            self.repo_path = repo_path

        def collect(self, base_ref: str) -> ReviewInput:
            return ReviewInput(base_ref=base_ref, changed_files=[])

    def fake_run_review(
        *,
        policy: Policy,
        review_input: ReviewInput,
        rule_registry,
    ) -> EngineReviewResult:
        nonlocal captured_review_input
        captured_review_input = review_input
        return EngineReviewResult(risk="none", findings=[], counts=FindingCounts())

    monkeypatch.setattr("mr_guardian.core.review.LocalGitProvider", FakeGitProvider)
    monkeypatch.setattr("mr_guardian.core.review.run_review", fake_run_review)

    result = review_merge_request(
        ReviewRequest(
            base="main",
            policy_path=policy_path,
            title="Add movement",
            description="## Test Plan\n- Ran",
        )
    )

    assert result.review_input.title == "Add movement"
    assert result.review_input.description == "## Test Plan\n- Ran"
    assert captured_review_input is not None
    assert captured_review_input.title == "Add movement"
