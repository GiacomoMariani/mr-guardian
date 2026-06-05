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
    """Read the current dashboard ETA note from storage."""
    with _connect(database_path) as connection:
        _initialize_eta_schema(connection)
        row = connection.execute(
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


def set_dashboard_eta_note(
    payload: DashboardEtaNotePayload,
    *,
    database_path: str | Path,
) -> DashboardEtaNote:
    """Store the dashboard ETA note, replacing any previous value."""
    updated_at = datetime.now(timezone.utc)
    with _connect(database_path) as connection:
        _initialize_eta_schema(connection)
        connection.execute(
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
                payload.message,
                payload.target_date.isoformat()
                if payload.target_date is not None
                else None,
                updated_at.isoformat(),
            ),
        )
        connection.commit()

    return DashboardEtaNote(
        message=payload.message,
        target_date=payload.target_date,
        updated_at=updated_at,
    )


def _connect(database_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _initialize_eta_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(ETA_SCHEMA)
    connection.commit()


def _optional_date(value: object) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(str(value))

