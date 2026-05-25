"""Prepare local Git worktrees for GitLab-triggered reviews."""

import re
import subprocess
from pathlib import Path
from time import time_ns

from pydantic import BaseModel, ConfigDict

from mr_guardian.models.gitlab import GitLabMergeRequestWebhook


class GitLabRepositorySyncError(Exception):
    """Raised when GitLab branch sync cannot prepare a review worktree."""


class GitLabSyncedReviewTarget(BaseModel):
    """Prepared local repository target for a GitLab-triggered review."""

    model_config = ConfigDict(frozen=True)

    repo_path: Path
    base_ref: str


class GitLabRepositorySync:
    """Synchronize GitLab MR refs into a temporary local worktree."""

    def __init__(
        self,
        *,
        repo_path: str | Path,
        worktree_dir: str | Path,
        remote_name: str = "origin",
    ) -> None:
        self.repo_path = Path(repo_path)
        self.worktree_dir = Path(worktree_dir)
        self.remote_name = remote_name

    def prepare(self, merge_request: GitLabMergeRequestWebhook) -> GitLabSyncedReviewTarget:
        """Fetch MR refs and create a detached worktree for the source branch."""
        self.worktree_dir.mkdir(parents=True, exist_ok=True)
        source_ref = self._remote_ref(merge_request.source_branch)
        target_ref = self._remote_ref(merge_request.target_branch)

        self._run_git(
            "fetch",
            self.remote_name,
            f"{merge_request.source_branch}:{source_ref}",
            f"{merge_request.target_branch}:{target_ref}",
        )

        worktree_path = self.worktree_dir / self._worktree_name(merge_request)
        self._run_git("worktree", "add", "--detach", str(worktree_path), source_ref)
        return GitLabSyncedReviewTarget(repo_path=worktree_path, base_ref=target_ref)

    def cleanup(self, target: GitLabSyncedReviewTarget) -> None:
        """Remove a prepared review worktree."""
        self._run_git("worktree", "remove", "--force", str(target.repo_path))

    def _remote_ref(self, branch_name: str) -> str:
        return f"refs/remotes/{self.remote_name}/{branch_name}"

    def _worktree_name(self, merge_request: GitLabMergeRequestWebhook) -> str:
        identifier = merge_request.merge_request_id or merge_request.source_branch
        return f"gitlab-mr-{_safe_path_part(identifier)}-{time_ns()}"

    def _run_git(self, *args: str) -> str:
        try:
            safe_repo_path = self.repo_path.resolve().as_posix()
            completed = subprocess.run(
                ["git", "-c", f"safe.directory={safe_repo_path}", "-C", str(self.repo_path), *args],
                capture_output=True,
                check=False,
                encoding="utf-8",
            )
        except FileNotFoundError as exc:
            msg = "Git executable is not available on PATH."
            raise GitLabRepositorySyncError(msg) from exc

        if completed.returncode != 0:
            error = completed.stderr.strip() or completed.stdout.strip() or "unknown Git error"
            msg = f"Git command failed while preparing GitLab review: git {' '.join(args)}: {error}"
            raise GitLabRepositorySyncError(msg)

        return completed.stdout


def _safe_path_part(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return sanitized or "unknown"
