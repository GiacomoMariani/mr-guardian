"""In-memory webhook review job tracking."""

from collections.abc import Callable
from threading import BoundedSemaphore, Lock
from uuid import uuid4

from pydantic import BaseModel, ConfigDict


class WebhookReviewJob(BaseModel):
    """Status for one asynchronous webhook-triggered review."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    status: str
    detail: str = ""
    review_id: int | None = None
    risk: str | None = None


class WebhookReviewJobStore:
    """Thread-safe in-memory store for webhook review jobs."""

    def __init__(self, *, max_concurrent_jobs: int = 1) -> None:
        self._jobs: dict[str, WebhookReviewJob] = {}
        self._lock = Lock()
        self._semaphore = BoundedSemaphore(max_concurrent_jobs)

    def create(self) -> WebhookReviewJob:
        """Create a queued job."""
        job = WebhookReviewJob(job_id=uuid4().hex, status="queued")
        self._set(job)
        return job

    def get(self, job_id: str) -> WebhookReviewJob | None:
        """Return one job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def run(self, job_id: str, worker: Callable[[], tuple[int, str]]) -> None:
        """Run a job with bounded concurrency and record the outcome."""
        self._set(WebhookReviewJob(job_id=job_id, status="waiting"))
        with self._semaphore:
            self._set(WebhookReviewJob(job_id=job_id, status="running"))
            try:
                review_id, risk = worker()
            except Exception as exc:
                self._set(
                    WebhookReviewJob(
                        job_id=job_id,
                        status="failed",
                        detail=str(exc),
                    )
                )
                return

            self._set(
                WebhookReviewJob(
                    job_id=job_id,
                    status="succeeded",
                    review_id=review_id,
                    risk=risk,
                )
            )

    def _set(self, job: WebhookReviewJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job


webhook_review_jobs = WebhookReviewJobStore()
