import subprocess
from pathlib import Path

import pytest

from mr_guardian.models.gitlab import GitLabMergeRequestWebhook
from mr_guardian.providers.gitlab_sync import GitLabRepositorySync, GitLabRepositorySyncError
from mr_guardian.providers.local_git import LocalGitProvider


def test_prepares_worktree_for_gitlab_merge_request(tmp_path: Path) -> None:
    remote_path = create_remote_with_merge_request_branches(tmp_path)
    service_repo = tmp_path / "service"
    run_git(tmp_path, "clone", str(remote_path), str(service_repo))

    sync = GitLabRepositorySync(
        repo_path=service_repo,
        worktree_dir=tmp_path / "worktrees",
        remote_name="origin",
    )

    target = sync.prepare(merge_request())
    try:
        review_input = LocalGitProvider(target.repo_path).collect(target.base_ref)
    finally:
        sync.cleanup(target)

    assert target.repo_path.exists() is False
    assert target.base_ref == "refs/remotes/origin/main"
    assert [changed_file.path.as_posix() for changed_file in review_input.changed_files] == [
        "mr_guardian/example.py"
    ]


def test_reports_clear_error_for_missing_gitlab_source_branch(tmp_path: Path) -> None:
    remote_path = create_remote_with_merge_request_branches(tmp_path)
    service_repo = tmp_path / "service"
    run_git(tmp_path, "clone", str(remote_path), str(service_repo))
    sync = GitLabRepositorySync(
        repo_path=service_repo,
        worktree_dir=tmp_path / "worktrees",
        remote_name="origin",
    )

    with pytest.raises(GitLabRepositorySyncError, match="does-not-exist"):
        sync.prepare(merge_request(source_branch="does-not-exist"))


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


def merge_request(
    *,
    source_branch: str = "feature/webhooks",
    target_branch: str = "main",
) -> GitLabMergeRequestWebhook:
    return GitLabMergeRequestWebhook(
        project_name="team/MRGuardian",
        title="Add webhook review",
        description="## Test Plan\n- Ran webhook test",
        url="https://gitlab.com/team/MRGuardian/-/merge_requests/7",
        source_branch=source_branch,
        target_branch=target_branch,
        author="Jane Developer",
        action="open",
        merge_request_id="7",
    )


def run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
