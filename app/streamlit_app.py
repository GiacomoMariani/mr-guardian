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
                "Project": run.project_name,
                "Branch": run.branch_name,
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
