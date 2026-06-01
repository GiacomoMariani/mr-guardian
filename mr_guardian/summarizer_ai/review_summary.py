"""Optional LLM-generated review summary support."""

import json
from collections.abc import Iterable
from importlib import import_module
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mr_guardian.models.review import Finding, FindingCounts, ReviewEvaluation, RiskLevel
from mr_guardian.models.review_input import DiffLine, ReviewInput
from mr_guardian.summarizer_ai.llm_rules import LlmTokenUsage


class LlmSummaryError(Exception):
    """Base error for LLM summary execution failures."""


class LlmSummaryExecutionError(LlmSummaryError):
    """Raised when an LLM summary provider request or response fails."""


class LlmSummaryRateLimitError(LlmSummaryExecutionError):
    """Raised when the LLM summary provider reports rate limiting."""


class ReviewSummaryInput(BaseModel):
    """Review data used to generate an LLM summary."""

    model_config = ConfigDict(frozen=True)

    base_ref: str
    developer_id: str
    review_input: ReviewInput
    risk: RiskLevel
    counts: FindingCounts
    findings: list[Finding]
    evaluations: list[ReviewEvaluation]


class LlmReviewSummaryOutput(BaseModel):
    """Structured LLM review summary output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str
    score: int = Field(ge=0, le=100)


class LlmReviewSummaryRunner(Protocol):
    """Interface for optional LLM review summary generation."""

    def summarize(
        self,
        *,
        review: ReviewSummaryInput,
        max_chars: int,
    ) -> LlmReviewSummaryOutput:
        """Generate a concise evaluation for a completed review."""

    @property
    def provider_name(self) -> str:
        """Return the configured provider name."""

    @property
    def model_name(self) -> str:
        """Return the configured model name."""

    @property
    def last_token_usage(self) -> LlmTokenUsage | None:
        """Return token usage from the latest completed call, when available."""


class OpenAiLlmReviewSummaryRunner:
    """OpenAI-backed review summary runner."""

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
        self._last_token_usage: LlmTokenUsage | None = None

    @property
    def provider_name(self) -> str:
        """Return the configured provider name."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Return the configured model name."""
        return self._model

    @property
    def last_token_usage(self) -> LlmTokenUsage | None:
        """Return token usage from the latest completed call, when available."""
        return self._last_token_usage

    def summarize(
        self,
        *,
        review: ReviewSummaryInput,
        max_chars: int,
    ) -> LlmReviewSummaryOutput:
        """Generate and normalize one LLM review evaluation."""
        self._last_token_usage = None
        output = self._call_model(prompt=_build_summary_prompt(review, max_chars=max_chars))
        return output.model_copy(
            update={"summary": _truncate_summary(output.summary.strip(), max_chars)}
        )

    def _call_model(self, *, prompt: str) -> LlmReviewSummaryOutput:
        try:
            openai_module = import_module("openai")
        except ImportError as exc:
            msg = "OpenAI support requires installing mr-guardian[ai]."
            raise LlmSummaryExecutionError(msg) from exc

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
                        "name": "mr_guardian_llm_review_summary",
                        "schema": _strict_response_schema(),
                        "strict": True,
                    }
                },
            )
            self._last_token_usage = _token_usage(response)
            return parse_llm_review_summary_output(response.output_text)
        except ValueError as exc:
            raise LlmSummaryExecutionError(str(exc)) from exc
        except Exception as exc:
            if _is_rate_limit_error(exc):
                msg = "LLM provider rate limit reached."
                raise LlmSummaryRateLimitError(msg) from exc
            msg = f"LLM summary provider request failed: {exc}"
            raise LlmSummaryExecutionError(msg) from exc


def create_llm_review_summary_runner(
    *,
    enabled: bool,
    provider: str,
    openai_api_key: str,
    openai_model: str,
    openai_timeout_seconds: float,
    openai_max_retries: int,
) -> LlmReviewSummaryRunner | None:
    """Create the configured LLM review summary runner."""
    if not enabled:
        return None
    normalized_provider = provider.strip().lower()
    if normalized_provider == "openai" and openai_api_key:
        return OpenAiLlmReviewSummaryRunner(
            api_key=openai_api_key,
            model=openai_model,
            timeout_seconds=openai_timeout_seconds,
            max_retries=openai_max_retries,
        )
    return None


def parse_llm_review_summary_output(raw_output: str) -> LlmReviewSummaryOutput:
    """Parse and validate raw LLM summary JSON output."""
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        msg = f"Invalid LLM summary JSON: {exc}"
        raise ValueError(msg) from exc

    try:
        return LlmReviewSummaryOutput.model_validate(data)
    except ValidationError as exc:
        msg = f"Invalid LLM summary structure: {exc}"
        raise ValueError(msg) from exc


