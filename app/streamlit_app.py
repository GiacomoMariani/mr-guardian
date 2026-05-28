"""Streamlit dashboard for MR Guardian review history."""

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

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

from mr_guardian.config import get_settings  # noqa: E402
from mr_guardian.core.dashboard import DashboardData, load_dashboard_data  # noqa: E402
from mr_guardian.core.lead_dashboard import load_lead_dashboard_summary  # noqa: E402
from mr_guardian.core.pm_dashboard import load_pm_dashboard_summary  # noqa: E402
from mr_guardian.models.lead_dashboard import LeadDeveloperSummary  # noqa: E402
from mr_guardian.storage import ReviewHistoryStore  # noqa: E402


def main() -> None:
    """Render the Streamlit dashboard."""
    import streamlit as st

    settings = get_settings()
    st.set_page_config(page_title="MR Guardian", layout="wide")
    st.title("MR Guardian")

    database_path = Path(
        st.sidebar.text_input("History database", str(settings.history_db_path))
    )
    recent_limit = st.sidebar.number_input(
        "Recent review limit",
        min_value=1,
        max_value=500,
        value=50,
        step=10,
    )

    data = load_dashboard_data(database_path, recent_limit=int(recent_limit))
    _render_metrics(st, data)
    _render_pm_dashboard(st, database_path)
    _render_lead_dashboard(st, database_path)
    _render_recent_reviews(st, data)
    _render_selected_report(st, database_path, data)


