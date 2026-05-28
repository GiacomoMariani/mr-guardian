import sys
from types import SimpleNamespace

import pytest

from mr_guardian.models.review import FindingCounts
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.summarizer_ai.review_summary import (
    LlmSummaryExecutionError,
    LlmSummaryRateLimitError,
    OpenAiLlmReviewSummaryRunner,
    ReviewSummaryInput,
    create_llm_review_summary_runner,
    parse_llm_review_summary_output,
)


def make_summary_input() -> ReviewSummaryInput:
    return ReviewSummaryInput(
        base_ref="main",
        developer_id="Test User",
        review_input=ReviewInput(base_ref="main", title="TK-234 Add movement", changed_files=[]),
        risk="none",
        counts=FindingCounts(),
        findings=[],
        evaluations=[],
    )


def test_parses_valid_llm_review_summary_output() -> None:
    output = parse_llm_review_summary_output('{"summary": "Review looks ready."}')

    assert output.summary == "Review looks ready."


def test_rejects_invalid_llm_review_summary_output() -> None:
    with pytest.raises(ValueError, match="Invalid LLM summary structure"):
        parse_llm_review_summary_output('{"summary": 123}')


def test_creates_review_summary_runner_only_when_enabled_and_configured() -> None:
    assert (
        create_llm_review_summary_runner(
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
        create_llm_review_summary_runner(
            enabled=True,
            provider="openai",
            openai_api_key="",
            openai_model="gpt-test",
            openai_timeout_seconds=1.0,
            openai_max_retries=0,
        )
        is None
    )
    runner = create_llm_review_summary_runner(
        enabled=True,
        provider="openai",
        openai_api_key="key",
        openai_model="gpt-test",
        openai_timeout_seconds=1.0,
        openai_max_retries=0,
    )

    assert isinstance(runner, OpenAiLlmReviewSummaryRunner)


def test_openai_review_summary_runner_captures_usage_and_truncates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured["request"] = kwargs
            return SimpleNamespace(
                output_text='{"summary": "This summary is longer than allowed."}',
                usage=SimpleNamespace(
                    input_tokens=100,
                    output_tokens=20,
                    total_tokens=120,
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
    runner = OpenAiLlmReviewSummaryRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=12.5,
        max_retries=4,
    )

    summary = runner.summarize(review=make_summary_input(), max_chars=12)

    assert summary == "This summ..."
    assert captured["api_key"] == "test-key"
    assert captured["timeout"] == 12.5
    assert captured["max_retries"] == 4
    assert isinstance(captured["request"], dict)
    assert captured["request"]["model"] == "gpt-test"
    assert "input" in captured["request"]
    assert "text" in captured["request"]
    assert runner.last_token_usage is not None
    assert runner.last_token_usage.input_tokens == 100
    assert runner.last_token_usage.output_tokens == 20
    assert runner.last_token_usage.total_tokens == 120


def test_openai_review_summary_runner_reports_rate_limits(
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
    runner = OpenAiLlmReviewSummaryRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=1.0,
        max_retries=0,
    )

    with pytest.raises(LlmSummaryRateLimitError, match="rate limit"):
        runner.summarize(review=make_summary_input(), max_chars=700)


def test_openai_review_summary_runner_reports_malformed_responses(
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
    runner = OpenAiLlmReviewSummaryRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=1.0,
        max_retries=0,
    )

    with pytest.raises(LlmSummaryExecutionError, match="Invalid LLM summary JSON"):
        runner.summarize(review=make_summary_input(), max_chars=700)
