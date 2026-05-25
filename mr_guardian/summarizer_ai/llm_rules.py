"""LLM rule execution and output normalization."""

import json
from collections.abc import Iterable
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mr_guardian.models.policy import PolicyRule, Severity
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import DiffLine, ReviewInput

ADVISORY_SEVERITIES: set[Severity] = {"high", "warning", "info"}


class LlmRuleError(Exception):
    """Base error for LLM rule execution failures."""


class LlmRuleConfigurationError(LlmRuleError):
    """Raised when LLM rule execution is not configured correctly."""


class LlmRuleExecutionError(LlmRuleError):
    """Raised when an LLM provider request or response fails."""


class LlmRuleRateLimitError(LlmRuleExecutionError):
    """Raised when an LLM provider reports rate limiting."""


class LlmRuleOutputFinding(BaseModel):
    """One finding returned by an LLM rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str
    severity: Severity | None = None
    file_path: Path | None = None
    line_number: int | None = None


class LlmRuleOutput(BaseModel):
    """Structured output expected from an LLM rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    findings: list[LlmRuleOutputFinding] = Field(default_factory=list)


class LlmRuleRunner(Protocol):
    """Interface for advisory LLM rule runners."""

    def evaluate(self, *, rule: PolicyRule, review_input: ReviewInput) -> list[Finding]:
        """Evaluate one LLM rule against review input."""


class DisabledLlmRuleRunner:
    """No-op runner used when LLM configuration is not available."""

    def evaluate(self, *, rule: PolicyRule, review_input: ReviewInput) -> list[Finding]:
        """Skip LLM rules without failing the review."""
        return []


class OpenAiLlmRuleRunner:
    """OpenAI-backed LLM rule runner."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def evaluate(self, *, rule: PolicyRule, review_input: ReviewInput) -> list[Finding]:
        """Run one LLM rule and convert structured output into findings."""
        output = self._call_model(
            prompt=_build_llm_prompt(rule=rule, review_input=review_input),
        )
        return findings_from_llm_output(rule=rule, output=output)

    def _call_model(self, *, prompt: str) -> LlmRuleOutput:
        try:
            openai_module = import_module("openai")
        except ImportError as exc:
            msg = "OpenAI support requires installing mr-guardian[ai]."
            raise LlmRuleConfigurationError(msg) from exc

        try:
            openai_client = cast(Any, openai_module).OpenAI
            client = openai_client(
                api_key=self._api_key,
                timeout=self._timeout_seconds,
                max_retries=self._max_retries,
            )
            response = client.responses.create(
                model=self._model,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "mr_guardian_llm_rule_output",
                        "schema": LlmRuleOutput.model_json_schema(),
                        "strict": True,
                    }
                },
            )
            return parse_llm_output(response.output_text)
        except ValueError as exc:
            raise LlmRuleExecutionError(str(exc)) from exc
        except Exception as exc:
            if _is_rate_limit_error(exc):
                msg = "LLM provider rate limit reached."
                raise LlmRuleRateLimitError(msg) from exc
            msg = f"LLM provider request failed: {exc}"
            raise LlmRuleExecutionError(msg) from exc


def create_llm_rule_runner(
    *,
    provider: str,
    openai_api_key: str,
    openai_model: str,
    openai_timeout_seconds: float,
    openai_max_retries: int,
) -> LlmRuleRunner:
    """Create the configured LLM rule runner."""
    normalized_provider = provider.strip().lower()
    if normalized_provider in {"", "disabled", "none"}:
        return DisabledLlmRuleRunner()
    if normalized_provider == "openai" and openai_api_key:
        return OpenAiLlmRuleRunner(
            api_key=openai_api_key,
            model=openai_model,
            timeout_seconds=openai_timeout_seconds,
            max_retries=openai_max_retries,
        )
    return DisabledLlmRuleRunner()


def findings_from_llm_output(*, rule: PolicyRule, output: LlmRuleOutput) -> list[Finding]:
    """Convert validated LLM output into advisory review findings."""
    max_findings = _max_findings(rule)
    findings: list[Finding] = []
    for output_finding in output.findings[:max_findings]:
        severity = output_finding.severity or rule.severity
        if severity == "blocking":
            severity = "high"
        findings.append(
            Finding(
                rule_id=rule.id,
                severity=severity,
                message=output_finding.message,
                source=rule.source,
                rule_type=rule.type,
                file_path=output_finding.file_path,
                line_number=output_finding.line_number,
            )
        )
    return findings


def parse_llm_output(raw_output: str) -> LlmRuleOutput:
    """Parse and validate raw LLM JSON output."""
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        msg = f"Invalid LLM output JSON: {exc}"
        raise ValueError(msg) from exc

    try:
        return LlmRuleOutput.model_validate(data)
    except ValidationError as exc:
        msg = f"Invalid LLM output structure: {exc}"
        raise ValueError(msg) from exc


def _build_llm_prompt(*, rule: PolicyRule, review_input: ReviewInput) -> str:
    parameters = rule.parameters
    inputs = parameters.get("inputs", {})
    include_changed_files = _bool_setting(inputs, "include_changed_files", default=True)
    include_diff = _bool_setting(inputs, "include_diff", default=True)

    sections = [
        "You are MR Guardian. Evaluate only the supplied diff context.",
        "Return JSON that matches this schema:",
        json.dumps(LlmRuleOutput.model_json_schema(), indent=2),
        "",
        "Rule:",
        f"ID: {rule.id}",
        f"Severity: {rule.severity}",
        f"Description: {rule.description}",
        "Prompt:",
        rule.prompt or "",
    ]

    if include_changed_files:
        sections.extend(["", "Changed files:"])
        sections.extend(
            f"- {changed_file.path.as_posix()}"
            for changed_file in review_input.changed_files
        )

    if include_diff:
        sections.extend(["", "Diff context:"])
        sections.extend(_diff_context(review_input))

    return "\n".join(sections)


def _diff_context(review_input: ReviewInput) -> Iterable[str]:
    for changed_file in review_input.changed_files:
        yield f"File: {changed_file.path.as_posix()} ({changed_file.status})"
        for hunk in changed_file.hunks:
            yield f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@"
            for diff_line in hunk.lines:
                yield _format_diff_line(diff_line)


def _format_diff_line(diff_line: DiffLine) -> str:
    prefix = {
        "addition": "+",
        "deletion": "-",
        "context": " ",
    }[diff_line.kind]
    line_number = diff_line.new_line_number or diff_line.old_line_number or 0
    return f"{prefix}{line_number}: {diff_line.content}"


def _max_findings(rule: PolicyRule) -> int:
    output_contract = rule.parameters.get("output_contract", {})
    if not isinstance(output_contract, dict):
        return 3
    value = output_contract.get("max_findings", 3)
    if not isinstance(value, int) or value < 1:
        return 3
    return value


def _bool_setting(settings: object, key: str, *, default: bool) -> bool:
    if not isinstance(settings, dict):
        return default
    value = settings.get(key, default)
    if not isinstance(value, bool):
        return default
    return value


def _is_rate_limit_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True
    return "ratelimit" in exc.__class__.__name__.lower().replace("_", "")
