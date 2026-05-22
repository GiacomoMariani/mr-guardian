"""Deterministic rules for Unity asset and project changes."""

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import (
    changed_file_patterns,
    dict_parameter,
    finding,
    matching_files,
    string_list,
)
from mr_guardian.rules.mr_metadata import (
    missing_sections_in_review_input,
    mr_text,
    required_sections,
)


class ChangedFilesRequireMrSectionRule:
    """Require MR sections when matching files changed."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        changed_files = matching_files(
            context.review_input.changed_files,
            changed_file_patterns(rule),
        )
        if not changed_files:
            return []

        missing_sections = missing_sections_in_review_input(
            context.review_input,
            required_sections(rule),
        )
        if not missing_sections:
            return []

        return [
            finding(
                rule,
                (
                    f"{changed_file.path.as_posix()} requires MR section(s): "
                    f"{', '.join(missing_sections)}."
                ),
                file_path=changed_file.path,
            )
            for changed_file in changed_files
        ]


class ChangedFilesRequireValidationRule:
    """Require validation evidence when matching files changed."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        changed_files = matching_files(
            context.review_input.changed_files,
            changed_file_patterns(rule),
        )
        if not changed_files:
            return []

        description = mr_text(context.review_input).lower()
        if "validation" in description or "test plan" in description:
            return []

        return [
            finding(
                rule,
                f"{changed_file.path.as_posix()} requires validation evidence in the MR.",
                file_path=changed_file.path,
            )
            for changed_file in changed_files
        ]


class ProductionCodeRequiresTestsOrValidationRule:
    """Require tests or MR validation when production code changes."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        production_files = matching_files(
            context.review_input.changed_files,
            changed_file_patterns(rule),
        )
        if not production_files:
            return []

        require_any = dict_parameter(rule, "require_any")
        test_patterns = string_list(require_any.get("changed_files"))
        if matching_files(context.review_input.changed_files, test_patterns):
            return []

        sections = string_list(require_any.get("mr_sections"))
        if sections and not missing_sections_in_review_input(context.review_input, sections):
            return []

        return [
            finding(
                rule,
                (
                    f"{changed_file.path.as_posix()} changes production code without "
                    "matching tests or MR validation."
                ),
                file_path=changed_file.path,
            )
            for changed_file in production_files
        ]
