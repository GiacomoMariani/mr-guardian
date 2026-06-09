"""Typed review result models."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mr_guardian.models.policy import EvaluationDimension, RuleType, Severity

RiskLevel = Literal["none", "info", "warning", "high", "blocking"]
LlmRuleStatus = Literal["succeeded", "skipped", "failed", "rate_limited"]
LlmSummaryStatus = Literal["succeeded", "failed", "rate_limited"]
EVALUATION_ORDER: tuple[EvaluationDimension, ...] = ("coding", "mr_structure")


class Finding(BaseModel):
    """A review finding."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    severity: Severity
    message: str
    source: str
    evaluation: EvaluationDimension = "coding"
    rule_type: RuleType | None = None
    file_path: Path | None = None
    line_number: int | None = None


class FindingCounts(BaseModel):
    """Counts of findings by severity."""

    model_config = ConfigDict(frozen=True)

    blocking: int = 0
    high: int = 0
    warning: int = 0
    info: int = 0


class LlmRuleMetric(BaseModel):
    """Runtime and token metrics for one LLM rule execution."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    provider: str
    model: str
    status: LlmRuleStatus
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    error_message: str | None = None


class LlmReviewSummary(BaseModel):
    """Optional LLM-generated summary for a completed review result."""

    model_config = ConfigDict(frozen=True)

    status: LlmSummaryStatus
    provider: str
    model: str
    duration_ms: int
    text: str | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    error_message: str | None = None


class LlmDeveloperProfile(BaseModel):
    """Optional LLM-generated developer profile snapshot for one review run."""

    model_config = ConfigDict(frozen=True)

    status: LlmSummaryStatus
    provider: str
    model: str
    duration_ms: int
    lookback_days: int = Field(ge=0)
    text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    error_message: str | None = None


class ReviewEvaluation(BaseModel):
    """MR-level summary for one evaluation dimension."""

    model_config = ConfigDict(frozen=True)

    evaluation: EvaluationDimension
    risk: RiskLevel
    counts: FindingCounts
    triggered_rule_ids: list[str] = Field(default_factory=list)


class EngineReviewResult(BaseModel):
    """Result returned by the shared review engine."""

    model_config = ConfigDict(frozen=True)

    risk: RiskLevel
    findings: list[Finding]
    counts: FindingCounts
    llm_metrics: list[LlmRuleMetric] = []
    evaluations: list[ReviewEvaluation] = Field(default_factory=list)


def summarize_review_evaluations(findings: list[Finding]) -> list[ReviewEvaluation]:
    """Summarize findings into the supported MR evaluation dimensions."""
    return [
        _review_evaluation(evaluation=evaluation, findings=findings)
        for evaluation in EVALUATION_ORDER
    ]


def _review_evaluation(
    *,
    evaluation: EvaluationDimension,
    findings: list[Finding],
) -> ReviewEvaluation:
    evaluation_findings = [
        finding for finding in findings if finding.evaluation == evaluation
    ]
    counts = FindingCounts(
        blocking=sum(1 for finding in evaluation_findings if finding.severity == "blocking"),
        high=sum(1 for finding in evaluation_findings if finding.severity == "high"),
        warning=sum(1 for finding in evaluation_findings if finding.severity == "warning"),
        info=sum(1 for finding in evaluation_findings if finding.severity == "info"),
    )
    return ReviewEvaluation(
        evaluation=evaluation,
        risk=_risk_from_counts(counts),
        counts=counts,
        triggered_rule_ids=_triggered_rule_ids(evaluation_findings),
    )


def _risk_from_counts(counts: FindingCounts) -> RiskLevel:
    if counts.blocking > 0:
        return "blocking"
    if counts.high > 0:
        return "high"
    if counts.warning > 0:
        return "warning"
    if counts.info > 0:
        return "info"
    return "none"


def _triggered_rule_ids(findings: list[Finding]) -> list[str]:
    rule_ids: list[str] = []
    seen_rule_ids: set[str] = set()
    for finding in findings:
        if finding.rule_id in seen_rule_ids:
            continue
        rule_ids.append(finding.rule_id)
        seen_rule_ids.add(finding.rule_id)
    return rule_ids
