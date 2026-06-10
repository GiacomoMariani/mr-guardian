from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.core.lead_dashboard import (
    load_lead_dashboard_summary,
    load_lead_developer_detail,
    prepare_lead_dashboard_summary,
    prepare_lead_developer_detail,
)
from mr_guardian.models.history import ReviewRunCreate
from mr_guardian.models.review import FindingCounts, LlmRuleMetric, ReviewEvaluation, RiskLevel
from mr_guardian.storage import ReviewHistoryStore


def make_review_run(
    *,
    developer_id: str,
    ticket_key: str | None,
    timestamp: datetime,
    risk: RiskLevel,
    review_score: int,
    triggered_rule_ids: list[str] | None = None,
    evaluations: list[ReviewEvaluation] | None = None,
    is_final: bool = False,
    llm_metrics: list[LlmRuleMetric] | None = None,
) -> ReviewRunCreate:
    rule_ids = triggered_rule_ids or (["RULE-001"] if risk != "none" else [])
    return ReviewRunCreate(
        review_scope="gitlab-webhook",
        branch_name="refs/remotes/origin/main",
        developer_id=developer_id,
        ticket_key=ticket_key,
        is_final=is_final,
        mr_id="42",
        policy_version=1,
        risk=risk,
        blocking_count=1 if risk == "blocking" else 0,
        high_count=1 if risk == "high" else 0,
        warning_count=1 if risk == "warning" else 0,
        info_count=1 if risk == "info" else 0,
        changed_file_count=2,
        changed_line_count=12,
        review_score=review_score,
        llm_metrics=llm_metrics or [],
        triggered_rule_ids=rule_ids,
        evaluations=evaluations or [],
        generated_review_report="## MR Guardian Review\n",
        timestamp=timestamp,
    )


def stored_runs(*runs: ReviewRunCreate) -> list:
    store = ReviewHistoryStore(":memory:")
    try:
        return [store.store_review_run(run) for run in runs]
    finally:
        store.close()


def _metric(cost: float) -> LlmRuleMetric:
    return LlmRuleMetric(
        rule_id="LLM-1",
        provider="openai",
        model="gpt-4.1-mini",
        status="succeeded",
        duration_ms=100,
        input_tokens=100,
        output_tokens=10,
        total_tokens=110,
        estimated_cost_usd=cost,
    )


def test_lead_summary_totals_estimated_cost() -> None:
    base_time = datetime(2026, 5, 25, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-1",
            timestamp=base_time,
            risk="warning",
            review_score=90,
            llm_metrics=[_metric(0.0030)],
        ),
        make_review_run(
            developer_id="Dan",
            ticket_key="TK-2",
            timestamp=base_time,
            risk="none",
            review_score=100,
            llm_metrics=[_metric(0.0008)],
        ),
        make_review_run(
            developer_id="Dan",
            ticket_key="TK-3",
            timestamp=base_time,
            risk="none",
            review_score=100,
        ),
    )

    summary = prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=base_time - timedelta(days=1),
        end_at=base_time + timedelta(days=1),
    )

    assert summary.total_estimated_cost_usd == 0.0038
    assert summary.total_tokens == 220
    assert summary.currency == "USD"


def test_lead_summary_cost_is_none_without_priced_reviews() -> None:
    base_time = datetime(2026, 5, 25, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-1",
            timestamp=base_time,
            risk="none",
            review_score=100,
        ),
    )

    summary = prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=base_time - timedelta(days=1),
        end_at=base_time + timedelta(days=1),
    )

    assert summary.total_estimated_cost_usd is None
    assert summary.total_tokens is None


def test_lead_developer_summary_totals_estimated_cost() -> None:
    base_time = datetime(2026, 5, 25, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-1",
            timestamp=base_time,
            risk="warning",
            review_score=90,
            llm_metrics=[_metric(0.0030)],
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-2",
            timestamp=base_time + timedelta(hours=1),
            risk="none",
            review_score=100,
            llm_metrics=[_metric(0.0005)],
        ),
        make_review_run(
            developer_id="Dan",
            ticket_key="TK-3",
            timestamp=base_time,
            risk="none",
            review_score=100,
            llm_metrics=[_metric(0.0008)],
        ),
    )

    summary = prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=base_time - timedelta(days=1),
        end_at=base_time + timedelta(days=1),
    )
    by_developer = {dev.developer_id: dev for dev in summary.developers}

    assert by_developer["Jane"].total_estimated_cost_usd == 0.0035
    assert by_developer["Dan"].total_estimated_cost_usd == 0.0008
    assert by_developer["Jane"].total_tokens == 220
    assert by_developer["Dan"].total_tokens == 110
    assert by_developer["Jane"].currency == "USD"


