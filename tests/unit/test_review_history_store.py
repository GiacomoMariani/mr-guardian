import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from mr_guardian.models.history import ReviewPolicySummary, ReviewRunCreate
from mr_guardian.models.review import (
    Finding,
    FindingCounts,
    LlmDeveloperProfile,
    LlmReviewSummary,
    LlmRuleMetric,
    ReviewEvaluation,
)
from mr_guardian.storage import ReviewHistoryStore


def make_review_run(
    *,
    review_scope: str = "local-all-policies",
    branch_name: str = "feature/reporting",
    developer_id: str = "Test User",
    ticket_key: str | None = None,
    triggered_rule_ids: list[str] | None = None,
    llm_metrics: list[LlmRuleMetric] | None = None,
    llm_summary: LlmReviewSummary | None = None,
    developer_profile: LlmDeveloperProfile | None = None,
    evaluations: list[ReviewEvaluation] | None = None,
    findings: list[Finding] | None = None,
    policy_summaries: list[ReviewPolicySummary] | None = None,
    timestamp: datetime | None = None,
    is_final: bool = False,
) -> ReviewRunCreate:
    rule_ids = triggered_rule_ids or ["PYTHON-PRINT-001"]
    return ReviewRunCreate(
        review_scope=review_scope,
        branch_name=branch_name,
        developer_id=developer_id,
        ticket_key=ticket_key,
        is_final=is_final,
        mr_id="42",
        commit_sha="abc123",
        policy_version=1,
        risk="warning",
        blocking_count=0,
        high_count=0,
        warning_count=len(rule_ids),
        info_count=0,
        changed_file_count=3,
        changed_line_count=12,
        findings=findings or [],
        triggered_rule_ids=rule_ids,
        evaluations=evaluations
        or [
            ReviewEvaluation(
                evaluation="coding",
                risk="warning",
                counts=FindingCounts(warning=len(rule_ids)),
                triggered_rule_ids=rule_ids,
            ),
            ReviewEvaluation(
                evaluation="mr_structure",
                risk="none",
                counts=FindingCounts(),
                triggered_rule_ids=[],
            ),
        ],
        llm_metrics=llm_metrics or [],
        llm_summary=llm_summary,
        developer_profile=developer_profile,
        policy_summaries=policy_summaries or [],
        generated_review_report="## MR Guardian Review\n",
        timestamp=timestamp,
    )


