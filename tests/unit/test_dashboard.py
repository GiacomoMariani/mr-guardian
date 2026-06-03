from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.core.dashboard import load_dashboard_data, prepare_dashboard_data
from mr_guardian.models.history import ReviewRunCreate, TriggeredRuleStat
from mr_guardian.models.review import LlmDeveloperProfile, LlmReviewSummary, RiskLevel
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
) -> ReviewRunCreate:
    rule_ids = triggered_rule_ids or ["PYTHON-PRINT-001"]
    return ReviewRunCreate(
        review_scope="local-all-policies",
        branch_name="main",
        developer_id=developer_id,
        ticket_key=ticket_key,
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
        )
    )
    store.close()

    html = streamlit_app._recent_reviews_table([record])

    assert "mg-dashboard-table" in html
    assert "Developer Page" not in html
    assert "Jane &lt;Lead&gt;" in html
    assert "?view=developer&amp;developer=Jane%20%3CLead%3E#Jane" in html
    assert "TK-234" in html


def test_recent_reviews_empty_state_uses_standalone_style() -> None:
    import app.streamlit_app as streamlit_app

    html = streamlit_app._recent_reviews_table([])

    assert "mg-empty-state" in html
    assert "No review history has been stored yet." in html


def test_dashboard_declares_clickable_tab_labels() -> None:
    import app.streamlit_app as streamlit_app

    assert streamlit_app._dashboard_tab_labels() == (
        "Project Health",
        "Delivery Health",
        "Lead Review",
        "Trends",
        "Triggered Rules",
        "Recent Reviews",
        "Stored Report",
    )


def test_dashboard_defaults_to_dark_theme() -> None:
    import app.streamlit_app as streamlit_app

    assert streamlit_app.DEFAULT_THEME_LABEL == "Dark"
    assert streamlit_app._default_theme_index() == 1


def test_dashboard_main_page_uses_tabs_not_anchor_nav() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "st.tabs(list(_dashboard_tab_labels()))" in source
    assert "render_section_nav" not in source
    assert "NavItem" not in source
    assert "st.sidebar" not in source


def test_dashboard_database_path_is_readonly_and_window_controls_are_scoped() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "st.text_input" not in source
    assert "mg-readonly-value" in source
    assert 'key="recent_reviews_limit"' in source
    assert 'key="pm_lookback_days"' in source
    assert 'key="lead_lookback_days"' in source
    assert 'key="developer_detail_lookback_days"' in source


def test_dashboard_exposes_best_practices_link() -> None:
    import app.streamlit_app as streamlit_app

    assert streamlit_app.BEST_PRACTICES_URL == (
        "https://github.com/GiacomoMariani/UnityBestPractices"
    )
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")
    assert "Best practices applied" in source


def test_latest_llm_review_panel_renders_summary() -> None:
    import app.streamlit_app as streamlit_app

    store = ReviewHistoryStore(":memory:")
    old_record = store.store_review_run(make_review_run())
    latest_record = store.store_review_run(
        make_review_run(
            developer_id="Jane",
            timestamp=datetime(2026, 5, 29, tzinfo=timezone.utc),
            llm_summary=LlmReviewSummary(
                status="succeeded",
                provider="openai",
                model="gpt-4.1-mini",
                duration_ms=820,
                text="This MR is ready after metadata cleanup.",
                score=82,
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
            ),
        )
    )
    store.close()

    selected_run = streamlit_app._latest_llm_summary_run([latest_record, old_record])
    html = streamlit_app._llm_review_summary_panel(selected_run)

    assert selected_run == latest_record
    assert "Latest LLM Review" in html
    assert "This MR is ready after metadata cleanup." in html
    assert "Score 82" in html
    assert "gpt-4.1-mini" in html


def test_latest_llm_review_panel_handles_legacy_summary_without_score() -> None:
    import app.streamlit_app as streamlit_app

    class LegacySummary:
        status = "succeeded"
        provider = "openai"
        model = "gpt-4.1-mini"
        duration_ms = 820
        text = "Legacy summary still renders."
        input_tokens = 10
        output_tokens = 20
        total_tokens = 30
        error_message = None

    class LegacyRun:
        review_id = 1
        timestamp = datetime(2026, 5, 29, tzinfo=timezone.utc)
        developer_id = "Jane"
        review_score = 91
        llm_summary = LegacySummary()

    html = streamlit_app._llm_review_summary_panel(LegacyRun())

    assert "Legacy summary still renders." in html
    assert "Score 91" in html


def test_latest_llm_review_panel_renders_empty_state() -> None:
    import app.streamlit_app as streamlit_app

    html = streamlit_app._llm_review_summary_panel(None)

    assert "No LLM review summary has been generated yet." in html


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
    assert "MR-META-001" in repeated_rules_html
    assert "PYTHON-PRINT-001" in reviews_html
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
    assert "mg-link-bar" in light_css
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
