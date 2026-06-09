"""Dashboard delivery ETA note helpers."""

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from mr_guardian.models.dashboard import DashboardEtaNote

ETA_SCHEMA = """
CREATE TABLE IF NOT EXISTS dashboard_eta_note (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    message TEXT NOT NULL,
    target_date TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dashboard_eta_notes (
    eta_note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    target_date TEXT,
    created_at TEXT NOT NULL
);
"""


class DashboardEtaNotePayload(BaseModel):
    """Input accepted by the delivery ETA API."""

    model_config = ConfigDict(frozen=True)

    message: str
    target_date: date | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        """Trim and validate the ETA message."""
        clean_value = value.strip()
        if not clean_value:
            msg = "ETA note message must not be empty."
            raise ValueError(msg)
        return clean_value


def dashboard_eta_note_payload_schema() -> dict[str, Any]:
    """Return the JSON schema for ETA note submissions."""
    return DashboardEtaNotePayload.model_json_schema()


def load_dashboard_eta_note(database_path: str | Path) -> DashboardEtaNote | None:
    """Read the most recent dashboard ETA note from storage."""
    with _connect(database_path) as connection:
        _initialize_eta_schema(connection)
        row = connection.execute(
            """
            SELECT message, target_date, created_at
            FROM dashboard_eta_notes
            ORDER BY eta_note_id DESC
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        return None
    return _eta_note_from_row(row)


def recent_dashboard_eta_notes(
    database_path: str | Path,
    *,
    limit: int = 20,
) -> list[DashboardEtaNote]:
    """Read stored dashboard ETA notes, most recent first."""
    with _connect(database_path) as connection:
        _initialize_eta_schema(connection)
        rows = connection.execute(
            """
            SELECT message, target_date, created_at
            FROM dashboard_eta_notes
            ORDER BY eta_note_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_eta_note_from_row(row) for row in rows]


def set_dashboard_eta_note(
    payload: DashboardEtaNotePayload,
    *,
    database_path: str | Path,
) -> DashboardEtaNote:
    """Append a new dashboard ETA note (prior notes are retained as history)."""
    created_at = datetime.now(timezone.utc)
    with _connect(database_path) as connection:
        _initialize_eta_schema(connection)
        connection.execute(
            """
            INSERT INTO dashboard_eta_notes (message, target_date, created_at)
            VALUES (?, ?, ?)
            """,
            (
                payload.message,
                payload.target_date.isoformat() if payload.target_date is not None else None,
                created_at.isoformat(),
            ),
        )
        connection.commit()

    return DashboardEtaNote(
        message=payload.message,
        target_date=payload.target_date,
        updated_at=created_at,
    )


def _connect(database_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _initialize_eta_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(ETA_SCHEMA)
    # Port the legacy singleton note into the append-only history table once.
    connection.execute(
        """
        INSERT INTO dashboard_eta_notes (message, target_date, created_at)
        SELECT message, target_date, updated_at
        FROM dashboard_eta_note
        WHERE id = 1
          AND NOT EXISTS (SELECT 1 FROM dashboard_eta_notes)
        """
    )
    connection.commit()


def _eta_note_from_row(row: sqlite3.Row) -> DashboardEtaNote:
    return DashboardEtaNote(
        message=str(row["message"]),
        target_date=_optional_date(row["target_date"]),
        updated_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _optional_date(value: object) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(str(value))
