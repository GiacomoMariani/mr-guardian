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

import streamlit as st  # noqa: E402  (safe here: the Pydantic check above has passed)

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
    render_trend_chart,
)
from app.streamlit_style import (  # noqa: E402
    THEME_LABELS,
    DashboardTheme,
    dashboard_css,
    theme_from_label,
)
from mr_guardian.config import get_settings  # noqa: E402
from mr_guardian.core.dashboard import DashboardData, load_dashboard_data  # noqa: E402
from mr_guardian.core.dashboard_eta import (  # noqa: E402
    load_dashboard_eta_note,
    recent_dashboard_eta_notes,
)
from mr_guardian.core.lead_dashboard import (  # noqa: E402
    load_lead_dashboard_summary,
    load_lead_developer_detail,
)
from mr_guardian.core.pm_dashboard import load_pm_dashboard_summary  # noqa: E402
from mr_guardian.core.weekly_llm_review import (  # noqa: E402
    load_latest_weekly_llm_review,
    load_recent_weekly_llm_reviews,
)
from mr_guardian.models.dashboard import DashboardEtaNote  # noqa: E402
from mr_guardian.models.history import (  # noqa: E402
    ReviewRunRecord,
    TriggeredRuleStat,
)
from mr_guardian.models.lead_dashboard import (  # noqa: E402
    LeadDeveloperSummary,
    LeadTicketAttemptSummary,
)
from mr_guardian.models.pm_dashboard import (  # noqa: E402
    PmRecurringBlocker,
    PmTicketStatus,
)
from mr_guardian.models.policy import PolicyRule  # noqa: E402
from mr_guardian.models.review import RiskLevel  # noqa: E402
from mr_guardian.models.weekly_review import WeeklyLlmReviewRecord  # noqa: E402
from mr_guardian.policies.catalog import load_rule_catalog, summarize_catalog  # noqa: E402
from mr_guardian.reporting.visual_report import render_visual_review_report  # noqa: E402
from mr_guardian.storage import ReviewHistoryStore  # noqa: E402

DASHBOARD_TAB_LABELS = (
    "Delivery Health",
    "Agent Review",
    "Recent Reviews",
    "Lead Review",
    "Trends",
    "Triggered Rules",
)
BEST_PRACTICES_URL = "https://github.com/GiacomoMariani/UnityBestPractices"
SOURCE_URL = "https://github.com/GiacomoMariani/mr-guardian"
DEFAULT_PHASE_LABEL = "Beta Phase"
DEFAULT_THEME_LABEL = "Dark"
THEME_STATE_KEY = "dashboard_theme"
DEFAULT_RECENT_REVIEW_LIMIT = 50
DEFAULT_PM_LOOKBACK_DAYS = 30
DEFAULT_LEAD_LOOKBACK_DAYS = 30
DEFAULT_DEVELOPER_LOOKBACK_DAYS = 30
DEFAULT_DASHBOARD_TAB_INDEX = 1
# The pager shows up to AGENT_REVIEW_PAGER_PAGE_SIZE reviews at a time and slides
# by AGENT_REVIEW_PAGER_STEP per «/» click. The «/» arrows are always rendered (at
# AGENT_REVIEW_PAGER_ARROW_WIDTH the relative width of a number button) and are
# disabled when there is nothing to page in that direction.
AGENT_REVIEW_PAGER_PAGE_SIZE = 10
AGENT_REVIEW_PAGER_STEP = 1
AGENT_REVIEW_PAGER_ARROW_WIDTH = 0.5
AGENT_REVIEW_SELECTED_KEY = "agent_review_selected_id"
AGENT_REVIEW_WINDOW_KEY = "agent_review_window_start"
AGENT_REVIEW_CAPTION = (
    "A complete review the agent produced — deterministic policy checks fused "
    "with bounded LLM reasoning into a single merge verdict."
)


def _db_mtime(database_path: Path) -> float:
    """Modification time of the history DB; bumps the loader caches when it changes."""
    try:
        return database_path.stat().st_mtime
    except OSError:
        return 0.0


_POLICY_DIR = "sources/yaml"


def _policy_dir_mtime(policy_dir: str) -> float:
    """Newest mtime across the policy YAML files; refreshes the catalog cache."""
    directory = Path(policy_dir)
    mtimes = [
        path.stat().st_mtime
        for pattern in ("*.yml", "*.yaml")
        for path in directory.glob(pattern)
    ]
    return max(mtimes, default=0.0)


@st.cache_data(show_spinner=False)
def _cached_rule_catalog(policy_dir: str, policy_mtime: float):
    return load_rule_catalog(policy_dir)


# The dashboard re-runs on every interaction, so the section loaders are cached and
# keyed on the DB mtime: tab/section switches are instant, and the cache refreshes
# automatically when a new review is written.
@st.cache_data(show_spinner=False)
def _cached_dashboard_data(database_path: Path, recent_limit: int, db_mtime: float):
    return load_dashboard_data(database_path, recent_limit=recent_limit)


@st.cache_data(show_spinner=False)
def _cached_pm_summary(database_path: Path, days: int, db_mtime: float):
    return load_pm_dashboard_summary(database_path, days=days)


@st.cache_data(show_spinner=False)
def _cached_lead_summary(database_path: Path, days: int, db_mtime: float):
    return load_lead_dashboard_summary(database_path, days=days)


@st.cache_data(show_spinner=False)
def _cached_developer_detail(
    database_path: Path, developer_id: str, days: int, db_mtime: float
):
    return load_lead_developer_detail(
        database_path, developer_id=developer_id, days=days
    )


@st.cache_data(show_spinner=False)
def _cached_weekly_review(database_path: Path, db_mtime: float):
    return load_latest_weekly_llm_review(database_path)


@st.cache_data(show_spinner=False)
def _cached_recent_weekly_reviews(database_path: Path, db_mtime: float):
    return load_recent_weekly_llm_reviews(database_path)


