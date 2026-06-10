"""Unity performance-oriented deterministic rules."""

import re

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import DiffLine
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import (
    added_lines,
    changed_file_patterns,
    dict_parameter,
    finding,
    matching_files,
    string_list,
)

DEFAULT_CALLBACKS = ("Update", "LateUpdate", "FixedUpdate")
DEFAULT_ALLOCATION_TOKENS = (
    "new ",
    ".Where(",
    ".Select(",
    ".ToList(",
    ".ToArray(",
    "string.Format(",
    '$"',
)
DEFAULT_POOLING_TOKENS = ("Instantiate(", "Destroy(")
DEFAULT_RUNTIME_METHOD_NAME_TOKENS = (
    "Update",
    "LateUpdate",
    "FixedUpdate",
    "Spawn",
    "Despawn",
    "Fire",
    "Shoot",
    "OnTrigger",
    "OnCollision",
)


class UnityPerFrameAllocationRule:
    """Flag likely allocations added inside Unity per-frame callbacks."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        callbacks = _configured_tokens(rule, "callbacks", DEFAULT_CALLBACKS)
        allocation_tokens = _configured_tokens(
            rule,
            "allocation_tokens",
            DEFAULT_ALLOCATION_TOKENS,
        )
        findings: list[Finding] = []

        for changed_file in matching_files(
            context.review_input.changed_files,
            changed_file_patterns(rule),
        ):
            for diff_line in _per_frame_added_lines(added_lines(changed_file), callbacks):
                if any(token in diff_line.content for token in allocation_tokens):
                    findings.append(
                        finding(
                            rule,
                            (
                                "Added likely allocation inside Unity per-frame callback; "
                                "consider caching, pooling, or moving work out of the frame loop."
                            ),
                            file_path=changed_file.path,
                            line_number=diff_line.new_line_number,
                        )
                    )

        return findings


class UnityRuntimeInstantiationRule:
    """Flag likely runtime Instantiate/Destroy usage that may need pooling."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        runtime_method_name_tokens = _configured_tokens(
            rule,
            "runtime_method_name_contains",
            DEFAULT_RUNTIME_METHOD_NAME_TOKENS,
        )
        pooling_tokens = _configured_tokens(rule, "pooling_tokens", DEFAULT_POOLING_TOKENS)
        findings: list[Finding] = []

        for changed_file in matching_files(
            context.review_input.changed_files,
            changed_file_patterns(rule),
        ):
            for diff_line in _runtime_method_added_lines(
                added_lines(changed_file),
                runtime_method_name_tokens,
            ):
                if any(token in diff_line.content for token in pooling_tokens):
                    findings.append(
                        finding(
                            rule,
                            (
                                "Added runtime Instantiate/Destroy usage; validate whether "
                                "object pooling is needed for this spawn/despawn path."
                            ),
                            file_path=changed_file.path,
                            line_number=diff_line.new_line_number,
                        )
                    )

        return findings


def _per_frame_added_lines(
    lines: list[DiffLine],
    callbacks: tuple[str, ...],
) -> list[DiffLine]:
    callback_pattern = re.compile(
        r"\b(?:void|IEnumerator)\s+(" + "|".join(re.escape(name) for name in callbacks) + r")\s*\("
    )
    selected_lines: list[DiffLine] = []
    in_callback = False
    brace_depth = 0
    seen_open_brace = False

    for line in lines:
        if not in_callback and callback_pattern.search(line.content):
            in_callback = True
            brace_depth = 0
            seen_open_brace = False

        if in_callback:
            selected_lines.append(line)
            brace_depth += line.content.count("{")
            if "{" in line.content:
                seen_open_brace = True
            brace_depth -= line.content.count("}")
            if seen_open_brace and brace_depth <= 0:
                in_callback = False

    return selected_lines


def _runtime_method_added_lines(
    lines: list[DiffLine],
    method_name_tokens: tuple[str, ...],
) -> list[DiffLine]:
    selected_lines: list[DiffLine] = []
    in_runtime_method = False
    brace_depth = 0
    seen_open_brace = False

    for line in lines:
        if not in_runtime_method and _runtime_method_declared(line.content, method_name_tokens):
            in_runtime_method = True
            brace_depth = 0
            seen_open_brace = False

        if in_runtime_method:
            selected_lines.append(line)
            brace_depth += line.content.count("{")
            if "{" in line.content:
                seen_open_brace = True
            brace_depth -= line.content.count("}")
            if seen_open_brace and brace_depth <= 0:
                in_runtime_method = False

    return selected_lines


def _runtime_method_declared(line: str, method_name_tokens: tuple[str, ...]) -> bool:
    match = re.search(
        r"\b(?:public|private|protected|internal)?\s*(?:void|IEnumerator)\s+"
        r"(?P<method_name>\w+)\s*\(",
        line,
    )
    if match is None:
        return False
    method_name = match.group("method_name")
    return any(token in method_name for token in method_name_tokens)


def _configured_tokens(
    rule: PolicyRule,
    key: str,
    default_tokens: tuple[str, ...],
) -> tuple[str, ...]:
    match = dict_parameter(rule, "match")
    tokens = string_list(match.get(key))
    return tuple(tokens) or default_tokens
