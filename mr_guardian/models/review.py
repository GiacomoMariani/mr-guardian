"""Typed review result models."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mr_guardian.models.policy import Severity

RiskLevel = Literal["none", "info", "warning", "high", "blocking"]


class Finding(BaseModel):
    """A deterministic review finding."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    severity: Severity
    message: str
    source: str
    file_path: Path | None = None
    line_number: int | None = None


class FindingCounts(BaseModel):
    """Counts of findings by severity."""

    model_config = ConfigDict(frozen=True)

    blocking: int = 0
    high: int = 0
    warning: int = 0
    info: int = 0


class EngineReviewResult(BaseModel):
    """Result returned by the shared review engine."""

    model_config = ConfigDict(frozen=True)

    risk: RiskLevel
    findings: list[Finding]
    counts: FindingCounts

