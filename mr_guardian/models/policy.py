"""Typed policy models."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

Severity = Literal["blocking", "high", "warning", "info"]


class BestPracticesMetadata(BaseModel):
    """Metadata describing the human-readable best-practices source."""

    model_config = ConfigDict(extra="allow", frozen=True)

    local_markdown_path: Path
    require_rule_id_links: bool


class PolicyRule(BaseModel):
    """Executable policy rule configuration."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    enabled: bool
    severity: Severity
    source: str
    description: str


class Policy(BaseModel):
    """MR Guardian policy file."""

    model_config = ConfigDict(extra="allow", frozen=True)

    version: int
    best_practices: BestPracticesMetadata
    rules: list[PolicyRule]

