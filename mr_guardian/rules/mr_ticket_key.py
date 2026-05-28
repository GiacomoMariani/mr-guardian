"""Deterministic MR ticket key rules."""

import re

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import finding, string_list

DEFAULT_TITLE_PATTERN = r"\bTK-\d+\b"


class MrTitleTicketKeyRule:
    """Require a configured ticket key pattern in the MR title."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        if not _applies_to_scope(context.review_input.review_scope, rule):
            return []

        title_pattern = _title_pattern(rule)
        if re.search(title_pattern, context.review_input.title):
            return []

        return [
            finding(
                rule,
                f"MR title must include a ticket key matching `{title_pattern}`.",
            )
        ]


def _title_pattern(rule: PolicyRule) -> str:
    pattern = rule.parameters.get("title_pattern")
    return pattern if isinstance(pattern, str) and pattern else DEFAULT_TITLE_PATTERN


def _applies_to_scope(review_scope: str, rule: PolicyRule) -> bool:
    required_review_scopes = string_list(rule.parameters.get("required_review_scopes"))
    if not required_review_scopes:
        return True
    return review_scope in required_review_scopes
