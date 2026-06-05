"""Dashboard-specific typed models."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DashboardEtaNote(BaseModel):
    """The singleton delivery ETA note shown on the dashboard."""

    model_config = ConfigDict(frozen=True)

    message: str
    target_date: date | None = None
    updated_at: datetime
