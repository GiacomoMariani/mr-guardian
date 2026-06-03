"""SQLite-backed review history storage."""

import sqlite3
from collections.abc import Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import cast

from mr_guardian.core.review_score import calculate_review_score
from mr_guardian.models.history import (
    DashboardEtaNote,
    ReviewPolicySummary,
    ReviewRunCreate,
    ReviewRunRecord,
    TriggeredRuleStat,
)
from mr_guardian.models.performance import DeveloperActivity
from mr_guardian.models.policy import EvaluationDimension, RuleType, Severity
from mr_guardian.models.review import (
    Finding,
    FindingCounts,
    LlmDeveloperProfile,
    LlmReviewSummary,
    LlmRuleMetric,
    LlmSummaryStatus,
    ReviewEvaluation,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS review_runs (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    review_scope TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    developer_id TEXT NOT NULL DEFAULT 'unknown',
    ticket_key TEXT,
    is_final INTEGER NOT NULL DEFAULT 0,
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
    review_score INTEGER NOT NULL DEFAULT 100,
    llm_summary TEXT,
    llm_summary_score INTEGER,
    llm_summary_status TEXT,
    llm_summary_provider TEXT,
    llm_summary_model TEXT,
    llm_summary_duration_ms INTEGER,
    llm_summary_input_tokens INTEGER,
    llm_summary_output_tokens INTEGER,
    llm_summary_total_tokens INTEGER,
    llm_summary_error_message TEXT,
    developer_profile TEXT,
    developer_profile_status TEXT,
    developer_profile_provider TEXT,
    developer_profile_model TEXT,
    developer_profile_duration_ms INTEGER,
    developer_profile_input_tokens INTEGER,
    developer_profile_output_tokens INTEGER,
    developer_profile_total_tokens INTEGER,
    developer_profile_error_message TEXT,
    developer_profile_lookback_days INTEGER,
    generated_review_report TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS triggered_rules (
    review_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    FOREIGN KEY (review_id) REFERENCES review_runs(review_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS review_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    source TEXT NOT NULL,
    evaluation TEXT NOT NULL,
    rule_type TEXT,
    file_path TEXT,
    line_number INTEGER,
    FOREIGN KEY (review_id) REFERENCES review_runs(review_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS review_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    policy_path TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    enabled_rule_count INTEGER NOT NULL,
    disabled_rule_count INTEGER NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_review_findings_review_id
ON review_findings(review_id);

CREATE INDEX IF NOT EXISTS idx_review_policies_review_id
ON review_policies(review_id);

CREATE INDEX IF NOT EXISTS idx_review_llm_rule_metrics_review_id
ON review_llm_rule_metrics(review_id);

CREATE TABLE IF NOT EXISTS review_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    evaluation TEXT NOT NULL,
    risk TEXT NOT NULL,
    blocking_count INTEGER NOT NULL,
    high_count INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    info_count INTEGER NOT NULL,
    FOREIGN KEY (review_id) REFERENCES review_runs(review_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS review_evaluation_triggered_rules (
    review_evaluation_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    FOREIGN KEY (review_evaluation_id)
        REFERENCES review_evaluations(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_review_evaluations_review_id
ON review_evaluations(review_id);

CREATE INDEX IF NOT EXISTS idx_review_evaluation_triggered_rules_rule_id
ON review_evaluation_triggered_rules(rule_id);

CREATE TABLE IF NOT EXISTS dashboard_eta_note (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    message TEXT NOT NULL,
    target_date TEXT,
    updated_at TEXT NOT NULL
);
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
        self._ensure_schema_indexes()
        self._connection.commit()

    def store_review_run(self, run: ReviewRunCreate) -> ReviewRunRecord:
        """Persist one review run and its triggered rule IDs."""
        self.initialize_schema()
        timestamp = run.timestamp or datetime.now(timezone.utc)
        review_score = run.review_score
        if review_score is None:
            review_score = calculate_review_score(
                blocking_count=run.blocking_count,
                high_count=run.high_count,
                warning_count=run.warning_count,
                info_count=run.info_count,
            )
        columns = self._review_run_columns()
        insert_columns = [
            "timestamp",
            "review_scope",
            "branch_name",
            "developer_id",
            "ticket_key",
            "is_final",
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
            "review_score",
            "llm_summary",
            "llm_summary_score",
            "llm_summary_status",
            "llm_summary_provider",
            "llm_summary_model",
            "llm_summary_duration_ms",
            "llm_summary_input_tokens",
            "llm_summary_output_tokens",
            "llm_summary_total_tokens",
            "llm_summary_error_message",
            "developer_profile",
            "developer_profile_status",
            "developer_profile_provider",
            "developer_profile_model",
            "developer_profile_duration_ms",
            "developer_profile_input_tokens",
            "developer_profile_output_tokens",
            "developer_profile_total_tokens",
            "developer_profile_error_message",
            "developer_profile_lookback_days",
            "generated_review_report",
        ]
        llm_summary = run.llm_summary
        developer_profile = run.developer_profile
        values = [
            timestamp.isoformat(),
            run.review_scope,
            run.branch_name,
            run.developer_id,
            run.ticket_key,
            1 if run.is_final else 0,
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
            review_score,
            llm_summary.text if llm_summary is not None else None,
            llm_summary.score if llm_summary is not None else None,
            llm_summary.status if llm_summary is not None else None,
            llm_summary.provider if llm_summary is not None else None,
            llm_summary.model if llm_summary is not None else None,
            llm_summary.duration_ms if llm_summary is not None else None,
            llm_summary.input_tokens if llm_summary is not None else None,
            llm_summary.output_tokens if llm_summary is not None else None,
            llm_summary.total_tokens if llm_summary is not None else None,
            llm_summary.error_message if llm_summary is not None else None,
            developer_profile.text if developer_profile is not None else None,
            developer_profile.status if developer_profile is not None else None,
            developer_profile.provider if developer_profile is not None else None,
            developer_profile.model if developer_profile is not None else None,
            developer_profile.duration_ms if developer_profile is not None else None,
            developer_profile.input_tokens if developer_profile is not None else None,
            developer_profile.output_tokens if developer_profile is not None else None,
            developer_profile.total_tokens if developer_profile is not None else None,
            developer_profile.error_message if developer_profile is not None else None,
            developer_profile.lookback_days if developer_profile is not None else None,
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
        self._insert_findings(review_id, run.findings)
        self._insert_policy_summaries(review_id, run.policy_summaries)
        self._insert_evaluations(review_id, run.evaluations)
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

    def update_developer_profile(
        self,
        *,
        review_id: int,
        developer_profile: LlmDeveloperProfile,
    ) -> ReviewRunRecord:
        """Attach an LLM developer profile snapshot to a stored review run."""
        self.initialize_schema()
        self._connection.execute(
            """
            UPDATE review_runs
            SET developer_profile = ?,
                developer_profile_status = ?,
                developer_profile_provider = ?,
                developer_profile_model = ?,
                developer_profile_duration_ms = ?,
                developer_profile_input_tokens = ?,
                developer_profile_output_tokens = ?,
                developer_profile_total_tokens = ?,
                developer_profile_error_message = ?,
                developer_profile_lookback_days = ?
            WHERE review_id = ?
            """,
            (
                developer_profile.text,
                developer_profile.status,
                developer_profile.provider,
                developer_profile.model,
                developer_profile.duration_ms,
                developer_profile.input_tokens,
                developer_profile.output_tokens,
                developer_profile.total_tokens,
                developer_profile.error_message,
                developer_profile.lookback_days,
                review_id,
            ),
        )
        self._connection.commit()
        return self._record_for_review_id(review_id)

    def delete_review_run(self, review_id: int) -> bool:
        """Delete one review run and return whether a row was removed."""
        self.initialize_schema()
        cursor = self._connection.execute(
            """
            DELETE FROM review_runs
            WHERE review_id = ?
            """,
            (review_id,),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def get_eta_note(self) -> DashboardEtaNote | None:
        """Return the singleton dashboard ETA note, if one has been stored."""
        self.initialize_schema()
        row = self._connection.execute(
            """
            SELECT message, target_date, updated_at
            FROM dashboard_eta_note
            WHERE id = 1
            """
        ).fetchone()
        if row is None:
            return None
        return DashboardEtaNote(
            message=str(row["message"]),
            target_date=_optional_date(row["target_date"]),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    def set_eta_note(
        self,
        *,
        message: str,
        target_date: date | None = None,
    ) -> DashboardEtaNote:
        """Overwrite the singleton dashboard ETA note."""
        self.initialize_schema()
        clean_message = message.strip()
        if not clean_message:
            msg = "ETA note message must not be empty."
            raise ValueError(msg)

        updated_at = datetime.now(timezone.utc)
        self._connection.execute(
            """
            INSERT INTO dashboard_eta_note (
                id,
                message,
                target_date,
                updated_at
            )
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                message = excluded.message,
                target_date = excluded.target_date,
                updated_at = excluded.updated_at
            """,
            (
                clean_message,
                target_date.isoformat() if target_date is not None else None,
                updated_at.isoformat(),
            ),
        )
        self._connection.commit()
        return DashboardEtaNote(
            message=clean_message,
            target_date=target_date,
            updated_at=updated_at,
        )

    def set_review_finality(
        self,
        *,
        review_id: int,
        is_final: bool,
    ) -> tuple[ReviewRunRecord, list[int]]:
        """Set one review's finality flag and clear prior finals for the ticket."""
        self.initialize_schema()
        row = self._connection.execute(
            """
            SELECT review_id, ticket_key
            FROM review_runs
            WHERE review_id = ?
            """,
            (review_id,),
        ).fetchone()
        if row is None:
            msg = f"Review {review_id} was not found."
            raise KeyError(msg)

        cleared_review_ids: list[int] = []
        ticket_key = _optional_str(row["ticket_key"])
        if is_final and ticket_key is not None:
            cleared_rows = self._connection.execute(
                """
                SELECT review_id
                FROM review_runs
                WHERE ticket_key = ?
                  AND review_id != ?
                  AND is_final = 1
                ORDER BY review_id ASC
                """,
                (ticket_key, review_id),
            ).fetchall()
            cleared_review_ids = [
                int(cleared_row["review_id"])
                for cleared_row in cleared_rows
            ]
            self._connection.execute(
                """
                UPDATE review_runs
                SET is_final = 0
                WHERE ticket_key = ?
                  AND review_id != ?
                """,
                (ticket_key, review_id),
            )

        self._connection.execute(
            """
            UPDATE review_runs
            SET is_final = ?
            WHERE review_id = ?
            """,
            (1 if is_final else 0, review_id),
        )
        self._connection.commit()
        return self._record_for_review_id(review_id), cleared_review_ids

    def review_runs_between(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> list[ReviewRunRecord]:
        """Return review runs within a timestamp window."""
        self.initialize_schema()
        rows = self._connection.execute(
            """
            SELECT *
            FROM review_runs
            WHERE timestamp >= ?
              AND timestamp <= ?
            ORDER BY timestamp ASC, review_id ASC
            """,
            (start_at.isoformat(), end_at.isoformat()),
        ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def review_runs_for_developer(
        self,
        *,
        developer_id: str,
        start_at: datetime,
        end_at: datetime,
    ) -> list[ReviewRunRecord]:
        """Return review runs for one developer within a timestamp window."""
        self.initialize_schema()
        rows = self._connection.execute(
            """
            SELECT *
            FROM review_runs
            WHERE developer_id = ?
              AND timestamp >= ?
              AND timestamp <= ?
            ORDER BY timestamp ASC, review_id ASC
            """,
            (developer_id, start_at.isoformat(), end_at.isoformat()),
        ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def developer_activity(self) -> list[DeveloperActivity]:
        """Return developers ordered by most recent stored review."""
        self.initialize_schema()
        rows = self._connection.execute(
            """
            SELECT
                developer_id,
                MAX(timestamp) AS last_review_at,
                COUNT(*) AS review_request_count,
                AVG(review_score) AS average_score
            FROM review_runs
            GROUP BY developer_id
            ORDER BY last_review_at DESC, developer_id ASC
            """
        ).fetchall()
        return [
            DeveloperActivity(
                developer_id=str(row["developer_id"]),
                last_review_at=datetime.fromisoformat(str(row["last_review_at"])),
                review_request_count=int(row["review_request_count"]),
                average_score=_optional_float(row["average_score"]),
            )
            for row in rows
        ]

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
        self._connection.execute("DELETE FROM review_findings")
        self._connection.execute("DELETE FROM review_policies")
        self._connection.execute("DELETE FROM review_llm_rule_metrics")
        self._connection.execute("DELETE FROM review_evaluation_triggered_rules")
        self._connection.execute("DELETE FROM review_evaluations")
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

    def _insert_findings(self, review_id: int, findings: Sequence[Finding]) -> None:
        self._connection.executemany(
            """
            INSERT INTO review_findings (
                review_id,
                rule_id,
                severity,
                message,
                source,
                evaluation,
                rule_type,
                file_path,
                line_number
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    review_id,
                    finding.rule_id,
                    finding.severity,
                    finding.message,
                    finding.source,
                    finding.evaluation,
                    finding.rule_type,
                    finding.file_path.as_posix()
                    if finding.file_path is not None
                    else None,
                    finding.line_number,
                )
                for finding in findings
            ],
        )

    def _insert_policy_summaries(
        self,
        review_id: int,
        policy_summaries: Sequence[ReviewPolicySummary],
    ) -> None:
        self._connection.executemany(
            """
            INSERT INTO review_policies (
                review_id,
                policy_path,
                policy_version,
                enabled_rule_count,
                disabled_rule_count
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    review_id,
                    policy.policy_path,
                    policy.policy_version,
                    policy.enabled_rule_count,
                    policy.disabled_rule_count,
                )
                for policy in policy_summaries
            ],
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

    def _insert_evaluations(
        self,
        review_id: int,
        evaluations: Sequence[ReviewEvaluation],
    ) -> None:
        for evaluation in evaluations:
            cursor = self._connection.execute(
                """
                INSERT INTO review_evaluations (
                    review_id,
                    evaluation,
                    risk,
                    blocking_count,
                    high_count,
                    warning_count,
                    info_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    evaluation.evaluation,
                    evaluation.risk,
                    evaluation.counts.blocking,
                    evaluation.counts.high,
                    evaluation.counts.warning,
                    evaluation.counts.info,
                ),
            )
            if cursor.lastrowid is None:
                msg = "SQLite did not return an evaluation ID for the inserted summary."
                raise RuntimeError(msg)
            self._insert_evaluation_triggered_rules(
                cursor.lastrowid,
                evaluation.triggered_rule_ids,
            )

    def _insert_evaluation_triggered_rules(
        self,
        review_evaluation_id: int,
        rule_ids: Sequence[str],
    ) -> None:
        self._connection.executemany(
            """
            INSERT INTO review_evaluation_triggered_rules (review_evaluation_id, rule_id)
            VALUES (?, ?)
            """,
            [(review_evaluation_id, rule_id) for rule_id in rule_ids],
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
            ticket_key=_optional_str(row["ticket_key"]),
            is_final=bool(int(row["is_final"])),
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
            review_score=int(row["review_score"]),
            findings=self._findings(review_id),
            triggered_rule_ids=self._triggered_rule_ids(review_id),
            evaluations=self._evaluations(review_id),
            llm_metrics=self._llm_metrics(review_id),
            llm_summary=_llm_summary_from_row(row),
            developer_profile=_developer_profile_from_row(row),
            policy_summaries=self._policy_summaries(review_id),
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

    def _findings(self, review_id: int) -> list[Finding]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM review_findings
            WHERE review_id = ?
            ORDER BY id ASC
            """,
            (review_id,),
        ).fetchall()
        return [
            Finding(
                rule_id=str(row["rule_id"]),
                severity=cast(Severity, row["severity"]),
                message=str(row["message"]),
                source=str(row["source"]),
                evaluation=cast(EvaluationDimension, row["evaluation"]),
                rule_type=cast(RuleType | None, _optional_str(row["rule_type"])),
                file_path=_optional_path(row["file_path"]),
                line_number=_optional_int(row["line_number"]),
            )
            for row in rows
        ]

    def _policy_summaries(self, review_id: int) -> list[ReviewPolicySummary]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM review_policies
            WHERE review_id = ?
            ORDER BY id ASC
            """,
            (review_id,),
        ).fetchall()
        return [
            ReviewPolicySummary(
                policy_path=str(row["policy_path"]),
                policy_version=int(row["policy_version"]),
                enabled_rule_count=int(row["enabled_rule_count"]),
                disabled_rule_count=int(row["disabled_rule_count"]),
            )
            for row in rows
        ]

    def _evaluations(self, review_id: int) -> list[ReviewEvaluation]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM review_evaluations
            WHERE review_id = ?
            ORDER BY id ASC
            """,
            (review_id,),
        ).fetchall()
        return [
            ReviewEvaluation(
                evaluation=row["evaluation"],
                risk=row["risk"],
                counts=FindingCounts(
                    blocking=int(row["blocking_count"]),
                    high=int(row["high_count"]),
                    warning=int(row["warning_count"]),
                    info=int(row["info_count"]),
                ),
                triggered_rule_ids=self._evaluation_triggered_rule_ids(int(row["id"])),
            )
            for row in rows
        ]

    def _evaluation_triggered_rule_ids(self, review_evaluation_id: int) -> list[str]:
        rows = self._connection.execute(
            """
            SELECT rule_id
            FROM review_evaluation_triggered_rules
            WHERE review_evaluation_id = ?
            ORDER BY rowid ASC
            """,
            (review_evaluation_id,),
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
        if "ticket_key" not in columns:
            self._connection.execute("ALTER TABLE review_runs ADD COLUMN ticket_key TEXT")
        if "is_final" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs "
                "ADD COLUMN is_final INTEGER NOT NULL DEFAULT 0"
            )
        if "review_score" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs "
                "ADD COLUMN review_score INTEGER NOT NULL DEFAULT 100"
            )
            self._connection.execute(
                """
                UPDATE review_runs
                SET review_score = CASE
                    WHEN (
                        100
                        - (blocking_count * 35)
                        - (high_count * 15)
                        - (warning_count * 5)
                        - info_count
                    ) < 0 THEN 0
                    WHEN (
                        100
                        - (blocking_count * 35)
                        - (high_count * 15)
                        - (warning_count * 5)
                        - info_count
                    ) > 100 THEN 100
                    ELSE (
                        100
                        - (blocking_count * 35)
                        - (high_count * 15)
                        - (warning_count * 5)
                        - info_count
                    )
                END
                """
            )
        if "llm_summary" not in columns:
            self._connection.execute("ALTER TABLE review_runs ADD COLUMN llm_summary TEXT")
        if "llm_summary_score" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN llm_summary_score INTEGER"
            )
        if "llm_summary_status" not in columns:
            self._connection.execute("ALTER TABLE review_runs ADD COLUMN llm_summary_status TEXT")
        if "llm_summary_provider" not in columns:
            self._connection.execute("ALTER TABLE review_runs ADD COLUMN llm_summary_provider TEXT")
        if "llm_summary_model" not in columns:
            self._connection.execute("ALTER TABLE review_runs ADD COLUMN llm_summary_model TEXT")
        if "llm_summary_duration_ms" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN llm_summary_duration_ms INTEGER"
            )
        if "llm_summary_input_tokens" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN llm_summary_input_tokens INTEGER"
            )
        if "llm_summary_output_tokens" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN llm_summary_output_tokens INTEGER"
            )
        if "llm_summary_total_tokens" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN llm_summary_total_tokens INTEGER"
            )
        if "llm_summary_error_message" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN llm_summary_error_message TEXT"
            )
        if "developer_profile" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN developer_profile TEXT"
            )
        if "developer_profile_status" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN developer_profile_status TEXT"
            )
        if "developer_profile_provider" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN developer_profile_provider TEXT"
            )
        if "developer_profile_model" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN developer_profile_model TEXT"
            )
        if "developer_profile_duration_ms" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN developer_profile_duration_ms INTEGER"
            )
        if "developer_profile_input_tokens" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN developer_profile_input_tokens INTEGER"
            )
        if "developer_profile_output_tokens" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN developer_profile_output_tokens INTEGER"
            )
        if "developer_profile_total_tokens" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN developer_profile_total_tokens INTEGER"
            )
        if "developer_profile_error_message" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN developer_profile_error_message TEXT"
            )
        if "developer_profile_lookback_days" not in columns:
            self._connection.execute(
                "ALTER TABLE review_runs ADD COLUMN developer_profile_lookback_days INTEGER"
            )

    def _ensure_schema_indexes(self) -> None:
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_review_runs_developer_timestamp
            ON review_runs(developer_id, timestamp DESC)
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_review_runs_ticket_key
            ON review_runs(ticket_key)
            """
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


def _optional_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    msg = f"Expected date-compatible SQLite value, got {type(value).__name__}."
    raise TypeError(msg)


def _optional_path(value: object) -> Path | None:
    path = _optional_str(value)
    if path is None:
        return None
    return Path(path)


def _llm_summary_from_row(row: sqlite3.Row) -> LlmReviewSummary | None:
    status = _optional_str(row["llm_summary_status"])
    if status is None:
        return None
    return LlmReviewSummary(
        status=cast(LlmSummaryStatus, status),
        provider=_optional_str(row["llm_summary_provider"]) or "unknown",
        model=_optional_str(row["llm_summary_model"]) or "unknown",
        duration_ms=_optional_int(row["llm_summary_duration_ms"]) or 0,
        text=_optional_str(row["llm_summary"]),
        score=_optional_int(row["llm_summary_score"]),
        input_tokens=_optional_int(row["llm_summary_input_tokens"]),
        output_tokens=_optional_int(row["llm_summary_output_tokens"]),
        total_tokens=_optional_int(row["llm_summary_total_tokens"]),
        error_message=_optional_str(row["llm_summary_error_message"]),
    )


def _developer_profile_from_row(row: sqlite3.Row) -> LlmDeveloperProfile | None:
    status = _optional_str(row["developer_profile_status"])
    if status is None:
        return None
    return LlmDeveloperProfile(
        status=cast(LlmSummaryStatus, status),
        provider=_optional_str(row["developer_profile_provider"]) or "unknown",
        model=_optional_str(row["developer_profile_model"]) or "unknown",
        duration_ms=_optional_int(row["developer_profile_duration_ms"]) or 0,
        lookback_days=_optional_int(row["developer_profile_lookback_days"]) or 0,
        text=_optional_str(row["developer_profile"]),
        input_tokens=_optional_int(row["developer_profile_input_tokens"]),
        output_tokens=_optional_int(row["developer_profile_output_tokens"]),
        total_tokens=_optional_int(row["developer_profile_total_tokens"]),
        error_message=_optional_str(row["developer_profile_error_message"]),
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    msg = f"Expected float-compatible SQLite value, got {type(value).__name__}."
    raise TypeError(msg)
