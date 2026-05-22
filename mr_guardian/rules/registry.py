"""Registry for deterministic rules."""

from mr_guardian.rules.base import DeterministicRule
from mr_guardian.rules.csharp_debug_log import CSharpDebugLogRule
from mr_guardian.rules.csharp_get_component import AddedLineTokenRule
from mr_guardian.rules.csharp_public_fields import CSharpPublicFieldsRule
from mr_guardian.rules.csharp_size import (
    CSharpClassSizeRule,
    CSharpMethodParameterCountRule,
    CSharpMethodSizeRule,
)
from mr_guardian.rules.mr_metadata import RequiredMrSectionRule
from mr_guardian.rules.python_print import PythonPrintRule
from mr_guardian.rules.size import (
    ChangedDirectoryCountRule,
    ChangedFileCountRule,
    ChangedLineCountRule,
)
from mr_guardian.rules.unity_assets import (
    ChangedFilesRequireMrSectionRule,
    ChangedFilesRequireValidationRule,
    ProductionCodeRequiresTestsOrValidationRule,
)


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
    return RuleRegistry(
        [
            ChangedFileCountRule("SIZE-FILES-001"),
            ChangedLineCountRule("SIZE-LINES-001"),
            ChangedDirectoryCountRule("SIZE-DIRECTORIES-001"),
            RequiredMrSectionRule("MR-META-001"),
            RequiredMrSectionRule("MR-META-002"),
            RequiredMrSectionRule("MR-META-003"),
            RequiredMrSectionRule("MR-META-004"),
            RequiredMrSectionRule("MR-META-005"),
            ChangedFilesRequireMrSectionRule("UNITY-SCENE-001"),
            ChangedFilesRequireValidationRule("UNITY-PREFAB-001"),
            ChangedFilesRequireMrSectionRule("UNITY-PROJECTSETTINGS-001"),
            ProductionCodeRequiresTestsOrValidationRule("UNITY-TESTS-001"),
            CSharpDebugLogRule(),
            AddedLineTokenRule("CSHARP-GETCOMPONENT-001", ("GetComponent<",)),
            CSharpClassSizeRule("CSHARP-SIZE-001"),
            CSharpMethodSizeRule("CSHARP-SIZE-002"),
            CSharpMethodParameterCountRule("CSHARP-PARAMETERS-001"),
            CSharpPublicFieldsRule("CSHARP-PUBLIC-FIELDS-001"),
            ChangedFileCountRule("AI-CODE-001"),
            PythonPrintRule(),
        ]
    )
