"""Common deterministic rule interface."""

from pathlib import Path
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
    repo_root: Path | None = None

    def read_changed_bytes(self, path: Path) -> bytes | None:
        """Return the bytes of a changed file from the review checkout, when available.

        Returns ``None`` when no checkout is wired in (e.g. diff-only reviews) or the
        file cannot be read (deleted, renamed away, absolute path, or unreadable), so
        asset rules can degrade gracefully instead of raising.
        """
        if self.repo_root is None or path.is_absolute():
            return None
        try:
            return (self.repo_root / path).read_bytes()
        except OSError:
            return None


class DeterministicRule(Protocol):
    """Protocol implemented by deterministic rules."""

    @property
    def rule_id(self) -> str:
        """Policy rule ID handled by this rule."""

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        """Evaluate the rule and return any findings."""
