"""Typed policy models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

Severity = Literal["blocking", "high", "warning", "info"]
RuleType = Literal["deterministic", "llm"]


class PolicyRule(BaseModel):
    """Executable policy rule configuration."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    type: RuleType
    enabled: bool
    severity: Severity
    source: str
    description: str

    @model_validator(mode="after")
    def validate_rule_type_constraints(self) -> "PolicyRule":
        """Validate constraints that depend on the rule type."""
        if self.type == "llm":
            if self.severity == "blocking":
                msg = "LLM rules must not use blocking severity."
                raise ValueError(msg)
            if "prompt" not in (self.model_extra or {}):
                msg = "LLM rules must include a prompt."
                raise ValueError(msg)
        return self


class Policy(BaseModel):
    """MR Guardian policy file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    rules: list[PolicyRule]