def _render_metrics(st, data: DashboardData) -> None:
    metric_columns = st.columns(5)
    risk_counts = {risk_count.risk: risk_count.count for risk_count in data.risk_counts}
    metric_columns[0].metric("Blocking Reviews", risk_counts.get("blocking", 0))
    metric_columns[1].metric("High Risk Reviews", risk_counts.get("high", 0))
    metric_columns[2].metric("Warning Reviews", risk_counts.get("warning", 0))
    metric_columns[3].metric("Info Reviews", risk_counts.get("info", 0))
    metric_columns[4].metric("AI-Code Risk Runs", data.ai_code_risk_frequency)

    st.subheader("Most Triggered Rules")
    if data.most_triggered_rules:
        st.dataframe(
            [
                {"Rule ID": stat.rule_id, "Count": stat.trigger_count}
                for stat in data.most_triggered_rules
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No triggered rules have been stored yet.")

    st.subheader("Trends")
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
    else:
        st.info("No trend data is available yet.")


def _render_recent_reviews(st, data: DashboardData) -> None:
    st.subheader("Recent Reviews")
    if not data.recent_reviews:
        st.info("No review runs have been stored yet.")
        return

    st.dataframe(
        [
            {
                "ID": run.review_id,
                "Timestamp": run.timestamp.isoformat(timespec="seconds"),
                "Scope": run.review_scope,
                "Branch": run.branch_name,
                "Developer": run.developer_id,
                "Ticket": run.ticket_key or "-",
                "Score": run.review_score,
                "Risk": run.risk,
                "Blocking": run.blocking_count,
                "High": run.high_count,
                "Warnings": run.warning_count,
                "Info": run.info_count,
                "Changed Files": run.changed_file_count,
                "Changed Lines": run.changed_line_count,
                "Rules": ", ".join(run.triggered_rule_ids),
            }
            for run in data.recent_reviews
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_pm_dashboard(st, database_path: Path) -> None:
    st.subheader("PM Delivery View")
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

    metric_columns = st.columns(6)
    metric_columns[0].metric("Tickets", summary.total_ticket_count)
    metric_columns[1].metric("Pass", summary.pass_count)
    metric_columns[2].metric("Warnings", summary.pass_with_warnings_count)
    metric_columns[3].metric("Fail", summary.fail_count)
    metric_columns[4].metric("Pass Rate", f"{summary.pass_rate:.1f}%")
    metric_columns[5].metric("Unlinked Reviews", summary.unlinked_review_count)

    if summary.tickets:
        st.dataframe(
            [
                {
                    "Ticket": ticket.ticket_key,
                    "Status": ticket.status,
                    "Latest Review": ticket.latest_review_at.isoformat(
                        timespec="seconds"
                    ),
                    "Assumed Deployed": ticket.assumed_deployed_at.isoformat(
                        timespec="seconds"
                    ),
                    "Risk": ticket.latest_risk,
                    "MR Requests": ticket.review_request_count,
                    "Average Score": ticket.average_score,
                    "Blocker": ticket.blocker_reason or "-",
                }
                for ticket in summary.tickets
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No ticket-linked reviews are available for this window.")

    st.subheader("Recurring Blockers")
    if summary.recurring_blockers:
        st.dataframe(
            [
                {
                    "Rule ID": blocker.rule_id,
                    "Affected Tickets": blocker.affected_ticket_count,
                    "Review Runs": blocker.review_run_count,
                    "Highest Severity": blocker.highest_severity_seen,
                }
                for blocker in summary.recurring_blockers
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No recurring blockers are visible in this window.")


def _render_lead_dashboard(st, database_path: Path) -> None:
    st.subheader("Lead Review View")
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
        st.info("No developer review history has been stored yet.")
        return

    show_all_developers = False
    if len(summary.developers) > 5:
        show_all_developers = st.checkbox("Show all lead developers", value=False)

    visible_developers = (
        summary.developers
        if show_all_developers
        else summary.developers[:5]
    )
    st.dataframe(
        [
            {
                "Developer": developer.developer_id,
                "Review Requests": developer.review_request_count,
                "Tickets": developer.ticket_count,
                "Avg Attempts": developer.average_attempts_per_ticket,
                "Avg Score": developer.average_score,
                "Latest Review": developer.latest_review_at.isoformat(timespec="seconds"),
                "Trend": developer.trend_direction,
                "Repeated Rules": developer.repeated_rule_count,
                "Unlinked Reviews": developer.unlinked_review_count,
            }
            for developer in visible_developers
        ],
        use_container_width=True,
        hide_index=True,
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
    metric_columns = st.columns(6)
    metric_columns[0].metric("Review Requests", developer_summary.review_request_count)
    metric_columns[1].metric(
        "Average Score",
        "-"
        if developer_summary.average_score is None
        else f"{developer_summary.average_score:.2f}",
    )
    metric_columns[2].metric("Avg Attempts", developer_summary.average_attempts_per_ticket)
    metric_columns[3].metric(
        "Coding Score",
        "-" if coding_score is None else f"{coding_score:.2f}",
    )
    metric_columns[4].metric(
        "MR Structure Score",
        "-" if mr_structure_score is None else f"{mr_structure_score:.2f}",
    )
    metric_columns[5].metric("Trend", developer_summary.trend_direction)

    if not developer_summary.tickets:
        st.info("No ticket-linked reviews are available for this developer and window.")
    else:
        st.dataframe(
            [
                {
                    "Ticket": ticket.ticket_key,
                    "Attempts": ticket.review_attempt_count,
                    "First Review": ticket.first_review_at.isoformat(timespec="seconds"),
                    "Latest Review": ticket.latest_review_at.isoformat(timespec="seconds"),
                    "Assumed Deployed": ticket.assumed_deployed_at.isoformat(
                        timespec="seconds"
                    ),
                    "Average Score": ticket.average_score,
                    "Latest Risk": ticket.latest_risk,
                }
                for ticket in developer_summary.tickets
            ],
            use_container_width=True,
            hide_index=True,
        )

    if developer_summary.repeated_rules:
        st.subheader("Developer Repeated Rules")
        st.dataframe(
            [
                {
                    "Rule ID": rule.rule_id,
                    "Review Runs": rule.review_run_count,
                    "Latest Review": rule.latest_review_at.isoformat(timespec="seconds"),
                }
                for rule in developer_summary.repeated_rules
            ],
            use_container_width=True,
            hide_index=True,
        )

    if developer_summary.evaluation_summaries:
        st.subheader("Coding vs MR Structure")
        st.dataframe(
            [
                {
                    "Evaluation": evaluation.evaluation,
                    "Review Count": evaluation.review_count,
                    "Average Score": evaluation.average_score,
                    "Blocking": evaluation.counts.blocking,
                    "High": evaluation.counts.high,
                    "Warning": evaluation.counts.warning,
                    "Info": evaluation.counts.info,
                }
                for evaluation in developer_summary.evaluation_summaries
            ],
            use_container_width=True,
            hide_index=True,
        )


def _evaluation_average_score(
    developer_summary: LeadDeveloperSummary,
    evaluation: str,
) -> float | None:
    for evaluation_summary in developer_summary.evaluation_summaries:
        if evaluation_summary.evaluation == evaluation:
            return evaluation_summary.average_score
    return None


def _render_selected_report(st, database_path: Path, data: DashboardData) -> None:
    st.subheader("Stored Report")
    if not data.recent_reviews:
        st.info("Run a review first, then select it here.")
        return

    review_ids = [run.review_id for run in data.recent_reviews]
    selected_review_id = st.selectbox("Review ID", review_ids)
    store = ReviewHistoryStore(database_path)
    try:
        selected_run = store.review_run(int(selected_review_id))
    finally:
        store.close()

    if selected_run is None:
        st.warning("Selected review could not be loaded.")
        return

    st.markdown(selected_run.generated_review_report)


if __name__ == "__main__":
    main()