def _trend_history_runs(now: datetime) -> list[ReviewRunCreate]:
    """Two reviews outside a 3-day window, then four inside it.

    Over the four windowed reviews alone the split-half delta is -5.5
    (100,100 -> 95,94 = "declining"); over the full six-review history the
    delta is ~-0.3 ("stable"). Used to prove the trend uses full history.
    """
    return [
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-1",
            timestamp=now - timedelta(days=11),
            risk="warning",
            review_score=95,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-2",
            timestamp=now - timedelta(days=10),
            risk="warning",
            review_score=95,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-3",
            timestamp=now - timedelta(days=2, hours=12),
            risk="none",
            review_score=100,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-4",
            timestamp=now - timedelta(days=2),
            risk="none",
            review_score=100,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-5",
            timestamp=now - timedelta(days=1, hours=12),
            risk="warning",
            review_score=95,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-6",
            timestamp=now - timedelta(days=1),
            risk="warning",
            review_score=94,
        ),
    ]


def test_lead_summary_groups_reviews_by_developer_and_ticket() -> None:
    start = datetime(2026, 5, 20, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-100",
            timestamp=start,
            risk="warning",
            review_score=95,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-100",
            timestamp=start + timedelta(hours=1),
            risk="none",
            review_score=100,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-200",
            timestamp=start + timedelta(hours=2),
            risk="high",
            review_score=85,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key=None,
            timestamp=start + timedelta(hours=3),
            risk="warning",
            review_score=95,
        ),
    )

    summary = prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=start - timedelta(days=1),
        end_at=start + timedelta(days=1),
    )

    jane = summary.developers[0]
    ticket_by_key = {ticket.ticket_key: ticket for ticket in jane.tickets}
    assert jane.developer_id == "Jane"
    assert jane.review_request_count == 4
    assert jane.ticket_count == 2
    assert jane.average_attempts_per_ticket == 1.5
    assert jane.average_score == 93.75
    assert jane.approved_ticket_count == 0
    assert jane.average_attempts_to_approval is None
    assert jane.multi_attempt_ticket_count == 1
    assert jane.unlinked_review_count == 1
    assert ticket_by_key["TK-100"].review_attempt_count == 2
    assert ticket_by_key["TK-100"].latest_risk == "none"
    assert ticket_by_key["TK-100"].is_approved is False
    assert ticket_by_key["TK-100"].approved_at is None
    assert ticket_by_key["TK-100"].attempts_to_approval is None
    assert ticket_by_key["TK-100"].assumed_deployed_at == start + timedelta(hours=1)


def test_lead_summary_tracks_approved_tickets_and_attempts_to_approval() -> None:
    start = datetime(2026, 5, 20, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-100",
            timestamp=start,
            risk="warning",
            review_score=95,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-100",
            timestamp=start + timedelta(hours=1),
            risk="none",
            review_score=100,
            is_final=True,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-100",
            timestamp=start + timedelta(hours=2),
            risk="warning",
            review_score=95,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-200",
            timestamp=start + timedelta(hours=3),
            risk="none",
            review_score=100,
            is_final=True,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-300",
            timestamp=start + timedelta(hours=4),
            risk="high",
            review_score=85,
        ),
    )

    summary = prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=start - timedelta(days=1),
        end_at=start + timedelta(days=1),
    )

    jane = summary.developers[0]
    tickets = {ticket.ticket_key: ticket for ticket in jane.tickets}
    assert jane.approved_ticket_count == 2
    assert jane.average_attempts_to_approval == 1.5
    assert tickets["TK-100"].is_approved is True
    assert tickets["TK-100"].approved_at == start + timedelta(hours=1)
    assert tickets["TK-100"].attempts_to_approval == 2
    assert tickets["TK-200"].attempts_to_approval == 1
    assert tickets["TK-300"].is_approved is False
    assert tickets["TK-300"].attempts_to_approval is None


