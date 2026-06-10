"""Review report rendering."""

from collections.abc import Iterable

from mr_guardian.core.review import ReviewResult
from mr_guardian.models.policy import Severity
from mr_guardian.models.review import (
    Finding,
    FindingCounts,
    LlmReviewSummary,
    LlmRuleMetric,
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

SKIPPED_LLM_STATUSES = {"skipped", "failed", "rate_limited"}
METADATA_MESSAGE_PREFIX = "MR metadata is missing required section(s): "


def render_review_report(result: ReviewResult) -> str:
    """Render a completed review result as a concise Markdown report."""
    findings = sorted(result.engine_result.findings, key=_finding_sort_key)
    skipped_llm_findings = [finding for finding in findings if _is_skipped_llm_finding(finding)]
    skipped_llm_metrics = _skipped_llm_metrics(result.engine_result.llm_metrics)
    skipped_rule_ids = _skipped_llm_rule_ids(skipped_llm_findings, skipped_llm_metrics)
    counts = result.engine_result.counts
    verdict, verdict_reason = _verdict(counts)

    lines = [
        "# MR Guardian Review",
        "",
        f"> **Verdict: `{verdict}`** - {verdict_reason}",
        (
            f"> Developer: `{_table_cell(result.developer_id)}` | "
            f"Files changed: **{len(result.review_input.changed_files)}** | "
            f"Lines: **{_count_changed_lines(result.review_input)}** | "
            f"Findings: **{len(findings)}**"
        ),
        "",
        "| Blocking | High | Warning | Info |",
        "|:--------:|:----:|:-------:|:----:|",
        (
            f"| {_count_cell(counts.blocking)} | {_count_cell(counts.high)} | "
            f"{_count_cell(counts.warning)} | {_count_cell(counts.info)} |"
        ),
    ]

    if result.llm_summary is not None:
        lines.extend(["", "## LLM Summary", ""])
        lines.extend(_render_llm_summary(result.llm_summary))

    section_number = 1
    if counts.blocking:
        lines.extend(["", f"## {section_number:02} - Why this is blocked", ""])
        lines.extend(_render_blocked_section(findings))
        section_number += 1

    if skipped_rule_ids:
        lines.extend(["", f"## {section_number:02} - Code analysis was not completed", ""])
        lines.extend(
            _render_skipped_llm_section(
                skipped_rule_ids=skipped_rule_ids,
                skipped_metrics=skipped_llm_metrics,
                skipped_findings=skipped_llm_findings,
            )
        )
        section_number += 1

    completed_llm_metrics = _completed_llm_metrics(result.engine_result.llm_metrics)
    if completed_llm_metrics:
        lines.extend(["", f"## {section_number:02} - LLM usage", ""])
        lines.extend(_render_llm_metric_table(completed_llm_metrics))
        section_number += 1

    lines.extend(["", f"## {section_number:02} - All findings", ""])
    lines.extend(_render_all_findings(findings, skipped_llm_findings))
    lines.extend(["", "## Next steps", ""])
    lines.extend(
        _render_next_steps(
            findings=findings,
            counts=counts,
            skipped_llm_rule_ids=skipped_rule_ids,
        )
    )
    lines.extend(["", _render_policy_footer(result)])

    return "\n".join(lines).rstrip()


def _verdict(counts: FindingCounts) -> tuple[str, str]:
    if counts.blocking:
        action = "action" if counts.blocking == 1 else "actions"
        return "BLOCKED", f"{counts.blocking} required {action} before merge"

    review_count = counts.high + counts.warning
    if review_count:
        item = "item" if review_count == 1 else "items"
        return "NEEDS REVIEW", f"{review_count} review {item} before merge"

    return "PASSED", "no required actions before merge"


def _count_cell(count: int) -> str:
    if count == 0:
        return "0"
    return f"**{count}**"


def _render_llm_summary(summary: LlmReviewSummary) -> list[str]:
    if summary.status == "succeeded" and summary.text:
        lines: list[str] = []
        if summary.score is not None:
            lines.append(f"**LLM score:** {summary.score}/100")
            lines.append("")
        lines.append(summary.text)
        return lines

    status = summary.status.replace("_", " ")
    if summary.error_message:
        return [f"LLM summary unavailable: {status} - {summary.error_message}"]
    return [f"LLM summary unavailable: {status}."]


def _render_blocked_section(findings: list[Finding]) -> list[str]:
    actionable_findings = [
        finding for finding in findings if finding.severity in {"blocking", "high", "warning"}
    ]
    metadata_findings = [finding for finding in actionable_findings if _metadata_sections(finding)]
    lines: list[str] = []

    if actionable_findings and len(actionable_findings) == len(metadata_findings):
        lines.append(
            "Every blocking and warning finding comes from **missing MR metadata "
            "sections** - not from the code itself. Add the required sections to "
            "the merge request description to clear the gate."
        )
        lines.append("")
    else:
        lines.append("This merge request has blocking findings that must be resolved before merge.")
        lines.append("")

    if metadata_findings:
        lines.extend(_render_metadata_table(metadata_findings))

    non_metadata_blocking = [
        finding
        for finding in findings
        if finding.severity == "blocking" and not _metadata_sections(finding)
    ]
    if non_metadata_blocking:
        if metadata_findings:
            lines.append("")
        lines.extend(_render_finding_table(non_metadata_blocking))

    return lines


def _render_metadata_table(findings: list[Finding]) -> list[str]:
    lines = [
        "| Section | Rule | Severity | Source |",
        "|---|---|---|---|",
    ]
    for finding in sorted(findings, key=_finding_sort_key):
        for section in _metadata_sections(finding):
            lines.append(
                "| "
                f"{_table_cell(section)} | "
                f"`{_table_cell(finding.rule_id)}` | "
                f"{SEVERITY_LABELS[finding.severity]} | "
                f"`{_table_cell(finding.source)}` |"
            )
    return lines


def _render_skipped_llm_section(
    *,
    skipped_rule_ids: list[str],
    skipped_metrics: list[LlmRuleMetric],
    skipped_findings: list[Finding],
) -> list[str]:
    provider_model = _skipped_provider_model(skipped_metrics)
    reason = _skipped_reason(skipped_metrics, skipped_findings)
    lines = [
        (
            f"> **{len(skipped_rule_ids)} LLM-based check(s) did not complete.** "
            f"The provider ({provider_model}) returned {reason}. A clean code result "
            "here does **not** mean the changed code passed review - re-run these "
            "checks before merge."
        ),
        "",
        "Skipped rules: " + ", ".join(f"`{rule_id}`" for rule_id in skipped_rule_ids),
    ]

    if skipped_metrics:
        lines.extend(["", *_render_llm_metric_table(skipped_metrics)])

    return lines


def _render_all_findings(
    findings: list[Finding],
    skipped_llm_findings: list[Finding],
) -> list[str]:
    if not findings:
        return ["No findings were triggered."]

    normal_findings = [finding for finding in findings if not _is_skipped_llm_finding(finding)]
    lines = _render_finding_table(normal_findings)

    if skipped_llm_findings:
        if not lines:
            lines = ["| Severity | Rule | Detail | Type | Source |", "|---|---|---|---|---|"]
        lines.append(_collapsed_skipped_llm_row(skipped_llm_findings))

    return lines


def _render_finding_table(findings: list[Finding]) -> list[str]:
    lines = ["| Severity | Rule | Detail | Type | Source |", "|---|---|---|---|---|"]
    for finding in sorted(findings, key=_finding_sort_key):
        detail = _finding_detail(finding)
        location = _format_location(finding)
        if location:
            detail = f"{detail} ({location})"
        lines.append(
            "| "
            f"`{SEVERITY_LABELS[finding.severity]}` | "
            f"`{_table_cell(finding.rule_id)}` | "
            f"{_table_cell(detail)} | "
            f"{_table_cell(finding.rule_type or 'unknown')} | "
            f"`{_table_cell(finding.source)}` |"
        )
    return lines


def _collapsed_skipped_llm_row(findings: list[Finding]) -> str:
    detail = "LLM rules skipped"
    reason = _skipped_reason(skipped_metrics=[], skipped_findings=findings)
    if reason != "an unavailable result":
        detail = f"{detail} - {reason}"
    return (
        "| "
        f"`Info x{len(findings)}` | "
        "`LLM skipped checks` | "
        f"{_table_cell(detail)} | "
        "llm | "
        "multiple |"
    )


def _render_next_steps(
    *,
    findings: list[Finding],
    counts: FindingCounts,
    skipped_llm_rule_ids: list[str],
) -> list[str]:
    steps: list[str] = []
    metadata_findings = [
        finding
        for finding in findings
        if finding.severity in {"blocking", "high", "warning"} and _metadata_sections(finding)
    ]
    blocking_sections = [
        section
        for finding in metadata_findings
        if finding.severity == "blocking"
        for section in _metadata_sections(finding)
    ]
    warning_sections = [
        section
        for finding in metadata_findings
        if finding.severity in {"high", "warning"}
        for section in _metadata_sections(finding)
    ]

    if blocking_sections:
        steps.append(
            "Add "
            + _format_section_list(blocking_sections)
            + " to the MR description to unblock the merge."
        )
    elif counts.blocking:
        steps.append(f"Resolve {counts.blocking} blocking finding(s) before merge.")

    if warning_sections:
        steps.append(
            "Add " + _format_section_list(warning_sections) + " to clear the metadata warnings."
        )
    elif counts.high or counts.warning:
        steps.append("Resolve or explicitly acknowledge the high and warning findings.")

    if skipped_llm_rule_ids:
        steps.append(
            "Re-run the review once the LLM provider is available so skipped checks can complete."
        )

    if not steps:
        steps.append("No immediate action required.")

    return [f"{index}. {step}" for index, step in enumerate(steps, start=1)]


def _render_policy_footer(result: ReviewResult) -> str:
    if not result.policy_results:
        return "<sub>**Policies evaluated:** none</sub>"

    policies = []
    for policy_result in result.policy_results:
        disabled = (
            f", {policy_result.disabled_rule_count} disabled"
            if policy_result.disabled_rule_count
            else ""
        )
        policies.append(
            f"`{policy_result.policy_path.name}` "
            f"({policy_result.enabled_rule_count} rules enabled{disabled})"
        )
    return "<sub>**Policies evaluated:** " + " | ".join(policies) + "</sub>"


def _is_skipped_llm_finding(finding: Finding) -> bool:
    return (
        finding.rule_type == "llm"
        and finding.severity == "info"
        and finding.message.startswith("LLM rule skipped:")
    )


def _skipped_llm_metrics(metrics: list[LlmRuleMetric]) -> list[LlmRuleMetric]:
    return [metric for metric in metrics if metric.status in SKIPPED_LLM_STATUSES]


def _completed_llm_metrics(metrics: list[LlmRuleMetric]) -> list[LlmRuleMetric]:
    return [metric for metric in metrics if metric.status not in SKIPPED_LLM_STATUSES]


def _render_llm_metric_table(metrics: list[LlmRuleMetric]) -> list[str]:
    lines = [
        "| Rule | Status | Duration | Tokens | Detail |",
        "|---|---:|---:|---:|---|",
    ]
    for metric in metrics:
        lines.append(
            "| "
            f"`{_table_cell(metric.rule_id)}` | "
            f"{_table_cell(metric.status)} | "
            f"{metric.duration_ms / 1000:.2f}s | "
            f"{_format_tokens(metric)} | "
            f"{_table_cell(metric.error_message or '-')} |"
        )
    return lines


def _format_tokens(metric: LlmRuleMetric) -> str:
    if metric.total_tokens is not None:
        return str(metric.total_tokens)
    if metric.input_tokens is None and metric.output_tokens is None:
        return "-"
    input_tokens = metric.input_tokens if metric.input_tokens is not None else 0
    output_tokens = metric.output_tokens if metric.output_tokens is not None else 0
    return str(input_tokens + output_tokens)


def _skipped_llm_rule_ids(
    skipped_findings: list[Finding],
    skipped_metrics: list[LlmRuleMetric],
) -> list[str]:
    rule_ids: list[str] = []
    seen_rule_ids: set[str] = set()
    for rule_id in [
        *(metric.rule_id for metric in skipped_metrics),
        *(finding.rule_id for finding in skipped_findings),
    ]:
        if rule_id in seen_rule_ids:
            continue
        rule_ids.append(rule_id)
        seen_rule_ids.add(rule_id)
    return sorted(rule_ids)


def _skipped_provider_model(metrics: list[LlmRuleMetric]) -> str:
    if not metrics:
        return "LLM provider"

    metric = metrics[0]
    return f"{_provider_label(metric.provider)} - `{metric.model}`"


def _skipped_reason(
    skipped_metrics: list[LlmRuleMetric],
    skipped_findings: list[Finding],
) -> str:
    statuses = {metric.status for metric in skipped_metrics}
    messages = [
        *(metric.error_message or "" for metric in skipped_metrics),
        *(finding.message for finding in skipped_findings),
    ]
    if "rate_limited" in statuses or any("rate limit" in message.lower() for message in messages):
        return "a rate limit"
    if "failed" in statuses:
        return "an error"
    if "skipped" in statuses:
        return "a skipped result"
    return "an unavailable result"


def _provider_label(provider: str) -> str:
    if provider.lower() == "openai":
        return "OpenAI"
    return provider


def _metadata_sections(finding: Finding) -> list[str]:
    if METADATA_MESSAGE_PREFIX not in finding.message:
        return []

    raw_sections = finding.message.split(METADATA_MESSAGE_PREFIX, maxsplit=1)[1]
    sections = raw_sections.strip().rstrip(".")
    return [section.strip() for section in sections.split(",") if section.strip()]


def _finding_detail(finding: Finding) -> str:
    sections = _metadata_sections(finding)
    if len(sections) == 1:
        return f"Missing required section: {sections[0]}"
    if len(sections) > 1:
        return "Missing required sections: " + _format_section_list(sections)
    return finding.message


def _format_section_list(sections: list[str]) -> str:
    unique_sections: list[str] = []
    seen_sections: set[str] = set()
    for section in sections:
        if section in seen_sections:
            continue
        unique_sections.append(section)
        seen_sections.add(section)

    if not unique_sections:
        return "the required sections"
    if len(unique_sections) == 1:
        return f"the {unique_sections[0]} section"
    if len(unique_sections) == 2:
        return f"the {unique_sections[0]} and {unique_sections[1]} sections"
    return "the " + ", ".join(unique_sections[:-1]) + f", and {unique_sections[-1]} sections"


def _table_cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|").strip()


def _finding_sort_key(finding: Finding) -> tuple[int, str, str, int, str]:
    return (
        SEVERITY_RANK[finding.severity],
        finding.rule_id,
        finding.file_path.as_posix() if finding.file_path is not None else "",
        finding.line_number or 0,
        finding.message,
    )


def _format_location(finding: Finding) -> str:
    if finding.file_path is None:
        return ""

    location = finding.file_path.as_posix()
    if finding.line_number is not None:
        location = f"{location}:{finding.line_number}"
    return location


def _count_changed_lines(review_input: ReviewInput) -> int:
    return sum(1 for line in _diff_lines(review_input) if line.kind in {"addition", "deletion"})


def _diff_lines(review_input: ReviewInput) -> Iterable[DiffLine]:
    for changed_file in review_input.changed_files:
        for hunk in changed_file.hunks:
            yield from hunk.lines
