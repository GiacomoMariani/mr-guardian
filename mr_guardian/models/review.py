"""Typed review result models."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mr_guardian.models.policy import RuleType, Severity

RiskLevel = Literal["none", "info", "warning", "high", "blocking"]
LlmRuleStatus = Literal["succeeded", "skipped", "failed", "rate_limited"]


class Finding(BaseModel):
    """A review finding."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    severity: Severity
    message: str
    source: str
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
    error_message: str | None = None


class EngineReviewResult(BaseModel):
    """Result returned by the shared review engine."""

    model_config = ConfigDict(frozen=True)

    risk: RiskLevel
    findings: list[Finding]
    counts: FindingCounts
    llm_metrics: list[LlmRuleMetric] = []
