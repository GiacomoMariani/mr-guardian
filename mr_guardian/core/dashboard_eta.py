"""Dashboard delivery ETA note helpers."""

from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from mr_guardian.models.history import DashboardEtaNote
from mr_guardian.storage import ReviewHistoryStore


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
    store = ReviewHistoryStore(database_path)
    try:
        return store.get_eta_note()
    finally:
        store.close()


def set_dashboard_eta_note(
    payload: DashboardEtaNotePayload,
    *,
    database_path: str | Path,
) -> DashboardEtaNote:
    """Store the dashboard ETA note, replacing any previous value."""
    store = ReviewHistoryStore(database_path)
    try:
        return store.set_eta_note(
            message=payload.message,
            target_date=payload.target_date,
        )
    finally:
        store.close()
