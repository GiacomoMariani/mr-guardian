"""FastAPI service entrypoint for MR Guardian."""

import logging
from hmac import compare_digest
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from mr_guardian.config import Settings, get_settings
from mr_guardian.core.gitlab_reviews import review_gitlab_merge_request
from mr_guardian.core.gitlab_webhooks import process_gitlab_webhook
from mr_guardian.core.webhook_jobs import WebhookReviewJob, webhook_review_jobs
from mr_guardian.models.gitlab import GitLabMergeRequestWebhook
from mr_guardian.providers.gitlab_api import GitLabMergeRequestCommenter
from mr_guardian.providers.gitlab_sync import GitLabRepositorySyncError
from mr_guardian.summarizer_ai import create_llm_rule_runner

logger = logging.getLogger(__name__)

app = FastAPI(title="MR Guardian")


@app.post("/webhooks/gitlab", status_code=202)
async def gitlab_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_gitlab_event: str | None = Header(default=None),
    x_gitlab_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Receive GitLab Merge Request webhook events."""
    settings = get_settings()
    configured_secret = settings.gitlab_webhook_secret
    if configured_secret and not compare_digest(x_gitlab_token or "", configured_secret):
        raise HTTPException(status_code=401, detail="Invalid GitLab webhook token.")

    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object payload.")

    result = process_gitlab_webhook(event_name=x_gitlab_event, payload=payload)
    if not result.accepted or result.merge_request is None:
        return {"status": "ignored", "reason": result.reason}

    mr = result.merge_request
    logger.info(
        "GitLab MR webhook accepted: project=%s title=%s url=%s source=%s "
        "target=%s author=%s action=%s",
        mr.project_name,
        mr.title,
        mr.url,
        mr.source_branch,
        mr.target_branch,
        mr.author,
        mr.action,
    )
    job = webhook_review_jobs.create()
    background_tasks.add_task(_run_gitlab_review_job, job.job_id, mr)
    return {
        "status": "queued",
        "job_id": job.job_id,
        "merge_request": mr.model_dump(),
    }


@app.get("/webhook-jobs/{job_id}")
async def webhook_job(job_id: str) -> WebhookReviewJob:
    """Return status for one webhook-triggered review job."""
    job = webhook_review_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Webhook review job not found.")
    return job


def _run_gitlab_review_job(job_id: str, mr: GitLabMergeRequestWebhook) -> None:
    def worker() -> tuple[int, str]:
        settings = get_settings()
        try:
            triggered_review = review_gitlab_merge_request(
                mr,
                repo_path=settings.repo_path,
                worktree_dir=settings.gitlab_worktree_dir,
                remote_name=settings.gitlab_remote_name,
                policy_directory=settings.policy_dir,
                database_path=settings.history_db_path,
                llm_rule_runner=create_llm_rule_runner(
                    provider=settings.llm_provider,
                    openai_api_key=settings.openai_api_key,
                    openai_model=settings.openai_model,
                    openai_timeout_seconds=settings.openai_timeout_seconds,
                    openai_max_retries=settings.openai_max_retries,
                ),
                review_commenter=_review_commenter(settings),
            )
        except GitLabRepositorySyncError:
            logger.exception("GitLab MR webhook review could not prepare repository state.")
            raise
        except Exception:
            logger.exception("GitLab MR webhook review failed.")
            raise

        return triggered_review.review_id, triggered_review.risk

    webhook_review_jobs.run(job_id, worker)


def _review_commenter(settings: Settings) -> GitLabMergeRequestCommenter | None:
    if not settings.gitlab_post_review_comments:
        return None
    return GitLabMergeRequestCommenter(
        base_url=settings.gitlab_base_url,
        token=settings.gitlab_token,
        timeout_seconds=settings.gitlab_api_timeout_seconds,
    )
