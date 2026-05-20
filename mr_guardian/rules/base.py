"""Common deterministic rule interface."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import ReviewInput


class RuleEvaluationContext(BaseModel):
    """Context available to deterministic rules."""

    model_config = ConfigDict(frozen=True)

    policy: Policy
    review_input: ReviewInput


class DeterministicRule(Protocol):
    """Protocol implemented by deterministic rules."""

    @property
    def rule_id(self) -> str:
        """Policy rule ID handled by this rule."""

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        """Evaluate the rule and return any findings."""