@st.cache_data(show_spinner=False)
def _cached_eta_note(database_path: Path, db_mtime: float):
    return load_dashboard_eta_note(database_path)


@st.cache_data(show_spinner=False)
def _cached_recent_eta_notes(database_path: Path, db_mtime: float):
    return recent_dashboard_eta_notes(database_path)


@st.cache_data(show_spinner=False)
def _cached_review_run(database_path: Path, review_id: int, db_mtime: float):
    store = ReviewHistoryStore(database_path)
    try:
        return store.review_run(review_id)
    finally:
        store.close()


def main() -> None:
    """Render the Streamlit dashboard."""
    import streamlit as st

    settings = get_settings()
    st.set_page_config(page_title="MR Guardian", layout="wide")
    database_path = Path(settings.history_db_path)
    # The theme control lives at the foot of the page, so resolve the active theme
    # from session state to drive the CSS before any content is rendered.
    theme = _selected_theme(st)
    st.markdown(dashboard_css(theme), unsafe_allow_html=True)

    if _is_developer_view(st):
        _render_developer_detail_page(
            st,
            database_path,
            theme,
        )
        _render_pipeline_hook(st)
        _render_bottom_controls(st, database_path)
        return

    data = _cached_dashboard_data(
        database_path,
        DEFAULT_RECENT_REVIEW_LIMIT,
        _db_mtime(database_path),
    )
    _render_page_heading(
        st,
        title="MR Guardian",
        kicker="Review Intelligence",
        body=(
            "An agentic merge-request reviewer that pairs deterministic policy "
            "checks with bounded, advisory LLM reasoning."
        ),
        meta_items=(
            ("Database", database_path.name),
            ("Reviews", str(len(data.recent_reviews))),
            ("Mode", "Dashboard"),
        ),
        top_links=(
            ("View source ↗", SOURCE_URL),
            ("Best practices applied ↗", BEST_PRACTICES_URL),
        ),
    )
    _render_dashboard_tabs(
        st,
        data=data,
        database_path=database_path,
        theme=theme,
    )
    _render_pipeline_hook(st)
    _render_browse_all_checks(st)
    _render_bottom_controls(st, database_path)


def _selected_theme(st) -> DashboardTheme:
    """Resolve the active theme from session state.

    The theme selector is rendered at the foot of the page, but its CSS must be
    applied before content renders, so we read the stored selection here (falling
    back to the default on a fresh load) and let the widget update it next run.
    """
    label = st.session_state.get(THEME_STATE_KEY, DEFAULT_THEME_LABEL)
    return theme_from_label(str(label))


def _render_bottom_controls(st, database_path: Path) -> None:
    """Render the theme selector and read-only history-database path at the foot."""
    columns = st.columns([1, 2.5])
    with columns[0]:
        st.selectbox(
            "Theme",
            list(THEME_LABELS),
            index=_default_theme_index(),
            key=THEME_STATE_KEY,
        )
    with columns[1]:
        _render_readonly_database_path(st, database_path)


def _render_pipeline_hook(st) -> None:
    """One-line 'how it works' explainer of the agentic pipeline, for the page foot."""
    steps = [
        ("Merge-request diff", False),
        ("Deterministic policy checks + bounded LLM reasoning", False),
        ("Single merge verdict", True),
    ]
    parts: list[str] = []
    for position, (label, accent) in enumerate(steps):
        if position:
            parts.append('<span class="mg-howitworks-arrow">→</span>')
        css_class = "mg-howitworks-step accent" if accent else "mg-howitworks-step"
        parts.append(f'<span class="{css_class}">{_html(label)}</span>')
    _render_html(
        st,
        '<div class="mg-howitworks">'
        '<span class="mg-howitworks-label">How it works</span>'
        f'<div class="mg-howitworks-flow">{"".join(parts)}</div>'
        "</div>",
    )


def _default_theme_index() -> int:
    return list(THEME_LABELS).index(DEFAULT_THEME_LABEL)


def _render_readonly_database_path(st, database_path: Path) -> None:
    _render_html(
        st,
        (
            '<div class="mg-readonly-control">'
            '<div class="mg-readonly-label">History database</div>'
            f'<div class="mg-readonly-value">{_html(str(database_path))}</div>'
            "</div>"
        ),
    )


def _dashboard_tab_labels() -> tuple[str, ...]:
    return DASHBOARD_TAB_LABELS


def _render_dashboard_tabs(
    st,
    *,
    data: DashboardData,
    database_path: Path,
    theme: DashboardTheme,
) -> None:
    # A horizontal radio (styled as a tab strip) drives the active section instead
    # of st.tabs: it honours a default index server-side, so the page renders
    # straight to Agent Review on first paint - no first-tab flash - while that tab
    # still sits second in the bar. Only the selected section is rendered each run.
    selected_section = st.radio(
        "Dashboard section",
        list(_dashboard_tab_labels()),
        index=DEFAULT_DASHBOARD_TAB_INDEX,
        horizontal=True,
        key="dashboard_section",
        label_visibility="collapsed",
    )

    if selected_section == "Delivery Health":
        _render_pm_dashboard(st, database_path)
        _render_eta_note(st, database_path)
        _render_eta_note_history(st, database_path)
        _render_weekly_llm_review(st, database_path)
    elif selected_section == "Agent Review":
        _render_selected_report(st, database_path, data, theme)
    elif selected_section == "Recent Reviews":
        _render_recent_reviews(st, database_path)
    elif selected_section == "Lead Review":
        _render_lead_dashboard(st, database_path)
    elif selected_section == "Trends":
        _render_trends(st, data)
    elif selected_section == "Triggered Rules":
        _render_triggered_rules(st, data)


def _render_page_heading(
    st,
    *,
    title: str,
    kicker: str,
    body: str,
    meta_items: tuple[tuple[str, str], ...] = (),
    top_links: tuple[tuple[str, str], ...] = (),
) -> None:
    st.markdown(
        render_page_header(
            title=title,
            kicker=kicker,
            body=body,
            meta_items=meta_items,
            top_links=top_links,
        ),
        unsafe_allow_html=True,
    )


