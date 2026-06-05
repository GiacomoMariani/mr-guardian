from datetime import date, datetime, timedelta, timezone
from inspect import getsource
from pathlib import Path

from mr_guardian.core.dashboard import load_dashboard_data, prepare_dashboard_data
from mr_guardian.models.history import DashboardEtaNote, ReviewRunCreate, TriggeredRuleStat
from mr_guardian.models.review import LlmDeveloperProfile, LlmReviewSummary, RiskLevel
from mr_guardian.models.weekly_review import WeeklyLlmReviewRecord
from mr_guardian.storage import ReviewHistoryStore


def make_review_run(
    *,
    risk: RiskLevel = "warning",
    triggered_rule_ids: list[str] | None = None,
    timestamp: datetime | None = None,
    developer_id: str = "Test User",
    ticket_key: str | None = None,
    developer_profile: LlmDeveloperProfile | None = None,
    llm_summary: LlmReviewSummary | None = None,
    is_final: bool = False,
) -> ReviewRunCreate:
    rule_ids = triggered_rule_ids or ["PYTHON-PRINT-001"]
    return ReviewRunCreate(
        review_scope="local-all-policies",
        branch_name="main",
        developer_id=developer_id,
        ticket_key=ticket_key,
        is_final=is_final,
        policy_version=1,
        risk=risk,
        blocking_count=1 if risk == "blocking" else 0,
        high_count=1 if risk == "high" else 0,
        warning_count=1 if risk == "warning" else 0,
        info_count=1 if risk == "info" else 0,
        changed_file_count=2,
        changed_line_count=10,
        triggered_rule_ids=rule_ids,
        generated_review_report="## MR Guardian Review\n",
        timestamp=timestamp,
        developer_profile=developer_profile,
        llm_summary=llm_summary,
    )


def test_dashboard_data_preparation_works_with_seeded_history() -> None:
    first_run = make_review_run(
        risk="blocking",
        triggered_rule_ids=["MR-META-001"],
        timestamp=datetime(2026, 5, 24, tzinfo=timezone.utc),
    )
    second_run = make_review_run(
        risk="warning",
        triggered_rule_ids=["AI-CODE-001"],
        timestamp=datetime(2026, 5, 25, tzinfo=timezone.utc),
    )
    store = ReviewHistoryStore(":memory:")
    first_record = store.store_review_run(first_run)
    second_record = store.store_review_run(second_run)
    most_triggered_rules = store.most_triggered_rules()
    store.close()

    data = prepare_dashboard_data(
        recent_reviews=[second_record, first_record],
        most_triggered_rules=most_triggered_rules,
    )

    assert [run.review_id for run in data.recent_reviews] == [2, 1]
    assert {risk_count.risk: risk_count.count for risk_count in data.risk_counts}[
        "blocking"
    ] == 1
    assert data.ai_code_risk_frequency == 1
    assert [point.date for point in data.trend_points] == ["2026-05-24", "2026-05-25"]
    assert data.developer_activity[0].developer_id == "Test User"


