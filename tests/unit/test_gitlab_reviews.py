from pathlib import Path

from mr_guardian.core.gitlab_reviews import review_gitlab_merge_request
from mr_guardian.core.review import PolicyReviewResult, ReviewRequest, ReviewResult
from mr_guardian.models.gitlab import GitLabMergeRequestWebhook
from mr_guardian.models.review import EngineReviewResult, Finding, FindingCounts
from mr_guardian.models.review_input import ChangedFile, DiffHunk, DiffLine, ReviewInput
from mr_guardian.providers.gitlab_sync import GitLabSyncedReviewTarget
from mr_guardian.storage import ReviewHistoryStore
from mr_guardian.summarizer_ai import DisabledLlmRuleRunner


def test_gitlab_webhook_triggers_local_review_and_stores_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_request: ReviewRequest | None = None
    sync_calls: list[str] = []

    def fake_review_merge_request(
        request: ReviewRequest,
        **_: object,
    ) -> ReviewResult:
        nonlocal captured_request
        captured_request = request
        return ReviewResult(
            base_ref=request.base,
            policy_directory=request.policy_directory,
            policy_results=[
                PolicyReviewResult(
                    policy_path=request.policy_directory / "python-policy.yml",
                    policy_version=1,
                    enabled_rule_count=1,
                    disabled_rule_count=0,
                    engine_result=EngineReviewResult(
                        risk="warning",
                        findings=[finding()],
                        counts=FindingCounts(warning=1),
                    ),
                )
            ],
            developer_id="Jane Developer",
            review_input=ReviewInput(
                base_ref=request.base,
                title=request.title,
                description=request.description,
                changed_files=[
                    ChangedFile(
                        path=Path("mr_guardian/example.py"),
                        status="modified",
                        hunks=[
                            DiffHunk(
                                old_start=1,
                                old_count=0,
                                new_start=1,
                                new_count=1,
                                lines=[
                                    DiffLine(
                                        kind="addition",
                                        content="print('ready')",
                                        old_line_number=None,
                                        new_line_number=1,
                                    )
                                ],
                            )
                        ],
                    )
                ],
            ),
            engine_result=EngineReviewResult(
                risk="warning",
                findings=[finding()],
                counts=FindingCounts(warning=1),
            ),
        )

    monkeypatch.setattr(
        "mr_guardian.core.gitlab_reviews.review_merge_request",
        fake_review_merge_request,
    )
    monkeypatch.setattr(
        "mr_guardian.core.gitlab_reviews.GitLabRepositorySync",
        fake_sync(sync_calls, tmp_path / "worktree"),
    )
    database_path = tmp_path / "history.sqlite"

    result = review_gitlab_merge_request(
        GitLabMergeRequestWebhook(
            project_id="42",
            project_name="team/MRGuardian",
            title="TK-234 Add webhook review",
            description="## Test Plan\n- Ran webhook test",
            url="https://gitlab.com/team/MRGuardian/-/merge_requests/7",
            source_branch="feature/webhooks",
            target_branch="main",
            author="Jane Developer",
            action="open",
            merge_request_id="7",
        ),
        repo_path=tmp_path,
        worktree_dir=tmp_path / "worktrees",
        remote_name="origin",
        policy_directory=tmp_path,
        database_path=database_path,
        llm_rule_runner=DisabledLlmRuleRunner(),
    )

    store = ReviewHistoryStore(database_path)
    recent_runs = store.recent_review_runs()
    store.close()

    assert captured_request == ReviewRequest(
        base="refs/remotes/origin/main",
        policy_directory=tmp_path,
        review_scope="gitlab-webhook",
        title="TK-234 Add webhook review",
        description="## Test Plan\n- Ran webhook test",
    )
    assert sync_calls == ["prepare", "cleanup"]
    assert result.review_id == 1
    assert result.risk == "warning"
    assert recent_runs[0].review_scope == "gitlab-webhook"
    assert recent_runs[0].mr_id == "7"
    assert recent_runs[0].branch_name == "refs/remotes/origin/main"
    assert recent_runs[0].developer_id == "Jane Developer"
    assert recent_runs[0].ticket_key == "TK-234"
    assert recent_runs[0].triggered_rule_ids == ["PYTHON-PRINT-001"]


def test_gitlab_webhook_posts_review_comment_when_configured(
    tmp_path: Path,
    monkeypatch,
) -> None:
    posted_comments: list[tuple[str, str, str]] = []

    def fake_review_merge_request(
        request: ReviewRequest,
        **_: object,
    ) -> ReviewResult:
        return ReviewResult(
            base_ref=request.base,
            policy_directory=request.policy_directory,
            policy_results=[],
            developer_id="Jane Developer",
            review_input=ReviewInput(base_ref=request.base, changed_files=[]),
            engine_result=EngineReviewResult(
                risk="none",
                findings=[],
                counts=FindingCounts(),
            ),
        )

    class FakeCommenter:
        def post_merge_request_note(
            self,
            *,
            project_ref: str,
            merge_request_iid: str,
            body: str,
        ) -> None:
            posted_comments.append((project_ref, merge_request_iid, body))

    monkeypatch.setattr(
        "mr_guardian.core.gitlab_reviews.review_merge_request",
        fake_review_merge_request,
    )
    monkeypatch.setattr(
        "mr_guardian.core.gitlab_reviews.GitLabRepositorySync",
        fake_sync([], tmp_path / "worktree"),
    )

    result = review_gitlab_merge_request(
        GitLabMergeRequestWebhook(
            project_id="42",
            project_name="team/MRGuardian",
            title="TK-234 Add webhook review",
            description="",
            url="https://gitlab.com/team/MRGuardian/-/merge_requests/7",
            source_branch="feature/webhooks",
            target_branch="main",
            author="Jane Developer",
            action="open",
            merge_request_id="7",
        ),
        repo_path=tmp_path,
        worktree_dir=tmp_path / "worktrees",
        remote_name="origin",
        policy_directory=tmp_path,
        database_path=tmp_path / "history.sqlite",
        llm_rule_runner=DisabledLlmRuleRunner(),
        review_commenter=FakeCommenter(),
    )

    assert result.comment_posted is True
    assert posted_comments[0][0] == "42"
    assert posted_comments[0][1] == "7"
    assert "# MR Guardian Review" in posted_comments[0][2]


def finding() -> Finding:
    return Finding(
        rule_id="PYTHON-PRINT-001",
        severity="warning",
        message="print calls should not be introduced.",
        source="python-policy.yml#PYTHON-PRINT-001",
        rule_type="deterministic",
        file_path=Path("mr_guardian/example.py"),
        line_number=1,
    )


def fake_sync(sync_calls: list[str], worktree_path: Path):
    class FakeSync:
        def __init__(
            self,
            *,
            repo_path: str | Path,
            worktree_dir: str | Path,
            remote_name: str,
        ) -> None:
            assert Path(repo_path).exists()
            assert Path(worktree_dir).name == "worktrees"
            assert remote_name == "origin"

        def prepare(self, merge_request: GitLabMergeRequestWebhook) -> GitLabSyncedReviewTarget:
            sync_calls.append("prepare")
            assert merge_request.source_branch == "feature/webhooks"
            assert merge_request.target_branch == "main"
            return GitLabSyncedReviewTarget(
                repo_path=worktree_path,
                base_ref="refs/remotes/origin/main",
            )

        def cleanup(self, target: GitLabSyncedReviewTarget) -> None:
            sync_calls.append("cleanup")
            assert target.repo_path == worktree_path

    return FakeSync
