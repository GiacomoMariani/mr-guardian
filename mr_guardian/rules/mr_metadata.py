"""Deterministic rules for MR metadata."""

from collections.abc import Iterable

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import dict_parameter, finding, string_list


class RequiredMrSectionRule:
    """Require configured sections in MR text."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        missing_sections = missing_sections_in_review_input(
            context.review_input,
            required_sections(rule),
        )
        if not missing_sections:
            return []

        return [
            finding(
                rule,
                f"MR metadata is missing required section(s): {', '.join(missing_sections)}.",
            )
        ]


def required_sections(rule: PolicyRule) -> list[str]:
    """Return required MR sections from rule parameters."""
    require = dict_parameter(rule, "require")
    return string_list(require.get("mr_sections"))


def missing_sections_in_review_input(
    review_input: ReviewInput,
    sections: Iterable[str],
) -> list[str]:
    """Return required section names absent from review input text."""
    review_text = mr_text(review_input).lower()
    return [section for section in sections if section.lower() not in review_text]


def mr_text(review_input: ReviewInput) -> str:
    """Return MR title and description as one searchable string."""
    return f"{review_input.title}\n{review_input.description}"