def test_lead_summary_sorts_developers_by_latest_review() -> None:
    start = datetime(2026, 5, 20, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            developer_id="Older",
            ticket_key="TK-100",
            timestamp=start,
            risk="none",
            review_score=100,
        ),
        make_review_run(
            developer_id="Recent",
            ticket_key="TK-200",
            timestamp=start + timedelta(days=1),
            risk="none",
            review_score=100,
        ),
    )

    summary = prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=start - timedelta(days=1),
        end_at=start + timedelta(days=2),
    )

    assert [developer.developer_id for developer in summary.developers] == [
        "Recent",
        "Older",
    ]


def test_lead_summary_detects_repeated_rules_per_developer() -> None:
    start = datetime(2026, 5, 20, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-100",
            timestamp=start,
            risk="high",
            review_score=85,
            triggered_rule_ids=["MR-META-001"],
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-200",
            timestamp=start + timedelta(hours=1),
            risk="blocking",
            review_score=65,
            triggered_rule_ids=["MR-META-001", "CSHARP-DEBUG-001"],
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-300",
            timestamp=start + timedelta(hours=2),
            risk="warning",
            review_score=95,
            triggered_rule_ids=["CSHARP-DEBUG-001"],
        ),
    )

    summary = prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=start - timedelta(days=1),
        end_at=start + timedelta(days=1),
    )

    jane = summary.developers[0]
    assert jane.repeated_rule_count == 2
    assert [(rule.rule_id, rule.review_run_count) for rule in jane.repeated_rules] == [
        ("CSHARP-DEBUG-001", 2),
        ("MR-META-001", 2),
    ]


def test_lead_summary_summarizes_evaluation_dimensions() -> None:
    start = datetime(2026, 5, 20, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-100",
            timestamp=start,
            risk="high",
            review_score=80,
            evaluations=[
                ReviewEvaluation(
                    evaluation="coding",
                    risk="warning",
                    counts=FindingCounts(warning=1),
                    triggered_rule_ids=["CSHARP-DEBUG-001"],
                ),
                ReviewEvaluation(
                    evaluation="mr_structure",
                    risk="high",
                    counts=FindingCounts(high=1),
                    triggered_rule_ids=["MR-META-001"],
                ),
            ],
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-200",
            timestamp=start + timedelta(hours=1),
            risk="none",
            review_score=100,
            evaluations=[
                ReviewEvaluation(
                    evaluation="coding",
                    risk="none",
                    counts=FindingCounts(),
                    triggered_rule_ids=[],
                ),
                ReviewEvaluation(
                    evaluation="mr_structure",
                    risk="none",
                    counts=FindingCounts(),
                    triggered_rule_ids=[],
                ),
            ],
        ),
    )

    summary = prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=start - timedelta(days=1),
        end_at=start + timedelta(days=1),
    )

    evaluations = {
        evaluation.evaluation: evaluation
        for evaluation in summary.developers[0].evaluation_summaries
    }
    assert evaluations["coding"].review_count == 2
    assert evaluations["coding"].average_score == 97.5
    assert evaluations["coding"].counts.warning == 1
    assert evaluations["mr_structure"].average_score == 92.5
    assert evaluations["mr_structure"].counts.high == 1


def test_lead_summary_uses_insufficient_data_trend_when_needed() -> None:
    start = datetime(2026, 5, 20, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-100",
            timestamp=start,
            risk="warning",
            review_score=95,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-200",
            timestamp=start + timedelta(hours=1),
            risk="none",
            review_score=100,
        ),
    )

    summary = prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=start - timedelta(days=1),
        end_at=start + timedelta(days=1),
    )

    assert summary.developers[0].trend_direction == "insufficient_data"


def test_lead_summary_detects_improving_trend_with_enough_data() -> None:
    start = datetime(2026, 5, 20, 10, tzinfo=timezone.utc)
    review_runs = stored_runs(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-100",
            timestamp=start,
            risk="high",
            review_score=70,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-101",
            timestamp=start + timedelta(hours=1),
            risk="warning",
            review_score=80,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-102",
            timestamp=start + timedelta(hours=2),
            risk="warning",
            review_score=95,
        ),
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-103",
            timestamp=start + timedelta(hours=3),
            risk="none",
            review_score=100,
        ),
    )

    summary = prepare_lead_dashboard_summary(
        review_runs=review_runs,
        start_at=start - timedelta(days=1),
        end_at=start + timedelta(days=1),
    )

    assert summary.developers[0].trend_direction == "improving"


