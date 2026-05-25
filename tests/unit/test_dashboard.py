from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.core.dashboard import load_dashboard_data, prepare_dashboard_data
from mr_guardian.models.history import ReviewRunCreate, TriggeredRuleStat
from mr_guardian.models.review import RiskLevel
from mr_guardian.storage import ReviewHistoryStore


def make_review_run(
    *,
    risk: RiskLevel = "warning",
    triggered_rule_ids: list[str] | None = None,
    timestamp: datetime | None = None,
) -> ReviewRunCreate:
    rule_ids = triggered_rule_ids or ["PYTHON-PRINT-001"]
    return ReviewRunCreate(
        project_name="MR Guardian",
        branch_name="main",
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


def test_recent_reviews_can_be_loaded_from_storage(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    old_timestamp = datetime(2026, 5, 24, tzinfo=timezone.utc)
    store.store_review_run(make_review_run(timestamp=old_timestamp))
    store.store_review_run(make_review_run(timestamp=old_timestamp + timedelta(days=1)))
    store.close()

    data = load_dashboard_data(tmp_path / "history.sqlite", recent_limit=1)

    assert len(data.recent_reviews) == 1
    assert data.recent_reviews[0].timestamp.date().isoformat() == "2026-05-25"


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


def test_no_rule_logic_exists_in_streamlit_folder() -> None:
    app_source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "run_review" not in app_source
    assert "default_rule_registry" not in app_source
    assert "RuleRegistry" not in app_source
