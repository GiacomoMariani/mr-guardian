"""Typed policy models."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Severity = Literal["blocking", "high", "warning", "info"]
RuleType = Literal["deterministic", "llm"]
EvaluationDimension = Literal["coding", "mr_structure"]


class PolicyRule(BaseModel):
    """Executable policy rule configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    type: RuleType
    implementation: str | None = None
    evaluation: EvaluationDimension = "coding"
    enabled: bool
    severity: Severity
    source: str
    description: str
    prompt: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rule_type_constraints(self) -> "PolicyRule":
        """Validate constraints that depend on the rule type."""
        if self.type == "deterministic" and not self.implementation:
            msg = "Deterministic rules must include an implementation."
            raise ValueError(msg)
        if self.type == "llm":
            if self.severity == "blocking":
                msg = "LLM rules must not use blocking severity."
                raise ValueError(msg)
            if not self.prompt:
                msg = "LLM rules must include a prompt."
                raise ValueError(msg)
        return self


class Policy(BaseModel):
    """MR Guardian policy file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    rules: list[PolicyRule]
