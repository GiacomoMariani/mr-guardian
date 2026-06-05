from pathlib import Path

import pytest

from mr_guardian.core.review import ReviewRequest, review_merge_request
from mr_guardian.models.policy import Policy
from mr_guardian.models.review import EngineReviewResult, Finding, FindingCounts
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.summarizer_ai import LlmReviewSummaryOutput, ReviewSummaryInput


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

        def developer_id(self) -> str:
            return "Test User"

    def fake_run_review(
        *,
        policy: Policy,
        review_input: ReviewInput,
        rule_registry,
        llm_rule_runner,
        repo_root=None,
    ) -> EngineReviewResult:
        nonlocal captured_review_input
        captured_review_input = review_input
        return EngineReviewResult(risk="none", findings=[], counts=FindingCounts())

    monkeypatch.setattr("mr_guardian.core.review.LocalGitProvider", FakeGitProvider)
    monkeypatch.setattr("mr_guardian.core.review.run_review", fake_run_review)

    result = review_merge_request(
        ReviewRequest(
            base="main",
            policy_directory=tmp_path,
            title="Add movement",
            description="## Test Plan\n- Ran",
        )
    )

    assert result.review_input.title == "Add movement"
    assert result.review_input.description == "## Test Plan\n- Ran"
    assert result.review_input.review_scope == "local-all-policies"
    assert result.developer_id == "Test User"
    assert result.policy_results[0].policy_path == policy_path
    assert captured_review_input is not None
    assert captured_review_input.title == "Add movement"


def test_review_merge_request_passes_review_scope_to_review_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_path = tmp_path / "policy.yml"
    policy_path.write_text("version: 1\nrules: []\n", encoding="utf-8")

    class FakeGitProvider:
        def __init__(self, repo_path: str | Path = ".") -> None:
            self.repo_path = repo_path

        def collect(self, base_ref: str) -> ReviewInput:
            return ReviewInput(base_ref=base_ref, changed_files=[])

        def developer_id(self) -> str:
            return "Test User"

    def fake_run_review(
        *,
        policy: Policy,
        review_input: ReviewInput,
        rule_registry,
        llm_rule_runner,
        repo_root=None,
    ) -> EngineReviewResult:
        assert review_input.review_scope == "gitlab-webhook"
        return EngineReviewResult(risk="none", findings=[], counts=FindingCounts())

    monkeypatch.setattr("mr_guardian.core.review.LocalGitProvider", FakeGitProvider)
    monkeypatch.setattr("mr_guardian.core.review.run_review", fake_run_review)

    result = review_merge_request(
        ReviewRequest(
            base="main",
            policy_directory=tmp_path,
            review_scope="gitlab-webhook",
        )
    )

    assert result.review_input.review_scope == "gitlab-webhook"


def test_review_merge_request_combines_multiple_policy_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "first.yml").write_text("version: 1\nrules: []\n", encoding="utf-8")
    (tmp_path / "second.yml").write_text("version: 2\nrules: []\n", encoding="utf-8")

    class FakeGitProvider:
        def __init__(self, repo_path: str | Path = ".") -> None:
            self.repo_path = repo_path

        def collect(self, base_ref: str) -> ReviewInput:
            return ReviewInput(base_ref=base_ref, changed_files=[])

        def developer_id(self) -> str:
            return "Test User"

    def fake_run_review(
        *,
        policy: Policy,
        review_input: ReviewInput,
        rule_registry,
        llm_rule_runner,
        repo_root=None,
    ) -> EngineReviewResult:
        finding = Finding(
            rule_id=f"POLICY-{policy.version}",
            severity="warning" if policy.version == 1 else "high",
            message="finding",
            source="policy.yml#rule",
        )
        return EngineReviewResult(
            risk="warning" if policy.version == 1 else "high",
            findings=[finding],
            counts=FindingCounts(
                warning=1 if policy.version == 1 else 0,
                high=1 if policy.version == 2 else 0,
            ),
        )

    monkeypatch.setattr("mr_guardian.core.review.LocalGitProvider", FakeGitProvider)
    monkeypatch.setattr("mr_guardian.core.review.run_review", fake_run_review)

    result = review_merge_request(ReviewRequest(base="main", policy_directory=tmp_path))

    assert len(result.policy_results) == 2
    assert result.policy_version == 2
    assert result.engine_result.counts.warning == 1
    assert result.engine_result.counts.high == 1
    assert result.engine_result.risk == "high"


