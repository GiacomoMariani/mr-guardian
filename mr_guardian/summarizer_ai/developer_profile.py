"""Optional LLM-generated developer profile support."""

import json
from collections.abc import Iterable
from importlib import import_module
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from mr_guardian.models.developer_profile import DeveloperProfileInput
from mr_guardian.models.history import ReviewRunRecord
from mr_guardian.models.lead_dashboard import (
    LeadEvaluationSummary,
    LeadRepeatedRule,
    LeadTicketAttemptSummary,
)
from mr_guardian.summarizer_ai.llm_rules import LlmTokenUsage


class LlmDeveloperProfileError(Exception):
    """Base error for LLM developer profile execution failures."""


class LlmDeveloperProfileExecutionError(LlmDeveloperProfileError):
    """Raised when the LLM developer profile request or response fails."""


class LlmDeveloperProfileRateLimitError(LlmDeveloperProfileExecutionError):
    """Raised when the LLM developer profile provider reports rate limiting."""


class LlmDeveloperProfileOutput(BaseModel):
    """Structured LLM developer profile output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: str


class LlmDeveloperProfileRunner(Protocol):
    """Interface for optional LLM developer profile generation."""

    def profile(
        self,
        *,
        developer: DeveloperProfileInput,
        max_chars: int,
    ) -> LlmDeveloperProfileOutput:
        """Generate a concise profile for a developer's recent review history."""

    @property
    def provider_name(self) -> str:
        """Return the configured provider name."""

    @property
    def model_name(self) -> str:
        """Return the configured model name."""

    @property
    def last_token_usage(self) -> LlmTokenUsage | None:
        """Return token usage from the latest completed call, when available."""


class OpenAiLlmDeveloperProfileRunner:
    """OpenAI-backed developer profile runner."""

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

    def profile(
        self,
        *,
        developer: DeveloperProfileInput,
        max_chars: int,
    ) -> LlmDeveloperProfileOutput:
        """Generate and normalize one LLM developer profile."""
        self._last_token_usage = None
        output = self._call_model(
            prompt=_build_developer_profile_prompt(developer, max_chars=max_chars)
        )
        return output.model_copy(
            update={"profile": _truncate_profile(output.profile.strip(), max_chars)}
        )

    def _call_model(self, *, prompt: str) -> LlmDeveloperProfileOutput:
        try:
            openai_module = import_module("openai")
        except ImportError as exc:
            msg = "OpenAI support requires installing mr-guardian[ai]."
            raise LlmDeveloperProfileExecutionError(msg) from exc

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
                        "name": "mr_guardian_llm_developer_profile",
                        "schema": _strict_response_schema(),
                        "strict": True,
                    }
                },
            )
            self._last_token_usage = _token_usage(response)
            return parse_llm_developer_profile_output(response.output_text)
        except ValueError as exc:
            raise LlmDeveloperProfileExecutionError(str(exc)) from exc
        except Exception as exc:
            if _is_rate_limit_error(exc):
                msg = "LLM provider rate limit reached."
                raise LlmDeveloperProfileRateLimitError(msg) from exc
            msg = f"LLM developer profile provider request failed: {exc}"
            raise LlmDeveloperProfileExecutionError(msg) from exc


def create_llm_developer_profile_runner(
    *,
    enabled: bool,
    provider: str,
    openai_api_key: str,
    openai_model: str,
    openai_timeout_seconds: float,
    openai_max_retries: int,
) -> LlmDeveloperProfileRunner | None:
    """Create the configured LLM developer profile runner."""
    if not enabled:
        return None
    normalized_provider = provider.strip().lower()
    if normalized_provider == "openai" and openai_api_key:
        return OpenAiLlmDeveloperProfileRunner(
            api_key=openai_api_key,
            model=openai_model,
            timeout_seconds=openai_timeout_seconds,
            max_retries=openai_max_retries,
        )
    return None


def parse_llm_developer_profile_output(raw_output: str) -> LlmDeveloperProfileOutput:
    """Parse and validate raw LLM developer profile JSON output."""
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        msg = f"Invalid LLM developer profile JSON: {exc}"
        raise ValueError(msg) from exc

    try:
        return LlmDeveloperProfileOutput.model_validate(data)
    except ValidationError as exc:
        msg = f"Invalid LLM developer profile structure: {exc}"
        raise ValueError(msg) from exc


