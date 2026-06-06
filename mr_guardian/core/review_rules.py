"""Which rules are involved in a stored review (tickets 059/060).

Pure (no Streamlit) so the dashboard stays a thin renderer over it.
"""

from collections.abc import Sequence

from mr_guardian.models.review import Finding

_SEVERITY_RANK = {"blocking": 0, "high": 1, "warning": 2, "info": 3}
_UNKNOWN_RANK = 99


def rules_that_ran(
    findings: Sequence[Finding],
    triggered_rule_ids: Sequence[str],
) -> list[str]:
    """Return de-duplicated rule IDs involved in a review, most severe first.

    Findings carry severity (used for ordering); rule IDs that only appear in
    ``triggered_rule_ids`` have no severity and sort last, then by ID.
    """
    rank_by_id: dict[str, int] = {}
    for finding in findings:
        rank = _SEVERITY_RANK.get(finding.severity, _UNKNOWN_RANK)
        current = rank_by_id.get(finding.rule_id)
        if current is None or rank < current:
            rank_by_id[finding.rule_id] = rank
    for rule_id in triggered_rule_ids:
        rank_by_id.setdefault(rule_id, _UNKNOWN_RANK)
    return sorted(rank_by_id, key=lambda rule_id: (rank_by_id[rule_id], rule_id))
