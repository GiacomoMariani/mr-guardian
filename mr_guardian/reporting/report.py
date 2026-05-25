"""Review report rendering."""

from collections import Counter
from collections.abc import Iterable

from mr_guardian.core.review import ReviewResult
from mr_guardian.models.policy import Severity
from mr_guardian.models.review import Finding, RiskLevel
from mr_guardian.models.review_input import DiffLine, ReviewInput

SEVERITY_ORDER: tuple[Severity, ...] = ("blocking", "high", "warning", "info")
SEVERITY_LABELS: dict[Severity, str] = {
    "blocking": "Blocking",
    "high": "High",
    "warning": "Warning",
    "info": "Info",
}
SEVERITY_RANK: dict[Severity, int] = {
    severity: index for index, severity in enumerate(SEVERITY_ORDER)
}
MAX_FINDINGS_PER_SEVERITY = 10
MAX_REVIEWER_FOCUS_ITEMS = 5
MAX_RULE_OVERVIEW_ITEMS = 5


def render_review_report(result: ReviewResult) -> str:
    """Render a completed review result as a Markdown report."""
    counts = result.engine_result.counts
    lines = [
        "## MR Guardian Review",
        "",
        f"**Risk:** {_format_risk(result.engine_result.risk)}",
        f"**Developer:** {result.developer_id}",
        "",
        "### Summary",
        "",
        f"- Blocking: {counts.blocking}",
        f"- High: {counts.high}",
        f"- Warning: {counts.warning}",
        f"- Info: {counts.info}",
        f"- Changed files: {len(result.review_input.changed_files)}",
        f"- Changed lines: {_count_changed_lines(result.review_input)}",
        "",
        "### Reviewer Focus",
        "",
    ]

    lines.extend(_render_reviewer_focus(result.engine_result.findings))
    lines.extend(["", "### Finding Overview", ""])
    lines.extend(_render_finding_overview(result.engine_result.findings))
    lines.extend(["", "### Policies", ""])

    if result.policy_results:
        lines.extend(
            f"- {policy_result.policy_path.as_posix()}: "
            f"{policy_result.enabled_rule_count} enabled, "
            f"{policy_result.disabled_rule_count} disabled"
            for policy_result in result.policy_results
        )
    else:
        lines.append("No policy files were evaluated.")

    lines.extend(
        [
            "",
            "### Findings",
            "",
            "Findings are grouped by severity and ordered by priority, rule ID, "
            "location, and message. "
            f"At most {MAX_FINDINGS_PER_SEVERITY} findings are shown per "
            "non-blocking severity.",
            "",
        ]
    )

    if not result.engine_result.findings:
        lines.append("No findings were triggered.")
        return "\n".join(lines)

    for severity in SEVERITY_ORDER:
        findings = [
            finding
            for finding in result.engine_result.findings
            if finding.severity == severity
        ]
        if not findings:
            continue

        ordered_findings = sorted(findings, key=_finding_sort_key)
        displayed_findings = _displayed_findings(severity, ordered_findings)
        lines.extend([f"#### {SEVERITY_LABELS[severity]}", ""])
        lines.extend(_render_finding(finding) for finding in displayed_findings)
        omitted_count = len(ordered_findings) - len(displayed_findings)
        if omitted_count:
            lines.append(
                f"- {omitted_count} additional {severity} finding(s) hidden by report limit."
            )
        lines.append("")

    return "\n".join(lines).rstrip()


def _render_finding(finding: Finding) -> str:
    lines = [f"- `{finding.rule_id}` - {finding.message}"]
    location = _format_location(finding)
    if location:
        lines.append(f"  - Location: {location}")
    lines.append(f"  - Source: {finding.source}")
    if finding.rule_type is not None:
        lines.append(f"  - Rule type: {finding.rule_type}")
    return "\n".join(lines)


