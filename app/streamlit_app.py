"""Streamlit dashboard for MR Guardian review history."""

import sys
from datetime import datetime
from html import escape
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _runtime_error() -> str | None:
    try:
        pydantic_version = version("pydantic")
    except PackageNotFoundError:
        return "MR Guardian requires Pydantic 2.7 or newer, but Pydantic is not installed."

    major_version = int(pydantic_version.split(".", maxsplit=1)[0])
    if major_version < 2:
        return (
            "MR Guardian requires Pydantic 2.7 or newer. "
            f"Streamlit is using Pydantic {pydantic_version}."
        )

    return None


RUNTIME_ERROR = _runtime_error()
if RUNTIME_ERROR is not None:
    import streamlit as st

    st.error(RUNTIME_ERROR)
    st.code(
        'python -m pip install -e ".[dashboard]"\n'
        "python -m streamlit run app/streamlit_app.py",
        language="powershell",
    )
    st.stop()

from app.streamlit_components import (  # noqa: E402
    MetricCard,
    TableCell,
    Tone,
    cell_chips,
    cell_link,
    cell_pill,
    cell_text,
    render_empty_state,
    render_metric_grid,
    render_page_header,
    render_raw_markdown_block,
    render_section,
    render_table,
)
from app.streamlit_style import (  # noqa: E402
    THEME_LABELS,
    DashboardTheme,
    dashboard_css,
    theme_from_label,
)
from mr_guardian.config import get_settings  # noqa: E402
from mr_guardian.core.dashboard import DashboardData, load_dashboard_data  # noqa: E402
from mr_guardian.core.lead_dashboard import (  # noqa: E402
    load_lead_dashboard_summary,
    load_lead_developer_detail,
)
from mr_guardian.core.pm_dashboard import load_pm_dashboard_summary  # noqa: E402
from mr_guardian.models.history import ReviewRunRecord, TriggeredRuleStat  # noqa: E402
from mr_guardian.models.lead_dashboard import LeadDeveloperSummary  # noqa: E402
from mr_guardian.models.pm_dashboard import (  # noqa: E402
    PmRecurringBlocker,
    PmTicketStatus,
)
from mr_guardian.models.review import RiskLevel  # noqa: E402
from mr_guardian.reporting.visual_report import render_visual_review_report  # noqa: E402
from mr_guardian.storage import ReviewHistoryStore  # noqa: E402


def main() -> None:
    """Render the Streamlit dashboard."""
    import streamlit as st

    settings = get_settings()
    st.set_page_config(page_title="MR Guardian", layout="wide")
    theme_label = st.sidebar.selectbox("Theme", list(THEME_LABELS), index=0)
    theme = theme_from_label(str(theme_label))
    st.markdown(dashboard_css(theme), unsafe_allow_html=True)

    database_path = Path(
        st.sidebar.text_input("History database", str(settings.history_db_path))
    )
    if _is_developer_view(st):
        _render_developer_detail_page(st, database_path, theme)
        return

    recent_limit = st.sidebar.number_input(
        "Recent review limit",
        min_value=1,
        max_value=500,
        value=50,
        step=10,
    )

    data = load_dashboard_data(database_path, recent_limit=int(recent_limit))
    _render_page_heading(
        st,
        title="MR Guardian",
        kicker="Review Intelligence",
        body=(
            "Policy-driven merge request review history, delivery risk, "
            "developer trends, and reviewer-ready reports."
        ),
        meta_items=(
            ("Database", database_path.name),
            ("Reviews", str(len(data.recent_reviews))),
            ("Mode", "Dashboard"),
        ),
    )
    _render_metrics(st, data)
    _render_pm_dashboard(st, database_path)
    _render_lead_dashboard(st, database_path)
    _render_recent_reviews(st, data)
    _render_selected_report(st, database_path, data, theme)


def _render_page_heading(
    st,
    *,
    title: str,
    kicker: str,
    body: str,
    meta_items: tuple[tuple[str, str], ...] = (),
) -> None:
    st.markdown(
        render_page_header(
            title=title,
            kicker=kicker,
            body=body,
            meta_items=meta_items,
        ),
        unsafe_allow_html=True,
    )