def test_load_lead_dashboard_summary_uses_selected_time_window(tmp_path: Path) -> None:
    now = datetime(2026, 5, 28, 10, tzinfo=timezone.utc)
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    store.store_review_run(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-OLD",
            timestamp=now - timedelta(days=10),
            risk="warning",
            review_score=95,
        )
    )
    store.store_review_run(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-NEW",
            timestamp=now - timedelta(days=1),
            risk="none",
            review_score=100,
        )
    )
    store.close()

    summary = load_lead_dashboard_summary(
        tmp_path / "history.sqlite",
        days=3,
        end_at=now,
    )

    assert summary.developers[0].tickets[0].ticket_key == "TK-NEW"


def test_prepare_lead_developer_detail_filters_to_selected_developer() -> None:
    start = datetime(2026, 5, 20, 10, tzinfo=timezone.utc)
    jane_run = make_review_run(
        developer_id="Jane",
        ticket_key="TK-100",
        timestamp=start,
        risk="warning",
        review_score=95,
    )
    other_run = make_review_run(
        developer_id="Other",
        ticket_key="TK-200",
        timestamp=start + timedelta(hours=1),
        risk="none",
        review_score=100,
    )
    review_runs = stored_runs(jane_run, other_run)

    detail = prepare_lead_developer_detail(
        developer_id="Jane",
        review_runs=review_runs,
        start_at=start - timedelta(days=1),
        end_at=start + timedelta(days=1),
    )

    assert detail is not None
    assert detail.developer.developer_id == "Jane"
    assert detail.developer.review_request_count == 1
    assert [run.developer_id for run in detail.review_runs] == ["Jane"]


def test_prepare_lead_developer_detail_returns_none_for_missing_developer() -> None:
    start = datetime(2026, 5, 20, 10, tzinfo=timezone.utc)

    detail = prepare_lead_developer_detail(
        developer_id="Missing",
        review_runs=[],
        start_at=start - timedelta(days=1),
        end_at=start + timedelta(days=1),
    )

    assert detail is None


def test_load_lead_developer_detail_uses_selected_time_window(tmp_path: Path) -> None:
    now = datetime(2026, 5, 28, 10, tzinfo=timezone.utc)
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    store.store_review_run(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-OLD",
            timestamp=now - timedelta(days=10),
            risk="warning",
            review_score=95,
        )
    )
    store.store_review_run(
        make_review_run(
            developer_id="Jane",
            ticket_key="TK-NEW",
            timestamp=now - timedelta(days=1),
            risk="none",
            review_score=100,
        )
    )
    store.close()

    detail = load_lead_developer_detail(
        tmp_path / "history.sqlite",
        developer_id="Jane",
        days=3,
        end_at=now,
    )

    assert detail is not None
    assert [run.ticket_key for run in detail.review_runs] == ["TK-NEW"]


def test_load_lead_dashboard_summary_trend_uses_full_history(tmp_path: Path) -> None:
    now = datetime(2026, 5, 28, 10, tzinfo=timezone.utc)
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    for run in _trend_history_runs(now):
        store.store_review_run(run)
    store.close()

    summary = load_lead_dashboard_summary(
        tmp_path / "history.sqlite",
        days=3,
        end_at=now,
    )

    jane = summary.developers[0]
    # Only the four recent reviews fall in the 3-day window ...
    assert jane.review_request_count == 4
    # ... and those four alone would read "declining" (delta -5.5), but the
    # trend is computed over the full six-review history -> "stable".
    assert jane.trend_direction == "stable"


def test_load_lead_developer_detail_trend_uses_full_history(tmp_path: Path) -> None:
    now = datetime(2026, 5, 28, 10, tzinfo=timezone.utc)
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    for run in _trend_history_runs(now):
        store.store_review_run(run)
    store.close()

    detail = load_lead_developer_detail(
        tmp_path / "history.sqlite",
        developer_id="Jane",
        days=3,
        end_at=now,
    )

    assert detail is not None
    # The displayed review list stays windowed (four rows) ...
    assert len(detail.review_runs) == 4
    # ... while the trend pill reflects the full history -> "stable".
    assert detail.developer.trend_direction == "stable"


def test_lead_aggregation_stays_outside_streamlit() -> None:
    app_source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "prepare_lead_dashboard_summary" not in app_source
    assert "defaultdict" not in app_source
