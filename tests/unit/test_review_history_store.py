import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mr_guardian.models.history import ReviewRunCreate
from mr_guardian.storage import ReviewHistoryStore


def make_review_run(
    *,
    review_scope: str = "local-all-policies",
    branch_name: str = "feature/reporting",
    developer_id: str = "Test User",
    triggered_rule_ids: list[str] | None = None,
    timestamp: datetime | None = None,
) -> ReviewRunCreate:
    rule_ids = triggered_rule_ids or ["PYTHON-PRINT-001"]
    return ReviewRunCreate(
        review_scope=review_scope,
        branch_name=branch_name,
        developer_id=developer_id,
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

    assert {"review_runs", "triggered_rules"}.issubset(table_names(database_path))


def test_stores_review_run(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(make_review_run())
    store.close()

    assert record.review_id == 1
    assert record.review_scope == "local-all-policies"
    assert record.branch_name == "feature/reporting"
    assert record.developer_id == "Test User"
    assert record.mr_id == "42"
    assert record.commit_sha == "abc123"
    assert record.risk == "warning"
    assert record.warning_count == 1
    assert record.changed_file_count == 3
    assert record.changed_line_count == 12
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


def test_stores_triggered_rule_ids(tmp_path: Path) -> None:
    store = ReviewHistoryStore(tmp_path / "history.sqlite")

    record = store.store_review_run(
        make_review_run(triggered_rule_ids=["PYTHON-PRINT-001", "CSHARP-DEBUG-001"])
    )
    store.close()

    assert record.triggered_rule_ids == ["PYTHON-PRINT-001", "CSHARP-DEBUG-001"]


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
