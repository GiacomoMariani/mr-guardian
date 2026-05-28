import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.summarizer_ai import DisabledLlmRuleRunner, create_llm_rule_runner
from mr_guardian.summarizer_ai.llm_rules import (
    LlmRuleExecutionError,
    LlmRuleOutput,
    LlmRuleOutputFinding,
    LlmRuleRateLimitError,
    OpenAiLlmRuleRunner,
    findings_from_llm_output,
    parse_llm_output,
)


def make_llm_rule(*, severity: str = "info", max_findings: int = 3) -> PolicyRule:
    return PolicyRule(
        id="PYTHON-DESIGN-LLM-001",
        type="llm",
        evaluation="coding",
        enabled=True,
        severity=severity,
        source="python-policy.yml#PYTHON-DESIGN-LLM-001",
        description="Check design concerns.",
        prompt="Review the diff.",
        parameters={"output_contract": {"max_findings": max_findings}},
    )


def make_review_input() -> ReviewInput:
    return ReviewInput(base_ref="main", changed_files=[])


def test_converts_valid_llm_output_into_advisory_findings() -> None:
    rule = make_llm_rule(severity="warning")
    output = LlmRuleOutput(
        findings=[
            LlmRuleOutputFinding(
                message="This abstraction is not justified by the diff.",
                severity="info",
                evaluation="mr_structure",
                file_path="mr_guardian/example.py",
                line_number=12,
            )
        ]
    )

    findings = findings_from_llm_output(rule=rule, output=output)

    assert len(findings) == 1
    assert findings[0].rule_id == "PYTHON-DESIGN-LLM-001"
    assert findings[0].severity == "info"
    assert findings[0].evaluation == "mr_structure"
    assert findings[0].rule_type == "llm"
    assert findings[0].file_path == Path("mr_guardian/example.py")
    assert findings[0].line_number == 12


def test_llm_output_cannot_create_blocking_findings() -> None:
    rule = make_llm_rule(severity="warning")
    output = LlmRuleOutput(
        findings=[
            LlmRuleOutputFinding(
                message="Reported as blocking by model.",
                severity="blocking",
                evaluation=None,
                file_path=None,
                line_number=None,
            )
        ]
    )

    findings = findings_from_llm_output(rule=rule, output=output)

    assert findings[0].severity == "high"
    assert findings[0].evaluation == "coding"


def test_limits_llm_findings_from_output_contract() -> None:
    rule = make_llm_rule(max_findings=1)
    output = LlmRuleOutput(
        findings=[
            LlmRuleOutputFinding(
                message="first",
                severity=None,
                evaluation=None,
                file_path=None,
                line_number=None,
            ),
            LlmRuleOutputFinding(
                message="second",
                severity=None,
                evaluation=None,
                file_path=None,
                line_number=None,
            ),
        ]
    )

    findings = findings_from_llm_output(rule=rule, output=output)

    assert [finding.message for finding in findings] == ["first"]


def test_parses_valid_llm_json_output() -> None:
    output = parse_llm_output(
        """
        {
          "findings": [
            {
              "message": "Use a simpler function.",
              "severity": "warning",
              "evaluation": "coding",
              "file_path": "mr_guardian/example.py",
              "line_number": 4
            }
          ]
        }
        """
    )

    assert output.findings[0].message == "Use a simpler function."
    assert output.findings[0].severity == "warning"
    assert output.findings[0].evaluation == "coding"


def test_llm_output_evaluation_defaults_to_rule_evaluation_when_omitted() -> None:
    output = parse_llm_output(
        """
        {
          "findings": [
            {
              "message": "Use a simpler function.",
              "severity": "warning",
              "file_path": "mr_guardian/example.py",
              "line_number": 4
            }
          ]
        }
        """
    )

    findings = findings_from_llm_output(rule=make_llm_rule(), output=output)

    assert output.findings[0].evaluation is None
    assert findings[0].evaluation == "coding"


