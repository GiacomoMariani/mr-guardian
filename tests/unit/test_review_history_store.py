import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.models.history import ReviewRunCreate
from mr_guardian.models.review import FindingCounts, LlmRuleMetric, ReviewEvaluation
from mr_guardian.storage import ReviewHistoryStore


def make_review_run(
    *,
    review_scope: str = "local-all-policies",
    branch_name: str = "feature/reporting",
    developer_id: str = "Test User",
    ticket_key: str | None = None,
    triggered_rule_ids: list[str] | None = None,
    llm_metrics: list[LlmRuleMetric] | None = None,
    evaluations: list[ReviewEvaluation] | None = None,
    timestamp: datetime | None = None,
) -> ReviewRunCreate:
    rule_ids = triggered_rule_ids or ["PYTHON-PRINT-001"]
    return ReviewRunCreate(
        review_scope=review_scope,
        branch_name=branch_name,
        developer_id=developer_id,
        ticket_key=ticket_key,
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
        "review_llm_rule_metrics",
        "review_evaluations",
        "review_evaluation_triggered_rules",
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
    assert record.evaluations[0].evaluation == "coding"
    assert record.evaluations[0].risk == "warning"
    assert record.evaluations[0].triggered_rule_ids == ["PYTHON-PRINT-001"]
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


def test_stores_triggered_rule_ids(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(triggered_rule_ids=["PYTHON-PRINT-001", "CSHARP-DEBUG-001"])
    )
    store.close()

    assert record.triggered_rule_ids == ["PYTHON-PRINT-001", "CSHARP-DEBUG-001"]


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
