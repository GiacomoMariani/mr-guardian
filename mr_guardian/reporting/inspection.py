"""Text rendering for inspection results."""

from mr_guardian.core.inspection import InspectionResult, InspectionSuiteResult
from mr_guardian.models.review import Finding


def render_inspection_result(result: InspectionResult) -> str:
    """Render an inspection result as plain text."""
    lines = [
        "MR Guardian Inspect",
        "",
        f"Policy: {result.policy_path.as_posix()}",
        f"Policy version: {result.policy_version}",
        f"Rules: {result.enabled_rule_count} enabled, {result.disabled_rule_count} disabled",
        "",
        f"Base: {result.base_ref}",
        f"Changed files: {len(result.review_input.changed_files)}",
    ]

    lines.extend(
        f"- {changed_file.status}: {changed_file.path.as_posix()}"
        for changed_file in result.review_input.changed_files
    )

    lines.extend(
        [
            "",
            "Engine:",
            f"Findings: {len(result.engine_result.findings)}",
            f"Risk: {result.engine_result.risk}",
        ]
    )

    lines.extend(
        _render_finding(finding)
        for finding in result.engine_result.findings
    )
    return "\n".join(lines)


def render_inspection_suite_result(result: InspectionSuiteResult) -> str:
    """Render an inspection suite result as plain text."""
    lines = [
        "MR Guardian Inspect All",
        "",
        f"Policies: {result.policy_directory.as_posix()}",
        f"Policy files: {len(result.policy_results)}",
    ]

    for policy_result in result.policy_results:
        lines.extend(
            [
                "",
                f"Policy: {policy_result.policy_path.as_posix()}",
                f"Rules: {policy_result.enabled_rule_count} enabled, "
                f"{policy_result.disabled_rule_count} disabled",
                f"Changed files: {len(policy_result.review_input.changed_files)}",
                f"Findings: {len(policy_result.engine_result.findings)}",
                f"Risk: {policy_result.engine_result.risk}",
            ]
        )
        lines.extend(
            _render_finding(finding)
            for finding in policy_result.engine_result.findings
        )

    return "\n".join(lines)


def _render_finding(finding: Finding) -> str:
    location = ""
    if finding.file_path is not None:
        location = f" {finding.file_path.as_posix()}"
        if finding.line_number is not None:
            location = f"{location}:{finding.line_number}"

    return f"- [{finding.severity}] {finding.rule_id}{location} - {finding.message}"
