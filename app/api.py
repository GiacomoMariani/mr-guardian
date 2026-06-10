"""FastAPI service entrypoint for MR Guardian."""

import logging
from collections.abc import Callable
from hmac import compare_digest
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from pydantic import TypeAdapter, ValidationError

from mr_guardian.config import Settings, get_settings
from mr_guardian.core.dashboard_eta import (
    DashboardEtaNotePayload,
    dashboard_eta_note_payload_schema,
    load_dashboard_eta_note,
    recent_dashboard_eta_notes,
    set_dashboard_eta_note,
)
from mr_guardian.core.developer_review import (
    load_developer_llm_review,
    load_recent_developer_llm_reviews,
    manual_developer_llm_review_payload_schema,
    store_developer_llm_review_payload,
)
from mr_guardian.core.gitlab_reviews import review_gitlab_merge_request
from mr_guardian.core.gitlab_webhooks import process_gitlab_webhook
from mr_guardian.core.history_reset import reset_all_history
from mr_guardian.core.manual_review import (
    ManualReviewError,
    ManualReviewPayload,
    manual_review_payload_schema,
    store_manual_review_payload,
)
from mr_guardian.core.review_components import (
    ReviewComponentNotFoundError,
    feed_review_evaluations,
    feed_review_findings,
    feed_review_llm_metrics,
    feed_review_policy_summaries,
    feed_review_triggered_rules,
    set_review_developer_profile,
    set_review_llm_summary,
)
from mr_guardian.core.review_deletion import ReviewNotFoundError, delete_stored_review
from mr_guardian.core.review_finality import (
    ReviewFinalityNotFoundError,
    ReviewFinalityPayload,
    set_stored_review_finality,
)
from mr_guardian.core.webhook_jobs import WebhookReviewJob, webhook_review_jobs
from mr_guardian.core.weekly_llm_review import (
    load_recent_weekly_llm_reviews,
    load_weekly_llm_review,
    manual_weekly_llm_review_payload_schema,
    store_weekly_llm_review_payload,
)
from mr_guardian.models.developer_review import DeveloperLlmReviewCreate
from mr_guardian.models.gitlab import GitLabMergeRequestWebhook
from mr_guardian.models.history import (
    ReviewPolicySummary,
    ReviewRunCreate,
    ReviewRunRecord,
    review_run_record_schema,
)
from mr_guardian.models.review import (
    Finding,
    LlmDeveloperProfile,
    LlmReviewSummary,
    LlmRuleMetric,
    ReviewEvaluation,
)
from mr_guardian.models.weekly_review import WeeklyLlmReviewCreate
from mr_guardian.providers.gitlab_api import GitLabMergeRequestCommenter
from mr_guardian.providers.gitlab_sync import GitLabRepositorySyncError
from mr_guardian.storage import ReviewHistoryStore
from mr_guardian.summarizer_ai import (
    create_llm_review_summary_runner,
    create_llm_rule_runner,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="MR Guardian")