def test_rejects_invalid_llm_output_evaluation() -> None:
    with pytest.raises(ValueError, match="Invalid LLM output structure"):
        parse_llm_output(
            """
            {
              "findings": [
                {
                  "message": "Use a simpler function.",
                  "severity": "warning",
                  "evaluation": "review_style",
                  "file_path": "mr_guardian/example.py",
                  "line_number": 4
                }
              ]
            }
            """
        )


def test_rejects_invalid_llm_json_output() -> None:
    with pytest.raises(ValueError, match="Invalid LLM output JSON"):
        parse_llm_output("{")


def test_rejects_malformed_llm_json_structure() -> None:
    with pytest.raises(ValueError, match="Invalid LLM output structure"):
        parse_llm_output('{"findings": [{"message": 123}]}')


def test_handles_missing_api_configuration_cleanly() -> None:
    runner = create_llm_rule_runner(
        provider="openai",
        openai_api_key="",
        openai_model="gpt-4.1-mini",
        openai_timeout_seconds=30.0,
        openai_max_retries=2,
    )

    assert isinstance(runner, DisabledLlmRuleRunner)


def test_configures_openai_timeout_and_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured["request"] = kwargs
            return SimpleNamespace(output_text='{"findings": []}')

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
    runner = OpenAiLlmRuleRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=12.5,
        max_retries=4,
    )

    findings = runner.evaluate(rule=make_llm_rule(), review_input=make_review_input())

    assert findings == []
    assert captured["api_key"] == "test-key"
    assert captured["timeout"] == 12.5
    assert captured["max_retries"] == 4
    assert isinstance(captured["request"], dict)
    assert captured["request"]["model"] == "gpt-test"
    assert "input" in captured["request"]
    assert "text" in captured["request"]


def test_openai_runner_captures_token_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                output_text='{"findings": []}',
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
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    runner = OpenAiLlmRuleRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=1.0,
        max_retries=0,
    )

    runner.evaluate(rule=make_llm_rule(), review_input=make_review_input())

    assert runner.last_token_usage is not None
    assert runner.last_token_usage.input_tokens == 100
    assert runner.last_token_usage.output_tokens == 20
    assert runner.last_token_usage.total_tokens == 120


def test_openai_schema_uses_plain_string_file_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured["request"] = kwargs
            return SimpleNamespace(output_text='{"findings": []}')

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
    runner = OpenAiLlmRuleRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=1.0,
        max_retries=0,
    )

    runner.evaluate(rule=make_llm_rule(), review_input=make_review_input())

    assert isinstance(captured["request"], dict)
    text_config = captured["request"]["text"]
    assert isinstance(text_config, dict)
    schema = text_config["format"]["schema"]  # type: ignore[index]
    finding_schema = schema["$defs"]["LlmRuleOutputFinding"]  # type: ignore[index]
    file_path_schema = finding_schema["properties"]["file_path"]  # type: ignore[index]
    assert file_path_schema["anyOf"][0] == {"type": "string"}  # type: ignore[index]
    assert set(finding_schema["required"]) == {  # type: ignore[index]
        "message",
        "severity",
        "evaluation",
        "file_path",
        "line_number",
    }
    assert schema["required"] == ["findings"]  # type: ignore[index]


def test_openai_runner_reports_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
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
    runner = OpenAiLlmRuleRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=1.0,
        max_retries=0,
    )

    with pytest.raises(LlmRuleRateLimitError, match="rate limit"):
        runner.evaluate(rule=make_llm_rule(), review_input=make_review_input())


def test_openai_runner_reports_malformed_responses(monkeypatch: pytest.MonkeyPatch) -> None:
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
    runner = OpenAiLlmRuleRunner(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=1.0,
        max_retries=0,
    )

    with pytest.raises(LlmRuleExecutionError, match="Invalid LLM output JSON"):
        runner.evaluate(rule=make_llm_rule(), review_input=make_review_input())
