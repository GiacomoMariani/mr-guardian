"""Developer LLM profile generation orchestration."""

from datetime import timedelta
from time import perf_counter

from mr_guardian.core.lead_dashboard import prepare_lead_developer_detail
from mr_guardian.models.developer_profile import DeveloperProfileInput
from mr_guardian.models.history import ReviewRunRecord
from mr_guardian.models.review import LlmDeveloperProfile, LlmSummaryStatus
from mr_guardian.storage import ReviewHistoryStore
from mr_guardian.summarizer_ai import (
    LlmDeveloperProfileRateLimitError,
    LlmDeveloperProfileRunner,
)


def maybe_update_developer_profile_snapshot(
    *,
    store: ReviewHistoryStore,
    record: ReviewRunRecord,
    developer_profile_runner: LlmDeveloperProfileRunner | None,
    lookback_days: int,
    max_chars: int,
) -> ReviewRunRecord:
    """Generate and store a developer profile snapshot when configured."""
    if developer_profile_runner is None:
        return record

    profile_input = build_developer_profile_input(
        store=store,
        record=record,
        lookback_days=lookback_days,
    )
    if profile_input is None:
        return record

    profile = _generate_profile_snapshot(
        profile_input,
        developer_profile_runner=developer_profile_runner,
        max_chars=max_chars,
    )
    return store.update_developer_profile(
        review_id=record.review_id,
        developer_profile=profile,
    )


def build_developer_profile_input(
    *,
    store: ReviewHistoryStore,
    record: ReviewRunRecord,
    lookback_days: int,
) -> DeveloperProfileInput | None:
    """Build recent developer history context for the LLM profile generator."""
    end_at = record.timestamp
    start_at = end_at - timedelta(days=lookback_days)
    review_runs = store.review_runs_for_developer(
        developer_id=record.developer_id,
        start_at=start_at,
        end_at=end_at,
    )
    detail = prepare_lead_developer_detail(
        developer_id=record.developer_id,
        review_runs=review_runs,
        start_at=start_at,
        end_at=end_at,
    )
    if detail is None:
        return None
    return DeveloperProfileInput(
        developer_id=record.developer_id,
        lookback_days=lookback_days,
        start_at=start_at,
        end_at=end_at,
        summary=detail.developer,
        review_runs=detail.review_runs,
    )


def _generate_profile_snapshot(
    profile_input: DeveloperProfileInput,
    *,
    developer_profile_runner: LlmDeveloperProfileRunner,
    max_chars: int,
) -> LlmDeveloperProfile:
    started_at = perf_counter()
    try:
        output = developer_profile_runner.profile(
            developer=profile_input,
            max_chars=max_chars,
        )
    except LlmDeveloperProfileRateLimitError as exc:
        return _profile_result(
            status="rate_limited",
            runner=developer_profile_runner,
            started_at=started_at,
            lookback_days=profile_input.lookback_days,
            text=None,
            error_message=str(exc),
        )
    except Exception as exc:
        return _profile_result(
            status="failed",
            runner=developer_profile_runner,
            started_at=started_at,
            lookback_days=profile_input.lookback_days,
            text=None,
            error_message=str(exc),
        )

    return _profile_result(
        status="succeeded",
        runner=developer_profile_runner,
        started_at=started_at,
        lookback_days=profile_input.lookback_days,
        text=output.profile,
        error_message=None,
    )


def _profile_result(
    *,
    status: LlmSummaryStatus,
    runner: LlmDeveloperProfileRunner,
    started_at: float,
    lookback_days: int,
    text: str | None,
    error_message: str | None,
) -> LlmDeveloperProfile:
    usage = runner.last_token_usage
    return LlmDeveloperProfile(
        status=status,
        provider=runner.provider_name,
        model=runner.model_name,
        duration_ms=max(0, round((perf_counter() - started_at) * 1000)),
        lookback_days=lookback_days,
        text=text,
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        total_tokens=usage.total_tokens if usage is not None else None,
        error_message=error_message,
    )
