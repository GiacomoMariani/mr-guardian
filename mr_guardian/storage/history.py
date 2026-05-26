"""SQLite-backed review history storage."""

import sqlite3
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from mr_guardian.models.history import ReviewRunCreate, ReviewRunRecord, TriggeredRuleStat
from mr_guardian.models.review import LlmRuleMetric

SCHEMA = """
CREATE TABLE IF NOT EXISTS review_runs (
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

CREATE TABLE IF NOT EXISTS triggered_rules (
    review_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    FOREIGN KEY (review_id) REFERENCES review_runs(review_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS review_llm_rule_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    error_message TEXT,
    FOREIGN KEY (review_id) REFERENCES review_runs(review_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_review_runs_timestamp
ON review_runs(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_triggered_rules_rule_id
ON triggered_rules(rule_id);

CREATE INDEX IF NOT EXISTS idx_review_llm_rule_metrics_review_id
ON review_llm_rule_metrics(review_id);
"""


class ReviewHistoryStore:
    """SQLite adapter for persisted review history."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = database_path
        self._connection = self._connect(database_path)

    def initialize_schema(self) -> None:
        """Create storage tables when they do not already exist."""
        self._connection.executescript(SCHEMA)
        self._ensure_schema_columns()
        self._connection.commit()

    def store_review_run(self, run: ReviewRunCreate) -> ReviewRunRecord:
        """Persist one review run and its triggered rule IDs."""
        self.initialize_schema()
        timestamp = run.timestamp or datetime.now(timezone.utc)
        columns = self._review_run_columns()
        insert_columns = [
            "timestamp",
            "review_scope",
            "branch_name",
            "developer_id",
            "mr_id",
            "commit_sha",
            "policy_version",
            "risk",
            "blocking_count",
            "high_count",
            "warning_count",
            "info_count",
            "changed_file_count",
            "changed_line_count",
            "generated_review_report",
        ]
        values = [
            timestamp.isoformat(),
            run.review_scope,
            run.branch_name,
            run.developer_id,
            run.mr_id,
            run.commit_sha,
            run.policy_version,
            run.risk,
            run.blocking_count,
            run.high_count,
            run.warning_count,
            run.info_count,
            run.changed_file_count,
            run.changed_line_count,
            run.generated_review_report,
        ]
        if "project_name" in columns:
            insert_columns.insert(2, "project_name")
            values.insert(2, run.review_scope)

        placeholders = ", ".join("?" for _ in insert_columns)
        cursor = self._connection.execute(
            f"""
            INSERT INTO review_runs ({", ".join(insert_columns)})
            VALUES ({placeholders})
            """,
            values,
        )
        if cursor.lastrowid is None:
            msg = "SQLite did not return a review ID for the inserted run."
            raise RuntimeError(msg)
        review_id = cursor.lastrowid
        self._insert_triggered_rules(review_id, run.triggered_rule_ids)
        self._insert_llm_metrics(review_id, run.llm_metrics)
        self._connection.commit()
        return self._record_for_review_id(review_id)

    def recent_review_runs(self, *, limit: int = 20) -> list[ReviewRunRecord]:
        """Return recent review runs newest first."""
        self.initialize_schema()
        rows = self._connection.execute(
            """
            SELECT *
            FROM review_runs
            ORDER BY timestamp DESC, review_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def review_run(self, review_id: int) -> ReviewRunRecord | None:
        """Return one review run by ID, if it exists."""
        self.initialize_schema()
        row = self._connection.execute(
            """
            SELECT *
            FROM review_runs
            WHERE review_id = ?
            """,
            (review_id,),
        ).fetchone()
        if row is None:
            return None
        return self._record_from_row(row)

    def most_triggered_rules(self, *, limit: int = 10) -> list[TriggeredRuleStat]:
        """Return rule IDs ordered by trigger frequency."""
        self.initialize_schema()
        rows = self._connection.execute(
            """
            SELECT rule_id, COUNT(*) AS trigger_count
            FROM triggered_rules
            GROUP BY rule_id
            ORDER BY trigger_count DESC, rule_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            TriggeredRuleStat(
                rule_id=str(row["rule_id"]),
                trigger_count=int(row["trigger_count"]),
            )
            for row in rows
        ]

    def clear_history(self) -> int:
        """Delete all stored review runs and return the removed run count."""
        self.initialize_schema()
        row = self._connection.execute("SELECT COUNT(*) AS run_count FROM review_runs").fetchone()
        run_count = int(row["run_count"]) if row is not None else 0
        self._connection.execute("DELETE FROM triggered_rules")
        self._connection.execute("DELETE FROM review_llm_rule_metrics")
        self._connection.execute("DELETE FROM review_runs")
        self._connection.commit()
        return run_count

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._connection.close()

    @staticmethod
    def _connect(database_path: str | Path) -> sqlite3.Connection:
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _insert_triggered_rules(self, review_id: int, rule_ids: Sequence[str]) -> None:
        self._connection.executemany(
            """
            INSERT INTO triggered_rules (review_id, rule_id)
            VALUES (?, ?)
            """,
            [(review_id, rule_id) for rule_id in rule_ids],
        )

    def _insert_llm_metrics(self, review_id: int, metrics: Sequence[LlmRuleMetric]) -> None:
        self._connection.executemany(
            """
            INSERT INTO review_llm_rule_metrics (
                review_id,
                rule_id,
                provider,
                model,
                status,
                duration_ms,
                input_tokens,
                output_tokens,
                total_tokens,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    review_id,
                    metric.rule_id,
                    metric.provider,
                    metric.model,
                    metric.status,
                    metric.duration_ms,
                    metric.input_tokens,
                    metric.output_tokens,
                    metric.total_tokens,
                    metric.error_message,
                )
                for metric in metrics
            ],
        )

    def _record_for_review_id(self, review_id: int) -> ReviewRunRecord:
        row = self._connection.execute(
            """
            SELECT *
            FROM review_runs
            WHERE review_id = ?
            """,
            (review_id,),
        ).fetchone()
        if row is None:
            msg = f"Stored review run {review_id} could not be read."
            raise RuntimeError(msg)
        return self._record_from_row(row)

    def _record_from_row(self, row: sqlite3.Row) -> ReviewRunRecord:
        review_id = int(row["review_id"])
        return ReviewRunRecord(
            review_id=review_id,
            timestamp=datetime.fromisoformat(str(row["timestamp"])),
            review_scope=str(row["review_scope"]),
            branch_name=str(row["branch_name"]),
            developer_id=str(row["developer_id"]),
            mr_id=_optional_str(row["mr_id"]),
            commit_sha=_optional_str(row["commit_sha"]),
            policy_version=int(row["policy_version"]),
            risk=row["risk"],
            blocking_count=int(row["blocking_count"]),
            high_count=int(row["high_count"]),
            warning_count=int(row["warning_count"]),
            info_count=int(row["info_count"]),
            changed_file_count=int(row["changed_file_count"]),
            changed_line_count=int(row["changed_line_count"]),
            triggered_rule_ids=self._triggered_rule_ids(review_id),
            llm_metrics=self._llm_metrics(review_id),
            generated_review_report=str(row["generated_review_report"]),
        )

    def _triggered_rule_ids(self, review_id: int) -> list[str]:
        rows = self._connection.execute(
            """
            SELECT rule_id
            FROM triggered_rules
            WHERE review_id = ?
            ORDER BY rowid ASC
            """,
            (review_id,),
        ).fetchall()
        return [str(row["rule_id"]) for row in rows]

    def _llm_metrics(self, review_id: int) -> list[LlmRuleMetric]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM review_llm_rule_metrics
            WHERE review_id = ?
            ORDER BY id ASC
            """,
            (review_id,),
        ).fetchall()
        return [
            LlmRuleMetric(
                rule_id=str(row["rule_id"]),
                provider=str(row["provider"]),
                model=str(row["model"]),
                status=row["status"],
                duration_ms=int(row["duration_ms"]),
                input_tokens=_optional_int(row["input_tokens"]),
                output_tokens=_optional_int(row["output_tokens"]),
                total_tokens=_optional_int(row["total_tokens"]),
                error_message=_optional_str(row["error_message"]),
            )
            for row in rows
        ]

    def _ensure_schema_columns(self) -> None:
        columns = self._review_run_columns()
        if "developer_id" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs "
                "ADD COLUMN developer_id TEXT NOT NULL DEFAULT 'unknown'"
            )
        if "review_scope" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs "
                "ADD COLUMN review_scope TEXT NOT NULL DEFAULT 'local-all-policies'"
            )
            if "project_name" in columns:
                self._connection.execute(
                    "UPDATE review_runs SET review_scope = project_name "
                    "WHERE review_scope = 'local-all-policies'"
                )

    def _review_run_columns(self) -> set[str]:
        return {
            str(row["name"])
            for row in self._connection.execute("PRAGMA table_info(review_runs)").fetchall()
        }


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    msg = f"Expected integer-compatible SQLite value, got {type(value).__name__}."
    raise TypeError(msg)
