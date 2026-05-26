from typing import Any

from fastapi.testclient import TestClient

from app.api import app
from mr_guardian.models.gitlab import GitLabMergeRequestWebhook
from mr_guardian.providers.gitlab_sync import GitLabRepositorySyncError


def merge_request_payload(*, action: str = "open") -> dict[str, Any]:
    return {
        "object_kind": "merge_request",
        "project": {"id": 42, "path_with_namespace": "team/MRGuardian"},
        "user": {"name": "Jane Developer"},
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


def test_api_health_check() -> None:
    response = client().get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_accepts_valid_open_merge_request_webhook(monkeypatch) -> None:
    monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr("app.api.review_gitlab_merge_request", fake_triggered_review)

    response = client().post(
        "/webhooks/gitlab",
        headers={"x-gitlab-event": "Merge Request Hook"},
        json=merge_request_payload(action="open"),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"]
    assert body["merge_request"]["project_id"] == "42"
    assert body["merge_request"]["project_name"] == "team/MRGuardian"

    job_response = client().get(f"/webhook-jobs/{body['job_id']}")
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "succeeded"
    assert job_response.json()["review_id"] == 7
    assert job_response.json()["risk"] == "warning"


def test_api_accepts_valid_reopen_merge_request_webhook(monkeypatch) -> None:
    monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr("app.api.review_gitlab_merge_request", fake_triggered_review)

    response = client().post(
        "/webhooks/gitlab",
        headers={"x-gitlab-event": "Merge Request Hook"},
        json=merge_request_payload(action="reopen"),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["merge_request"]["action"] == "reopen"


def test_api_ignores_non_merge_request_webhook(monkeypatch) -> None:
    monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)

    response = client().post(
        "/webhooks/gitlab",
        headers={"x-gitlab-event": "Push Hook"},
        json={"object_kind": "push"},
    )

    assert response.status_code == 202
    assert response.json() == {"status": "ignored", "reason": "ignored_event"}


def test_api_ignores_unsupported_merge_request_action(monkeypatch) -> None:
    monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)

    response = client().post(
        "/webhooks/gitlab",
        headers={"x-gitlab-event": "Merge Request Hook"},
        json=merge_request_payload(action="update"),
    )

    assert response.status_code == 202
    assert response.json() == {"status": "ignored", "reason": "ignored_action"}


def test_api_rejects_invalid_webhook_secret(monkeypatch) -> None:
    monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "expected-secret")

    response = client().post(
        "/webhooks/gitlab",
        headers={
            "x-gitlab-event": "Merge Request Hook",
            "x-gitlab-token": "wrong-secret",
        },
        json=merge_request_payload(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid GitLab webhook token."}


def test_api_accepts_valid_webhook_secret(monkeypatch) -> None:
    monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "expected-secret")
    monkeypatch.setattr("app.api.review_gitlab_merge_request", fake_triggered_review)

    response = client().post(
        "/webhooks/gitlab",
        headers={
            "x-gitlab-event": "Merge Request Hook",
            "x-gitlab-token": "expected-secret",
        },
        json=merge_request_payload(),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_api_reports_repository_sync_failure(monkeypatch) -> None:
    monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)

    def fail_review(*_: object, **__: object) -> FakeTriggeredReview:
        raise GitLabRepositorySyncError("Git fetch failed.")

    monkeypatch.setattr("app.api.review_gitlab_merge_request", fail_review)

    response = client().post(
        "/webhooks/gitlab",
        headers={"x-gitlab-event": "Merge Request Hook"},
        json=merge_request_payload(),
    )

    assert response.status_code == 202
    body = response.json()
    job_response = client().get(f"/webhook-jobs/{body['job_id']}")
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "failed"
    assert job_response.json()["detail"] == "Git fetch failed."


def test_api_reports_missing_webhook_job() -> None:
    response = client().get("/webhook-jobs/not-found")

    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook review job not found."}


def client() -> TestClient:
    return TestClient(app)


class FakeTriggeredReview:
    review_id = 7
    risk = "warning"


def fake_triggered_review(
    merge_request: GitLabMergeRequestWebhook,
    **_: object,
) -> FakeTriggeredReview:
    assert merge_request.target_branch == "main"
    return FakeTriggeredReview()
