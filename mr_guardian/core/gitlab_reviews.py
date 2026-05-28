"""GitLab-triggered review orchestration."""

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from mr_guardian.core.review import ReviewRequest, review_merge_request
from mr_guardian.core.review_history import store_review_result
from mr_guardian.models.gitlab import GitLabMergeRequestWebhook
from mr_guardian.models.history import ReviewRunRecord
from mr_guardian.providers.gitlab_sync import GitLabRepositorySync
from mr_guardian.reporting.report import render_review_report
from mr_guardian.summarizer_ai import LlmReviewSummaryRunner, LlmRuleRunner


class GitLabTriggeredReview(BaseModel):
    """Stored review created from a GitLab webhook."""

    model_config = ConfigDict(frozen=True)

    merge_request: GitLabMergeRequestWebhook
    review_id: int
    risk: str
    comment_posted: bool = False


class GitLabReviewCommenter(Protocol):
    """Interface for posting review comments to a GitLab MR."""

    def post_merge_request_note(
        self,
        *,
        project_ref: str,
        merge_request_iid: str,
        body: str,
    ) -> None:
        """Post one review comment."""


def review_gitlab_merge_request(
    merge_request: GitLabMergeRequestWebhook,
    *,
    repo_path: str | Path,
    worktree_dir: str | Path,
    remote_name: str,
    policy_directory: str | Path,
    database_path: Path,
    llm_rule_runner: LlmRuleRunner,
    llm_summary_runner: LlmReviewSummaryRunner | None = None,
    llm_summary_max_chars: int = 700,
    review_commenter: GitLabReviewCommenter | None = None,
) -> GitLabTriggeredReview:
    """Run and store a local review for an accepted GitLab MR webhook."""
    sync = GitLabRepositorySync(
        repo_path=repo_path,
        worktree_dir=worktree_dir,
        remote_name=remote_name,
    )
    target = sync.prepare(merge_request)
    try:
        result = review_merge_request(
            ReviewRequest(
                base=target.base_ref,
                policy_directory=Path(policy_directory),
                review_scope="gitlab-webhook",
                title=merge_request.title,
                description=merge_request.description,
            ),
            repo_path=target.repo_path,
            llm_rule_runner=llm_rule_runner,
            llm_summary_runner=llm_summary_runner,
            llm_summary_max_chars=llm_summary_max_chars,
        )
        result = result.model_copy(update={"developer_id": merge_request.author})
        report = render_review_report(result)
        record = store_review_result(
            result,
            report=report,
            database_path=database_path,
            review_scope="gitlab-webhook",
            mr_id=merge_request.merge_request_id,
            developer_id=merge_request.author,
        )
        comment_posted = _post_review_comment(
            commenter=review_commenter,
            merge_request=merge_request,
            report=report,
        )
    finally:
        sync.cleanup(target)
    return _triggered_review(
        merge_request=merge_request,
        record=record,
        comment_posted=comment_posted,
    )


def _post_review_comment(
    *,
    commenter: GitLabReviewCommenter | None,
    merge_request: GitLabMergeRequestWebhook,
    report: str,
) -> bool:
    if commenter is None:
        return False
    if merge_request.merge_request_id is None:
        msg = "GitLab Merge Request IID is required to post review comments."
        raise ValueError(msg)
    commenter.post_merge_request_note(
        project_ref=merge_request.project_ref,
        merge_request_iid=merge_request.merge_request_id,
        body=report,
    )
    return True


def _triggered_review(
    *,
    merge_request: GitLabMergeRequestWebhook,
    record: ReviewRunRecord,
    comment_posted: bool,
) -> GitLabTriggeredReview:
    return GitLabTriggeredReview(
        merge_request=merge_request,
        review_id=record.review_id,
        risk=record.risk,
        comment_posted=comment_posted,
    )
