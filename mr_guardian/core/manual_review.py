"""Manual review submission and validation."""

import json
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from mr_guardian.core.engine import calculate_risk, count_findings
from mr_guardian.core.review_score import calculate_review_score_from_counts
from mr_guardian.core.ticket_keys import extract_ticket_key_from_title
from mr_guardian.models.history import ReviewRunCreate, ReviewRunRecord
from mr_guardian.models.review import (
    EVALUATION_ORDER,
    Finding,
    ReviewEvaluation,
    RiskLevel,
    summarize_review_evaluations,
)
from mr_guardian.storage import ReviewHistoryStore


class ManualReviewError(Exception):
    """Base error for manual review submission failures."""


class ManualReviewJsonError(ManualReviewError):
    """Raised when a manual review file is not valid JSON."""


class ManualReviewValidationError(ManualReviewError):
    """Raised when a manual review payload is structurally invalid."""


class ManualReviewPayload(BaseModel):
    """Validated manual review submission payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_scope: str
    branch_name: str
    title: str = ""
    developer_id: str = "unknown"
    policy_version: int = Field(ge=0)
    risk: RiskLevel
    findings: list[Finding]
    evaluations: list[ReviewEvaluation]
    changed_file_count: int = Field(ge=0)
    changed_line_count: int = Field(ge=0)
    generated_review_report: str
    mr_id: str | None = None
    commit_sha: str | None = None
    timestamp: datetime | None = None

    @field_validator("review_scope", "branch_name", "developer_id", "generated_review_report")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        """Reject empty required string fields."""
        if not value.strip():
            msg = "Field must not be empty."
            raise ValueError(msg)
        return value


def load_manual_review_payload(path: str | Path) -> ManualReviewPayload:
    """Load, parse, and validate a manual review JSON payload."""
    payload_path = Path(path)
    try:
        raw_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        msg = f"Invalid JSON in manual review file '{payload_path}': {exc}"
        raise ManualReviewJsonError(msg) from exc

    if not isinstance(raw_payload, dict):
        msg = f"Invalid manual review file '{payload_path}': expected a JSON object."
        raise ManualReviewValidationError(msg)

    try:
        payload = ManualReviewPayload.model_validate(raw_payload)
    except ValidationError as exc:
        msg = f"Invalid manual review structure in '{payload_path}': {exc}"
        raise ManualReviewValidationError(msg) from exc

    validate_manual_review_payload(payload)
    return payload


def validate_manual_review_payload(payload: ManualReviewPayload) -> None:
    """Validate submitted review-level risk and evaluation summaries."""
    counts = count_findings(payload.findings)
    expected_risk = calculate_risk(counts)
    if payload.risk != expected_risk:
        msg = (
            f"Manual review risk '{payload.risk}' does not match findings risk "
            f"'{expected_risk}'."
        )
        raise ManualReviewValidationError(msg)

    _validate_evaluations(payload.evaluations, payload.findings)


def manual_review_to_review_run(payload: ManualReviewPayload) -> ReviewRunCreate:
    """Convert a validated manual review payload into storage input."""
    counts = count_findings(payload.findings)
    evaluations = summarize_review_evaluations(payload.findings)
    return ReviewRunCreate(
        review_scope=payload.review_scope,
        branch_name=payload.branch_name,
        developer_id=payload.developer_id,
        ticket_key=extract_ticket_key_from_title(payload.title),
        mr_id=payload.mr_id,
        commit_sha=payload.commit_sha,
        policy_version=payload.policy_version,
        risk=calculate_risk(counts),
        blocking_count=counts.blocking,
        high_count=counts.high,
        warning_count=counts.warning,
        info_count=counts.info,
        changed_file_count=payload.changed_file_count,
        changed_line_count=payload.changed_line_count,
        review_score=calculate_review_score_from_counts(counts),
        triggered_rule_ids=[finding.rule_id for finding in payload.findings],
        evaluations=evaluations,
        generated_review_report=payload.generated_review_report,
        timestamp=payload.timestamp,
    )


def store_manual_review_file(
    path: str | Path,
    *,
    database_path: str | Path,
) -> ReviewRunRecord:
    """Load, validate, and store one manual review payload."""
    payload = load_manual_review_payload(path)
    store = ReviewHistoryStore(database_path)
    try:
        return store.store_review_run(manual_review_to_review_run(payload))
    finally:
        store.close()


def _validate_evaluations(
    submitted_evaluations: list[ReviewEvaluation],
    findings: list[Finding],
) -> None:
    expected_evaluations = summarize_review_evaluations(findings)
    expected_by_dimension = {
        evaluation.evaluation: evaluation for evaluation in expected_evaluations
    }
    submitted_by_dimension = _submitted_evaluations_by_dimension(submitted_evaluations)

    expected_dimensions = set(EVALUATION_ORDER)
    submitted_dimensions = set(submitted_by_dimension)
    if submitted_dimensions != expected_dimensions:
        msg = (
            "Manual review evaluations must include exactly these dimensions: "
            f"{', '.join(EVALUATION_ORDER)}."
        )
        raise ManualReviewValidationError(msg)

    for dimension in EVALUATION_ORDER:
        _validate_evaluation_summary(
            submitted=submitted_by_dimension[dimension],
            expected=expected_by_dimension[dimension],
        )


def _submitted_evaluations_by_dimension(
    evaluations: list[ReviewEvaluation],
) -> dict[str, ReviewEvaluation]:
    by_dimension: dict[str, ReviewEvaluation] = {}
    for evaluation in evaluations:
        if evaluation.evaluation in by_dimension:
            msg = f"Duplicate manual review evaluation '{evaluation.evaluation}'."
            raise ManualReviewValidationError(msg)
        by_dimension[evaluation.evaluation] = evaluation
    return by_dimension


def _validate_evaluation_summary(
    *,
    submitted: ReviewEvaluation,
    expected: ReviewEvaluation,
) -> None:
    if submitted.risk != expected.risk:
        msg = (
            f"Manual review evaluation '{submitted.evaluation}' risk '{submitted.risk}' "
            f"does not match findings risk '{expected.risk}'."
        )
        raise ManualReviewValidationError(msg)

    if submitted.counts != expected.counts:
        msg = (
            f"Manual review evaluation '{submitted.evaluation}' counts do not match "
            "submitted findings."
        )
        raise ManualReviewValidationError(msg)

    if submitted.triggered_rule_ids != expected.triggered_rule_ids:
        msg = (
            f"Manual review evaluation '{submitted.evaluation}' triggered_rule_ids do "
            "not match submitted findings."
        )
        raise ManualReviewValidationError(msg)


def manual_review_error_report(exc: ManualReviewError) -> str:
    """Render a concise manual review submission error."""
    return f"Manual review submission failed: {exc}"


def manual_review_success_report(record: ReviewRunRecord) -> str:
    """Render a concise manual review submission confirmation."""
    return "\n".join(
        [
            "Manual review stored successfully.",
            f"Review ID: {record.review_id}",
            f"Scope: {record.review_scope}",
            f"Branch: {record.branch_name}",
            f"Ticket: {record.ticket_key or '-'}",
            f"Score: {record.review_score}",
            f"Risk: {record.risk}",
        ]
    )


def manual_review_payload_schema() -> dict[str, Any]:
    """Return the JSON schema for manual review payloads."""
    return ManualReviewPayload.model_json_schema()
