"""Typed inputs for LLM-generated developer profile snapshots."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from mr_guardian.models.history import ReviewRunRecord
from mr_guardian.models.lead_dashboard import LeadDeveloperSummary


class DeveloperProfileInput(BaseModel):
    """Recent developer review context sent to the profile generator."""

    model_config = ConfigDict(frozen=True)

    developer_id: str
    lookback_days: int
    start_at: datetime
    end_at: datetime
    summary: LeadDeveloperSummary
    review_runs: list[ReviewRunRecord]