def _build_summary_prompt(review: ReviewSummaryInput, *, max_chars: int) -> str:
    sections = [
        "You are MR Guardian. Write a concise merge request review evaluation.",
        f"Maximum summary length: {max_chars} characters.",
        "Return a score from 0 to 100 where higher means healthier and easier to review.",
        "Do not create new findings, new risks, or new blocking decisions.",
        "Explain only the completed review result.",
        "Use all provided review, finding, file, and diff context.",
        "Return JSON that matches this schema:",
        json.dumps(LlmReviewSummaryOutput.model_json_schema(), indent=2),
        "",
        "Review metadata:",
        f"Base branch: {review.base_ref}",
        f"Developer: {review.developer_id}",
        f"Title: {review.review_input.title}",
        f"Overall risk: {review.risk}",
        (
            "Counts: "
            f"blocking={review.counts.blocking}, "
            f"high={review.counts.high}, "
            f"warning={review.counts.warning}, "
            f"info={review.counts.info}"
        ),
        "",
        "Evaluation summaries:",
    ]
    sections.extend(_evaluation_lines(review.evaluations))
    sections.extend(["", "Top findings:"])
    sections.extend(_finding_lines(review.findings))
    sections.extend(["", "Changed files:"])
    sections.extend(_changed_file_lines(review.review_input))
    sections.extend(["", "Diff context:"])
    sections.extend(_diff_context(review.review_input))
    return "\n".join(sections)


def _evaluation_lines(evaluations: list[ReviewEvaluation]) -> Iterable[str]:
    if not evaluations:
        yield "- none"
        return
    for evaluation in evaluations:
        yield (
            f"- {evaluation.evaluation}: risk={evaluation.risk}, "
            f"rules={', '.join(evaluation.triggered_rule_ids) or 'none'}"
        )


def _finding_lines(findings: list[Finding]) -> Iterable[str]:
    if not findings:
        yield "- none"
        return
    for finding in findings:
        location = _format_location(finding)
        location_text = f" at {location}" if location else ""
        yield (
            f"- [{finding.severity}] {finding.rule_id}{location_text}: "
            f"{finding.message}"
        )


def _changed_file_lines(review_input: ReviewInput) -> Iterable[str]:
    if not review_input.changed_files:
        yield "- none"
        return
    for changed_file in review_input.changed_files:
        yield f"- {changed_file.path.as_posix()} ({changed_file.status})"


def _diff_context(review_input: ReviewInput) -> Iterable[str]:
    emitted = 0
    for changed_file in review_input.changed_files:
        yield f"File: {changed_file.path.as_posix()} ({changed_file.status})"
        emitted += 1
        for hunk in changed_file.hunks:
            yield f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@"
            emitted += 1
            for diff_line in hunk.lines:
                yield _format_diff_line(diff_line)
                emitted += 1
    if emitted == 0:
        yield "No diff context."


def _format_diff_line(diff_line: DiffLine) -> str:
    prefix = {
        "addition": "+",
        "deletion": "-",
        "context": " ",
    }[diff_line.kind]
    line_number = diff_line.new_line_number or diff_line.old_line_number or 0
    return f"{prefix}{line_number}: {diff_line.content}"


def _format_location(finding: Finding) -> str:
    if finding.file_path is None:
        return ""
    location = finding.file_path.as_posix()
    if finding.line_number is not None:
        location = f"{location}:{finding.line_number}"
    return location


def _truncate_summary(summary: str, max_chars: int) -> str:
    if max_chars < 1:
        return ""
    if len(summary) <= max_chars:
        return summary
    if max_chars <= 3:
        return summary[:max_chars]
    return f"{summary[: max_chars - 3].rstrip()}..."


def _token_usage(response: object) -> LlmTokenUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return LlmTokenUsage(
        input_tokens=_optional_int(getattr(usage, "input_tokens", None)),
        output_tokens=_optional_int(getattr(usage, "output_tokens", None)),
        total_tokens=_optional_int(getattr(usage, "total_tokens", None)),
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return None


def _is_rate_limit_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True
    return "ratelimit" in exc.__class__.__name__.lower().replace("_", "")


def _strict_response_schema() -> dict[str, Any]:
    schema = LlmReviewSummaryOutput.model_json_schema()
    _require_all_properties(schema)
    return schema


def _require_all_properties(schema: object) -> None:
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            schema["required"] = list(properties)
        for value in schema.values():
            _require_all_properties(value)
        return

    if isinstance(schema, list):
        for item in schema:
            _require_all_properties(item)
