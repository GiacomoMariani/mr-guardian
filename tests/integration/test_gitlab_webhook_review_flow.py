import subprocess
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api import app
from mr_guardian.storage import ReviewHistoryStore


def test_gitlab_webhook_runs_review_and_stores_history(tmp_path: Path, monkeypatch) -> None:
    remote_path = create_remote_with_merge_request_branches(tmp_path)
    service_repo = tmp_path / "service"
    run_git(tmp_path, "clone", str(remote_path), str(service_repo))
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "python-policy.yml").write_text(
        """
version: 1

rules:
  - id: PYTHON-PRINT-001
    type: deterministic
    implementation: python_print
    enabled: true
    severity: warning
    source: python-policy.yml#PYTHON-PRINT-001
    description: Python code should use logging instead of newly introduced print calls.
    parameters:
      match:
        changed_files:
          - "**/*.py"
        added_lines_contain:
          - "print("
""",
        encoding="utf-8",
    )
    database_path = tmp_path / "history.sqlite"

    monkeypatch.setenv("MR_GUARDIAN_REPO_PATH", str(service_repo))
    monkeypatch.setenv("MR_GUARDIAN_POLICY_DIR", str(policy_dir))
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.setenv("GITLAB_WORKTREE_DIR", str(tmp_path / "worktrees"))
    monkeypatch.setenv("GITLAB_REMOTE_NAME", "origin")
    monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)

    test_client = TestClient(app)
    response = test_client.post(
        "/webhooks/gitlab",
        headers={"x-gitlab-event": "Merge Request Hook"},
        json=merge_request_payload(),
    )

    assert response.status_code == 202
    job_response = test_client.get(f"/webhook-jobs/{response.json()['job_id']}")
    assert job_response.json()["status"] == "succeeded"

    store = ReviewHistoryStore(database_path)
    recent_runs = store.recent_review_runs()
    store.close()

    assert len(recent_runs) == 1
    assert recent_runs[0].review_scope == "gitlab-webhook"
    assert recent_runs[0].branch_name == "refs/remotes/origin/main"
    assert recent_runs[0].triggered_rule_ids == ["PYTHON-PRINT-001"]


def create_remote_with_merge_request_branches(tmp_path: Path) -> Path:
    remote_path = tmp_path / "origin.git"
    seed_repo = tmp_path / "seed"
    run_git(tmp_path, "init", "--bare", str(remote_path))
    run_git(tmp_path, "init", "-b", "main", str(seed_repo))
    run_git(seed_repo, "config", "user.email", "test@example.com")
    run_git(seed_repo, "config", "user.name", "Test User")
    example_path = seed_repo / "mr_guardian" / "example.py"
    example_path.parent.mkdir(parents=True)
    example_path.write_text("def ready():\n    return True\n", encoding="utf-8")
    run_git(seed_repo, "add", ".")
    run_git(seed_repo, "commit", "-m", "initial")
    run_git(seed_repo, "remote", "add", "origin", str(remote_path))
    run_git(seed_repo, "push", "origin", "main")
    run_git(seed_repo, "checkout", "-b", "feature/webhooks")
    example_path.write_text("def ready():\n    print('ready')\n    return True\n", encoding="utf-8")
    run_git(seed_repo, "add", ".")
    run_git(seed_repo, "commit", "-m", "feature")
    run_git(seed_repo, "push", "origin", "feature/webhooks")
    return remote_path


def merge_request_payload() -> dict[str, Any]:
    return {
        "object_kind": "merge_request",
        "project": {"path_with_namespace": "team/MRGuardian"},
        "user": {"name": "Jane Developer"},
        "object_attributes": {
            "action": "open",
            "iid": 7,
            "title": "Add webhook listener",
            "description": "## Test Plan\n- Ran webhook test",
            "url": "https://gitlab.com/team/MRGuardian/-/merge_requests/7",
            "source_branch": "feature/webhooks",
            "target_branch": "main",
        },
    }


def run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