def _render_html(st, html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def _render_metrics(st, data: DashboardData) -> None:
    risk_counts = {risk_count.risk: risk_count.count for risk_count in data.risk_counts}
    _render_html(
        st,
        render_section(
            index=1,
            title="Overview",
            eyebrow="Recent review window",
            body_html=render_metric_grid(
                [
                    MetricCard(
                        label="Blocking Reviews",
                        value=risk_counts.get("blocking", 0),
                        tone="blocking",
                    ),
                    MetricCard(
                        label="High Risk Reviews",
                        value=risk_counts.get("high", 0),
                        tone="high",
                    ),
                    MetricCard(
                        label="Warning Reviews",
                        value=risk_counts.get("warning", 0),
                        tone="warning",
                    ),
                    MetricCard(
                        label="Info Reviews",
                        value=risk_counts.get("info", 0),
                        tone="info",
                    ),
                    MetricCard(
                        label="AI-Code Risk Runs",
                        value=data.ai_code_risk_frequency,
                        tone="accent",
                    ),
                ]
            ),
        ),
    )

    _render_html(
        st,
        render_section(
            index=2,
            title="Most Triggered Rules",
            body_html=_triggered_rules_table(data.most_triggered_rules),
        ),
    )

    _render_html(
        st,
        render_section(
            index=3,
            title="Risk Trends",
            body_html=_trend_table(data),
        ),
    )
    if data.trend_points:
        st.line_chart(
            {
                "Blocking": {
                    point.date: point.blocking_count
                    for point in data.trend_points
                },
                "Warnings": {
                    point.date: point.warning_count
                    for point in data.trend_points
                },
            }
        )


def _render_recent_reviews(st, data: DashboardData) -> None:
    _render_html(
        st,
        render_section(
            index=8,
            title="Recent Reviews",
            body_html=_recent_reviews_table(data.recent_reviews),
        ),
    )


def _render_pm_dashboard(st, database_path: Path) -> None:
    lookback_days = st.number_input(
        "PM lookback days",
        min_value=1,
        max_value=365,
        value=30,
        step=1,
    )
    summary = load_pm_dashboard_summary(
        database_path,
        days=int(lookback_days),
    )

    _render_html(
        st,
        render_section(
            index=4,
            title="PM Delivery View",
            eyebrow=f"{lookback_days} days",
            body_html=(
                render_metric_grid(
                    [
                        MetricCard("Tickets", summary.total_ticket_count, "accent"),
                        MetricCard("Pass", summary.pass_count, "pass"),
                        MetricCard(
                            "Warnings",
                            summary.pass_with_warnings_count,
                            "warning",
                        ),
                        MetricCard("Fail", summary.fail_count, "blocking"),
                        MetricCard("Pass Rate", f"{summary.pass_rate:.1f}%", "pass"),
                        MetricCard(
                            "Unlinked Reviews",
                            summary.unlinked_review_count,
                            "neutral",
                        ),
                    ]
                )
                + _pm_tickets_table(summary.tickets)
            ),
        ),
    )

    _render_html(
        st,
        render_section(
            index=5,
            title="Recurring Blockers",
            body_html=_pm_blockers_table(summary.recurring_blockers),
        ),
    )


def _render_lead_dashboard(st, database_path: Path) -> None:
    lookback_days = st.number_input(
        "Lead lookback days",
        min_value=1,
        max_value=365,
        value=30,
        step=1,
    )
    summary = load_lead_dashboard_summary(
        database_path,
        days=int(lookback_days),
    )
    if not summary.developers:
        _render_html(
            st,
            render_section(
                index=6,
                title="Lead Review View",
                eyebrow=f"{lookback_days} days",
                body_html=render_table(
                    ["Developer"],
                    [],
                    empty_message="No developer review history has been stored yet.",
                ),
            ),
        )
        return

    show_all_developers = False
    if len(summary.developers) > 5:
        show_all_developers = st.checkbox("Show all lead developers", value=False)

    visible_developers = (
        summary.developers
        if show_all_developers
        else summary.developers[:5]
    )
    _render_html(
        st,
        render_section(
            index=6,
            title="Lead Review View",
            eyebrow=f"{lookback_days} days",
            body_html=_lead_developers_table(visible_developers),
        ),
    )

    selected_developer = st.selectbox(
        "Lead developer",
        [developer.developer_id for developer in visible_developers],
    )
    developer_summary = next(
        developer
        for developer in summary.developers
        if developer.developer_id == selected_developer
    )

    coding_score = _evaluation_average_score(developer_summary, "coding")
    mr_structure_score = _evaluation_average_score(developer_summary, "mr_structure")
    _render_html(
        st,
        render_section(
            index=7,
            title=f"Selected Developer: {selected_developer}",
            body_html=(
                render_metric_grid(
                    [
                        MetricCard(
                            "Review Requests",
                            developer_summary.review_request_count,
                            "accent",
                        ),
                        MetricCard(
                            "Average Score",
                            _score(developer_summary.average_score),
                            "pass",
                        ),
                        MetricCard(
                            "Avg Attempts",
                            developer_summary.average_attempts_per_ticket,
                        ),
                        MetricCard("Coding Score", _score(coding_score), "info"),
                        MetricCard(
                            "MR Structure Score",
                            _score(mr_structure_score),
                            "warning",
                        ),
                        MetricCard("Trend", developer_summary.trend_direction),
                    ]
                )
                + _lead_tickets_table(developer_summary)
                + _lead_repeated_rules_table(developer_summary)
                + _lead_evaluations_table(developer_summary)
            ),
        ),
    )


def _render_developer_detail_page(
    st,
    database_path: Path,
    theme: DashboardTheme,
) -> None:
    developer_id = _query_param(st, "developer")
    if not developer_id:
        st.warning("Developer detail page requires a developer query parameter.")
        st.markdown("[Back to dashboard](./)")
        return

    st.markdown(
        '<div class="mg-back-link"><a href="./">Back to dashboard</a></div>',
        unsafe_allow_html=True,
    )
    _render_page_heading(
        st,
        title=f"Developer: {developer_id}",
        kicker="Developer Detail",
        body=(
            "Focused review history, score trend, ticket attempts, repeated rules, "
            "and review reports for this developer."
        ),
        meta_items=(("Developer", developer_id), ("Database", database_path.name)),
    )
    lookback_days = st.sidebar.number_input(
        "Developer detail lookback days",
        min_value=1,
        max_value=365,
        value=30,
        step=1,
    )
    detail = load_lead_developer_detail(
        database_path,
        developer_id=developer_id,
        days=int(lookback_days),
    )
    if detail is None:
        _render_html(
            st,
            render_section(
                index=1,
                title="Developer Reviews",
                body_html=render_table(
                    ["Review"],
                    [],
                    empty_message=(
                        "No review history is available for this developer and window."
                    ),
                ),
            ),
        )
        return

    developer = detail.developer
    coding_score = _evaluation_average_score(developer, "coding")
    mr_structure_score = _evaluation_average_score(developer, "mr_structure")
    _render_html(
        st,
        render_section(
            index=1,
            title="Developer Metrics",
            eyebrow=f"{lookback_days} days",
            body_html=render_metric_grid(
                [
                    MetricCard("Review Requests", developer.review_request_count, "accent"),
                    MetricCard("Tickets", developer.ticket_count, "accent"),
                    MetricCard("Avg Attempts", developer.average_attempts_per_ticket),
                    MetricCard("Average Score", _score(developer.average_score), "pass"),
                    MetricCard("Trend", developer.trend_direction),
                    MetricCard("Coding Score", _score(coding_score), "info"),
                    MetricCard(
                        "MR Structure Score",
                        _score(mr_structure_score),
                        "warning",
                    ),
                    MetricCard(
                        "Latest Review",
                        _format_datetime(developer.latest_review_at),
                    ),
                    MetricCard("Repeated Rules", developer.repeated_rule_count),
                    MetricCard("Unlinked Reviews", developer.unlinked_review_count),
                ]
            ),
        ),
    )

    _render_html(
        st,
        render_section(
            index=2,
            title="Tickets",
            body_html=_lead_tickets_table(developer),
        ),
    )

    _render_html(
        st,
        render_section(
            index=3,
            title="Repeated Rules",
            body_html=_lead_repeated_rules_table(developer),
        ),
    )

    _render_html(
        st,
        render_section(
            index=4,
            title="Coding vs MR Structure",
            body_html=_lead_evaluations_table(developer),
        ),
    )

    _render_html(
        st,
        render_section(
            index=5,
            title="Developer Reviews",
            body_html=_developer_reviews_table(detail.review_runs),
        ),
    )

    selected_review_id = st.selectbox(
        "Developer review report",
        [run.review_id for run in detail.review_runs],
    )
    selected_run = next(
        run for run in detail.review_runs if run.review_id == selected_review_id
    )
    _render_review_report_tabs(st, selected_run, theme)


def _evaluation_average_score(
    developer_summary: LeadDeveloperSummary,
    evaluation: str,
) -> float | None:
    for evaluation_summary in developer_summary.evaluation_summaries:
        if evaluation_summary.evaluation == evaluation:
            return evaluation_summary.average_score
    return None


def _render_selected_report(
    st,
    database_path: Path,
    data: DashboardData,
    theme: DashboardTheme,
) -> None:
    if not data.recent_reviews:
        _render_html(
            st,
            render_section(
                index=9,
                title="Stored Report",
                body_html=render_empty_state("Run a review first, then select it here."),
            ),
        )
        return

    _render_html(
        st,
        render_section(
            index=9,
            title="Stored Report",
            body_html=render_empty_state("Choose a stored review to inspect."),
        ),
    )
    review_ids = [run.review_id for run in data.recent_reviews]
    selected_review_id = st.selectbox("Review ID", review_ids)
    store = ReviewHistoryStore(database_path)
    try:
        selected_run = store.review_run(int(selected_review_id))
    finally:
        store.close()

    if selected_run is None:
        _render_html(
            st,
            render_section(
                index=10,
                title="Selected Review",
                body_html=render_empty_state("Selected review could not be loaded."),
            ),
        )
        return

    _render_review_report_tabs(st, selected_run, theme)


def _render_review_report_tabs(st, selected_run, theme: DashboardTheme) -> None:
    visual_tab, raw_tab = st.tabs(["Visual Report", "Raw Markdown"])
    with visual_tab:
        st.components.v1.html(
            render_visual_review_report(selected_run, theme=theme),
            height=1100,
            scrolling=True,
        )
    with raw_tab:
        _render_html(st, render_raw_markdown_block(selected_run.generated_review_report))


def _triggered_rules_table(stats: list[TriggeredRuleStat]) -> str:
    return render_table(
        ["Rule", "Triggers"],
        [
            [
                cell_text(stat.rule_id, mono=True),
                cell_text(stat.trigger_count, align="right"),
            ]
            for stat in stats
        ],
        empty_message="No triggered rules have been stored yet.",
    )


def _trend_table(data: DashboardData) -> str:
    return render_table(
        ["Date", "Blocking Findings", "Warning Findings"],
        [
            [
                cell_text(point.date, mono=True),
                cell_text(point.blocking_count, align="right"),
                cell_text(point.warning_count, align="right"),
            ]
            for point in data.trend_points
        ],
        empty_message="No trend data is available yet.",
    )


def _recent_reviews_table(runs: list[ReviewRunRecord]) -> str:
    return render_table(
        [
            "ID",
            "Timestamp",
            "Developer",
            "Ticket",
            "Score",
            "Risk",
            "Findings",
            "Scope",
        ],
        [
            [
                cell_text(run.review_id, align="right"),
                cell_text(_format_datetime(run.timestamp), mono=True),
                cell_link(run.developer_id, _developer_link(run.developer_id)),
                cell_text(run.ticket_key or "-", mono=True),
                cell_text(run.review_score, align="right"),
                _risk_pill(run.risk),
                cell_text(
                    run.blocking_count
                    + run.high_count
                    + run.warning_count
                    + run.info_count,
                    align="right",
                ),
                cell_text(run.review_scope),
            ]
            for run in runs
        ],
        empty_message="No review history has been stored yet.",
    )


def _pm_tickets_table(tickets: list[PmTicketStatus]) -> str:
    return render_table(
        [
            "Ticket",
            "Status",
            "Risk",
            "Reviews",
            "Avg Score",
            "Latest Review",
            "Assumed Deployed",
            "Blocker",
        ],
        [
            [
                cell_text(ticket.ticket_key, mono=True),
                _status_pill(ticket.status),
                _risk_pill(ticket.latest_risk),
                cell_text(ticket.review_request_count, align="right"),
                cell_text(_score(ticket.average_score), align="right"),
                cell_text(_format_datetime(ticket.latest_review_at), mono=True),
                cell_text(_format_datetime(ticket.assumed_deployed_at), mono=True),
                cell_text(ticket.blocker_reason or "-"),
            ]
            for ticket in tickets
        ],
        empty_message="No ticket-linked reviews are available for this window.",
    )


def _pm_blockers_table(blockers: list[PmRecurringBlocker]) -> str:
    return render_table(
        ["Rule", "Tickets", "Review Runs", "Highest Severity"],
        [
            [
                cell_text(blocker.rule_id, mono=True),
                cell_text(blocker.affected_ticket_count, align="right"),
                cell_text(blocker.review_run_count, align="right"),
                _risk_pill(blocker.highest_severity_seen),
            ]
            for blocker in blockers
        ],
        empty_message="No recurring blockers are visible in this window.",
    )


def _lead_developers_table(developers: list[LeadDeveloperSummary]) -> str:
    return render_table(
        [
            "Developer",
            "Review Requests",
            "Tickets",
            "Avg Attempts",
            "Avg Score",
            "Latest Review",
            "Trend",
            "Repeated Rules",
            "Unlinked Reviews",
        ],
        [
            [
                cell_link(developer.developer_id, _developer_link(developer.developer_id)),
                cell_text(developer.review_request_count, align="right"),
                cell_text(developer.ticket_count, align="right"),
                cell_text(developer.average_attempts_per_ticket, align="right"),
                cell_text(_score(developer.average_score), align="right"),
                cell_text(_format_datetime(developer.latest_review_at), mono=True),
                _trend_pill(developer.trend_direction),
                cell_text(developer.repeated_rule_count, align="right"),
                cell_text(developer.unlinked_review_count, align="right"),
            ]
            for developer in developers
        ],
        empty_message="No developer review history has been stored yet.",
    )


def _lead_tickets_table(developer: LeadDeveloperSummary) -> str:
    return render_table(
        [
            "Ticket",
            "Attempts",
            "First Review",
            "Latest Review",
            "Assumed Deployed",
            "Avg Score",
            "Latest Risk",
        ],
        [
            [
                cell_text(ticket.ticket_key, mono=True),
                cell_text(ticket.review_attempt_count, align="right"),
                cell_text(_format_datetime(ticket.first_review_at), mono=True),
                cell_text(_format_datetime(ticket.latest_review_at), mono=True),
                cell_text(_format_datetime(ticket.assumed_deployed_at), mono=True),
                cell_text(_score(ticket.average_score), align="right"),
                _risk_pill(ticket.latest_risk),
            ]
            for ticket in developer.tickets
        ],
        empty_message="No ticket-linked reviews are available for this developer.",
    )


def _lead_repeated_rules_table(developer: LeadDeveloperSummary) -> str:
    return render_table(
        ["Rule", "Review Runs", "Latest Review"],
        [
            [
                cell_text(rule.rule_id, mono=True),
                cell_text(rule.review_run_count, align="right"),
                cell_text(_format_datetime(rule.latest_review_at), mono=True),
            ]
            for rule in developer.repeated_rules
        ],
        empty_message="No repeated rules are visible for this developer.",
    )


def _lead_evaluations_table(developer: LeadDeveloperSummary) -> str:
    return render_table(
        [
            "Evaluation",
            "Reviews",
            "Avg Score",
            "Blocking",
            "High",
            "Warning",
            "Info",
        ],
        [
            [
                cell_text(_evaluation_label(summary.evaluation)),
                cell_text(summary.review_count, align="right"),
                cell_text(_score(summary.average_score), align="right"),
                cell_text(summary.counts.blocking, align="right"),
                cell_text(summary.counts.high, align="right"),
                cell_text(summary.counts.warning, align="right"),
                cell_text(summary.counts.info, align="right"),
            ]
            for summary in developer.evaluation_summaries
        ],
        empty_message="No coding or MR-structure evaluation data is available yet.",
    )


def _developer_reviews_table(runs: list[ReviewRunRecord]) -> str:
    return render_table(
        [
            "ID",
            "Timestamp",
            "Ticket",
            "Score",
            "Risk",
            "Blocking",
            "High",
            "Warnings",
            "Info",
            "Changed Files",
            "Changed Lines",
            "Rules",
        ],
        [
            [
                cell_text(run.review_id, align="right"),
                cell_text(_format_datetime(run.timestamp), mono=True),
                cell_text(run.ticket_key or "-", mono=True),
                cell_text(run.review_score, align="right"),
                _risk_pill(run.risk),
                cell_text(run.blocking_count, align="right"),
                cell_text(run.high_count, align="right"),
                cell_text(run.warning_count, align="right"),
                cell_text(run.info_count, align="right"),
                cell_text(run.changed_file_count, align="right"),
                cell_text(run.changed_line_count, align="right"),
                _rule_chips(run.triggered_rule_ids),
            ]
            for run in runs
        ],
        empty_message="No review runs are available for this developer.",
    )


def _rule_chips(rule_ids: list[str], *, limit: int = 4) -> TableCell:
    visible_rules = rule_ids[:limit]
    if len(rule_ids) > limit:
        visible_rules = [*visible_rules, f"+{len(rule_ids) - limit} more"]
    return cell_chips(visible_rules)


def _risk_pill(risk: RiskLevel) -> TableCell:
    return cell_pill(_risk_label(risk), _risk_tone(risk))


def _status_pill(status: str) -> TableCell:
    if status == "fail":
        return cell_pill("Fail", "blocking")
    if status == "pass_with_warnings":
        return cell_pill("Warnings", "warning")
    return cell_pill("Pass", "pass")


def _trend_pill(trend: str) -> TableCell:
    if trend == "improving":
        return cell_pill("Improving", "pass")
    if trend == "declining":
        return cell_pill("Declining", "blocking")
    if trend == "stable":
        return cell_pill("Stable", "info")
    return cell_pill("Insufficient Data", "neutral")


def _risk_tone(risk: RiskLevel) -> Tone:
    if risk == "blocking":
        return "blocking"
    if risk == "high":
        return "high"
    if risk == "warning":
        return "warning"
    if risk == "info":
        return "info"
    return "pass"


def _risk_label(risk: RiskLevel) -> str:
    if risk == "none":
        return "None"
    return risk.replace("_", " ").title()


def _evaluation_label(evaluation: str) -> str:
    if evaluation == "mr_structure":
        return "MR Structure"
    return evaluation.replace("_", " ").title()


def _score(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.isoformat(timespec="seconds")


def _is_developer_view(st) -> bool:
    return _query_param(st, "view") == "developer"


def _query_param(st, key: str) -> str | None:
    value = st.query_params.get(key)
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value)


def _developer_link(developer_id: str) -> str:
    return (
        f"?view=developer&developer={quote(developer_id, safe='')}"
        f"#{developer_id}"
    )


_DEVELOPER_LINK_DISPLAY_TEXT = r"#(.+)$"


def _html(value: str) -> str:
    return escape(value, quote=True)


if __name__ == "__main__":
    main()
