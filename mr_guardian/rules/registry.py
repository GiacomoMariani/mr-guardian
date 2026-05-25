"""Registry for deterministic rules."""

from collections.abc import Callable

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

DEFAULT_RULE_FACTORIES: dict[str, Callable[[], DeterministicRule]] = {
    "SIZE-FILES-001": lambda: ChangedFileCountRule("SIZE-FILES-001"),
    "SIZE-LINES-001": lambda: ChangedLineCountRule("SIZE-LINES-001"),
    "SIZE-DIRECTORIES-001": lambda: ChangedDirectoryCountRule("SIZE-DIRECTORIES-001"),
    "MR-META-001": lambda: RequiredMrSectionRule("MR-META-001"),
    "MR-META-002": lambda: RequiredMrSectionRule("MR-META-002"),
    "MR-META-003": lambda: RequiredMrSectionRule("MR-META-003"),
    "MR-META-004": lambda: RequiredMrSectionRule("MR-META-004"),
    "MR-META-005": lambda: RequiredMrSectionRule("MR-META-005"),
    "UNITY-SCENE-001": lambda: ChangedFilesRequireMrSectionRule("UNITY-SCENE-001"),
    "UNITY-PREFAB-001": lambda: ChangedFilesRequireValidationRule("UNITY-PREFAB-001"),
    "UNITY-PROJECTSETTINGS-001": lambda: ChangedFilesRequireMrSectionRule(
        "UNITY-PROJECTSETTINGS-001"
    ),
    "UNITY-TESTS-001": lambda: ProductionCodeRequiresTestsOrValidationRule("UNITY-TESTS-001"),
    "CSHARP-DEBUG-001": CSharpDebugLogRule,
    "CSHARP-GETCOMPONENT-001": lambda: AddedLineTokenRule(
        "CSHARP-GETCOMPONENT-001",
        ("GetComponent<",),
    ),
    "CSHARP-SIZE-001": lambda: CSharpClassSizeRule("CSHARP-SIZE-001"),
    "CSHARP-SIZE-002": lambda: CSharpMethodSizeRule("CSHARP-SIZE-002"),
    "CSHARP-PARAMETERS-001": lambda: CSharpMethodParameterCountRule("CSHARP-PARAMETERS-001"),
    "CSHARP-PUBLIC-FIELDS-001": lambda: CSharpPublicFieldsRule("CSHARP-PUBLIC-FIELDS-001"),
    "AI-CODE-001": lambda: ChangedFileCountRule("AI-CODE-001"),
    "PYTHON-PRINT-001": PythonPrintRule,
}


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
    return RuleRegistry([factory() for factory in DEFAULT_RULE_FACTORIES.values()])
