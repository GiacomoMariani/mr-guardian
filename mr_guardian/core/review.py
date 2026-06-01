"""Review orchestration entry points."""

from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ConfigDict

from mr_guardian.core.engine import calculate_risk, count_findings, run_review
from mr_guardian.models.policy import Policy
from mr_guardian.models.review import (
    EngineReviewResult,
    LlmReviewSummary,
    LlmSummaryStatus,
    summarize_review_evaluations,
)
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.policies import load_policy, policy_paths_from_directory, resolve_policy_directory
from mr_guardian.providers import LocalGitProvider
from mr_guardian.rules import RuleRegistry, default_rule_registry
from mr_guardian.summarizer_ai import (
    DisabledLlmRuleRunner,
    LlmReviewSummaryRunner,
    LlmRuleRunner,
    LlmSummaryRateLimitError,
    ReviewSummaryInput,
)


class ReviewRequest(BaseModel):
    """Inputs needed to run a merge request review."""

    model_config = ConfigDict(frozen=True)

    base: str
    policy_directory: Path = Path("sources/yaml")
    review_scope: str = "local-all-policies"
    title: str = ""
    description: str = ""


class PolicyReviewResult(BaseModel):
    """Review result for one policy file."""

    model_config = ConfigDict(frozen=True)

    policy_path: Path
    policy_version: int
    enabled_rule_count: int
    disabled_rule_count: int
    engine_result: EngineReviewResult


class ReviewResult(BaseModel):
    """Result of a merge request review."""

    model_config = ConfigDict(frozen=True)

    base_ref: str
    policy_directory: Path
    policy_results: list[PolicyReviewResult]
    developer_id: str = "unknown"
    review_input: ReviewInput
    engine_result: EngineReviewResult
    llm_summary: LlmReviewSummary | None = None

    @property
    def risk(self) -> str:
        """Return the calculated review risk."""
        return self.engine_result.risk

    @property
    def policy_version(self) -> int:
        """Return the highest policy version evaluated in this review."""
        return max(
            (policy_result.policy_version for policy_result in self.policy_results),
            default=0,
        )


def review_merge_request(
    request: ReviewRequest,
    *,
    repo_path: str | Path = ".",
    rule_registry: RuleRegistry | None = None,
    llm_rule_runner: LlmRuleRunner | None = None,
    llm_summary_runner: LlmReviewSummaryRunner | None = None,
    llm_summary_max_chars: int = 700,
) -> ReviewResult:
    """Run the local review pipeline for a merge request."""
    requested_policy_directory = Path(request.policy_directory)
    provider = LocalGitProvider(repo_path)
    review_input = provider.collect(request.base).model_copy(
        update={
            "review_scope": request.review_scope,
            "title": request.title,
            "description": request.description,
        }
    )
    registry = rule_registry or default_rule_registry()
    resolved_llm_rule_runner = llm_rule_runner or DisabledLlmRuleRunner()

    with resolve_policy_directory(requested_policy_directory) as resolved_policy_directory:
        policy_paths = policy_paths_from_directory(resolved_policy_directory)
        policy_results = [
            _review_policy(
                policy_path=policy_path,
                review_input=review_input,
                rule_registry=registry,
                llm_rule_runner=resolved_llm_rule_runner,
            )
            for policy_path in policy_paths
        ]
    engine_result = _combine_engine_results(
        [policy_result.engine_result for policy_result in policy_results]
    )

    result = ReviewResult(
        base_ref=request.base,
        policy_directory=resolved_policy_directory,
        policy_results=policy_results,
        developer_id=provider.developer_id(),
        review_input=review_input,
        engine_result=engine_result,
    )
    if llm_summary_runner is None:
        return result
    return _with_llm_summary(
        result,
        llm_summary_runner=llm_summary_runner,
        max_chars=llm_summary_max_chars,
    )


def _review_policy(
    *,
    policy_path: Path,
    review_input: ReviewInput,
    rule_registry: RuleRegistry,
    llm_rule_runner: LlmRuleRunner,
) -> PolicyReviewResult:
    policy = load_policy(policy_path)
    return PolicyReviewResult(
        policy_path=policy_path,
        policy_version=policy.version,
        enabled_rule_count=_enabled_rule_count(policy),
        disabled_rule_count=_disabled_rule_count(policy),
        engine_result=run_review(
            policy=policy,
            review_input=review_input,
            rule_registry=rule_registry,
            llm_rule_runner=llm_rule_runner,
        ),
    )


def _combine_engine_results(results: list[EngineReviewResult]) -> EngineReviewResult:
    findings = [
        finding
        for result in results
        for finding in result.findings
    ]
    counts = count_findings(findings)
    return EngineReviewResult(
        risk=calculate_risk(counts),
        findings=findings,
        counts=counts,
        llm_metrics=[
            metric
            for result in results
            for metric in result.llm_metrics
        ],
        evaluations=summarize_review_evaluations(findings),
    )


def _with_llm_summary(
    result: ReviewResult,
    *,
    llm_summary_runner: LlmReviewSummaryRunner,
    max_chars: int,
) -> ReviewResult:
    started_at = perf_counter()
    try:
        summary_output = llm_summary_runner.summarize(
            review=ReviewSummaryInput(
                base_ref=result.base_ref,
                developer_id=result.developer_id,
                review_input=result.review_input,
                risk=result.engine_result.risk,
                counts=result.engine_result.counts,
                findings=result.engine_result.findings,
                evaluations=result.engine_result.evaluations
                or summarize_review_evaluations(result.engine_result.findings),
            ),
            max_chars=max_chars,
        )
    except LlmSummaryRateLimitError as exc:
        summary = _llm_summary_result(
            status="rate_limited",
            runner=llm_summary_runner,
            started_at=started_at,
            text=None,
            error_message=str(exc),
        )
    except Exception as exc:
        summary = _llm_summary_result(
            status="failed",
            runner=llm_summary_runner,
            started_at=started_at,
            text=None,
            error_message=str(exc),
        )
    else:
        summary = _llm_summary_result(
            status="succeeded",
            runner=llm_summary_runner,
            started_at=started_at,
            text=summary_output.summary,
            score=summary_output.score,
            error_message=None,
        )
    return result.model_copy(update={"llm_summary": summary})


def _llm_summary_result(
    *,
    status: LlmSummaryStatus,
    runner: LlmReviewSummaryRunner,
    started_at: float,
    text: str | None,
    error_message: str | None,
    score: int | None = None,
) -> LlmReviewSummary:
    usage = runner.last_token_usage
    return LlmReviewSummary(
        status=status,
        provider=runner.provider_name,
        model=runner.model_name,
        duration_ms=max(0, round((perf_counter() - started_at) * 1000)),
        text=text,
        score=score,
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        total_tokens=usage.total_tokens if usage is not None else None,
        error_message=error_message,
    )


def _enabled_rule_count(policy: Policy) -> int:
    return sum(1 for rule in policy.rules if rule.enabled)


def _disabled_rule_count(policy: Policy) -> int:
    return sum(1 for rule in policy.rules if not rule.enabled)
