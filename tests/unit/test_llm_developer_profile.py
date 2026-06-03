import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from mr_guardian.models.developer_profile import DeveloperProfileInput
from mr_guardian.models.history import ReviewRunRecord
from mr_guardian.models.lead_dashboard import (
    LeadDeveloperSummary,
    LeadEvaluationSummary,
    LeadRepeatedRule,
    LeadTicketAttemptSummary,
)
from mr_guardian.models.review import FindingCounts
from mr_guardian.summarizer_ai.developer_profile import (
    LlmDeveloperProfileExecutionError,
    LlmDeveloperProfileRateLimitError,
    OpenAiLlmDeveloperProfileRunner,
    create_llm_developer_profile_runner,
    parse_llm_developer_profile_output,
)


def make_profile_input() -> DeveloperProfileInput:
    timestamp = datetime(2026, 5, 29, tzinfo=timezone.utc)
    return DeveloperProfileInput(
        developer_id="Jane Developer",
        lookback_days=30,
        start_at=datetime(2026, 4, 29, tzinfo=timezone.utc),
        end_at=timestamp,
        summary=LeadDeveloperSummary(
            developer_id="Jane Developer",
            review_request_count=2,
            ticket_count=1,
            average_attempts_per_ticket=2.0,
            approved_ticket_count=1,
            average_attempts_to_approval=2.0,
            average_score=84.5,
            latest_review_at=timestamp,
            trend_direction="insufficient_data",
            multi_attempt_ticket_count=1,
            repeated_rule_count=1,
            unlinked_review_count=0,
            tickets=[
                LeadTicketAttemptSummary(
                    ticket_key="TK-234",
                    review_attempt_count=2,
                    first_review_at=timestamp,
                    latest_review_at=timestamp,
                    assumed_deployed_at=timestamp,
                    is_approved=True,
                    approved_at=timestamp,
                    attempts_to_approval=2,
                    average_score=84.5,
                    latest_risk="warning",
                )
            ],
            repeated_rules=[
                LeadRepeatedRule(
                    rule_id="MR-META-001",
                    review_run_count=2,
                    latest_review_at=timestamp,
                )
            ],
            evaluation_summaries=[
                LeadEvaluationSummary(
                    evaluation="coding",
                    review_count=2,
                    average_score=92.5,
                    counts=FindingCounts(warning=1),
                )
            ],
        ),
        review_runs=[
            ReviewRunRecord(
                review_id=1,
                timestamp=timestamp,
                review_scope="local-all-policies",
                branch_name="main",
                developer_id="Jane Developer",
                ticket_key="TK-234",
                policy_version=1,
                risk="warning",
                blocking_count=0,
                high_count=0,
                warning_count=1,
                info_count=0,
                changed_file_count=2,
                changed_line_count=12,
                review_score=95,
                triggered_rule_ids=["MR-META-001"],
                generated_review_report="## Report",
            )
        ],
    )


def test_parses_valid_llm_developer_profile_output() -> None:
    output = parse_llm_developer_profile_output(
        '{"profile": "Recent reviews show improving MR structure."}'
    )

    assert output.profile == "Recent reviews show improving MR structure."


def test_rejects_invalid_llm_developer_profile_output() -> None:
    with pytest.raises(ValueError, match="Invalid LLM developer profile structure"):
        parse_llm_developer_profile_output('{"profile": 123}')


def test_creates_developer_profile_runner_only_when_enabled_and_configured() -> None:
    assert (
        create_llm_developer_profile_runner(
            enabled=False,
            provider="openai",
            openai_api_key="key",
            openai_model="gpt-test",
            openai_timeout_seconds=1.0,
            openai_max_retries=0,
        )
        is None
    )
    assert (
        create_llm_developer_profile_runner(
            enabled=True,
            provider="openai",
            openai_api_key="",
            openai_model="gpt-test",
            openai_timeout_seconds=1.0,
            openai_max_retries=0,
        )
        is None
    )

    runner = create_llm_developer_profile_runner(
        enabled=True,
        provider="openai",
        openai_api_key="key",
        openai_model="gpt-test",
        openai_timeout_seconds=1.0,
        openai_max_retries=0,
    )

    assert isinstance(runner, OpenAiLlmDeveloperProfileRunner)


def test_openai_developer_profile_runner_captures_usage_and_truncates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured["request"] = kwargs
            return SimpleNamespace(
                output_text='{"profile": "This profile is longer than allowed."}',
                usage=SimpleNamespace(
                    input_tokens=200,
                    output_tokens=30,
                    total_tokens=230,
                ),
            )

    class FakeOpenAI:
        def __init__(
            self,
            *,
            api_key: str,
            timeout: float,
            max_retries: int,
        ) -> None:
            captured["api_key"] = api_key
            captured["timeout"] = timeout
            captured["max_retries"] = max_retries
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    runner = OpenAiLlmDeveloperProfileRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=12.5,
        max_retries=4,
    )

    profile = runner.profile(developer=make_profile_input(), max_chars=12)

    assert profile.profile == "This prof..."
    assert captured["api_key"] == "test-key"
    assert captured["timeout"] == 12.5
    assert captured["max_retries"] == 4
    assert isinstance(captured["request"], dict)
    assert captured["request"]["model"] == "gpt-test"
    prompt = captured["request"]["input"]
    assert isinstance(prompt, str)
    assert "Jane Developer" in prompt
    assert "TK-234" in prompt
    assert "MR-META-001" in prompt
    assert "coding" in prompt
    assert "Approved ticket count: 1" in prompt
    assert "attempts_to_approval=2" in prompt
    assert runner.last_token_usage is not None
    assert runner.last_token_usage.total_tokens == 230


def test_openai_developer_profile_runner_reports_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRateLimitError(Exception):
        status_code = 429

    class FakeResponses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            raise FakeRateLimitError("too many requests")

    class FakeOpenAI:
        def __init__(
            self,
            *,
            api_key: str,
            timeout: float,
            max_retries: int,
        ) -> None:
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    runner = OpenAiLlmDeveloperProfileRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=1.0,
        max_retries=0,
    )

    with pytest.raises(LlmDeveloperProfileRateLimitError, match="rate limit"):
        runner.profile(developer=make_profile_input(), max_chars=700)


def test_openai_developer_profile_runner_reports_malformed_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(output_text="{")

    class FakeOpenAI:
        def __init__(
            self,
            *,
            api_key: str,
            timeout: float,
            max_retries: int,
        ) -> None:
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    runner = OpenAiLlmDeveloperProfileRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=1.0,
        max_retries=0,
    )

    with pytest.raises(
        LlmDeveloperProfileExecutionError,
        match="Invalid LLM developer profile JSON",
    ):
        runner.profile(developer=make_profile_input(), max_chars=700)
