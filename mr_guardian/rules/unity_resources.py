"""Unity asset-loading deterministic rules."""

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import (
    added_lines,
    changed_file_patterns,
    dict_parameter,
    finding,
    matching_files,
    string_list,
)

DEFAULT_RESOURCE_TOKENS = ("Resources.Load", "Resources.LoadAll")


class UnityResourcesLoadRule:
    """Flag newly added Resources API usage for asset-loading review."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        resource_tokens = _configured_tokens(rule)
        findings: list[Finding] = []

        for changed_file in matching_files(
            context.review_input.changed_files,
            changed_file_patterns(rule),
        ):
            for diff_line in added_lines(changed_file):
                if _line_uses_resources(diff_line.content, resource_tokens):
                    findings.append(
                        finding(
                            rule,
                            (
                                "Added Resources.Load usage; check Addressables, serialized "
                                "references, or document an explicit asset-loading plan."
                            ),
                            file_path=changed_file.path,
                            line_number=diff_line.new_line_number,
                        )
                    )

        return findings


def _configured_tokens(rule: PolicyRule) -> tuple[str, ...]:
    match = dict_parameter(rule, "match")
    tokens = string_list(match.get("resource_tokens"))
    return tuple(tokens) or DEFAULT_RESOURCE_TOKENS


def _line_uses_resources(line: str, resource_tokens: tuple[str, ...]) -> bool:
    stripped = line.strip()
    return not stripped.startswith("//") and any(token in line for token in resource_tokens)
