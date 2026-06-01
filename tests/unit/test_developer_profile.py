from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.core.developer_profile import build_developer_profile_input
from mr_guardian.core.review import PolicyReviewResult, ReviewResult
from mr_guardian.core.review_history import store_review_result
from mr_guardian.models.developer_profile import DeveloperProfileInput
from mr_guardian.models.history import ReviewRunCreate
from mr_guardian.models.review import EngineReviewResult, FindingCounts
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.storage import ReviewHistoryStore
from mr_guardian.summarizer_ai import (
    LlmDeveloperProfileOutput,
    LlmDeveloperProfileRateLimitError,
)


def make_review_run(
    *,
    developer_id: str = "Jane",
    timestamp: datetime,
    ticket_key: str | None = "TK-234",
    review_score: int = 95,
) -> ReviewRunCreate:
    return ReviewRunCreate(
        review_scope="local-all-policies",
        branch_name="main",
        developer_id=developer_id,
        ticket_key=ticket_key,
        policy_version=1,
        risk="warning",
        blocking_count=0,
        high_count=0,
        warning_count=1,
        info_count=0,
        changed_file_count=1,
        changed_line_count=5,
        review_score=review_score,
        triggered_rule_ids=["MR-META-001"],
        generated_review_report="## Report",
        timestamp=timestamp,
    )


def make_review_result(*, developer_id: str = "Jane") -> ReviewResult:
    engine_result = EngineReviewResult(
        risk="none",
        findings=[],
        counts=FindingCounts(),
    )
    return ReviewResult(
        base_ref="main",
        policy_directory=Path("sources/yaml"),
        policy_results=[
            PolicyReviewResult(
                policy_path=Path("sources/yaml/python-policy.yml"),
                policy_version=1,
                enabled_rule_count=2,
                disabled_rule_count=0,
                engine_result=engine_result,
            )
        ],
        developer_id=developer_id,
        review_input=ReviewInput(
            base_ref="main",
            title="TK-234 Add movement",
            changed_files=[],
        ),
        engine_result=engine_result,
    )


def test_builds_developer_profile_input_from_configured_lookback_window(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 5, 29, 10, tzinfo=timezone.utc)
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    store.store_review_run(
        make_review_run(developer_id="Jane", timestamp=now - timedelta(days=40))
    )
    included = store.store_review_run(
        make_review_run(developer_id="Jane", timestamp=now - timedelta(days=10))
    )
    current = store.store_review_run(make_review_run(developer_id="Jane", timestamp=now))
    store.store_review_run(make_review_run(developer_id="Other", timestamp=now))

    profile_input = build_developer_profile_input(
        store=store,
        record=current,
        lookback_days=30,
    )
    store.close()

    assert profile_input is not None
    assert profile_input.developer_id == "Jane"
    assert profile_input.lookback_days == 30
    assert [run.review_id for run in profile_input.review_runs] == [
        current.review_id,
        included.review_id,
    ]
    assert profile_input.summary.review_request_count == 2
    assert profile_input.summary.ticket_count == 1


def test_store_review_result_regenerates_only_current_developer_profile(
    tmp_path: Path,
) -> None:
    captured_input: DeveloperProfileInput | None = None

    class FakeProfileRunner:
        @property
        def provider_name(self) -> str:
            return "test-provider"

        @property
        def model_name(self) -> str:
            return "test-model"

        @property
        def last_token_usage(self):
            return None

        def profile(
            self,
            *,
            developer: DeveloperProfileInput,
            max_chars: int,
        ) -> LlmDeveloperProfileOutput:
            nonlocal captured_input
            captured_input = developer
            assert max_chars == 512
            return LlmDeveloperProfileOutput(profile="Jane has one clean recent review.")

    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    store.store_review_run(
        make_review_run(
            developer_id="Other",
            timestamp=datetime(2026, 5, 29, 9, tzinfo=timezone.utc),
        )
    )
    store.close()

    record = store_review_result(
        make_review_result(developer_id="Jane"),
        report="## Report",
        database_path=tmp_path / "history.sqlite",
        review_scope="local-all-policies",
        developer_profile_runner=FakeProfileRunner(),
        developer_profile_lookback_days=7,
        developer_profile_max_chars=512,
    )

    assert captured_input is not None
    assert captured_input.developer_id == "Jane"
    assert {run.developer_id for run in captured_input.review_runs} == {"Jane"}
    assert record.developer_profile is not None
    assert record.developer_profile.status == "succeeded"
    assert record.developer_profile.text == "Jane has one clean recent review."
    assert record.developer_profile.lookback_days == 7


def test_store_review_result_skips_profile_when_disabled(tmp_path: Path) -> None:
    record = store_review_result(
        make_review_result(developer_id="Jane"),
        report="## Report",
        database_path=tmp_path / "history.sqlite",
        review_scope="local-all-policies",
        developer_profile_runner=None,
    )

    assert record.developer_profile is None


def test_store_review_result_stores_profile_failure_without_failing_review(
    tmp_path: Path,
) -> None:
    class FailingProfileRunner:
        @property
        def provider_name(self) -> str:
            return "test-provider"

        @property
        def model_name(self) -> str:
            return "test-model"

        @property
        def last_token_usage(self):
            return None

        def profile(
            self,
            *,
            developer: DeveloperProfileInput,
            max_chars: int,
        ) -> LlmDeveloperProfileOutput:
            raise RuntimeError("profile failed")

    record = store_review_result(
        make_review_result(developer_id="Jane"),
        report="## Report",
        database_path=tmp_path / "history.sqlite",
        review_scope="local-all-policies",
        developer_profile_runner=FailingProfileRunner(),
    )

    assert record.developer_profile is not None
    assert record.developer_profile.status == "failed"
    assert record.developer_profile.text is None
    assert record.developer_profile.error_message == "profile failed"


def test_store_review_result_stores_profile_rate_limit_without_failing_review(
    tmp_path: Path,
) -> None:
    class RateLimitedProfileRunner:
        @property
        def provider_name(self) -> str:
            return "test-provider"

        @property
        def model_name(self) -> str:
            return "test-model"

        @property
        def last_token_usage(self):
            return None

        def profile(
            self,
            *,
            developer: DeveloperProfileInput,
            max_chars: int,
        ) -> LlmDeveloperProfileOutput:
            raise LlmDeveloperProfileRateLimitError("LLM provider rate limit reached.")

    record = store_review_result(
        make_review_result(developer_id="Jane"),
        report="## Report",
        database_path=tmp_path / "history.sqlite",
        review_scope="local-all-policies",
        developer_profile_runner=RateLimitedProfileRunner(),
    )

    assert record.developer_profile is not None
    assert record.developer_profile.status == "rate_limited"
    assert record.developer_profile.error_message == "LLM provider rate limit reached."
