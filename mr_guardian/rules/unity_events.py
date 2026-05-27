"""Rule detecting Unity event subscriptions without visible cleanup."""

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import ChangedFile
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import (
    added_lines,
    changed_file_patterns,
    dict_parameter,
    finding,
    matching_files,
    string_list,
)

DEFAULT_SUBSCRIBE_TOKENS = ("+=", ".AddListener(", "AddEventListener(")
DEFAULT_UNSUBSCRIBE_TOKENS = ("-=", ".RemoveListener(", "RemoveEventListener(")


class UnityEventSubscriptionRule:
    """Flag event subscriptions when no unsubscribe path is visible in the diff."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        findings: list[Finding] = []
        subscribe_tokens = _configured_tokens(rule, "subscribe_tokens", DEFAULT_SUBSCRIBE_TOKENS)
        unsubscribe_tokens = _configured_tokens(
            rule,
            "unsubscribe_tokens",
            DEFAULT_UNSUBSCRIBE_TOKENS,
        )

        for changed_file in matching_files(
            context.review_input.changed_files,
            changed_file_patterns(rule),
        ):
            if _has_unsubscribe(changed_file, unsubscribe_tokens):
                continue

            for diff_line in added_lines(changed_file):
                if any(token in diff_line.content for token in subscribe_tokens):
                    findings.append(
                        finding(
                            rule,
                            (
                                "Added event subscription without a matching unsubscribe "
                                "visible in the changed file diff."
                            ),
                            file_path=changed_file.path,
                            line_number=diff_line.new_line_number,
                        )
                    )

        return findings


def _has_unsubscribe(changed_file: ChangedFile, tokens: tuple[str, ...]) -> bool:
    return any(
        token in diff_line.content
        for hunk in changed_file.hunks
        for diff_line in hunk.lines
        for token in tokens
    )


def _configured_tokens(
    rule: PolicyRule,
    key: str,
    default_tokens: tuple[str, ...],
) -> tuple[str, ...]:
    match = dict_parameter(rule, "match")
    tokens = string_list(match.get(key))
    return tuple(tokens) or default_tokens