def _render_reviewer_focus(findings: list[Finding]) -> list[str]:
    if not findings:
        return ["No immediate reviewer action required."]

    ordered_findings = sorted(findings, key=_priority_sort_key)
    displayed_findings = ordered_findings[:MAX_REVIEWER_FOCUS_ITEMS]
    lines = [f"- {_format_focus_finding(finding)}" for finding in displayed_findings]
    omitted_count = len(ordered_findings) - len(displayed_findings)
    if omitted_count:
        lines.append(f"- {omitted_count} lower-priority finding(s) omitted from focus.")
    return lines


def _render_finding_overview(findings: list[Finding]) -> list[str]:
    if not findings:
        return ["No triggered rules."]

    rule_counts = Counter(finding.rule_id for finding in findings)
    ordered_rule_ids = sorted(
        rule_counts,
        key=lambda rule_id: (
            -rule_counts[rule_id],
            _highest_severity_rank(findings, rule_id),
            rule_id,
        ),
    )
    displayed_rule_ids = ordered_rule_ids[:MAX_RULE_OVERVIEW_ITEMS]
    lines = [
        (
            f"- `{rule_id}`: {rule_counts[rule_id]} finding(s), "
            f"highest severity {_format_risk(_highest_severity(findings, rule_id))}, "
            f"{_rule_type_label(findings, rule_id)}"
        )
        for rule_id in displayed_rule_ids
    ]
    omitted_count = len(ordered_rule_ids) - len(displayed_rule_ids)
    if omitted_count:
        lines.append(f"- {omitted_count} additional triggered rule(s) omitted from overview.")
    return lines


def _displayed_findings(severity: Severity, findings: list[Finding]) -> list[Finding]:
    if severity == "blocking":
        return findings
    return findings[:MAX_FINDINGS_PER_SEVERITY]


def _finding_sort_key(finding: Finding) -> tuple[int, str, str, int, str]:
    return (
        SEVERITY_RANK[finding.severity],
        finding.rule_id,
        finding.file_path.as_posix() if finding.file_path is not None else "",
        finding.line_number or 0,
        finding.message,
    )


def _priority_sort_key(finding: Finding) -> tuple[int, str, int, str, str]:
    return (
        SEVERITY_RANK[finding.severity],
        finding.file_path.as_posix() if finding.file_path is not None else "",
        finding.line_number or 0,
        finding.rule_id,
        finding.message,
    )


def _format_focus_finding(finding: Finding) -> str:
    location = _format_location(finding)
    location_text = f" at {location}" if location else ""
    return (
        f"[{SEVERITY_LABELS[finding.severity]}] "
        f"`{finding.rule_id}`{location_text} - {finding.message}"
    )


def _format_location(finding: Finding) -> str:
    if finding.file_path is None:
        return ""

    location = finding.file_path.as_posix()
    if finding.line_number is not None:
        location = f"{location}:{finding.line_number}"
    return location


def _format_risk(risk: RiskLevel | Severity) -> str:
    if risk == "none":
        return "None"
    return SEVERITY_LABELS[risk]


def _highest_severity(findings: list[Finding], rule_id: str) -> Severity:
    return min(
        (finding.severity for finding in findings if finding.rule_id == rule_id),
        key=lambda severity: SEVERITY_RANK[severity],
    )


def _highest_severity_rank(findings: list[Finding], rule_id: str) -> int:
    return SEVERITY_RANK[_highest_severity(findings, rule_id)]


def _rule_type_label(findings: list[Finding], rule_id: str) -> str:
    rule_types = {
        finding.rule_type
        for finding in findings
        if finding.rule_id == rule_id and finding.rule_type is not None
    }
    if not rule_types:
        return "rule type unknown"
    if len(rule_types) == 1:
        return f"{next(iter(rule_types))} rule"
    return "mixed rule types"


def _count_changed_lines(review_input: ReviewInput) -> int:
    return sum(
        1
        for line in _diff_lines(review_input)
        if line.kind in {"addition", "deletion"}
    )


def _diff_lines(review_input: ReviewInput) -> Iterable[DiffLine]:
    for changed_file in review_input.changed_files:
        for hunk in changed_file.hunks:
            yield from hunk.lines
