"""Review report rendering."""

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


def render_review_report(result: ReviewResult) -> str:
    """Render a completed review result as a Markdown report."""
    counts = result.engine_result.counts
    lines = [
        "## MR Guardian Review",
        "",
        f"**Risk:** {_format_risk(result.engine_result.risk)}",
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
        "### Findings",
        "",
    ]

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

        lines.extend([f"#### {SEVERITY_LABELS[severity]}", ""])
        lines.extend(_render_finding(finding) for finding in findings)
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


def _format_location(finding: Finding) -> str:
    if finding.file_path is None:
        return ""

    location = finding.file_path.as_posix()
    if finding.line_number is not None:
        location = f"{location}:{finding.line_number}"
    return location


def _format_risk(risk: RiskLevel) -> str:
    if risk == "none":
        return "None"
    return SEVERITY_LABELS[risk]


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