def test_recent_reviews_can_be_loaded_from_storage(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    old_timestamp = datetime(2026, 5, 24, tzinfo=timezone.utc)
    store.store_review_run(make_review_run(timestamp=old_timestamp))
    store.store_review_run(make_review_run(timestamp=old_timestamp + timedelta(days=1)))
    store.close()

    data = load_dashboard_data(tmp_path / "history.sqlite", recent_limit=1)

    assert len(data.recent_reviews) == 1
    assert data.recent_reviews[0].timestamp.date().isoformat() == "2026-05-25"
    assert data.developer_activity[0].last_review_at.date().isoformat() == "2026-05-25"


def test_risk_counts_can_be_calculated_from_storage_data() -> None:
    store = ReviewHistoryStore(":memory:")
    blocking_record = store.store_review_run(make_review_run(risk="blocking"))
    warning_record = store.store_review_run(make_review_run(risk="warning"))
    store.close()

    data = prepare_dashboard_data(
        recent_reviews=[blocking_record, warning_record],
        most_triggered_rules=[],
    )

    counts = {risk_count.risk: risk_count.count for risk_count in data.risk_counts}

    assert counts["blocking"] == 1
    assert counts["warning"] == 1
    assert counts["none"] == 0


def test_developer_activity_is_sorted_by_latest_review() -> None:
    old_timestamp = datetime(2026, 5, 24, tzinfo=timezone.utc)
    new_timestamp = old_timestamp + timedelta(days=1)
    store = ReviewHistoryStore(":memory:")
    old_record = store.store_review_run(
        make_review_run(developer_id="Older Developer", timestamp=old_timestamp)
    )
    new_record = store.store_review_run(
        make_review_run(developer_id="Recent Developer", timestamp=new_timestamp)
    )
    store.close()

    data = prepare_dashboard_data(
        recent_reviews=[old_record, new_record],
        most_triggered_rules=[],
    )

    assert [item.developer_id for item in data.developer_activity] == [
        "Recent Developer",
        "Older Developer",
    ]


def test_most_triggered_rules_can_be_calculated_from_storage_data() -> None:
    data = prepare_dashboard_data(
        recent_reviews=[],
        most_triggered_rules=[TriggeredRuleStat(rule_id="MR-META-001", trigger_count=3)],
    )

    assert data.most_triggered_rules[0].rule_id == "MR-META-001"
    assert data.most_triggered_rules[0].trigger_count == 3


def test_streamlit_app_imports_without_running_review() -> None:
    import app.streamlit_app as streamlit_app

    assert callable(streamlit_app.main)


def test_developer_link_is_url_safe() -> None:
    import app.streamlit_app as streamlit_app

    assert (
        streamlit_app._developer_link("Jane Developer/Lead")
        == "?view=developer&developer=Jane%20Developer%2FLead#Jane Developer/Lead"
    )


def test_recent_reviews_render_custom_table_with_clickable_developer() -> None:
    import app.streamlit_app as streamlit_app

    store = ReviewHistoryStore(":memory:")
    record = store.store_review_run(
        make_review_run(
            developer_id="Jane <Lead>",
            ticket_key="TK-234",
            timestamp=datetime(2026, 5, 29, tzinfo=timezone.utc),
            is_final=True,
        )
    )
    store.close()

    html = streamlit_app._recent_reviews_table([record])

    assert "mg-dashboard-table" in html
    assert "Developer Page" not in html
    assert "Jane &lt;Lead&gt;" in html
    assert "?view=developer&amp;developer=Jane%20%3CLead%3E#Jane" in html
    assert "TK-234" in html
    assert "<th>Final</th>" in html
    assert "Approved" in html


def test_recent_reviews_empty_state_uses_standalone_style() -> None:
    import app.streamlit_app as streamlit_app

    html = streamlit_app._recent_reviews_table([])

    assert "mg-empty-state" in html
    assert "No review history has been stored yet." in html


def test_dashboard_declares_clickable_tab_labels() -> None:
    import app.streamlit_app as streamlit_app

    assert streamlit_app._dashboard_tab_labels() == (
        "Delivery Health",
        "Agent Review",
        "Recent Reviews",
        "Lead Review",
        "Trends",
        "Triggered Rules",
    )


def test_agent_review_tab_is_second_and_opens_by_default() -> None:
    import app.streamlit_app as streamlit_app

    labels = streamlit_app._dashboard_tab_labels()
    assert streamlit_app.DEFAULT_DASHBOARD_TAB_INDEX == 1
    assert labels[streamlit_app.DEFAULT_DASHBOARD_TAB_INDEX] == "Agent Review"

    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")
    # The radio nav defaults to Agent Review server-side (no first-tab flash); the
    # old client-side tab nudge is gone.
    assert "st.radio(" in source
    assert "index=DEFAULT_DASHBOARD_TAB_INDEX" in source
    assert "_render_default_tab_script" not in source
    assert "subtitle=AGENT_REVIEW_CAPTION" in source
    assert "A complete review the agent produced" in source


def test_review_pager_shows_all_ids_with_disabled_arrows_when_they_fit() -> None:
    import app.streamlit_app as streamlit_app

    slots = streamlit_app._review_pager_slots(
        [3, 4, 5, 6, 7], window_start=0, page_size=10
    )
    assert slots[0] == ("prev", True)  # present but disabled — nothing to page
    assert slots[-1] == ("next", True)
    assert [value for kind, value in slots if kind == "id"] == [3, 4, 5, 6, 7]


def test_review_pager_at_latest_end_disables_next() -> None:
    import app.streamlit_app as streamlit_app

    ids = list(range(1, 16))  # 1..15
    # Default window sits at the latest end: start = 15 - 10 = 5 -> ids[5:15] = 6..15.
    slots = streamlit_app._review_pager_slots(ids, window_start=5, page_size=10)
    assert slots[0] == ("prev", False)  # can page back -> enabled
    assert slots[-1] == ("next", True)  # already at the latest end -> disabled
    assert [value for kind, value in slots if kind == "id"] == list(range(6, 16))


def test_review_pager_at_start_disables_prev() -> None:
    import app.streamlit_app as streamlit_app

    ids = list(range(1, 16))
    slots = streamlit_app._review_pager_slots(ids, window_start=0, page_size=10)
    assert slots[0] == ("prev", True)  # at the start -> disabled
    assert slots[-1] == ("next", False)  # can page forward -> enabled
    assert [value for kind, value in slots if kind == "id"] == list(range(1, 11))


def test_review_pager_in_the_middle_enables_both_arrows() -> None:
    import app.streamlit_app as streamlit_app

    slots = streamlit_app._review_pager_slots(
        list(range(1, 31)), window_start=10, page_size=10
    )
    assert slots[0] == ("prev", False)
    assert slots[-1] == ("next", False)
    assert [value for kind, value in slots if kind == "id"] == list(range(11, 21))


def test_dashboard_loaders_are_cached() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "@st.cache_data" in source
    assert "_cached_dashboard_data(" in source
    assert "_cached_review_run(" in source
    # cache key includes the DB mtime so it refreshes when a review is written
    assert "_db_mtime(database_path)" in source


def test_db_mtime_returns_zero_for_missing_file(tmp_path) -> None:
    import app.streamlit_app as streamlit_app

    assert streamlit_app._db_mtime(tmp_path / "nope.sqlite") == 0.0
    existing = tmp_path / "db.sqlite"
    existing.write_text("x", encoding="utf-8")
    assert streamlit_app._db_mtime(existing) > 0


def test_pipeline_hook_renders_three_steps() -> None:
    import app.streamlit_app as streamlit_app

    captured: list[str] = []

    class FakeSt:
        def markdown(self, html: str, unsafe_allow_html: bool = False) -> None:
            captured.append(html)

    streamlit_app._render_pipeline_hook(FakeSt())
    html = "".join(captured)
    assert "mg-howitworks" in html
    assert "How it works" in html
    assert "Merge-request diff" in html
    assert "Deterministic policy checks + bounded LLM reasoning" in html
    assert "Single merge verdict" in html
    assert html.count("mg-howitworks-arrow") == 2  # two arrows between three steps


def test_review_report_height_scales_and_clamps() -> None:
    import app.streamlit_app as streamlit_app
    from types import SimpleNamespace

    def run(findings=None, **counts: int) -> SimpleNamespace:
        base = {
            "blocking_count": 0,
            "high_count": 0,
            "warning_count": 0,
            "info_count": 0,
        }
        base.update(counts)
        return SimpleNamespace(findings=findings, **base)

    assert streamlit_app._review_report_height(run()) == 700  # ~one-page initial
    assert streamlit_app._review_report_height(run(findings=[1] * 5)) == 700 + 50 * 5
    assert streamlit_app._review_report_height(run(findings=[1] * 100)) == 2400  # max


def test_trends_use_custom_chart_and_dynamic_report_height() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "st.line_chart(" not in source  # call replaced by the themed Altair chart
    assert "st.altair_chart(" in source
    assert "_render_trend_chart" in source
    assert "height=_review_report_height(selected_run)" in source
    assert "height=1100" not in source


def test_render_section_omits_panel_number_when_index_is_none() -> None:
    from app.streamlit_components import render_section

    numbered = render_section(index=1, title="Agent Review", body_html="<p>x</p>")
    unnumbered = render_section(title="Agent Review", body_html="<p>x</p>")

    assert "mg-panel-num" in numbered
    assert ">01<" in numbered
    assert "mg-panel-num" not in unnumbered
    assert "Agent Review" in unnumbered


def test_dashboard_defaults_to_dark_theme() -> None:
    import app.streamlit_app as streamlit_app

    assert streamlit_app.DEFAULT_THEME_LABEL == "Dark"
    assert streamlit_app._default_theme_index() == 1


def test_dashboard_main_page_uses_radio_section_nav() -> None:
    import app.streamlit_app as streamlit_app

    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert 'key="dashboard_section"' in source
    assert "horizontal=True" in source
    assert "render_section_nav" not in source
    assert "NavItem" not in source
    assert "st.sidebar" not in source
    assert 'selected_section == "Delivery Health"' in source
    assert 'selected_section == "Agent Review"' in source
    assert "readiness_percent = _render_pm_dashboard(st, database_path)" in source
    assert "readiness_percent=readiness_percent" in source
    assert "_render_weekly_llm_review(st, database_path)" in source
    assert "Project Health" not in streamlit_app._dashboard_tab_labels()
    assert "_render_project_health" not in source


def test_dashboard_database_path_is_readonly_and_window_controls_are_scoped() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "st.text_input" not in source
    assert "mg-readonly-value" in source
    assert 'key="recent_reviews_limit"' in source
    assert 'key="lead_lookback_days"' in source
    assert 'key="developer_detail_lookback_days"' in source


def test_delivery_health_first_tab_is_summary_only() -> None:
    import app.streamlit_app as streamlit_app

    source = getsource(streamlit_app._render_pm_dashboard)

    assert "DEFAULT_PM_LOOKBACK_DAYS" in source
    assert "st.number_input" not in source
    assert "_pm_tickets_table" not in source
    assert "_pm_blockers_table" not in source
    assert "Recurring Blockers" not in source
    assert "return summary.pass_rate" in source


def test_beta_phase_eta_uses_readiness_eyebrow() -> None:
    import app.streamlit_app as streamlit_app

    source = getsource(streamlit_app._render_eta_note)

    assert "action_html=_readiness_badge(readiness_percent)" in source


def test_readiness_badge_is_prominent() -> None:
    import app.streamlit_app as streamlit_app
    from app.streamlit_style import dashboard_css

    html = streamlit_app._readiness_badge(75.0)
    css = dashboard_css("dark")

    assert "mg-readiness-badge" in html
    assert "<strong>75%</strong>" in html
    assert ".mg-readiness-badge" in css
    assert "font-size: 22px;" in css


def test_dashboard_exposes_source_and_best_practices_links() -> None:
    import app.streamlit_app as streamlit_app
    from app.streamlit_components import render_page_header

    assert streamlit_app.BEST_PRACTICES_URL == (
        "https://github.com/GiacomoMariani/UnityBestPractices"
    )
    assert streamlit_app.SOURCE_URL == "https://github.com/GiacomoMariani/mr-guardian"
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")
    assert "Best practices applied ↗" in source
    assert "View source ↗" in source
    assert "_render_best_practices_link" not in source

    html = render_page_header(
        title="MR Guardian",
        kicker="Review Intelligence",
        body="Review body.",
        top_links=(
            ("View source ↗", streamlit_app.SOURCE_URL),
            ("Best practices applied ↗", streamlit_app.BEST_PRACTICES_URL),
        ),
    )
    assert "mg-app-hero-top" in html
    assert "mg-hero-links" in html
    assert "Review Intelligence" in html
    assert "View source ↗" in html
    assert "Best practices applied ↗" in html
    assert streamlit_app.SOURCE_URL in html
    assert streamlit_app.BEST_PRACTICES_URL in html


def test_eta_note_panel_renders_empty_state_with_disclaimer() -> None:
    import app.streamlit_app as streamlit_app

    html = streamlit_app._eta_note_panel(None)

    assert "No beta phase ETA note has been set yet." in html
    assert "Confirm beta phase dates" in html


def test_eta_note_panel_renders_note_with_target_and_updated_timestamp() -> None:
    import app.streamlit_app as streamlit_app

    html = streamlit_app._eta_note_panel(
        DashboardEtaNote(
            message="Milestone looks merge-ready by Friday.",
            target_date=date(2026, 6, 5),
            updated_at=datetime(2026, 6, 3, 10, 30, tzinfo=timezone.utc),
        )
    )

    assert "Milestone looks merge-ready by Friday." in html
    assert "2026-06-05" in html
    assert "2026-06-03T10:30:00+00:00" in html
    assert "Confirm beta phase dates" in html


def test_dashboard_loads_eta_note_through_core() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "load_dashboard_eta_note" in source
    assert "set_dashboard_eta_note" not in source


def test_weekly_llm_review_panel_renders_stored_summary() -> None:
    import app.streamlit_app as streamlit_app

    record = WeeklyLlmReviewRecord(
        weekly_review_id=1,
        week_start=date(2026, 6, 1),
        week_end=date(2026, 6, 7),
        created_at=datetime(2026, 6, 7, 18, tzinfo=timezone.utc),
        result="on_track",
        score=84,
        summary="The week is on track with one remaining high-risk review.",
        mr_count=12,
        developer_count=4,
        ticket_count=7,
        approved_ticket_count=5,
        observed_ticket_count=2,
        blocking_review_count=0,
        high_risk_review_count=1,
        warning_review_count=3,
        info_review_count=8,
        top_risks=["One ticket still has a high-risk review."],
        recommended_actions=["Clear the high-risk ticket before the beta cut."],
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=1200,
        output_tokens=240,
        total_tokens=1440,
        estimated_cost_usd=0.0031,
    )

    html = streamlit_app._weekly_llm_review_panel(record)
    badge_html = streamlit_app._weekly_llm_result_badge(record)

    assert "Weekly assessment" in html
    assert "The week is on track with one remaining high-risk review." in html
    assert "84/100" in html
    assert "LLM-calculated score" in html
    assert "MRs This Week" in html
    assert "One ticket still has a high-risk review." in html
    assert "Clear the high-risk ticket before the beta cut." in html
    assert "gpt-4.1-mini" in html
    assert "input 1200" in html
    assert "0.0031 USD" in html
    assert "On Track" in badge_html


def test_weekly_llm_review_panel_renders_empty_state() -> None:
    import app.streamlit_app as streamlit_app

    html = streamlit_app._weekly_llm_review_panel(None)

    assert "No weekly LLM review has been stored yet." in html


def test_dashboard_loads_weekly_llm_review_through_core() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "load_latest_weekly_llm_review" in source
    assert "store_weekly_llm_review" not in source


def test_lead_developers_render_name_as_link_without_extra_open_column() -> None:
    import app.streamlit_app as streamlit_app
    from mr_guardian.core.lead_dashboard import prepare_lead_dashboard_summary

    store = ReviewHistoryStore(":memory:")
    record = store.store_review_run(
        make_review_run(
            developer_id="Jane Developer",
            ticket_key="TK-234",
            timestamp=datetime(2026, 5, 29, tzinfo=timezone.utc),
        )
    )
    store.close()
    summary = prepare_lead_dashboard_summary(
        review_runs=[record],
        start_at=datetime(2026, 5, 28, tzinfo=timezone.utc),
        end_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
    )

    html = streamlit_app._lead_developers_table(summary.developers)

    assert "Jane Developer</a>" in html
    assert "Developer Page" not in html
    assert "<th>Developer</th>" in html
    assert "<th>Review Requests</th>" in html
    assert "<th>Approved Tickets</th>" in html
    assert "<th>Avg Approval Attempts</th>" in html


def test_developer_detail_tables_render_real_ticket_and_rule_data() -> None:
    import app.streamlit_app as streamlit_app
    from mr_guardian.core.lead_dashboard import prepare_lead_dashboard_summary

    first = datetime(2026, 5, 28, tzinfo=timezone.utc)
    store = ReviewHistoryStore(":memory:")
    first_record = store.store_review_run(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-234",
            timestamp=first,
            triggered_rule_ids=["MR-META-001"],
        )
    )
    second_record = store.store_review_run(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-234",
            timestamp=first + timedelta(hours=1),
            triggered_rule_ids=["MR-META-001", "PYTHON-PRINT-001"],
        )
    )
    store.close()
    summary = prepare_lead_dashboard_summary(
        review_runs=[first_record, second_record],
        start_at=first - timedelta(days=1),
        end_at=first + timedelta(days=1),
    )
    developer = summary.developers[0]

    tickets_html = streamlit_app._lead_tickets_table(developer)
    repeated_rules_html = streamlit_app._lead_repeated_rules_table(developer)
    reviews_html = streamlit_app._developer_reviews_table([second_record])

    assert "TK-234" in tickets_html
    assert "Observed" in tickets_html
    assert "Attempts To Approval" in tickets_html
    assert "MR-META-001" in repeated_rules_html
    assert "PYTHON-PRINT-001" in reviews_html
    assert "<th>Final</th>" in reviews_html
    assert "mg-chip" in reviews_html


