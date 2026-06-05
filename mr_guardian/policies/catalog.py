"""Resolve rule IDs to their policy definitions — the dashboard rule catalog.

Ticket 059. Pure (no Streamlit) so it stays unit-testable and cacheable: it reads
the policy YAML directory into a ``{rule_id: PolicyRule}`` map plus a small summary,
which the dashboard uses to turn rule IDs into clickable, self-describing chips.
"""

from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from mr_guardian.models.policy import PolicyRule
from mr_guardian.policies.defaults import resolve_policy_directory
from mr_guardian.policies.loader import load_policies_from_directory


class RuleCatalogSummary(BaseModel):
    """Aggregate counts over a rule catalog."""

    model_config = ConfigDict(frozen=True)

    total: int
    blocking: int
    by_type: dict[str, int]
    by_dimension: dict[str, int]
    by_severity: dict[str, int]


def load_rule_catalog(policy_directory: str | Path) -> dict[str, PolicyRule]:
    """Return a ``{rule_id: PolicyRule}`` map for every rule in the policy directory.

    Falls back to the packaged default policies when the directory has no YAML
    (mirrors the review pipeline). On duplicate IDs, the last file loaded wins.
    """
    with resolve_policy_directory(Path(policy_directory)) as resolved:
        policies = load_policies_from_directory(resolved)
    catalog: dict[str, PolicyRule] = {}
    for policy in policies:
        for rule in policy.rules:
            catalog[rule.id] = rule
    return catalog


def summarize_catalog(catalog: dict[str, PolicyRule]) -> RuleCatalogSummary:
    """Summarize a catalog by type, evaluation dimension, and severity."""
    rules = list(catalog.values())
    by_severity = Counter(str(rule.severity) for rule in rules)
    return RuleCatalogSummary(
        total=len(rules),
        blocking=by_severity.get("blocking", 0),
        by_type=dict(Counter(str(rule.type) for rule in rules)),
        by_dimension=dict(Counter(str(rule.evaluation) for rule in rules)),
        by_severity=dict(by_severity),
    )
