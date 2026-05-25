"""Typed GitLab webhook models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

GitLabMergeRequestAction = Literal["open", "reopen", "reopened"]


class GitLabMergeRequestWebhook(BaseModel):
    """Normalized GitLab Merge Request webhook details."""

    model_config = ConfigDict(frozen=True)

    project_id: str | None = None
    project_name: str
    title: str
    description: str = ""
    url: str
    source_branch: str
    target_branch: str
    author: str
    action: GitLabMergeRequestAction
    merge_request_id: str | None = None

    @property
    def project_ref(self) -> str:
        """Return the preferred GitLab API project reference."""
        return self.project_id or self.project_name


class GitLabWebhookResult(BaseModel):
    """Result of processing one GitLab webhook payload."""

    model_config = ConfigDict(frozen=True)

    accepted: bool
    reason: str
    merge_request: GitLabMergeRequestWebhook | None = None
