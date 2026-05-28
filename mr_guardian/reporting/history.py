"""Review history rendering."""

from mr_guardian.models.history import ReviewRunRecord, TriggeredRuleStat


def render_review_history(
    review_runs: list[ReviewRunRecord],
    *,
    most_triggered_rules: list[TriggeredRuleStat] | None = None,
) -> str:
    """Render review history as a readable plain-text report."""
    lines = ["MR Guardian Review History", ""]

    if not review_runs:
        lines.append("No review runs have been stored yet.")
        return "\n".join(lines)

    headers = [
        "ID",
        "Timestamp",
        "Scope",
        "Branch",
        "Developer",
        "Ticket",
        "Score",
        "Risk",
        "B",
        "H",
        "W",
        "I",
        "Rules",
    ]
    rows = [
        [
            str(run.review_id),
            run.timestamp.isoformat(timespec="seconds"),
            run.review_scope,
            run.branch_name,
            run.developer_id,
            run.ticket_key or "-",
            str(run.review_score),
            run.risk,
            str(run.blocking_count),
            str(run.high_count),
            str(run.warning_count),
            str(run.info_count),
            ", ".join(run.triggered_rule_ids) or "-",
        ]
        for run in review_runs
    ]

    lines.extend(_render_table(headers, rows))

    if most_triggered_rules:
        lines.extend(["", "Most Triggered Rules", ""])
        rule_rows = [
            [stat.rule_id, str(stat.trigger_count)]
            for stat in most_triggered_rules
        ]
        lines.extend(_render_table(["Rule ID", "Count"], rule_rows))

    return "\n".join(lines)


def render_clear_history_result(removed_run_count: int) -> str:
    """Render the result of clearing review history."""
    return f"Removed {removed_run_count} review run(s)."


def _render_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    separator = "  ".join("-" * width for width in widths)
    rendered_rows = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        separator,
    ]
    rendered_rows.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return rendered_rows