def table_names(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
    return {str(row[0]) for row in rows}


def test_creates_sqlite_database(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    store = ReviewHistoryStore(database_path)

    store.initialize_schema()
    store.close()

    assert database_path.exists()


def test_initializes_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    store = ReviewHistoryStore(database_path)

    store.initialize_schema()
    store.close()

    assert {
        "review_runs",
        "triggered_rules",
        "review_findings",
        "review_policies",
        "review_llm_rule_metrics",
        "review_evaluations",
        "review_evaluation_triggered_rules",
        "dashboard_eta_note",
    }.issubset(table_names(database_path))


def test_stores_review_run(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(make_review_run())
    store.close()

    assert record.review_id == 1
    assert record.review_scope == "local-all-policies"
    assert record.branch_name == "feature/reporting"
    assert record.developer_id == "Test User"
    assert record.ticket_key is None
    assert record.mr_id == "42"
    assert record.commit_sha == "abc123"
    assert record.risk == "warning"
    assert record.warning_count == 1
    assert record.review_score == 95
    assert record.changed_file_count == 3
    assert record.changed_line_count == 12
    assert record.findings == []
    assert record.policy_summaries == []
    assert record.evaluations[0].evaluation == "coding"
    assert record.evaluations[0].risk == "warning"
    assert record.evaluations[0].triggered_rule_ids == ["PYTHON-PRINT-001"]
    assert record.llm_summary is None
    assert record.developer_profile is None
    assert record.generated_review_report == "## MR Guardian Review\n"


def test_migrates_existing_history_database(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE review_runs (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                project_name TEXT NOT NULL,
                branch_name TEXT NOT NULL,
                mr_id TEXT,
                commit_sha TEXT,
                policy_version INTEGER NOT NULL,
                risk TEXT NOT NULL,
                blocking_count INTEGER NOT NULL,
                high_count INTEGER NOT NULL,
                warning_count INTEGER NOT NULL,
                info_count INTEGER NOT NULL,
                changed_file_count INTEGER NOT NULL,
                changed_line_count INTEGER NOT NULL,
                generated_review_report TEXT NOT NULL
            );

            CREATE TABLE triggered_rules (
                review_id INTEGER NOT NULL,
                rule_id TEXT NOT NULL,
                FOREIGN KEY (review_id) REFERENCES review_runs(review_id) ON DELETE CASCADE
            );
            """
        )

    store = ReviewHistoryStore(database_path)
    record = store.store_review_run(make_review_run())
    store.close()

    assert record.developer_id == "Test User"
    assert record.review_scope == "local-all-policies"
    assert record.ticket_key is None
    assert record.review_score == 95
    assert {evaluation.evaluation for evaluation in record.evaluations} == {
        "coding",
        "mr_structure",
    }


def test_migrates_existing_rows_with_review_score(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE review_runs (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                review_scope TEXT NOT NULL,
                branch_name TEXT NOT NULL,
                developer_id TEXT NOT NULL DEFAULT 'unknown',
                mr_id TEXT,
                commit_sha TEXT,
                policy_version INTEGER NOT NULL,
                risk TEXT NOT NULL,
                blocking_count INTEGER NOT NULL,
                high_count INTEGER NOT NULL,
                warning_count INTEGER NOT NULL,
                info_count INTEGER NOT NULL,
                changed_file_count INTEGER NOT NULL,
                changed_line_count INTEGER NOT NULL,
                generated_review_report TEXT NOT NULL
            );

            INSERT INTO review_runs (
                timestamp,
                review_scope,
                branch_name,
                developer_id,
                mr_id,
                commit_sha,
                policy_version,
                risk,
                blocking_count,
                high_count,
                warning_count,
                info_count,
                changed_file_count,
                changed_line_count,
                generated_review_report
            )
            VALUES (
                '2026-05-25T10:00:00+00:00',
                'gitlab-webhook',
                'refs/remotes/origin/main',
                'Jane Developer',
                '42',
                'abc123',
                1,
                'blocking',
                1,
                1,
                2,
                3,
                4,
                20,
                '## MR Guardian Review'
            );

            CREATE TABLE triggered_rules (
                review_id INTEGER NOT NULL,
                rule_id TEXT NOT NULL,
                FOREIGN KEY (review_id) REFERENCES review_runs(review_id) ON DELETE CASCADE
            );
            """
        )

    store = ReviewHistoryStore(database_path)
    migrated_run = store.review_run(1)
    store.close()

    assert migrated_run is not None
    assert migrated_run.ticket_key is None
    assert migrated_run.review_score == 37
    assert migrated_run.llm_summary is None
    assert migrated_run.developer_profile is None


def test_stores_triggered_rule_ids(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(triggered_rule_ids=["PYTHON-PRINT-001", "CSHARP-DEBUG-001"])
    )
    store.close()

    assert record.triggered_rule_ids == ["PYTHON-PRINT-001", "CSHARP-DEBUG-001"]


def test_stores_structured_findings(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(
            findings=[
                Finding(
                    rule_id="PYTHON-PRINT-001",
                    severity="warning",
                    message="print calls should be replaced with logging.",
                    source="python-policy.yml#PYTHON-PRINT-001",
                    evaluation="coding",
                    rule_type="deterministic",
                    file_path=Path("mr_guardian/example.py"),
                    line_number=4,
                )
            ]
        )
    )
    found_run = store.review_run(record.review_id)
    store.close()

    assert found_run is not None
    assert len(found_run.findings) == 1
    assert found_run.findings[0].rule_id == "PYTHON-PRINT-001"
    assert found_run.findings[0].file_path == Path("mr_guardian/example.py")
    assert found_run.findings[0].line_number == 4


def test_stores_policy_summaries(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(
            policy_summaries=[
                ReviewPolicySummary(
                    policy_path="sources/yaml/python-policy.yml",
                    policy_version=1,
                    enabled_rule_count=2,
                    disabled_rule_count=1,
                )
            ]
        )
    )
    found_run = store.review_run(record.review_id)
    store.close()

    assert found_run is not None
    assert len(found_run.policy_summaries) == 1
    assert found_run.policy_summaries[0].policy_path == "sources/yaml/python-policy.yml"
    assert found_run.policy_summaries[0].enabled_rule_count == 2
    assert found_run.policy_summaries[0].disabled_rule_count == 1


def test_stores_ticket_key_and_review_score(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(
            ticket_key="TK-234",
            triggered_rule_ids=["PYTHON-PRINT-001", "CSHARP-DEBUG-001"],
        )
    )
    store.close()

    assert record.ticket_key == "TK-234"
    assert record.review_score == 90


def test_stores_review_finality_flag(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    stored = store.store_review_run(
        make_review_run(ticket_key="TK-234", is_final=True)
    )
    found = store.review_run(stored.review_id)
    store.close()

    assert stored.is_final is True
    assert found is not None
    assert found.is_final is True


def test_sets_review_finality_and_clears_other_final_ticket_reviews(
    tmp_path: Path,
) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    first = store.store_review_run(make_review_run(ticket_key="TK-234", is_final=True))
    second = store.store_review_run(make_review_run(ticket_key="TK-234"))
    other_ticket = store.store_review_run(
        make_review_run(ticket_key="TK-999", is_final=True)
    )

    updated, cleared_review_ids = store.set_review_finality(
        review_id=second.review_id,
        is_final=True,
    )
    first_after = store.review_run(first.review_id)
    other_after = store.review_run(other_ticket.review_id)
    store.close()

    assert updated.review_id == second.review_id
    assert updated.is_final is True
    assert cleared_review_ids == [first.review_id]
    assert first_after is not None
    assert first_after.is_final is False
    assert other_after is not None
    assert other_after.is_final is True


def test_sets_review_finality_for_unlinked_review_without_clearing_other_reviews(
    tmp_path: Path,
) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    first = store.store_review_run(make_review_run(ticket_key=None, is_final=True))
    second = store.store_review_run(make_review_run(ticket_key=None))

    updated, cleared_review_ids = store.set_review_finality(
        review_id=second.review_id,
        is_final=True,
    )
    first_after = store.review_run(first.review_id)
    store.close()

    assert updated.is_final is True
    assert cleared_review_ids == []
    assert first_after is not None
    assert first_after.is_final is True


def test_unsets_review_finality(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    stored = store.store_review_run(make_review_run(ticket_key="TK-234", is_final=True))

    updated, cleared_review_ids = store.set_review_finality(
        review_id=stored.review_id,
        is_final=False,
    )
    store.close()

    assert updated.is_final is False
    assert cleared_review_ids == []


def test_setting_review_finality_for_missing_review_raises_key_error(
    tmp_path: Path,
) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    try:
        with pytest.raises(KeyError, match="Review 999 was not found."):
            store.set_review_finality(review_id=999, is_final=True)
    finally:
        store.close()


def test_stores_llm_rule_metrics(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(
            llm_metrics=[
                LlmRuleMetric(
                    rule_id="PYTHON-DESIGN-LLM-001",
                    provider="openai",
                    model="gpt-4.1-mini",
                    status="succeeded",
                    duration_ms=1420,
                    input_tokens=1200,
                    output_tokens=80,
                    total_tokens=1280,
                ),
                LlmRuleMetric(
                    rule_id="AI-CODE-LLM-001",
                    provider="openai",
                    model="gpt-4.1-mini",
                    status="rate_limited",
                    duration_ms=380,
                    error_message="LLM provider rate limit reached.",
                ),
            ]
        )
    )
    found_run = store.review_run(record.review_id)
    store.close()

    assert found_run is not None
    assert found_run.llm_metrics[0].rule_id == "PYTHON-DESIGN-LLM-001"
    assert found_run.llm_metrics[0].input_tokens == 1200
    assert found_run.llm_metrics[0].total_tokens == 1280
    assert found_run.llm_metrics[1].status == "rate_limited"
    assert found_run.llm_metrics[1].input_tokens is None
    assert found_run.llm_metrics[1].error_message == "LLM provider rate limit reached."


def test_stores_llm_review_summary(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(
            llm_summary=LlmReviewSummary(
                status="succeeded",
                provider="openai",
                model="gpt-4.1-mini",
                duration_ms=820,
                text="Review summary.",
                score=78,
                input_tokens=300,
                output_tokens=40,
                total_tokens=340,
            )
        )
    )
    found_run = store.review_run(record.review_id)
    store.close()

    assert found_run is not None
    assert found_run.llm_summary is not None
    assert found_run.llm_summary.status == "succeeded"
    assert found_run.llm_summary.provider == "openai"
    assert found_run.llm_summary.model == "gpt-4.1-mini"
    assert found_run.llm_summary.duration_ms == 820
    assert found_run.llm_summary.text == "Review summary."
    assert found_run.llm_summary.score == 78
    assert found_run.llm_summary.input_tokens == 300
    assert found_run.llm_summary.output_tokens == 40
    assert found_run.llm_summary.total_tokens == 340


def test_stores_failed_llm_review_summary(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(
            llm_summary=LlmReviewSummary(
                status="failed",
                provider="openai",
                model="gpt-4.1-mini",
                duration_ms=120,
                error_message="provider unavailable",
            )
        )
    )
    found_run = store.review_run(record.review_id)
    store.close()

    assert found_run is not None
    assert found_run.llm_summary is not None
    assert found_run.llm_summary.status == "failed"
    assert found_run.llm_summary.text is None
    assert found_run.llm_summary.score is None
    assert found_run.llm_summary.error_message == "provider unavailable"


def test_stores_developer_profile_snapshot(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(
            developer_profile=LlmDeveloperProfile(
                status="succeeded",
                provider="openai",
                model="gpt-4.1-mini",
                duration_ms=950,
                lookback_days=30,
                text="Jane is improving review readiness across recent tickets.",
                input_tokens=500,
                output_tokens=60,
                total_tokens=560,
            )
        )
    )
    found_run = store.review_run(record.review_id)
    store.close()

    assert found_run is not None
    assert found_run.developer_profile is not None
    assert found_run.developer_profile.status == "succeeded"
    assert found_run.developer_profile.provider == "openai"
    assert found_run.developer_profile.model == "gpt-4.1-mini"
    assert found_run.developer_profile.duration_ms == 950
    assert found_run.developer_profile.lookback_days == 30
    assert (
        found_run.developer_profile.text
        == "Jane is improving review readiness across recent tickets."
    )
    assert found_run.developer_profile.total_tokens == 560


def test_updates_developer_profile_snapshot(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    record = store.store_review_run(make_review_run())

    updated = store.update_developer_profile(
        review_id=record.review_id,
        developer_profile=LlmDeveloperProfile(
            status="failed",
            provider="openai",
            model="gpt-4.1-mini",
            duration_ms=100,
            lookback_days=14,
            error_message="provider unavailable",
        ),
    )
    store.close()

    assert updated.developer_profile is not None
    assert updated.developer_profile.status == "failed"
    assert updated.developer_profile.text is None
    assert updated.developer_profile.lookback_days == 14
    assert updated.developer_profile.error_message == "provider unavailable"


def test_stores_evaluation_summaries(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(
            evaluations=[
                ReviewEvaluation(
                    evaluation="coding",
                    risk="warning",
                    counts=FindingCounts(warning=2),
                    triggered_rule_ids=["PYTHON-PRINT-001", "CSHARP-DEBUG-001"],
                ),
                ReviewEvaluation(
                    evaluation="mr_structure",
                    risk="high",
                    counts=FindingCounts(high=1),
                    triggered_rule_ids=["SIZE-FILES-001"],
                ),
            ]
        )
    )
    found_run = store.review_run(record.review_id)
    store.close()

    assert found_run is not None
    assert found_run.evaluations[0].evaluation == "coding"
    assert found_run.evaluations[0].risk == "warning"
    assert found_run.evaluations[0].counts.warning == 2
    assert found_run.evaluations[0].triggered_rule_ids == [
        "PYTHON-PRINT-001",
        "CSHARP-DEBUG-001",
    ]
    assert found_run.evaluations[1].evaluation == "mr_structure"
    assert found_run.evaluations[1].risk == "high"
    assert found_run.evaluations[1].triggered_rule_ids == ["SIZE-FILES-001"]


def test_reads_recent_review_runs(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    old_timestamp = datetime(2026, 5, 21, tzinfo=timezone.utc)
    new_timestamp = old_timestamp + timedelta(days=1)

    store.store_review_run(make_review_run(branch_name="old", timestamp=old_timestamp))
    store.store_review_run(make_review_run(branch_name="new", timestamp=new_timestamp))

    recent_runs = store.recent_review_runs(limit=1)
    store.close()

    assert len(recent_runs) == 1
    assert recent_runs[0].branch_name == "new"


def test_reads_review_runs_between_timestamps(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    start = datetime(2026, 5, 20, tzinfo=timezone.utc)
    inside = start + timedelta(days=1)
    outside = start - timedelta(days=1)
    store.store_review_run(make_review_run(branch_name="outside", timestamp=outside))
    expected = store.store_review_run(make_review_run(branch_name="inside", timestamp=inside))

    runs = store.review_runs_between(
        start_at=start,
        end_at=start + timedelta(days=2),
    )
    store.close()

    assert [run.review_id for run in runs] == [expected.review_id]


def test_reads_review_runs_for_developer_in_time_window(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    start = datetime(2026, 5, 20, tzinfo=timezone.utc)
    inside = start + timedelta(days=1)
    outside = start - timedelta(days=1)
    store.store_review_run(
        make_review_run(developer_id="Jane Developer", timestamp=outside)
    )
    expected = store.store_review_run(
        make_review_run(
            developer_id="Jane Developer",
            ticket_key="TK-234",
            timestamp=inside,
        )
    )
    store.store_review_run(
        make_review_run(developer_id="Other Developer", timestamp=inside)
    )

    runs = store.review_runs_for_developer(
        developer_id="Jane Developer",
        start_at=start,
        end_at=start + timedelta(days=2),
    )
    store.close()

    assert [run.review_id for run in runs] == [expected.review_id]


def test_reads_developer_activity_sorted_by_latest_review(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    old_timestamp = datetime(2026, 5, 21, tzinfo=timezone.utc)
    new_timestamp = old_timestamp + timedelta(days=1)
    store.store_review_run(
        make_review_run(developer_id="Older Developer", timestamp=old_timestamp)
    )
    store.store_review_run(
        make_review_run(developer_id="Recent Developer", timestamp=new_timestamp)
    )

    activity = store.developer_activity()
    store.close()

    assert [developer.developer_id for developer in activity] == [
        "Recent Developer",
        "Older Developer",
    ]
    assert activity[0].last_review_at == new_timestamp
    assert activity[0].review_request_count == 1
    assert activity[0].average_score == 95


def test_reads_review_run_by_id(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    stored_run = store.store_review_run(make_review_run())
    found_run = store.review_run(stored_run.review_id)
    missing_run = store.review_run(999)
    store.close()

    assert found_run is not None
    assert found_run.review_id == stored_run.review_id
    assert found_run.generated_review_report == "## MR Guardian Review\n"
    assert missing_run is None


def test_deletes_one_review_run_and_dependent_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    store = ReviewHistoryStore(database_path)
    first = store.store_review_run(
        make_review_run(
            triggered_rule_ids=["PYTHON-PRINT-001"],
            findings=[
                Finding(
                    rule_id="PYTHON-PRINT-001",
                    severity="warning",
                    message="print calls should be replaced with logging.",
                    source="python-policy.yml#PYTHON-PRINT-001",
                    evaluation="coding",
                    rule_type="deterministic",
                )
            ],
            policy_summaries=[
                ReviewPolicySummary(
                    policy_path="sources/yaml/python-policy.yml",
                    policy_version=1,
                    enabled_rule_count=2,
                    disabled_rule_count=0,
                )
            ],
            llm_metrics=[
                LlmRuleMetric(
                    rule_id="PYTHON-DESIGN-LLM-001",
                    provider="openai",
                    model="gpt-4.1-mini",
                    status="succeeded",
                    duration_ms=100,
                )
            ],
        )
    )
    second = store.store_review_run(
        make_review_run(triggered_rule_ids=["CSHARP-DEBUG-001"])
    )

    deleted = store.delete_review_run(first.review_id)
    missing_deleted = store.review_run(first.review_id)
    remaining = store.review_run(second.review_id)
    stats = store.most_triggered_rules()
    store.close()

    assert deleted is True
    assert missing_deleted is None
    assert remaining is not None
    assert remaining.review_id == second.review_id
    assert [(stat.rule_id, stat.trigger_count) for stat in stats] == [
        ("CSHARP-DEBUG-001", 1)
    ]

    with sqlite3.connect(database_path) as connection:
        for table_name in (
            "triggered_rules",
            "review_findings",
            "review_policies",
            "review_llm_rule_metrics",
            "review_evaluations",
        ):
            row = connection.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE review_id = ?",
                (first.review_id,),
            ).fetchone()
            assert row is not None
            assert row[0] == 0


def test_delete_missing_review_run_returns_false(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    deleted = store.delete_review_run(999)
    store.close()

    assert deleted is False


def test_reads_most_triggered_rules(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    store.store_review_run(
        make_review_run(triggered_rule_ids=["PYTHON-PRINT-001", "CSHARP-DEBUG-001"])
    )
    store.store_review_run(make_review_run(triggered_rule_ids=["PYTHON-PRINT-001"]))

    stats = store.most_triggered_rules()
    store.close()

    assert [(stat.rule_id, stat.trigger_count) for stat in stats] == [
        ("PYTHON-PRINT-001", 2),
        ("CSHARP-DEBUG-001", 1),
    ]


def test_supports_in_memory_sqlite() -> None:
    store = ReviewHistoryStore(":memory:")

    record = store.store_review_run(make_review_run())
    recent_runs = store.recent_review_runs()
    store.close()

    assert record.review_id == 1
    assert len(recent_runs) == 1


def test_handles_empty_history_cleanly() -> None:
    store = ReviewHistoryStore(":memory:")

    recent_runs = store.recent_review_runs()
    stats = store.most_triggered_rules()
    store.close()

    assert recent_runs == []
    assert stats == []


def test_clears_review_history() -> None:
    store = ReviewHistoryStore(":memory:")
    store.store_review_run(make_review_run(triggered_rule_ids=["PYTHON-PRINT-001"]))
    store.store_review_run(make_review_run(triggered_rule_ids=["CSHARP-DEBUG-001"]))

    removed_run_count = store.clear_history()
    recent_runs = store.recent_review_runs()
    stats = store.most_triggered_rules()
    store.close()

    assert removed_run_count == 2
    assert recent_runs == []
    assert stats == []


def test_reads_empty_eta_note() -> None:
    store = ReviewHistoryStore(":memory:")

    note = store.get_eta_note()
    store.close()

    assert note is None


def test_sets_and_reads_eta_note(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    stored = store.set_eta_note(
        message="Team expects the milestone to be merge-ready this Friday.",
        target_date=date(2026, 6, 5),
    )
    found = store.get_eta_note()
    store.close()

    assert stored.message == "Team expects the milestone to be merge-ready this Friday."
    assert stored.target_date == date(2026, 6, 5)
    assert found == stored


def test_eta_note_target_date_is_optional() -> None:
    store = ReviewHistoryStore(":memory:")

    note = store.set_eta_note(message="No date is committed yet.")
    found = store.get_eta_note()
    store.close()

    assert note.target_date is None
    assert found is not None
    assert found.target_date is None


def test_eta_note_overwrites_singleton_row(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    store = ReviewHistoryStore(database_path)

    first = store.set_eta_note(
        message="First ETA.",
        target_date=date(2026, 6, 5),
    )
    second = store.set_eta_note(message="Second ETA.")
    found = store.get_eta_note()
    store.close()

    assert first.updated_at <= second.updated_at
    assert found == second
    assert second.message == "Second ETA."
    assert second.target_date is None

    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM dashboard_eta_note").fetchone()
    assert row is not None
    assert row[0] == 1


def test_eta_note_rejects_empty_message() -> None:
    store = ReviewHistoryStore(":memory:")

    try:
        with pytest.raises(ValueError, match="ETA note message must not be empty."):
            store.set_eta_note(message="   ")
    finally:
        store.close()