_FINDINGS_ADAPTER = TypeAdapter(list[Finding])
_EVALUATIONS_ADAPTER = TypeAdapter(list[ReviewEvaluation])
_POLICY_SUMMARIES_ADAPTER = TypeAdapter(list[ReviewPolicySummary])
_LLM_METRICS_ADAPTER = TypeAdapter(list[LlmRuleMetric])
_TRIGGERED_RULES_ADAPTER = TypeAdapter(list[str])


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Return a lightweight health check response."""
    return {"status": "ok"}


@app.get("/reviews/manual/schema")
async def manual_review_schema() -> dict[str, Any]:
    """Return the manual review submission JSON schema."""
    return manual_review_payload_schema()


@app.get("/reviews/schema")
async def review_schema() -> dict[str, Any]:
    """Return the stored review run JSON schema."""
    return review_run_record_schema()


@app.get("/weekly-llm-reviews/schema")
async def weekly_llm_review_schema() -> dict[str, Any]:
    """Return the manual weekly LLM review submission JSON schema."""
    return manual_weekly_llm_review_payload_schema()


@app.get("/weekly-llm-reviews")
async def list_weekly_llm_reviews(limit: int = 20) -> Any:
    """Return recent weekly LLM reviews, most recent first."""
    return load_recent_weekly_llm_reviews(
        database_path=get_settings().history_db_path,
        limit=limit,
    )


@app.get("/weekly-llm-reviews/{weekly_review_id}")
async def get_weekly_llm_review(weekly_review_id: int) -> Any:
    """Return one stored weekly LLM review by ID."""
    record = load_weekly_llm_review(
        database_path=get_settings().history_db_path,
        weekly_review_id=weekly_review_id,
    )
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Weekly LLM review {weekly_review_id} was not found.",
        )
    return record


@app.get("/developer-llm-reviews/schema")
async def developer_llm_review_schema() -> dict[str, Any]:
    """Return the manual developer LLM review submission JSON schema."""
    return manual_developer_llm_review_payload_schema()


@app.get("/developer-llm-reviews")
async def list_developer_llm_reviews(developer: str | None = None, limit: int = 20) -> Any:
    """Return recent developer LLM reviews, most recent first (optionally one developer)."""
    return load_recent_developer_llm_reviews(
        database_path=get_settings().history_db_path,
        developer_id=developer,
        limit=limit,
    )


@app.get("/developer-llm-reviews/{developer_review_id}")
async def get_developer_llm_review(developer_review_id: int) -> Any:
    """Return one stored developer LLM review by ID."""
    record = load_developer_llm_review(
        database_path=get_settings().history_db_path,
        developer_review_id=developer_review_id,
    )
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Developer LLM review {developer_review_id} was not found.",
        )
    return record


@app.get("/dashboard/eta-note/schema")
async def eta_note_schema() -> dict[str, Any]:
    """Return the dashboard ETA note submission JSON schema."""
    return dashboard_eta_note_payload_schema()


@app.get("/dashboard/eta-note")
async def get_eta_note() -> Any:
    """Return the current dashboard ETA note."""
    return load_dashboard_eta_note(database_path=get_settings().history_db_path)


@app.get("/dashboard/eta-note/history")
async def get_eta_note_history(limit: int = 20) -> Any:
    """Return recent dashboard ETA notes, most recent first."""
    return recent_dashboard_eta_notes(
        database_path=get_settings().history_db_path,
        limit=limit,
    )


@app.post("/dashboard/eta-note")
async def post_eta_note(
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> Any:
    """Overwrite the dashboard ETA note."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    try:
        raw_payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object payload.")

    try:
        payload = DashboardEtaNotePayload.model_validate(raw_payload)
        return set_dashboard_eta_note(
            payload,
            database_path=settings.history_db_path,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ETA note structure: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/reviews/manual", status_code=201)
async def submit_manual_review(request: Request) -> dict[str, Any]:
    """Validate and store a manually written review."""
    try:
        raw_payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object payload.")

    try:
        payload = ManualReviewPayload.model_validate(raw_payload)
        record = store_manual_review_payload(
            payload,
            database_path=get_settings().history_db_path,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid manual review structure: {exc}",
        ) from exc
    except ManualReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "stored",
        "review_id": record.review_id,
        "risk": record.risk,
        "score": record.review_score,
        "ticket_key": record.ticket_key,
    }


@app.post("/reviews", status_code=201)
async def create_review_run(
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Create one review run from a verbatim payload (admin only).

    The canonical entry point for feeding a review: the supplied ReviewRunCreate is
    stored as-is and the new review_id is returned, which the per-component feed
    endpoints (/reviews/{id}/findings, /evaluations, /llm-summary, ...) then target.
    Child collections may be supplied inline here or fed separately afterward.
    """
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    raw_payload = await _read_json_object(request)
    try:
        run = ReviewRunCreate.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid review run structure: {exc}",
        ) from exc

    record = _store_review_run(run, settings)
    return {
        "status": "created",
        "review_id": record.review_id,
        "ticket_key": record.ticket_key,
        "risk": record.risk,
        "score": record.review_score,
        "is_final": record.is_final,
    }


@app.post("/reviews/import", status_code=201)
async def import_review_run(
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Import one fully-formed review run, preserving all fields (admin only).

    Identical storage to POST /reviews, retained as the named entry point for porting
    an existing history database into a fresh deployment: the supplied ReviewRunCreate
    is stored verbatim (ticket key and LLM annotations preserved, unlike
    /reviews/manual).
    """
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    raw_payload = await _read_json_object(request)
    try:
        run = ReviewRunCreate.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid review run structure: {exc}",
        ) from exc

    record = _store_review_run(run, settings)
    return {
        "status": "imported",
        "review_id": record.review_id,
        "ticket_key": record.ticket_key,
        "risk": record.risk,
        "score": record.review_score,
        "is_final": record.is_final,
    }


