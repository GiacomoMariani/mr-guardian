"""GitLab webhook parsing and normalization."""

from collections.abc import Mapping
from typing import Any, cast

from mr_guardian.models.gitlab import (
    GitLabMergeRequestAction,
    GitLabMergeRequestWebhook,
    GitLabWebhookResult,
)

MERGE_REQUEST_EVENT_NAME = "Merge Request Hook"
MERGE_REQUEST_OBJECT_KIND = "merge_request"
SUPPORTED_MR_ACTIONS = {"open", "reopen", "reopened"}


def process_gitlab_webhook(
    *,
    event_name: str | None,
    payload: Mapping[str, Any],
) -> GitLabWebhookResult:
    """Normalize a GitLab webhook payload when it is a supported MR event."""
    if event_name != MERGE_REQUEST_EVENT_NAME:
        return GitLabWebhookResult(accepted=False, reason="ignored_event")

    if payload.get("object_kind") != MERGE_REQUEST_OBJECT_KIND:
        return GitLabWebhookResult(accepted=False, reason="ignored_object_kind")

    attributes = _mapping(payload.get("object_attributes"))
    action = _string(attributes.get("action"))
    if action not in SUPPORTED_MR_ACTIONS:
        return GitLabWebhookResult(accepted=False, reason="ignored_action")
    normalized_action = cast(GitLabMergeRequestAction, action)

    return GitLabWebhookResult(
        accepted=True,
        reason="accepted",
        merge_request=GitLabMergeRequestWebhook(
            project_id=_project_id(payload),
            project_name=_project_name(payload),
            title=_string(attributes.get("title")),
            description=_string(attributes.get("description")),
            url=_string(attributes.get("url")),
            source_branch=_string(attributes.get("source_branch")),
            target_branch=_string(attributes.get("target_branch")),
            author=_author(payload),
            action=normalized_action,
            merge_request_id=_optional_string(attributes.get("iid") or attributes.get("id")),
        ),
    )


def _project_name(payload: Mapping[str, Any]) -> str:
    project = _mapping(payload.get("project"))
    return (
        _string(project.get("path_with_namespace"))
        or _string(project.get("name"))
        or "unknown"
    )


def _project_id(payload: Mapping[str, Any]) -> str | None:
    project = _mapping(payload.get("project"))
    return _optional_string(project.get("id"))


def _author(payload: Mapping[str, Any]) -> str:
    user = _mapping(payload.get("user"))
    return _string(user.get("name")) or _string(user.get("username")) or "unknown"


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _string(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _optional_string(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)
