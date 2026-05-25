"""SQLite-backed review history storage."""

import sqlite3
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from mr_guardian.models.history import ReviewRunCreate, ReviewRunRecord, TriggeredRuleStat

SCHEMA = """
CREATE TABLE IF NOT EXISTS review_runs (
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

CREATE TABLE IF NOT EXISTS triggered_rules (
    review_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    FOREIGN KEY (review_id) REFERENCES review_runs(review_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_review_runs_timestamp
ON review_runs(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_triggered_rules_rule_id
ON triggered_rules(rule_id);
"""


class ReviewHistoryStore:
    """SQLite adapter for persisted review history."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = database_path
        self._connection = self._connect(database_path)

    def initialize_schema(self) -> None:
        """Create storage tables when they do not already exist."""
        self._connection.executescript(SCHEMA)
        self._connection.commit()

    def store_review_run(self, run: ReviewRunCreate) -> ReviewRunRecord:
        """Persist one review run and its triggered rule IDs."""
        self.initialize_schema()
        timestamp = run.timestamp or datetime.now(timezone.utc)
        cursor = self._connection.execute(
            """
            INSERT INTO review_runs (
                timestamp,
                project_name,
                branch_name,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp.isoformat(),
                run.project_name,
                run.branch_name,
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
            ),
        )
        if cursor.lastrowid is None:
            msg = "SQLite did not return a review ID for the inserted run."
            raise RuntimeError(msg)
        review_id = cursor.lastrowid
        self._insert_triggered_rules(review_id, run.triggered_rule_ids)
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
            project_name=str(row["project_name"]),
            branch_name=str(row["branch_name"]),
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


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
