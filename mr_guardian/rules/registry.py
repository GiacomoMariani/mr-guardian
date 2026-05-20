"""Registry for deterministic rules."""

from mr_guardian.rules.base import DeterministicRule
from mr_guardian.rules.csharp_debug_log import CSharpDebugLogRule
from mr_guardian.rules.python_print import PythonPrintRule


class RuleRegistry:
    """Small registry mapping policy rule IDs to deterministic rule implementations."""

    def __init__(self, rules: list[DeterministicRule] | None = None) -> None:
        self._rules: dict[str, DeterministicRule] = {}
        for rule in rules or []:
            self.register(rule)

    def register(self, rule: DeterministicRule) -> None:
        """Register a deterministic rule implementation."""
        self._rules[rule.rule_id] = rule

    def get(self, rule_id: str) -> DeterministicRule | None:
        """Return a registered rule by ID, if present."""
        return self._rules.get(rule_id)


def default_rule_registry() -> RuleRegistry:
    """Return the default deterministic rule registry."""
    return RuleRegistry([CSharpDebugLogRule(), PythonPrintRule()])