def test_review_merge_request_attaches_llm_summary_without_changing_review_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "policy.yml").write_text("version: 1\nrules: []\n", encoding="utf-8")
    captured_summary_input: ReviewSummaryInput | None = None

    class FakeGitProvider:
        def __init__(self, repo_path: str | Path = ".") -> None:
            self.repo_path = repo_path

        def collect(self, base_ref: str) -> ReviewInput:
            return ReviewInput(base_ref=base_ref, changed_files=[])

        def developer_id(self) -> str:
            return "Test User"

    class FakeSummaryRunner:
        @property
        def provider_name(self) -> str:
            return "test-provider"

        @property
        def model_name(self) -> str:
            return "test-model"

        @property
        def last_token_usage(self):
            return None

        def summarize(
            self,
            *,
            review: ReviewSummaryInput,
            max_chars: int,
        ) -> LlmReviewSummaryOutput:
            nonlocal captured_summary_input
            captured_summary_input = review
            assert max_chars == 200
            return LlmReviewSummaryOutput(summary="Review summary.", score=84)

    def fake_run_review(
        *,
        policy: Policy,
        review_input: ReviewInput,
        rule_registry,
        llm_rule_runner,
        repo_root=None,
    ) -> EngineReviewResult:
        finding = Finding(
            rule_id="PYTHON-PRINT-001",
            severity="warning",
            message="print calls should not be introduced.",
            source="python-policy.yml#PYTHON-PRINT-001",
        )
        return EngineReviewResult(
            risk="warning",
            findings=[finding],
            counts=FindingCounts(warning=1),
        )

    monkeypatch.setattr("mr_guardian.core.review.LocalGitProvider", FakeGitProvider)
    monkeypatch.setattr("mr_guardian.core.review.run_review", fake_run_review)

    result = review_merge_request(
        ReviewRequest(base="main", policy_directory=tmp_path),
        llm_summary_runner=FakeSummaryRunner(),
        llm_summary_max_chars=200,
    )

    assert result.risk == "warning"
    assert result.engine_result.counts.warning == 1
    assert [finding.rule_id for finding in result.engine_result.findings] == [
        "PYTHON-PRINT-001"
    ]
    assert result.llm_summary is not None
    assert result.llm_summary.status == "succeeded"
    assert result.llm_summary.text == "Review summary."
    assert result.llm_summary.score == 84
    assert result.llm_summary.provider == "test-provider"
    assert captured_summary_input is not None
    assert captured_summary_input.risk == "warning"


def test_review_merge_request_records_llm_summary_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "policy.yml").write_text("version: 1\nrules: []\n", encoding="utf-8")

    class FakeGitProvider:
        def __init__(self, repo_path: str | Path = ".") -> None:
            self.repo_path = repo_path

        def collect(self, base_ref: str) -> ReviewInput:
            return ReviewInput(base_ref=base_ref, changed_files=[])

        def developer_id(self) -> str:
            return "Test User"

    class FailingSummaryRunner:
        @property
        def provider_name(self) -> str:
            return "test-provider"

        @property
        def model_name(self) -> str:
            return "test-model"

        @property
        def last_token_usage(self):
            return None

        def summarize(
            self,
            *,
            review: ReviewSummaryInput,
            max_chars: int,
        ) -> LlmReviewSummaryOutput:
            raise RuntimeError("summary failed")

    def fake_run_review(
        *,
        policy: Policy,
        review_input: ReviewInput,
        rule_registry,
        llm_rule_runner,
        repo_root=None,
    ) -> EngineReviewResult:
        return EngineReviewResult(risk="none", findings=[], counts=FindingCounts())

    monkeypatch.setattr("mr_guardian.core.review.LocalGitProvider", FakeGitProvider)
    monkeypatch.setattr("mr_guardian.core.review.run_review", fake_run_review)

    result = review_merge_request(
        ReviewRequest(base="main", policy_directory=tmp_path),
        llm_summary_runner=FailingSummaryRunner(),
    )

    assert result.risk == "none"
    assert result.llm_summary is not None
    assert result.llm_summary.status == "failed"
    assert result.llm_summary.text is None
    assert result.llm_summary.error_message == "summary failed"


def test_review_merge_request_uses_packaged_default_policies_when_repo_defaults_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    class FakeGitProvider:
        def __init__(self, repo_path: str | Path = ".") -> None:
            self.repo_path = repo_path

        def collect(self, base_ref: str) -> ReviewInput:
            return ReviewInput(base_ref=base_ref, changed_files=[])

        def developer_id(self) -> str:
            return "Test User"

    def fake_run_review(
        *,
        policy: Policy,
        review_input: ReviewInput,
        rule_registry,
        llm_rule_runner,
        repo_root=None,
    ) -> EngineReviewResult:
        return EngineReviewResult(risk="none", findings=[], counts=FindingCounts())

    monkeypatch.setattr("mr_guardian.core.review.LocalGitProvider", FakeGitProvider)
    monkeypatch.setattr("mr_guardian.core.review.run_review", fake_run_review)

    result = review_merge_request(ReviewRequest(base="main"))

    assert not Path("sources/yaml").exists()
    assert {policy_result.policy_path.name for policy_result in result.policy_results} == {
        "python-policy.yml",
        "unity-policy.yml",
    }
