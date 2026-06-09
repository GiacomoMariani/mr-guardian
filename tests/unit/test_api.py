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


def weekly_review_payload() -> dict[str, Any]:
    return {
        "week_start": "2026-06-01",
        "week_end": "2026-06-07",
        "result": "on_track",
        "score": 84,
        "summary": "The week is on track with a few metadata cleanup items.",
        "mr_count": 12,
        "developer_count": 4,
        "ticket_count": 7,
        "approved_ticket_count": 5,
        "observed_ticket_count": 2,
        "blocking_review_count": 1,
        "high_risk_review_count": 2,
        "warning_review_count": 3,
        "info_review_count": 4,
        "top_risks": ["Two tickets still have high-risk review signals."],
        "recommended_actions": ["Clear high-risk tickets before the beta cut."],
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "input_tokens": 1200,
        "output_tokens": 240,
        "total_tokens": 1440,
        "estimated_cost_usd": 0.0031,
        "currency": "usd",
    }


def review_run_payload() -> dict[str, Any]:
    return {
        "review_scope": "import-review",
        "branch_name": "feature/TK-900-import",
        "developer_id": "Import Bot",
        "ticket_key": "TK-900",
        "policy_version": 1,
        "risk": "none",
        "blocking_count": 0,
        "high_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "changed_file_count": 1,
        "changed_line_count": 5,
        "triggered_rule_ids": [],
        "generated_review_report": "# Imported review\n\nVerbatim body.",
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
    assert "is_final" in body["properties"]
    assert "llm_summary" in body["properties"]
    assert "developer_profile" in body["properties"]
    assert "llm_summary_score" in body["x-sqlite-columns"]
    assert "is_final" in body["x-sqlite-columns"]


def test_api_returns_weekly_llm_review_schema() -> None:
    response = client().get("/weekly-llm-reviews/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "WeeklyLlmReviewCreate"
    assert "week_start" in body["properties"]
    assert "score" in body["properties"]
    assert "phase" in body["properties"]
    assert body["x-storage-notes"]["week_start"] == "Must be a Monday."


def test_api_returns_eta_note_schema() -> None:
    response = client().get("/dashboard/eta-note/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "DashboardEtaNotePayload"
    assert "message" in body["properties"]
    assert "target_date" in body["properties"]


def test_api_returns_empty_eta_note(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))

    response = client().get("/dashboard/eta-note")

    assert response.status_code == 200
    assert response.json() is None


def test_api_stores_and_returns_eta_note(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    response = client().post(
        "/dashboard/eta-note",
        json={
            "message": "  Milestone looks merge-ready by Friday.  ",
            "target_date": "2026-06-05",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Milestone looks merge-ready by Friday."
    assert body["target_date"] == "2026-06-05"
    assert body["updated_at"]

    get_response = client().get("/dashboard/eta-note")
    assert get_response.status_code == 200
    assert get_response.json()["message"] == "Milestone looks merge-ready by Friday."


def test_api_eta_note_post_overwrites_previous_note(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    client().post(
        "/dashboard/eta-note",
        json={"message": "First ETA.", "target_date": "2026-06-05"},
    )
    response = client().post(
        "/dashboard/eta-note",
        json={"message": "Second ETA."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Second ETA."
    assert body["target_date"] is None

    store = ReviewHistoryStore(tmp_path / "history.sqlite")
    try:
        note = store.get_eta_note()
    finally:
        store.close()

    assert note is not None
    assert note.message == "Second ETA."


def test_api_eta_note_admin_token_is_enforced(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.setenv("MR_GUARDIAN_ADMIN_TOKEN", "expected-token")

    response = client().post(
        "/dashboard/eta-note",
        headers={"x-mr-guardian-admin-token": "wrong-token"},
        json={"message": "Delivery ETA."},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid MR Guardian admin token."}


def test_api_eta_note_accepts_valid_admin_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.setenv("MR_GUARDIAN_ADMIN_TOKEN", "expected-token")

    response = client().post(
        "/dashboard/eta-note",
        headers={"x-mr-guardian-admin-token": "expected-token"},
        json={"message": "Delivery ETA."},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Delivery ETA."


def test_api_eta_note_rejects_invalid_payloads(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    invalid_json_response = client().post(
        "/dashboard/eta-note",
        content="{",
        headers={"content-type": "application/json"},
    )
    non_object_response = client().post("/dashboard/eta-note", json=[])
    empty_response = client().post("/dashboard/eta-note", json={"message": "   "})
    bad_date_response = client().post(
        "/dashboard/eta-note",
        json={"message": "Delivery ETA.", "target_date": "not-a-date"},
    )

    assert invalid_json_response.status_code == 400
    assert invalid_json_response.json() == {"detail": "Invalid JSON payload."}
    assert non_object_response.status_code == 400
    assert non_object_response.json() == {"detail": "Expected JSON object payload."}
    assert empty_response.status_code == 400
    assert "Invalid ETA note structure" in empty_response.json()["detail"]
    assert bad_date_response.status_code == 400
    assert "Invalid ETA note structure" in bad_date_response.json()["detail"]


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


def test_api_stores_valid_weekly_llm_review(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    response = client().post(
        "/weekly-llm-reviews/manual",
        json=weekly_review_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "status": "stored",
        "weekly_review_id": 1,
        "week_start": "2026-06-01",
        "week_end": "2026-06-07",
        "result": "on_track",
        "score": 84,
    }

    store = ReviewHistoryStore(database_path)
    try:
        record = store.latest_weekly_llm_review()
    finally:
        store.close()

    assert record is not None
    assert record.result == "on_track"
    assert record.currency == "USD"
    assert record.top_risks == ["Two tickets still have high-risk review signals."]


def test_api_weekly_llm_review_admin_token_is_enforced(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.setenv("MR_GUARDIAN_ADMIN_TOKEN", "expected-token")

    response = client().post(
        "/weekly-llm-reviews/manual",
        headers={"x-mr-guardian-admin-token": "wrong-token"},
        json=weekly_review_payload(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid MR Guardian admin token."}


def test_api_rejects_invalid_weekly_llm_review_payload(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    payload = weekly_review_payload()
    payload["week_start"] = "2026-06-02"

    response = client().post("/weekly-llm-reviews/manual", json=payload)

    assert response.status_code == 400
    assert "Invalid weekly LLM review structure" in response.json()["detail"]
    assert "week_start must be a Monday" in response.json()["detail"]


def test_api_rejects_invalid_weekly_llm_review_json(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    invalid_json_response = client().post(
        "/weekly-llm-reviews/manual",
        content="{",
        headers={"content-type": "application/json"},
    )
    non_object_response = client().post("/weekly-llm-reviews/manual", json=[])

    assert invalid_json_response.status_code == 400
    assert invalid_json_response.json() == {"detail": "Invalid JSON payload."}
    assert non_object_response.status_code == 400
    assert non_object_response.json() == {"detail": "Expected JSON object payload."}


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


def test_api_sets_review_finality_and_clears_previous_final_review(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    first_review_id = client().post(
        "/reviews/manual",
        json=manual_review_payload(),
    ).json()["review_id"]
    second_review_id = client().post(
        "/reviews/manual",
        json=manual_review_payload(),
    ).json()["review_id"]
    first_response = client().post(
        f"/reviews/{first_review_id}/finality",
        json={"final": True},
    )
    second_response = client().post(
        f"/reviews/{second_review_id}/finality",
        json={"final": True},
    )

    assert first_response.status_code == 200
    assert first_response.json()["is_final"] is True
    assert first_response.json()["cleared_review_ids"] == []
    assert second_response.status_code == 200
    assert second_response.json() == {
        "status": "updated",
        "review_id": second_review_id,
        "is_final": True,
        "ticket_key": "TK-234",
        "cleared_review_ids": [first_review_id],
    }

    store = ReviewHistoryStore(database_path)
    try:
        first = store.review_run(first_review_id)
        second = store.review_run(second_review_id)
    finally:
        store.close()

    assert first is not None
    assert first.is_final is False
    assert second is not None
    assert second.is_final is True


def test_api_unsets_review_finality(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    review_id = client().post("/reviews/manual", json=manual_review_payload()).json()[
        "review_id"
    ]
    client().post(f"/reviews/{review_id}/finality", json={"final": True})
    response = client().post(f"/reviews/{review_id}/finality", json={"final": False})

    assert response.status_code == 200
    assert response.json()["is_final"] is False
    assert response.json()["cleared_review_ids"] == []


def test_api_reports_missing_review_finality_update(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    response = client().post("/reviews/999/finality", json={"final": True})

    assert response.status_code == 404
    assert response.json() == {"detail": "Review 999 was not found."}


def test_api_rejects_invalid_review_finality_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    response = client().post("/reviews/0/finality", json={"final": True})

    assert response.status_code == 400
    assert response.json() == {"detail": "Review ID must be a positive integer."}


def test_api_rejects_invalid_admin_token_for_review_finality(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.setenv("MR_GUARDIAN_ADMIN_TOKEN", "expected-token")

    response = client().post(
        "/reviews/1/finality",
        headers={"x-mr-guardian-admin-token": "wrong-token"},
        json={"final": True},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid MR Guardian admin token."}


def test_api_accepts_valid_admin_token_for_review_finality(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.setenv("MR_GUARDIAN_ADMIN_TOKEN", "expected-token")

    review_id = client().post("/reviews/manual", json=manual_review_payload()).json()[
        "review_id"
    ]
    response = client().post(
        f"/reviews/{review_id}/finality",
        headers={"x-mr-guardian-admin-token": "expected-token"},
        json={"final": True},
    )

    assert response.status_code == 200
    assert response.json()["is_final"] is True


def test_api_rejects_invalid_review_finality_payloads(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    invalid_json_response = client().post(
        "/reviews/1/finality",
        content="{",
        headers={"content-type": "application/json"},
    )
    non_object_response = client().post("/reviews/1/finality", json=[])
    missing_final_response = client().post("/reviews/1/finality", json={})
    non_boolean_response = client().post(
        "/reviews/1/finality",
        json={"final": "true"},
    )

    assert invalid_json_response.status_code == 400
    assert invalid_json_response.json() == {"detail": "Invalid JSON payload."}
    assert non_object_response.status_code == 400
    assert non_object_response.json() == {"detail": "Expected JSON object payload."}
    assert missing_final_response.status_code == 400
    assert "Invalid review finality structure" in missing_final_response.json()["detail"]
    assert non_boolean_response.status_code == 400
    assert "Invalid review finality structure" in non_boolean_response.json()["detail"]


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


def test_api_creates_review_run(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    response = client().post("/reviews", json=review_run_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "created"
    assert body["review_id"] == 1
    assert body["risk"] == "none"
    assert body["ticket_key"] == "TK-900"

    store = ReviewHistoryStore(database_path)
    try:
        record = store.review_run(1)
    finally:
        store.close()

    assert record is not None
    assert record.developer_id == "Import Bot"
    assert record.findings == []


def test_api_create_review_run_admin_token_is_enforced(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.setenv("MR_GUARDIAN_ADMIN_TOKEN", "expected-token")

    response = client().post(
        "/reviews",
        headers={"x-mr-guardian-admin-token": "wrong-token"},
        json=review_run_payload(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid MR Guardian admin token."}


def test_api_feeds_findings_and_replaces_on_repeat(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    review_id = client().post("/reviews", json=review_run_payload()).json()["review_id"]
    findings = [
        {
            "rule_id": "RULE-1",
            "severity": "warning",
            "message": "First finding.",
            "source": "import#RULE-1",
            "evaluation": "coding",
        },
        {
            "rule_id": "RULE-2",
            "severity": "info",
            "message": "Second finding.",
            "source": "import#RULE-2",
            "evaluation": "coding",
        },
    ]

    first = client().post(f"/reviews/{review_id}/findings", json=findings)
    assert first.status_code == 200
    assert first.json() == {
        "status": "stored",
        "review_id": review_id,
        "finding_count": 2,
    }

    # Idempotent replace: re-feeding a single finding replaces the prior set.
    second = client().post(f"/reviews/{review_id}/findings", json=findings[:1])
    assert second.status_code == 200
    assert second.json()["finding_count"] == 1

    store = ReviewHistoryStore(database_path)
    try:
        record = store.review_run(review_id)
    finally:
        store.close()

    assert record is not None
    assert [finding.rule_id for finding in record.findings] == ["RULE-1"]


def test_api_feeds_triggered_rules(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    review_id = client().post("/reviews", json=review_run_payload()).json()["review_id"]
    response = client().post(
        f"/reviews/{review_id}/triggered-rules",
        json=["RULE-1", "RULE-2"],
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "stored",
        "review_id": review_id,
        "triggered_rule_count": 2,
    }

    store = ReviewHistoryStore(database_path)
    try:
        record = store.review_run(review_id)
    finally:
        store.close()

    assert record is not None
    assert record.triggered_rule_ids == ["RULE-1", "RULE-2"]


def test_api_feeds_evaluations_and_replaces_on_repeat(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    review_id = client().post("/reviews", json=review_run_payload()).json()["review_id"]
    first = client().post(
        f"/reviews/{review_id}/evaluations",
        json=[
            {
                "evaluation": "coding",
                "risk": "warning",
                "counts": {"blocking": 0, "high": 0, "warning": 1, "info": 0},
                "triggered_rule_ids": ["RULE-1", "RULE-2"],
            },
            {
                "evaluation": "mr_structure",
                "risk": "none",
                "counts": {"blocking": 0, "high": 0, "warning": 0, "info": 0},
                "triggered_rule_ids": [],
            },
        ],
    )
    assert first.status_code == 200
    assert first.json()["evaluation_count"] == 2

    second = client().post(
        f"/reviews/{review_id}/evaluations",
        json=[
            {
                "evaluation": "coding",
                "risk": "none",
                "counts": {"blocking": 0, "high": 0, "warning": 0, "info": 0},
                "triggered_rule_ids": ["RULE-9"],
            }
        ],
    )
    assert second.status_code == 200
    assert second.json()["evaluation_count"] == 1

    store = ReviewHistoryStore(database_path)
    try:
        record = store.review_run(review_id)
    finally:
        store.close()

    # The replace dropped the prior evaluations and their triggered-rule children.
    assert record is not None
    assert len(record.evaluations) == 1
    assert record.evaluations[0].triggered_rule_ids == ["RULE-9"]


def test_api_feeds_policy_summaries(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    review_id = client().post("/reviews", json=review_run_payload()).json()["review_id"]
    response = client().post(
        f"/reviews/{review_id}/policies",
        json=[
            {
                "policy_path": "sources/yaml/unity.yaml",
                "policy_version": 1,
                "enabled_rule_count": 12,
                "disabled_rule_count": 3,
            }
        ],
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "stored",
        "review_id": review_id,
        "policy_count": 1,
    }


def test_api_feeds_llm_metrics(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    review_id = client().post("/reviews", json=review_run_payload()).json()["review_id"]
    response = client().post(
        f"/reviews/{review_id}/llm-metrics",
        json=[
            {
                "rule_id": "LLM-RULE-1",
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "status": "succeeded",
                "duration_ms": 120,
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            }
        ],
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "stored",
        "review_id": review_id,
        "llm_metric_count": 1,
    }


def test_api_sets_llm_summary(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    review_id = client().post("/reviews", json=review_run_payload()).json()["review_id"]
    response = client().put(
        f"/reviews/{review_id}/llm-summary",
        json={
            "status": "succeeded",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "duration_ms": 300,
            "text": "Looks merge-ready.",
            "score": 88,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "updated",
        "review_id": review_id,
        "llm_summary_status": "succeeded",
    }

    store = ReviewHistoryStore(database_path)
    try:
        record = store.review_run(review_id)
    finally:
        store.close()

    assert record is not None
    assert record.llm_summary is not None
    assert record.llm_summary.text == "Looks merge-ready."
    assert record.llm_summary.score == 88


def test_api_sets_developer_profile(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    review_id = client().post("/reviews", json=review_run_payload()).json()["review_id"]
    response = client().put(
        f"/reviews/{review_id}/developer-profile",
        json={
            "status": "succeeded",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "duration_ms": 400,
            "lookback_days": 30,
            "text": "Strong, consistent contributor.",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "updated",
        "review_id": review_id,
        "developer_profile_status": "succeeded",
    }

    store = ReviewHistoryStore(database_path)
    try:
        record = store.review_run(review_id)
    finally:
        store.close()

    assert record is not None
    assert record.developer_profile is not None
    assert record.developer_profile.text == "Strong, consistent contributor."
    assert record.developer_profile.lookback_days == 30


def test_api_feed_component_reports_missing_review(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    response = client().post("/reviews/999/findings", json=[])

    assert response.status_code == 404
    assert response.json() == {"detail": "Review 999 was not found."}


def test_api_feed_component_rejects_invalid_review_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    response = client().post("/reviews/0/findings", json=[])

    assert response.status_code == 400
    assert response.json() == {"detail": "Review ID must be a positive integer."}


def test_api_feed_component_admin_token_is_enforced(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.setenv("MR_GUARDIAN_ADMIN_TOKEN", "expected-token")

    response = client().post(
        "/reviews/1/findings",
        headers={"x-mr-guardian-admin-token": "wrong-token"},
        json=[],
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid MR Guardian admin token."}


def test_api_feed_findings_rejects_invalid_payloads(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    review_id = client().post("/reviews", json=review_run_payload()).json()["review_id"]
    invalid_json = client().post(
        f"/reviews/{review_id}/findings",
        content="{",
        headers={"content-type": "application/json"},
    )
    non_array = client().post(f"/reviews/{review_id}/findings", json={})
    bad_struct = client().post(
        f"/reviews/{review_id}/findings",
        json=[{"severity": "warning"}],
    )

    assert invalid_json.status_code == 400
    assert invalid_json.json() == {"detail": "Invalid JSON payload."}
    assert non_array.status_code == 400
    assert non_array.json() == {"detail": "Expected JSON array payload."}
    assert bad_struct.status_code == 400
    assert "Invalid findings structure" in bad_struct.json()["detail"]


def test_api_feed_llm_summary_rejects_non_object(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    review_id = client().post("/reviews", json=review_run_payload()).json()["review_id"]
    non_object = client().put(f"/reviews/{review_id}/llm-summary", json=[])
    bad_struct = client().put(
        f"/reviews/{review_id}/llm-summary",
        json={"status": "succeeded"},
    )

    assert non_object.status_code == 400
    assert non_object.json() == {"detail": "Expected JSON object payload."}
    assert bad_struct.status_code == 400
    assert "Invalid LLM summary structure" in bad_struct.json()["detail"]


def test_api_weekly_review_accepts_and_stores_phase(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    payload = weekly_review_payload()
    payload["phase"] = "Release Candidate"
    response = client().post("/weekly-llm-reviews/manual", json=payload)

    assert response.status_code == 201

    store = ReviewHistoryStore(database_path)
    try:
        record = store.latest_weekly_llm_review()
    finally:
        store.close()

    assert record is not None
    assert record.phase == "Release Candidate"


def test_api_weekly_review_phase_defaults_to_beta_phase(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    # weekly_review_payload() omits phase -> the model default applies.
    client().post("/weekly-llm-reviews/manual", json=weekly_review_payload())

    store = ReviewHistoryStore(database_path)
    try:
        record = store.latest_weekly_llm_review()
    finally:
        store.close()

    assert record is not None
    assert record.phase == "Beta Phase"


def test_api_eta_note_history_returns_recent_notes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    client().post("/dashboard/eta-note", json={"message": "First ETA."})
    client().post("/dashboard/eta-note", json={"message": "Second ETA."})

    response = client().get("/dashboard/eta-note/history")

    assert response.status_code == 200
    messages = [note["message"] for note in response.json()]
    assert messages == ["Second ETA.", "First ETA."]


def test_api_eta_note_post_appends_to_history(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "history.sqlite"
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.delenv("MR_GUARDIAN_ADMIN_TOKEN", raising=False)

    client().post("/dashboard/eta-note", json={"message": "First ETA."})
    client().post("/dashboard/eta-note", json={"message": "Second ETA."})

    # GET returns the latest; both are retained.
    assert client().get("/dashboard/eta-note").json()["message"] == "Second ETA."

    store = ReviewHistoryStore(database_path)
    try:
        history = store.recent_eta_notes()
    finally:
        store.close()
    assert [note.message for note in history] == ["Second ETA.", "First ETA."]


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