def test_developer_profile_panel_renders_latest_profile_snapshot() -> None:
    import app.streamlit_app as streamlit_app

    store = ReviewHistoryStore(":memory:")
    old_record = store.store_review_run(
        make_review_run(
            developer_id="Jane",
            timestamp=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
    )
    latest_record = store.store_review_run(
        make_review_run(
            developer_id="Jane",
            timestamp=datetime(2026, 5, 29, tzinfo=timezone.utc),
            developer_profile=LlmDeveloperProfile(
                status="succeeded",
                provider="openai",
                model="gpt-4.1-mini",
                duration_ms=1234,
                lookback_days=30,
                text="Jane is improving <fast>.",
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
            ),
        )
    )
    store.close()

    selected_run = streamlit_app._latest_developer_profile_run(
        [latest_record, old_record]
    )
    html = streamlit_app._developer_profile_panel(selected_run)

    assert selected_run == latest_record
    assert "Latest LLM Developer Profile" in html
    assert "Jane is improving &lt;fast&gt;." in html
    assert "Succeeded" in html
    assert "30 day window" in html
    assert "gpt-4.1-mini" in html
    assert "input 10" in html


def test_developer_view_query_param_is_detected() -> None:
    import app.streamlit_app as streamlit_app

    class FakeStreamlit:
        query_params = {"view": "developer"}

    assert streamlit_app._is_developer_view(FakeStreamlit())


def test_dashboard_theme_css_supports_light_and_dark_modes() -> None:
    from app.streamlit_style import dashboard_css, theme_from_label

    light_css = dashboard_css("light")
    dark_css = dashboard_css("dark")

    assert theme_from_label("Light") == "light"
    assert theme_from_label("Dark") == "dark"
    assert "--paper: #F1EBDD;" in light_css
    assert "--paper: #15120D;" in dark_css
    assert "Hanken Grotesk" in light_css
    assert "JetBrains Mono" in dark_css
    assert "mg-app-hero" in light_css
    assert "mg-hero-top-link" in light_css
    assert "mg-hero-links" in light_css
    assert "mg-pager-label" in light_css
    assert "[data-testid=\"stTextInput\"] input" in light_css
    assert "-webkit-text-fill-color: var(--ink)" in light_css
    assert "[data-baseweb=\"tab-list\"]" in light_css
    assert "[data-testid=\"stSidebar\"]" in light_css
    assert "display: none;" in light_css
    assert ".mg-readonly-value" in light_css
    assert "pointer-events: none;" in light_css
    assert "stMetric" in dark_css


def test_no_rule_logic_exists_in_streamlit_folder() -> None:
    app_source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "run_review" not in app_source
    assert "default_rule_registry" not in app_source
    assert "RuleRegistry" not in app_source


def test_standalone_placeholder_values_do_not_appear_in_dashboard_rendering() -> None:
    import app.streamlit_app as streamlit_app

    html = "\n".join(
        [
            streamlit_app._recent_reviews_table([]),
            streamlit_app._triggered_rules_table([]),
            streamlit_app._pm_tickets_table([]),
            streamlit_app._pm_blockers_table([]),
        ]
    )

    assert "RagDemo" not in html
    assert "Demo Developer" not in html
