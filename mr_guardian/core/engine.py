"""Shared deterministic review engine."""

from time import perf_counter

from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review import (
    EngineReviewResult,
    Finding,
    FindingCounts,
    LlmRuleMetric,
    LlmRuleStatus,
    RiskLevel,
)
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.registry import RuleRegistry
from mr_guardian.summarizer_ai import DisabledLlmRuleRunner, LlmRuleRateLimitError, LlmRuleRunner


def run_review(
    *,
    policy: Policy,
    review_input: ReviewInput,
    rule_registry: RuleRegistry,
    llm_rule_runner: LlmRuleRunner | None = None,
) -> EngineReviewResult:
    """Run enabled policy rules against review input."""
    context = RuleEvaluationContext(policy=policy, review_input=review_input)
    findings: list[Finding] = []
    llm_metrics: list[LlmRuleMetric] = []
    llm_runner = llm_rule_runner or DisabledLlmRuleRunner()

    for policy_rule in policy.rules:
        if not policy_rule.enabled:
            continue
        if policy_rule.type == "llm":
            rule_findings, metric = _evaluate_llm_rule(
                rule=policy_rule,
                review_input=review_input,
                llm_runner=llm_runner,
            )
            findings.extend(rule_findings)
            llm_metrics.append(metric)
            continue

        rule = rule_registry.get(policy_rule.id)
        if rule is None:
            continue

        rule_findings = rule.evaluate(context, policy_rule)
        findings.extend(
            finding.model_copy(
                update={
                    "rule_id": policy_rule.id,
                    "severity": policy_rule.severity,
                    "source": policy_rule.source,
                    "rule_type": policy_rule.type,
                }
            )
            for finding in rule_findings
        )

    counts = count_findings(findings)
    return EngineReviewResult(
        risk=calculate_risk(counts),
        findings=findings,
        counts=counts,
        llm_metrics=llm_metrics,
    )


def _evaluate_llm_rule(
    *,
    rule: PolicyRule,
    review_input: ReviewInput,
    llm_runner: LlmRuleRunner,
) -> tuple[list[Finding], LlmRuleMetric]:
    started_at = perf_counter()
    try:
        findings = llm_runner.evaluate(rule=rule, review_input=review_input)
    except LlmRuleRateLimitError as exc:
        return [_llm_failure_finding(rule, exc)], _llm_metric(
            rule=rule,
            runner=llm_runner,
            status="rate_limited",
            started_at=started_at,
            error_message=str(exc),
        )
    except Exception as exc:
        return [_llm_failure_finding(rule, exc)], _llm_metric(
            rule=rule,
            runner=llm_runner,
            status="failed",
            started_at=started_at,
            error_message=str(exc),
        )

    return findings, _llm_metric(
        rule=rule,
        runner=llm_runner,
        status="succeeded",
        started_at=started_at,
        error_message=None,
    )


def _llm_metric(
    *,
    rule: PolicyRule,
    runner: LlmRuleRunner,
    status: LlmRuleStatus,
    started_at: float,
    error_message: str | None,
) -> LlmRuleMetric:
    usage = runner.last_token_usage
    return LlmRuleMetric(
        rule_id=rule.id,
        provider=runner.provider_name,
        model=runner.model_name,
        status=status,
        duration_ms=max(0, round((perf_counter() - started_at) * 1000)),
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        total_tokens=usage.total_tokens if usage is not None else None,
        error_message=error_message,
    )


def _llm_failure_finding(rule: PolicyRule, exc: Exception) -> Finding:
    return Finding(
        rule_id=rule.id,
        severity="info",
        message=f"LLM rule skipped: {exc}",
        source=rule.source,
        rule_type=rule.type,
    )


def count_findings(findings: list[Finding]) -> FindingCounts:
    """Count findings by severity."""
    return FindingCounts(
        blocking=sum(1 for finding in findings if finding.severity == "blocking"),
        high=sum(1 for finding in findings if finding.severity == "high"),
        warning=sum(1 for finding in findings if finding.severity == "warning"),
        info=sum(1 for finding in findings if finding.severity == "info"),
    )


def calculate_risk(counts: FindingCounts) -> RiskLevel:
    """Calculate the initial risk level from finding counts."""
    if counts.blocking > 0:
        return "blocking"
    if counts.high > 0:
        return "high"
    if counts.warning > 0:
        return "warning"
    if counts.info > 0:
        return "info"
    return "none"