def _render_html(st, html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def _render_eta_note(st, database_path: Path) -> None:
    db_mtime = _db_mtime(database_path)
    note = _cached_eta_note(database_path, db_mtime)
    weekly_review = _cached_weekly_review(database_path, db_mtime)
    phase_label = (
        weekly_review.phase if weekly_review is not None else DEFAULT_PHASE_LABEL
    )
    _render_html(
        st,
        render_section(
            index=2,
            title=f"{phase_label} ETA",
            action_html=_readiness_badge(weekly_review),
            body_html=_eta_note_panel(note, phase_label),
        ),
    )


def _eta_note_panel(note: DashboardEtaNote | None, phase_label: str) -> str:
    phase_lower = phase_label.lower()
    disclaimer = (
        f"Based on AI evaluation. Confirm {phase_lower} dates and delivery risk "
        "with the team."
    )
    if note is None:
        return "\n".join(
            [
                '<div class="mg-eta-note empty">',
                (
                    '<div class="mg-eta-message">'
                    f"No {_html(phase_lower)} ETA note has been set yet."
                    "</div>"
                ),
                f'<div class="mg-eta-disclaimer">{_html(disclaimer)}</div>',
                "</div>",
            ]
        )

    target_date = note.target_date.isoformat() if note.target_date is not None else "-"
    return "\n".join(
        [
            '<div class="mg-eta-note">',
            f'<div class="mg-eta-message">{_html(note.message)}</div>',
            '<div class="mg-eta-meta">',
            f"<span>Target <b>{_html(target_date)}</b></span>",
            f"<span>Updated <b>{_html(_format_datetime(note.updated_at))}</b></span>",
            "</div>",
            f'<div class="mg-eta-disclaimer">{_html(disclaimer)}</div>',
            "</div>",
        ]
    )


def _readiness_badge(weekly_review: WeeklyLlmReviewRecord | None) -> str:
    value = f"{weekly_review.score}%" if weekly_review is not None else "—"
    return (
        '<div class="mg-readiness-badge">'
        '<span>Readiness</span>'
        f"<strong>{value}</strong>"
        "</div>"
    )


def _render_eta_note_history(st, database_path: Path) -> None:
    notes = _cached_recent_eta_notes(database_path, _db_mtime(database_path))
    # The newest note is already shown above as the current ETA note.
    previous = notes[1:]
    if not previous:
        return
    with st.expander(f"Previous notes ({len(previous)})", expanded=False):
        _render_html(st, _eta_note_history_panel(previous))


def _eta_note_history_panel(notes: list[DashboardEtaNote]) -> str:
    items: list[str] = []
    for note in notes:
        target = note.target_date.isoformat() if note.target_date is not None else "-"
        items.append(
            "\n".join(
                [
                    '<div class="mg-eta-note">',
                    f'<div class="mg-eta-message">{_html(note.message)}</div>',
                    '<div class="mg-eta-meta">',
                    f"<span>Target <b>{_html(target)}</b></span>",
                    f"<span>Updated <b>{_html(_format_datetime(note.updated_at))}</b></span>",
                    "</div>",
                    "</div>",
                ]
            )
        )
    return '<div class="mg-eta-history">' + "\n".join(items) + "</div>"


def _render_weekly_llm_review(st, database_path: Path) -> None:
    reviews = _cached_recent_weekly_reviews(database_path, _db_mtime(database_path))
    selected = reviews[0] if reviews else None
    # When more than one week is stored, let the user pick which to view (latest first).
    if len(reviews) > 1:
        selected_index = st.selectbox(
            "Week",
            list(range(len(reviews))),
            index=0,
            format_func=lambda i: (
                f"{reviews[i].week_start.isoformat()} → {reviews[i].week_end.isoformat()}"
            ),
            key="weekly_review_week",
        )
        selected = reviews[selected_index]
    _render_html(
        st,
        render_section(
            index=3,
            title="Weekly LLM Review",
            action_html=_weekly_llm_result_badge(selected),
            body_html=_weekly_llm_review_panel(selected),
        ),
    )


def _render_triggered_rules(st, data: DashboardData) -> None:
    _render_html(
        st,
        render_section(
            index=5,
            title="Most Triggered Rules",
            anchor_id="triggered-rules",
            body_html=_triggered_rules_table(data.most_triggered_rules),
        ),
    )


def _render_trends(st, data: DashboardData) -> None:
    _render_trend_chart(st, data.trend_points)
    _render_html(
        st,
        render_section(
            index=4,
            title="Risk Trends",
            anchor_id="trends",
            body_html=_trend_table(data),
        ),
    )


def _render_trend_chart(st, trend_points) -> None:
    """Render a dashboard-styled risk-trend chart."""
    _render_html(
        st,
        render_trend_chart(
            [
                (point.date, point.blocking_count, point.warning_count)
                for point in trend_points
            ]
        ),
    )


def _render_recent_reviews(st, database_path: Path) -> None:
    recent_limit = st.number_input(
        "Recent review limit",
        min_value=1,
        max_value=500,
        value=DEFAULT_RECENT_REVIEW_LIMIT,
        step=10,
        key="recent_reviews_limit",
    )
    data = _cached_dashboard_data(
        database_path, int(recent_limit), _db_mtime(database_path)
    )
    _render_html(
        st,
        render_section(
            index=6,
            title="Recent Reviews",
            anchor_id="recent-reviews",
            body_html=_recent_reviews_table(data.recent_reviews),
        ),
    )


def _render_pm_dashboard(st, database_path: Path) -> None:
    lookback_days = DEFAULT_PM_LOOKBACK_DAYS
    summary = _cached_pm_summary(
        database_path,
        lookback_days,
        _db_mtime(database_path),
    )

    _render_html(
        st,
        render_section(
            index=1,
            title="Delivery Health",
            eyebrow=f"{lookback_days} days",
            anchor_id="delivery-health",
            body_html=render_metric_grid(
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
            ),
        ),
    )


def _render_lead_dashboard(st, database_path: Path) -> None:
    lookback_days = st.number_input(
        "Lead lookback days",
        min_value=1,
        max_value=365,
        value=DEFAULT_LEAD_LOOKBACK_DAYS,
        step=1,
        key="lead_lookback_days",
    )
    summary = _cached_lead_summary(
        database_path,
        int(lookback_days),
        _db_mtime(database_path),
    )
    if not summary.developers:
        _render_html(
            st,
            render_section(
                index=3,
                title="Lead Review View",
                anchor_id="lead-review",
                eyebrow=f"{int(lookback_days)} days",
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
            index=3,
            title="Lead Review View",
            anchor_id="lead-review",
            eyebrow=f"{int(lookback_days)} days",
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
            index=3,
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
                            _score(developer_summary.average_attempts_per_ticket),
                        ),
                        MetricCard(
                            "Approved Tickets",
                            developer_summary.approved_ticket_count,
                            "pass",
                        ),
                        MetricCard(
                            "Avg Approval Attempts",
                            _score(developer_summary.average_attempts_to_approval),
                            "pass",
                        ),
                        MetricCard("Coding Score", _score(coding_score), "info"),
                        MetricCard(
                            "MR Structure Score",
                            _score(mr_structure_score),
                            "warning",
                        ),
                        MetricCard("Trend", *_trend_label_tone(developer_summary.trend_direction)),
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
    lookback_days = st.number_input(
        "Developer detail lookback days",
        min_value=1,
        max_value=365,
        value=DEFAULT_DEVELOPER_LOOKBACK_DAYS,
        step=1,
        key="developer_detail_lookback_days",
    )
    detail = _cached_developer_detail(
        database_path,
        developer_id,
        int(lookback_days),
        _db_mtime(database_path),
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
    # The "Average Score" card is a real average of the dimension scores it sits next to
    # (coding + MR structure) — not the overall review-score average, which deducts every
    # finding's penalty from 100 and so reads lower than the mean of the two.
    average_score = _mean_score(coding_score, mr_structure_score)
    settings = get_settings()
    # Lead with the LLM developer profile (the headline artifact) — its scores plus the
    # AI write-up — then the activity metrics below it.
    _render_html(
        st,
        render_section(
            title="Latest LLM Developer Profile",
            eyebrow="AI-generated",
            body_html=(
                render_metric_grid(
                    [
                        _score_card(
                            "Average Score",
                            average_score,
                            settings.score_target_average,
                        ),
                        _score_card(
                            "Coding Score", coding_score, settings.score_target_coding
                        ),
                        _score_card(
                            "MR Structure Score",
                            mr_structure_score,
                            settings.score_target_structure,
                        ),
                    ]
                )
                + _developer_profile_panel(
                    _latest_developer_profile_run(detail.review_runs),
                    show_title=False,
                )
            ),
        ),
    )

    _render_html(
        st,
        render_section(
            index=1,
            title="Developer Metrics",
            anchor_id="developer-metrics",
            body_html=render_metric_grid(
                [
                    MetricCard("Review Requests", developer.review_request_count, "accent"),
                    MetricCard("Tickets", developer.ticket_count, "accent"),
                    MetricCard("Avg Attempts", _score(developer.average_attempts_per_ticket)),
                    MetricCard("Approved Tickets", developer.approved_ticket_count, "pass"),
                    MetricCard("Trend", *_trend_label_tone(developer.trend_direction)),
                ]
            ),
        ),
    )

    _render_html(
        st,
        render_section(
            index=3,
            title="Tickets",
            body_html=_lead_tickets_table(developer),
        ),
    )

    _render_html(
        st,
        render_section(
            index=4,
            title="Repeated Rules",
            body_html=_lead_repeated_rules_table(developer),
        ),
    )

    _render_html(
        st,
        render_section(
            index=5,
            title="Coding vs MR Structure",
            body_html=_lead_evaluations_table(developer),
        ),
    )

    rule_catalog = _cached_rule_catalog(_POLICY_DIR, _policy_dir_mtime(_POLICY_DIR))
    _render_html(
        st,
        render_section(
            index=6,
            title="Developer Reviews",
            body_html=_developer_reviews_table(detail.review_runs, rule_catalog),
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


def _mean_score(*scores: float | int | None) -> float | None:
    """Arithmetic mean of the present (non-None) scores; None when none are present."""
    present = [score for score in scores if score is not None]
    return sum(present) / len(present) if present else None


def _review_pager_slots(
    ids: list[int],
    *,
    window_start: int,
    page_size: int,
) -> list[tuple[str, int | bool]]:
    """Describe the review pager controls for a sorted id list.

    Returns ordered ``(kind, value)`` slots: a leading ``("prev", disabled)`` arrow,
    one ``("id", review_id)`` per visible review, and a trailing ``("next", disabled)``
    arrow. Both arrows are always present; ``disabled`` is True when there is nothing
    to page in that direction (including when every id fits in one page).
    """
    count = len(ids)
    if count <= page_size:
        visible = list(ids)
        prev_disabled = True
        next_disabled = True
    else:
        max_start = count - page_size
        start = max(0, min(window_start, max_start))
        visible = ids[start : start + page_size]
        prev_disabled = start <= 0
        next_disabled = start >= max_start
    return [
        ("prev", prev_disabled),
        *(("id", review_id) for review_id in visible),
        ("next", next_disabled),
    ]


def _pager_select_review(review_id: int) -> None:
    import streamlit as st

    st.session_state[AGENT_REVIEW_SELECTED_KEY] = review_id


def _pager_shift_window(delta: int) -> None:
    import streamlit as st

    current = st.session_state.get(AGENT_REVIEW_WINDOW_KEY, 0)
    st.session_state[AGENT_REVIEW_WINDOW_KEY] = current + delta


def _render_review_pager(st, review_ids: list[int]) -> int:
    """Render the review-id button pager and return the selected review id.

    Buttons are labelled with each review's 1-based position (oldest = 1, newest
    = len) rather than its raw database id, so the row reads 1..N regardless of
    gaps in the ids; selection still tracks the real review id underneath.
    Defaults the selection to the latest review. When the ids overflow one page
    (``AGENT_REVIEW_PAGER_PAGE_SIZE``) a sliding window is shown; the «/» arrows are
    always rendered (smaller than the number buttons) and disabled when there is
    nothing to page in that direction.
    """
    ids = sorted(review_ids)
    count = len(ids)
    positions = {review_id: index + 1 for index, review_id in enumerate(ids)}
    if st.session_state.get(AGENT_REVIEW_SELECTED_KEY) not in ids:
        st.session_state[AGENT_REVIEW_SELECTED_KEY] = ids[-1]
    selected_id = st.session_state[AGENT_REVIEW_SELECTED_KEY]

    if count > AGENT_REVIEW_PAGER_PAGE_SIZE:
        max_start = count - AGENT_REVIEW_PAGER_PAGE_SIZE
        if AGENT_REVIEW_WINDOW_KEY not in st.session_state:
            st.session_state[AGENT_REVIEW_WINDOW_KEY] = max_start
        window_start = max(0, min(st.session_state[AGENT_REVIEW_WINDOW_KEY], max_start))
        st.session_state[AGENT_REVIEW_WINDOW_KEY] = window_start
    else:
        window_start = 0

    slots = _review_pager_slots(
        ids,
        window_start=window_start,
        page_size=AGENT_REVIEW_PAGER_PAGE_SIZE,
    )
    _render_html(st, '<div class="mg-pager-label">Review</div>')
    column_widths = [
        AGENT_REVIEW_PAGER_ARROW_WIDTH if kind in ("prev", "next") else 1.0
        for kind, _ in slots
    ]
    for column, (kind, value) in zip(st.columns(column_widths), slots, strict=False):
        with column:
            if kind == "id":
                st.button(
                    str(positions[value]),
                    key=f"agent-review-id-{value}",
                    type="primary" if value == selected_id else "secondary",
                    use_container_width=True,
                    on_click=_pager_select_review,
                    args=(value,),
                )
            elif kind == "prev":
                st.button(
                    "«",
                    key="agent-review-prev",
                    disabled=bool(value),
                    use_container_width=True,
                    on_click=_pager_shift_window,
                    args=(-AGENT_REVIEW_PAGER_STEP,),
                )
            else:
                st.button(
                    "»",
                    key="agent-review-next",
                    disabled=bool(value),
                    use_container_width=True,
                    on_click=_pager_shift_window,
                    args=(AGENT_REVIEW_PAGER_STEP,),
                )
    return st.session_state[AGENT_REVIEW_SELECTED_KEY]


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
                title="Agent Review",
                anchor_id="agent-review",
                body_html=render_empty_state("Run a review first, then select it here."),
            ),
        )
        return

    _render_html(
        st,
        render_section(
            title="Agent Review",
            subtitle=AGENT_REVIEW_CAPTION,
            anchor_id="agent-review",
            body_html="",
        ),
    )
    review_ids = [run.review_id for run in data.recent_reviews]
    selected_review_id = _render_review_pager(st, review_ids)
    selected_run = _cached_review_run(
        database_path, int(selected_review_id), _db_mtime(database_path)
    )

    if selected_run is None:
        _render_html(
            st,
            render_section(
                title="Agent Review",
                body_html=render_empty_state("Selected review could not be loaded."),
            ),
        )
        return

    _render_review_report_tabs(st, selected_run, theme)


_SKIPPED_LLM_STATUSES = {"skipped", "failed", "rate_limited"}


def _run_has_skipped_llm(run: ReviewRunRecord) -> bool:
    """True when the report will render the "Code analysis was not completed" callout —
    i.e. an LLM rule that did not complete (a skipped/failed/rate-limited metric, or a
    skipped-LLM info finding). The report draws that as an extra section, so the height
    estimate must reserve room for it. Uses ``getattr`` so it is safe on the lightweight
    test mocks (which omit ``llm_metrics`` and use placeholder findings)."""
    metrics = getattr(run, "llm_metrics", None) or []
    if any(getattr(m, "status", None) in _SKIPPED_LLM_STATUSES for m in metrics):
        return True
    findings = getattr(run, "findings", None) or []
    return any(
        getattr(f, "rule_type", None) == "llm"
        and getattr(f, "severity", None) == "info"
        and str(getattr(f, "message", "")).startswith("LLM rule skipped:")
        for f in findings
    )


def _review_report_height(run: ReviewRunRecord) -> int:
    """Estimate the embedded visual-report iframe height with only a small slack and
    no inner scrollbar. The dashboard block-container caps at 1280px, so the report's
    width — and therefore its content height — is stable on any desktop ≥1280px, which
    lets the estimate run tight (~30px slack). Calibrated against the rendered embedded
    reports: a passed report ≈650px, a 2-finding blocked one ≈950px; blocked reports
    add the "why this is blocked" section, and a skipped-LLM review adds the "Code
    analysis was not completed" callout. (Narrower/mobile viewports may scroll —
    tracked in the responsive backlog.)"""
    findings = (
        len(run.findings)
        if run.findings
        else run.blocking_count + run.high_count + run.warning_count + run.info_count
    )
    note = 80 if (run.llm_summary and run.llm_summary.text) else 0
    skipped = 170 if _run_has_skipped_llm(run) else 0
    height = 680 + 56 * findings + (210 if run.blocking_count else 0) + note + skipped
    return min(2800, height)


def _render_review_report_tabs(st, selected_run, theme: DashboardTheme) -> None:
    # The catalog makes each finding row in the report expandable (rule description +
    # prompt), so the report is self-contained — no separate "policies triggered" list.
    catalog = _cached_rule_catalog(_POLICY_DIR, _policy_dir_mtime(_POLICY_DIR))
    # Same relative ``?view=developer`` link the Lead view uses; the report opens it in a
    # new tab (its iframe sandbox blocks in-place nav). Relative, so it works on any host.
    developer_url = _developer_link(selected_run.developer_id)
    visual_tab, raw_tab = st.tabs(["Visual Report", "Raw Markdown"])
    with visual_tab:
        st.components.v1.html(
            render_visual_review_report(
                selected_run,
                theme=theme,
                embedded=True,
                rule_details=catalog,
                developer_url=developer_url,
            ),
            height=_review_report_height(selected_run),
            scrolling=True,
        )
    with raw_tab:
        _render_html(st, render_raw_markdown_block(selected_run.generated_review_report))


_RULE_SOURCE_BLOB = f"{SOURCE_URL}/blob/main/sources/yaml/"
_CHECKS_PER_ROW = 4


def _rule_source_url(source: str) -> str | None:
    """Map a rule ``source`` (``file.yml#ID``) to its file URL on the public repo."""
    filename = source.split("#", 1)[0].strip()
    if not filename.endswith((".yml", ".yaml")):
        return None
    return _RULE_SOURCE_BLOB + filename


def _render_rule_popover(st, rule_id: str, rule: PolicyRule | None) -> None:
    with st.popover(rule_id, use_container_width=True):
        if rule is None:
            st.markdown(f"**{rule_id}**")
            st.caption("Definition is not in the current policy.")
            return
        kind = "LLM" if rule.type == "llm" else "Deterministic"
        st.markdown(f"**{rule_id}**")
        st.caption(f"{kind} · {rule.severity} · {rule.evaluation}")
        st.write(rule.description)
        if rule.prompt:
            st.caption("LLM prompt")
            st.code(rule.prompt.strip(), language="markdown")
        source_url = _rule_source_url(rule.source)
        if source_url is not None:
            st.markdown(f"[View source ↗]({source_url})")


def _render_rule_chip_grid(st, rule_ids, catalog) -> None:
    for start in range(0, len(rule_ids), _CHECKS_PER_ROW):
        chunk = rule_ids[start : start + _CHECKS_PER_ROW]
        columns = st.columns(_CHECKS_PER_ROW)
        for column, rule_id in zip(columns, chunk, strict=False):
            with column:
                _render_rule_popover(st, rule_id, catalog.get(rule_id))


def _render_browse_all_checks(st) -> None:
    catalog = _cached_rule_catalog(_POLICY_DIR, _policy_dir_mtime(_POLICY_DIR))
    if not catalog:
        return
    summary = summarize_catalog(catalog)
    # Lazy reveal: st.expander renders its body even when collapsed, which would
    # build all ~56 rule popovers on every rerun. A toggled button renders the
    # chips only while open, so the collapsed default costs nothing.
    state_key = "browse_all_checks_open"
    if st.button(f"Browse all {summary.total} policies", key="browse_all_checks_btn"):
        st.session_state[state_key] = not st.session_state.get(state_key, False)
    if not st.session_state.get(state_key, False):
        return
    deterministic = sorted(
        rule_id for rule_id, rule in catalog.items() if rule.type == "deterministic"
    )
    llm = sorted(rule_id for rule_id, rule in catalog.items() if rule.type == "llm")
    st.caption(
        f"{summary.by_type.get('llm', 0)} LLM · "
        f"{summary.by_type.get('deterministic', 0)} deterministic · "
        f"{summary.blocking} blocking · {len(summary.by_dimension)} dimensions"
    )
    if deterministic:
        st.markdown(f"**Deterministic gates** ({len(deterministic)})")
        _render_rule_chip_grid(st, deterministic, catalog)
    if llm:
        st.markdown(f"**LLM judgment** ({len(llm)})")
        _render_rule_chip_grid(st, llm, catalog)


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
            "Final",
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
                _review_final_pill(run.is_final),
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
            "Delivery",
            "Risk",
            "Reviews",
            "Avg Score",
            "Latest Review",
            "Approved / Observed At",
            "Blocker",
        ],
        [
            [
                cell_text(ticket.ticket_key, mono=True),
                _status_pill(ticket.status),
                _delivery_state_pill(ticket.delivery_state),
                _risk_pill(ticket.latest_risk),
                cell_text(ticket.review_request_count, align="right"),
                cell_text(_score(ticket.average_score), align="right"),
                cell_text(_format_datetime(ticket.latest_review_at), mono=True),
                cell_text(_pm_delivery_date(ticket), mono=True),
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
            "Approved Tickets",
            "Avg Approval Attempts",
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
                cell_text(developer.approved_ticket_count, align="right"),
                cell_text(
                    _score(developer.average_attempts_to_approval),
                    align="right",
                ),
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
            "State",
            "Attempts",
            "Attempts To Approval",
            "First Review",
            "Latest Review",
            "Approved / Observed At",
            "Avg Score",
            "Latest Risk",
        ],
        [
            [
                cell_text(ticket.ticket_key, mono=True),
                _ticket_approval_pill(ticket.is_approved),
                cell_text(ticket.review_attempt_count, align="right"),
                cell_text(_approval_attempts(ticket.attempts_to_approval), align="right"),
                cell_text(_format_datetime(ticket.first_review_at), mono=True),
                cell_text(_format_datetime(ticket.latest_review_at), mono=True),
                cell_text(_lead_ticket_delivery_date(ticket), mono=True),
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


def _developer_reviews_table(
    runs: list[ReviewRunRecord], catalog: dict[str, PolicyRule] | None = None
) -> str:
    return render_table(
        [
            "ID",
            "Timestamp",
            "Ticket",
            "Final",
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
                _review_final_pill(run.is_final),
                cell_text(run.review_score, align="right"),
                _risk_pill(run.risk),
                cell_text(run.blocking_count, align="right"),
                cell_text(run.high_count, align="right"),
                cell_text(run.warning_count, align="right"),
                cell_text(run.info_count, align="right"),
                cell_text(run.changed_file_count, align="right"),
                cell_text(run.changed_line_count, align="right"),
                _rule_chips(run.triggered_rule_ids, catalog),
            ]
            for run in runs
        ],
        empty_message="No review runs are available for this developer.",
    )


def _weekly_llm_review_panel(review: WeeklyLlmReviewRecord | None) -> str:
    if review is None:
        return render_empty_state("No weekly LLM review has been stored yet.")

    tone = _weekly_llm_result_tone(review.result)
    summary = _html(review.summary).replace("\n", "<br>")
    return "\n".join(
        [
            '<div class="mg-profile-card mg-weekly-review-card">',
            '<div class="mg-profile-card-head">',
            "<div>",
            '<div class="mg-profile-card-title">Weekly assessment</div>',
            (
                '<div class="mg-profile-card-meta">'
                f"Week {_html(review.week_start.isoformat())} to "
                f"{_html(review.week_end.isoformat())} · "
                f"Stored {_html(_format_datetime(review.created_at))}"
                "</div>"
            ),
            "</div>",
            (
                '<div class="mg-weekly-score">'
                "<span>LLM-calculated score</span>"
                f"<strong>{review.score}/100</strong>"
                "</div>"
            ),
            "</div>",
            render_metric_grid(
                [
                    MetricCard(
                        label="LLM Score",
                        value=f"{review.score}/100",
                        tone=tone,
                        detail="Calculated by LLM",
                    ),
                    MetricCard(
                        label="MRs This Week",
                        value=review.mr_count,
                        tone="accent",
                    ),
                    MetricCard(
                        label="Developers",
                        value=review.developer_count,
                        tone="neutral",
                    ),
                    MetricCard(
                        label="Tickets",
                        value=review.ticket_count,
                        tone="neutral",
                    ),
                    MetricCard(
                        label="Approved / Observed",
                        value=f"{review.approved_ticket_count}/{review.observed_ticket_count}",
                        tone="pass",
                    ),
                    MetricCard(
                        label="Blocking / High / Warning",
                        value=(
                            f"{review.blocking_review_count}/"
                            f"{review.high_risk_review_count}/"
                            f"{review.warning_review_count}"
                        ),
                        tone=_weekly_risk_metric_tone(review),
                        detail=f"Info reviews {review.info_review_count}",
                    ),
                ]
            ),
            f'<div class="mg-profile-card-body">{summary}</div>',
            '<div class="mg-weekly-review-lists">',
            _weekly_review_list("Top risks", review.top_risks, "No top risks recorded."),
            _weekly_review_list(
                "Recommended actions",
                review.recommended_actions,
                "No recommended actions recorded.",
            ),
            "</div>",
            '<div class="mg-profile-card-foot">',
            "<span>LLM-generated weekly review</span>",
            f"<span>Provider <b>{_html(review.provider)}</b></span>",
            f"<span>Model <b>{_html(review.model)}</b></span>",
            f"<span>Week <b>{_html(review.week_start.isoformat())}</b> to "
            f"<b>{_html(review.week_end.isoformat())}</b></span>",
            f"<span>{_html(_weekly_token_usage(review))}</span>",
            f"<span>Estimated cost <b>{_html(_weekly_cost(review))}</b></span>",
            "</div>",
            "</div>",
        ]
    )


def _weekly_llm_result_badge(review: WeeklyLlmReviewRecord | None) -> str:
    if review is None:
        return ""
    return cell_pill(
        _weekly_llm_result_label(review.result),
        _weekly_llm_result_tone(review.result),
    ).html


def _weekly_llm_result_label(result: str) -> str:
    if result == "optimal":
        return "Optimal"
    if result == "on_track":
        return "On Track"
    if result == "needs_attention":
        return "Needs Attention"
    if result == "at_risk":
        return "At Risk"
    if result == "blocked":
        return "Blocked"
    return result.replace("_", " ").title()


def _weekly_llm_result_tone(result: str) -> Tone:
    if result in {"optimal", "on_track"}:
        return "pass"
    if result == "needs_attention":
        return "warning"
    if result == "at_risk":
        return "high"
    return "blocking"


def _weekly_risk_metric_tone(review: WeeklyLlmReviewRecord) -> Tone:
    if review.blocking_review_count > 0:
        return "blocking"
    if review.high_risk_review_count > 0:
        return "high"
    if review.warning_review_count > 0:
        return "warning"
    return "pass"


def _weekly_review_list(title: str, values: list[str], empty_message: str) -> str:
    if values:
        items = "".join(f"<li>{_html(value)}</li>" for value in values)
    else:
        items = f'<li class="empty">{_html(empty_message)}</li>'
    return "\n".join(
        [
            '<div class="mg-weekly-review-list">',
            f"<h3>{_html(title)}</h3>",
            f"<ul>{items}</ul>",
            "</div>",
        ]
    )


def _weekly_token_usage(review: WeeklyLlmReviewRecord) -> str:
    usage_parts = [
        _token_count("input", review.input_tokens),
        _token_count("output", review.output_tokens),
        _token_count("total", review.total_tokens),
    ]
    usage = " · ".join(part for part in usage_parts if part)
    return usage or "token usage unavailable"


def _weekly_cost(review: WeeklyLlmReviewRecord) -> str:
    if review.estimated_cost_usd is None:
        return "unavailable"
    return f"{review.estimated_cost_usd:.4f} {review.currency}"


def _latest_developer_profile_run(
    runs: list[ReviewRunRecord],
) -> ReviewRunRecord | None:
    for run in runs:
        if run.developer_profile is not None:
            return run
    return None


def _developer_profile_panel(run: ReviewRunRecord | None, *, show_title: bool = True) -> str:
    profile = run.developer_profile if run is not None else None
    if run is None or profile is None or not profile.text:
        # No usable LLM write-up (never generated, or a failed generation).
        return render_empty_state("No info found.")

    profile_text = profile.text
    usage_parts = [
        _token_count("input", profile.input_tokens),
        _token_count("output", profile.output_tokens),
        _token_count("total", profile.total_tokens),
    ]
    usage = " · ".join(part for part in usage_parts if part)
    if not usage:
        usage = "token usage unavailable"

    title_html = (
        '<div class="mg-profile-card-title">Latest LLM Developer Profile</div>'
        if show_title
        else ""
    )
    body = _html(profile_text).replace("\n", "<br>")
    return "\n".join(
        [
            '<div class="mg-profile-card">',
            '<div class="mg-profile-card-head">',
            "<div>",
            title_html,
            (
                '<div class="mg-profile-card-meta">'
                f"Review {_html(str(run.review_id))} · "
                f"{_html(_format_datetime(run.timestamp))} · "
                f"{_html(str(profile.lookback_days))} day window"
                "</div>"
            ),
            "</div>",
            _llm_status_pill(profile.status).html,
            "</div>",
            f'<div class="mg-profile-card-body">{body}</div>',
            '<div class="mg-profile-card-foot">',
            f"<span>Provider <b>{_html(profile.provider)}</b></span>",
            f"<span>Model <b>{_html(profile.model)}</b></span>",
            f"<span>Duration <b>{profile.duration_ms}ms</b></span>",
            f"<span>{_html(usage)}</span>",
            "</div>",
            "</div>",
        ]
    )


def _token_count(label: str, value: int | None) -> str:
    if value is None:
        return ""
    return f"{label} {value}"


def _rule_chips(
    rule_ids: list[str],
    catalog: dict[str, PolicyRule] | None = None,
    *,
    limit: int = 4,
) -> TableCell:
    # Each rule the catalog knows about becomes a link to its policy source (new tab)
    # with the rule description as a hover tooltip; unknown/stale ids stay plain.
    visible_rules = rule_ids[:limit]
    hrefs: list[str | None] = []
    titles: list[str | None] = []
    for rule_id in visible_rules:
        rule = catalog.get(rule_id) if catalog else None
        hrefs.append(_rule_source_url(rule.source) if rule else None)
        titles.append(rule.description if rule else None)
    if len(rule_ids) > limit:
        visible_rules = [*visible_rules, f"+{len(rule_ids) - limit} more"]
        hrefs.append(None)
        titles.append(None)
    return cell_chips(visible_rules, hrefs=hrefs, titles=titles)


def _risk_pill(risk: RiskLevel) -> TableCell:
    return cell_pill(_risk_label(risk), _risk_tone(risk))


def _status_pill(status: str) -> TableCell:
    if status == "fail":
        return cell_pill("Fail", "blocking")
    if status == "pass_with_warnings":
        return cell_pill("Warnings", "warning")
    return cell_pill("Pass", "pass")


def _delivery_state_pill(state: str) -> TableCell:
    if state == "approved":
        return cell_pill("Approved", "pass")
    return cell_pill("Observed", "neutral")


def _ticket_approval_pill(is_approved: bool) -> TableCell:
    if is_approved:
        return cell_pill("Approved", "pass")
    return cell_pill("Observed", "neutral")


def _review_final_pill(is_final: bool) -> TableCell:
    if is_final:
        return cell_pill("Approved", "pass")
    return cell_pill("Observed", "neutral")


def _pm_delivery_date(ticket: PmTicketStatus) -> str:
    if ticket.approved_at is not None:
        return _format_datetime(ticket.approved_at)
    return _format_datetime(ticket.assumed_deployed_at)


def _lead_ticket_delivery_date(ticket: LeadTicketAttemptSummary) -> str:
    if ticket.approved_at is not None:
        return _format_datetime(ticket.approved_at)
    return _format_datetime(ticket.assumed_deployed_at)


def _approval_attempts(value: int | None) -> str:
    if value is None:
        return "-"
    return str(value)


def _llm_status_pill(status: str) -> TableCell:
    if status == "succeeded":
        return cell_pill("Succeeded", "pass")
    if status == "rate_limited":
        return cell_pill("Rate Limited", "warning")
    return cell_pill(status.replace("_", " ").title(), "blocking")


def _trend_label_tone(trend: str) -> tuple[str, Tone]:
    """Map the raw ``TrendDirection`` enum to a human label + colour tone, shared by
    the table pills and the metric cards so the trend never shows as ``insufficient_data``."""
    if trend == "improving":
        return "Improving", "pass"
    if trend == "declining":
        return "Declining", "blocking"
    # "stable", "insufficient_data", and anything unknown all read as Stable — a
    # not-enough-data trend is treated as no concerning movement.
    return "Stable", "info"


def _trend_pill(trend: str) -> TableCell:
    return cell_pill(*_trend_label_tone(trend))


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
        # Whole numbers read cleaner without a trailing ".0" (75.0 -> 75); keep one
        # decimal for genuine fractions (1.33 -> 1.3).
        return str(int(value)) if value.is_integer() else f"{value:.1f}"
    return str(value)


def _score_card(label: str, value: float | int | None, target: int) -> MetricCard:
    """A score card with a per-dimension target (from settings): green when the score
    meets the target, amber when below, plus a "Target N" detail line for context."""
    if value is None:
        return MetricCard(label, "-", "neutral")
    tone: Tone = "pass" if value >= target else "warning"
    return MetricCard(label, _score(value), tone, detail=f"Target {target}")


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    # Human-readable instead of a raw ISO string (no "T", seconds, or tz offset),
    # so it stays readable in cards and doesn't wrap across lines in the metric grid.
    return value.strftime("%Y-%m-%d %H:%M")


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
