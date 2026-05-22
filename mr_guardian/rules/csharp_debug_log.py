"""Rule detecting newly added debug logging in Unity C# files."""

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import ChangedFile, DiffLine
from mr_guardian.rules.base import RuleEvaluationContext

RULE_ID = "CSHARP-DEBUG-001"
DEFAULT_DEBUG_TOKENS = ("Debug.Log", "print(")


class CSharpDebugLogRule:
    """Detect newly added debug logging in Unity C# files."""

    @property
    def rule_id(self) -> str:
        return RULE_ID

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        """Return findings for added Debug.Log or print statements."""
        debug_tokens = _debug_tokens_from_policy(rule)
        findings: list[Finding] = []

        for changed_file in context.review_input.changed_files:
            if not _is_relevant_csharp_file(changed_file):
                continue

            for diff_line in _added_lines(changed_file):
                if any(token in diff_line.content for token in debug_tokens):
                    findings.append(
                        Finding(
                            rule_id=rule.id,
                            severity=rule.severity,
                            message=(
                                "Debug logging should not be introduced in production "
                                "Unity C# code unless explicitly allowed."
                            ),
                            source=rule.source,
                            file_path=changed_file.path,
                            line_number=diff_line.new_line_number,
                        )
                    )

        return findings


def _is_relevant_csharp_file(changed_file: ChangedFile) -> bool:
    path = changed_file.path.as_posix()
    return (
        changed_file.status in {"added", "modified", "renamed"}
        and path.startswith("Assets/")
        and path.endswith(".cs")
    )


def _added_lines(changed_file: ChangedFile) -> list[DiffLine]:
    return [
        diff_line
        for hunk in changed_file.hunks
        for diff_line in hunk.lines
        if diff_line.kind == "addition"
    ]


def _debug_tokens_from_policy(rule: PolicyRule) -> tuple[str, ...]:
    match_config = rule.parameters.get("match")
    if not isinstance(match_config, dict):
        return DEFAULT_DEBUG_TOKENS

    tokens = match_config.get("added_lines_contain")
    if not isinstance(tokens, list):
        return DEFAULT_DEBUG_TOKENS

    parsed_tokens = tuple(token for token in tokens if isinstance(token, str))
    return parsed_tokens or DEFAULT_DEBUG_TOKENS
