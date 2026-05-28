"""Review report rendering."""

from collections import Counter
from collections.abc import Iterable

from mr_guardian.core.review import ReviewResult
from mr_guardian.models.policy import EvaluationDimension, Severity
from mr_guardian.models.review import (
    EVALUATION_ORDER,
    Finding,
    LlmReviewSummary,
    LlmRuleMetric,
    ReviewEvaluation,
    RiskLevel,
    summarize_review_evaluations,
)
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
EVALUATION_LABELS: dict[EvaluationDimension, str] = {
    "coding": "Coding",
    "mr_structure": "MR structure",
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
    ]

    if result.llm_summary is not None:
        lines.extend(["", "### LLM Summary", ""])
        lines.extend(_render_llm_summary(result.llm_summary))

    lines.extend(
        [
            "",
            "### Evaluation",
            "",
        ]
    )

    lines.extend(_render_evaluations(_review_evaluations(result)))
    lines.extend(
        [
            "",
            "### Reviewer Focus",
            "",
        ]
    )

    lines.extend(_render_reviewer_focus(result.engine_result.findings))
    lines.extend(["", "### LLM Usage", ""])
    lines.extend(_render_llm_usage(result.engine_result.llm_metrics))
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


def _render_evaluations(evaluations: list[ReviewEvaluation]) -> list[str]:
    lines: list[str] = []
    for evaluation in evaluations:
        lines.append(
            f"- {EVALUATION_LABELS[evaluation.evaluation]}: "
            f"{_format_risk(evaluation.risk)}"
        )
        lines.append(f"  - Blocking: {evaluation.counts.blocking}")
        lines.append(f"  - High: {evaluation.counts.high}")
        lines.append(f"  - Warning: {evaluation.counts.warning}")
        lines.append(f"  - Info: {evaluation.counts.info}")
        if evaluation.triggered_rule_ids:
            lines.append(f"  - Rules: {', '.join(evaluation.triggered_rule_ids)}")
        else:
            lines.append("  - Rules: none")
    return lines


def _review_evaluations(result: ReviewResult) -> list[ReviewEvaluation]:
    evaluations = result.engine_result.evaluations or summarize_review_evaluations(
        result.engine_result.findings
    )
    evaluation_by_dimension = {
        evaluation.evaluation: evaluation for evaluation in evaluations
    }
    fallback_evaluations = summarize_review_evaluations(result.engine_result.findings)
    fallback_by_dimension = {
        evaluation.evaluation: evaluation for evaluation in fallback_evaluations
    }
    return [
        evaluation_by_dimension.get(
            evaluation,
            fallback_by_dimension[evaluation],
        )
        for evaluation in EVALUATION_ORDER
    ]


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


def _render_llm_usage(metrics: list[LlmRuleMetric]) -> list[str]:
    if not metrics:
        return ["No LLM rules were executed."]

    lines: list[str] = []
    for metric in metrics:
        lines.append(f"- `{metric.rule_id}`")
        lines.append(f"  - Status: {metric.status}")
        lines.append(f"  - Provider: {metric.provider}")
        lines.append(f"  - Model: {metric.model}")
        lines.append(f"  - Duration: {metric.duration_ms / 1000:.2f}s")
        if metric.input_tokens is not None:
            lines.append(f"  - Input tokens: {metric.input_tokens}")
        if metric.output_tokens is not None:
            lines.append(f"  - Output tokens: {metric.output_tokens}")
        if metric.total_tokens is not None:
            lines.append(f"  - Total tokens: {metric.total_tokens}")
        if metric.error_message is not None:
            lines.append(f"  - Error: {metric.error_message}")
    return lines


def _render_llm_summary(summary: LlmReviewSummary) -> list[str]:
    if summary.status == "succeeded" and summary.text:
        return [summary.text]

    status = summary.status.replace("_", " ")
    if summary.error_message:
        return [f"LLM summary unavailable: {status} - {summary.error_message}"]
    return [f"LLM summary unavailable: {status}."]


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
