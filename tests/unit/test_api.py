from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api import app
from mr_guardian.models.gitlab import GitLabMergeRequestWebhook
from mr_guardian.providers.gitlab_sync import GitLabRepositorySyncError
from mr_guardian.storage import ReviewHistoryStore


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


def manual_review_payload() -> dict[str, Any]:
    return {
        "review_scope": "manual-review",
        "branch_name": "feature/TK-234-manual-review",
        "title": "TK-234 Manual review",
        "developer_id": "API Reviewer",
        "policy_version": 1,
        "risk": "warning",
        "findings": [
            {
                "rule_id": "MANUAL-001",
                "severity": "warning",
                "message": "Reviewer requested clearer test evidence.",
                "source": "manual-review#MANUAL-001",
                "evaluation": "mr_structure",
                "rule_type": "deterministic",
                "file_path": None,
                "line_number": None,
            }
        ],
        "evaluations": [
            {
                "evaluation": "coding",
                "risk": "none",
                "counts": {
                    "blocking": 0,
                    "high": 0,
                    "warning": 0,
                    "info": 0,
                },
                "triggered_rule_ids": [],
            },
            {
                "evaluation": "mr_structure",
                "risk": "warning",
                "counts": {
                    "blocking": 0,
                    "high": 0,
                    "warning": 1,
                    "info": 0,
                },
                "triggered_rule_ids": ["MANUAL-001"],
            },
        ],
        "changed_file_count": 2,
        "changed_line_count": 20,
        "generated_review_report": "# Manual Review\n\nReviewer requested clearer test evidence.",
        "mr_id": "42",
        "commit_sha": None,
    }


def test_api_health_check() -> None:
    response = client().get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_returns_manual_review_schema() -> None:
    response = client().get("/reviews/manual/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "ManualReviewPayload"
    assert "findings" in body["properties"]


def test_api_returns_stored_review_schema() -> None:
    response = client().get("/reviews/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "ReviewRunRecord"
    assert "llm_summary" in body["properties"]
    assert "developer_profile" in body["properties"]
    assert "llm_summary_score" in body["x-sqlite-columns"]


def test_api_stores_valid_manual_review(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))

    response = client().post("/reviews/manual", json=manual_review_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "stored"
    assert body["review_id"] == 1
    assert body["risk"] == "warning"
    assert body["score"] == 95
    assert body["ticket_key"] == "TK-234"

    store = ReviewHistoryStore(database_path)
    try:
        record = store.review_run(1)
    finally:
        store.close()

    assert record is not None
    assert record.developer_id == "API Reviewer"
    assert record.ticket_key == "TK-234"
    assert record.findings[0].rule_id == "MANUAL-001"


def test_api_deletes_existing_review(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    stored_response = client().post("/reviews/manual", json=manual_review_payload())
    review_id = stored_response.json()["review_id"]

    response = client().delete(f"/reviews/{review_id}")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "review_id": review_id}

    store = ReviewHistoryStore(database_path)
    try:
        record = store.review_run(review_id)
    finally:
        store.close()

    assert record is None


def test_api_reports_missing_review_delete(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    response = client().delete("/reviews/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Review 999 was not found."}


def test_api_rejects_invalid_review_delete_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    response = client().delete("/reviews/0")

    assert response.status_code == 400
    assert response.json() == {"detail": "Review ID must be a positive integer."}


def test_api_rejects_invalid_admin_token_for_review_delete(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.setenv("MR_GUARDIAN_ADMIN_TOKEN", "expected-token")

    response = client().delete(
        "/reviews/1",
        headers={"x-mr-guardian-admin-token": "wrong-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid MR Guardian admin token."}


def test_api_accepts_valid_admin_token_for_review_delete(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.setenv("MR_GUARDIAN_ADMIN_TOKEN", "expected-token")

    stored_response = client().post("/reviews/manual", json=manual_review_payload())
    review_id = stored_response.json()["review_id"]
    response = client().delete(
        f"/reviews/{review_id}",
        headers={"x-mr-guardian-admin-token": "expected-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "review_id": review_id}


def test_streamlit_has_no_review_delete_ui() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "delete_review" not in source
    assert "DELETE /reviews" not in source


def test_api_rejects_invalid_manual_review_payload(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))

    payload = manual_review_payload()
    payload.pop("branch_name")
    response = client().post("/reviews/manual", json=payload)

    assert response.status_code == 400
    assert "Invalid manual review structure" in response.json()["detail"]


def test_api_rejects_manual_review_risk_mismatch(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))

    payload = manual_review_payload()
    payload["risk"] = "none"
    response = client().post("/reviews/manual", json=payload)

    assert response.status_code == 400
    assert "does not match findings risk" in response.json()["detail"]


def test_api_rejects_non_object_manual_review_payload(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))

    response = client().post("/reviews/manual", json=[])

    assert response.status_code == 400
    assert response.json() == {"detail": "Expected JSON object payload."}


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
