from typing import Any

from mr_guardian.core.gitlab_webhooks import process_gitlab_webhook


def merge_request_payload(*, action: str = "open") -> dict[str, Any]:
    return {
        "object_kind": "merge_request",
        "project": {
            "id": 42,
            "name": "MRGuardian",
            "path_with_namespace": "team/MRGuardian",
        },
        "user": {
            "name": "Jane Developer",
            "username": "jane",
        },
        "object_attributes": {
            "action": action,
            "iid": 7,
            "title": "Add webhook listener",
            "description": "## Test Plan\n- Ran webhook test",
            "url": "https://gitlab.com/team/MRGuardian/-/merge_requests/7",
            "source_branch": "feature/webhooks",
            "target_branch": "main",
        },
    }


def test_accepts_open_merge_request_event() -> None:
    result = process_gitlab_webhook(
        event_name="Merge Request Hook",
        payload=merge_request_payload(action="open"),
    )

    assert result.accepted is True
    assert result.merge_request is not None
    assert result.merge_request.project_id == "42"
    assert result.merge_request.project_ref == "42"
    assert result.merge_request.project_name == "team/MRGuardian"
    assert result.merge_request.title == "Add webhook listener"
    assert result.merge_request.description == "## Test Plan\n- Ran webhook test"
    assert result.merge_request.url == "https://gitlab.com/team/MRGuardian/-/merge_requests/7"
    assert result.merge_request.source_branch == "feature/webhooks"
    assert result.merge_request.target_branch == "main"
    assert result.merge_request.author == "Jane Developer"
    assert result.merge_request.action == "open"
    assert result.merge_request.merge_request_id == "7"


def test_accepts_reopened_merge_request_event() -> None:
    result = process_gitlab_webhook(
        event_name="Merge Request Hook",
        payload=merge_request_payload(action="reopen"),
    )

    assert result.accepted is True
    assert result.merge_request is not None
    assert result.merge_request.action == "reopen"


def test_ignores_non_merge_request_events() -> None:
    result = process_gitlab_webhook(
        event_name="Push Hook",
        payload={"object_kind": "push"},
    )

    assert result.accepted is False
    assert result.reason == "ignored_event"


def test_ignores_unsupported_merge_request_actions() -> None:
    result = process_gitlab_webhook(
        event_name="Merge Request Hook",
        payload=merge_request_payload(action="update"),
    )

    assert result.accepted is False
    assert result.reason == "ignored_action"