@app.post("/weekly-llm-reviews/manual", status_code=201)
async def submit_weekly_llm_review(
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Validate and store an externally generated weekly LLM review."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    try:
        raw_payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object payload.")

    try:
        payload = WeeklyLlmReviewCreate.model_validate(raw_payload)
        record = store_weekly_llm_review_payload(
            payload,
            database_path=settings.history_db_path,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid weekly LLM review structure: {exc}",
        ) from exc

    return {
        "status": "stored",
        "weekly_review_id": record.weekly_review_id,
        "week_start": record.week_start.isoformat(),
        "week_end": record.week_end.isoformat(),
        "result": record.result,
        "score": record.score,
    }


@app.post("/developer-llm-reviews/manual", status_code=201)
async def submit_developer_llm_review(
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Validate and store an externally generated biweekly developer LLM review."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    try:
        raw_payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object payload.")

    try:
        payload = DeveloperLlmReviewCreate.model_validate(raw_payload)
        record = store_developer_llm_review_payload(
            payload,
            database_path=settings.history_db_path,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid developer LLM review structure: {exc}",
        ) from exc

    return {
        "status": "stored",
        "developer_review_id": record.developer_review_id,
        "developer_id": record.developer_id,
        "period_start": record.period_start.isoformat(),
        "period_end": record.period_end.isoformat(),
        "result": record.result,
        "score": record.score,
    }


@app.delete("/reviews/{review_id}")
async def delete_review(
    review_id: int,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Delete one stored review from history."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    try:
        deleted_review_id = delete_stored_review(
            review_id=review_id,
            database_path=settings.history_db_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "deleted", "review_id": deleted_review_id}


@app.post("/reviews/{review_id}/finality")
async def set_review_finality(
    review_id: int,
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> Any:
    """Set one stored review's finality flag."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    try:
        raw_payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object payload.")

    try:
        payload = ReviewFinalityPayload.model_validate(raw_payload)
        return set_stored_review_finality(
            review_id=review_id,
            is_final=payload.final,
            database_path=settings.history_db_path,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid review finality structure: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ReviewFinalityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/reviews/{review_id}/findings")
async def feed_review_findings_endpoint(
    review_id: int,
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Replace the findings stored for one review run (idempotent feed)."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    raw_payload = await _read_json_array(request)
    try:
        findings = _FINDINGS_ADAPTER.validate_python(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid findings structure: {exc}",
        ) from exc

    record = _feed_component(
        lambda: feed_review_findings(
            review_id=review_id,
            findings=findings,
            database_path=settings.history_db_path,
        )
    )
    return {
        "status": "stored",
        "review_id": record.review_id,
        "finding_count": len(record.findings),
    }


@app.post("/reviews/{review_id}/triggered-rules")
async def feed_review_triggered_rules_endpoint(
    review_id: int,
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Replace the triggered-rule IDs stored for one review run."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    raw_payload = await _read_json_array(request)
    try:
        rule_ids = _TRIGGERED_RULES_ADAPTER.validate_python(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid triggered rules structure: {exc}",
        ) from exc

    record = _feed_component(
        lambda: feed_review_triggered_rules(
            review_id=review_id,
            rule_ids=rule_ids,
            database_path=settings.history_db_path,
        )
    )
    return {
        "status": "stored",
        "review_id": record.review_id,
        "triggered_rule_count": len(record.triggered_rule_ids),
    }


@app.post("/reviews/{review_id}/evaluations")
async def feed_review_evaluations_endpoint(
    review_id: int,
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Replace the evaluation summaries stored for one review run."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    raw_payload = await _read_json_array(request)
    try:
        evaluations = _EVALUATIONS_ADAPTER.validate_python(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid evaluations structure: {exc}",
        ) from exc

    record = _feed_component(
        lambda: feed_review_evaluations(
            review_id=review_id,
            evaluations=evaluations,
            database_path=settings.history_db_path,
        )
    )
    return {
        "status": "stored",
        "review_id": record.review_id,
        "evaluation_count": len(record.evaluations),
    }


@app.post("/reviews/{review_id}/policies")
async def feed_review_policies_endpoint(
    review_id: int,
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Replace the policy summaries stored for one review run."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    raw_payload = await _read_json_array(request)
    try:
        policy_summaries = _POLICY_SUMMARIES_ADAPTER.validate_python(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid policy summaries structure: {exc}",
        ) from exc

    record = _feed_component(
        lambda: feed_review_policy_summaries(
            review_id=review_id,
            policy_summaries=policy_summaries,
            database_path=settings.history_db_path,
        )
    )
    return {
        "status": "stored",
        "review_id": record.review_id,
        "policy_count": len(record.policy_summaries),
    }


@app.post("/reviews/{review_id}/llm-metrics")
async def feed_review_llm_metrics_endpoint(
    review_id: int,
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Replace the LLM rule metrics stored for one review run."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    raw_payload = await _read_json_array(request)
    try:
        metrics = _LLM_METRICS_ADAPTER.validate_python(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid LLM metrics structure: {exc}",
        ) from exc

    record = _feed_component(
        lambda: feed_review_llm_metrics(
            review_id=review_id,
            metrics=metrics,
            database_path=settings.history_db_path,
        )
    )
    return {
        "status": "stored",
        "review_id": record.review_id,
        "llm_metric_count": len(record.llm_metrics),
    }


@app.put("/reviews/{review_id}/llm-summary")
async def feed_review_llm_summary_endpoint(
    review_id: int,
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Attach or overwrite the LLM review summary for one review run."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    raw_payload = await _read_json_object(request)
    try:
        llm_summary = LlmReviewSummary.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid LLM summary structure: {exc}",
        ) from exc

    record = _feed_component(
        lambda: set_review_llm_summary(
            review_id=review_id,
            llm_summary=llm_summary,
            database_path=settings.history_db_path,
        )
    )
    return {
        "status": "updated",
        "review_id": record.review_id,
        "llm_summary_status": record.llm_summary.status if record.llm_summary is not None else None,
    }


@app.put("/reviews/{review_id}/developer-profile")
async def feed_review_developer_profile_endpoint(
    review_id: int,
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Attach or overwrite the developer profile snapshot for one review run."""
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    raw_payload = await _read_json_object(request)
    try:
        developer_profile = LlmDeveloperProfile.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid developer profile structure: {exc}",
        ) from exc

    record = _feed_component(
        lambda: set_review_developer_profile(
            review_id=review_id,
            developer_profile=developer_profile,
            database_path=settings.history_db_path,
        )
    )
    return {
        "status": "updated",
        "review_id": record.review_id,
        "developer_profile_status": record.developer_profile.status
        if record.developer_profile is not None
        else None,
    }


@app.post("/admin/reset")
async def reset_all_data(
    request: Request,
    x_mr_guardian_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Delete ALL stored data — reviews, weekly reviews, and ETA notes (irreversible).

    Admin-gated and guarded by an explicit confirmation flag: the request body must be
    {"confirm": true}.
    """
    settings = get_settings()
    _verify_admin_token(settings, x_mr_guardian_admin_token)

    raw_payload = await _read_json_object(request)
    if raw_payload.get("confirm") is not True:
        raise HTTPException(
            status_code=400,
            detail='Reset requires {"confirm": true} in the request body.',
        )

    return reset_all_history(database_path=settings.history_db_path).model_dump()


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
                llm_summary_runner=create_llm_review_summary_runner(
                    enabled=settings.llm_summary_enabled,
                    provider=settings.llm_provider,
                    openai_api_key=settings.openai_api_key,
                    openai_model=settings.openai_model,
                    openai_timeout_seconds=settings.openai_timeout_seconds,
                    openai_max_retries=settings.openai_max_retries,
                ),
                llm_summary_max_chars=settings.llm_summary_max_chars,
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


def _store_review_run(run: ReviewRunCreate, settings: Settings) -> ReviewRunRecord:
    store = ReviewHistoryStore(settings.history_db_path)
    try:
        return store.store_review_run(run)
    finally:
        store.close()


def _feed_component(operation: Callable[[], ReviewRunRecord]) -> ReviewRunRecord:
    try:
        return operation()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ReviewComponentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _read_json_object(request: Request) -> dict[str, Any]:
    try:
        raw_payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc
    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object payload.")
    return raw_payload


async def _read_json_array(request: Request) -> list[Any]:
    try:
        raw_payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc
    if not isinstance(raw_payload, list):
        raise HTTPException(status_code=400, detail="Expected JSON array payload.")
    return raw_payload


def _verify_admin_token(settings: Settings, supplied_token: str | None) -> None:
    if settings.admin_token and not compare_digest(
        supplied_token or "",
        settings.admin_token,
    ):
        raise HTTPException(status_code=401, detail="Invalid MR Guardian admin token.")