def _build_developer_profile_prompt(
    developer: DeveloperProfileInput,
    *,
    max_chars: int,
) -> str:
    summary = developer.summary
    sections = [
        "You are MR Guardian. Write a concise developer review profile.",
        f"Maximum profile length: {max_chars} characters.",
        "Describe observable review patterns only.",
        "Do not speculate about intent, personality, seniority, or performance outside the data.",
        "Keep the profile useful for a technical lead reviewing delivery and review risk.",
        "Return JSON that matches this schema:",
        json.dumps(LlmDeveloperProfileOutput.model_json_schema(), indent=2),
        "",
        "Profile window:",
        f"Developer: {developer.developer_id}",
        f"Lookback days: {developer.lookback_days}",
        f"Start: {developer.start_at.isoformat()}",
        f"End: {developer.end_at.isoformat()}",
        "",
        "Developer metrics:",
        f"Review count: {summary.review_request_count}",
        f"Ticket count: {summary.ticket_count}",
        f"Average review score: {_format_optional_score(summary.average_score)}",
        f"Average attempts per ticket: {summary.average_attempts_per_ticket}",
        f"Latest review: {summary.latest_review_at.isoformat()}",
        f"Trend direction: {summary.trend_direction}",
        f"Multi-attempt tickets: {summary.multi_attempt_ticket_count}",
        f"Repeated rule count: {summary.repeated_rule_count}",
        f"Unlinked review count: {summary.unlinked_review_count}",
        "",
        "Ticket attempts:",
    ]
    sections.extend(_ticket_lines(summary.tickets))
    sections.extend(["", "Repeated rules:"])
    sections.extend(_repeated_rule_lines(summary.repeated_rules))
    sections.extend(["", "Evaluation summaries:"])
    sections.extend(_evaluation_lines(summary.evaluation_summaries))
    sections.extend(["", "Recent reviews:"])
    sections.extend(_review_lines(developer.review_runs))
    return "\n".join(sections)


def _ticket_lines(tickets: list[LeadTicketAttemptSummary]) -> Iterable[str]:
    if not tickets:
        yield "- none"
        return
    for ticket in tickets:
        yield (
            f"- {ticket.ticket_key}: attempts={ticket.review_attempt_count}, "
            f"first={ticket.first_review_at.isoformat()}, "
            f"latest={ticket.latest_review_at.isoformat()}, "
            f"assumed_deployed={ticket.assumed_deployed_at.isoformat()}, "
            f"average_score={ticket.average_score:.1f}, "
            f"latest_risk={ticket.latest_risk}"
        )


def _repeated_rule_lines(rules: list[LeadRepeatedRule]) -> Iterable[str]:
    if not rules:
        yield "- none"
        return
    for rule in rules:
        yield (
            f"- {rule.rule_id}: review_runs={rule.review_run_count}, "
            f"latest={rule.latest_review_at.isoformat()}"
        )


def _evaluation_lines(evaluations: list[LeadEvaluationSummary]) -> Iterable[str]:
    if not evaluations:
        yield "- none"
        return
    for evaluation in evaluations:
        yield (
            f"- {evaluation.evaluation}: reviews={evaluation.review_count}, "
            f"average_score={_format_optional_score(evaluation.average_score)}, "
            f"blocking={evaluation.counts.blocking}, "
            f"high={evaluation.counts.high}, "
            f"warning={evaluation.counts.warning}, "
            f"info={evaluation.counts.info}"
        )


def _review_lines(review_runs: list[ReviewRunRecord]) -> Iterable[str]:
    if not review_runs:
        yield "- none"
        return
    for run in review_runs:
        rule_ids = ", ".join(run.triggered_rule_ids) or "none"
        yield (
            f"- review_id={run.review_id}, timestamp={run.timestamp.isoformat()}, "
            f"ticket={run.ticket_key or 'none'}, risk={run.risk}, "
            f"score={run.review_score}, blocking={run.blocking_count}, "
            f"high={run.high_count}, warning={run.warning_count}, "
            f"info={run.info_count}, changed_files={run.changed_file_count}, "
            f"changed_lines={run.changed_line_count}, rules={rule_ids}"
        )


def _format_optional_score(score: float | None) -> str:
    if score is None:
        return "none"
    return f"{score:.1f}"


def _truncate_profile(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 3)].rstrip() + "..."


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
    schema = LlmDeveloperProfileOutput.model_json_schema()
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
