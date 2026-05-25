"""Shared deterministic review engine."""

from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review import EngineReviewResult, Finding, FindingCounts, RiskLevel
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.registry import RuleRegistry
from mr_guardian.summarizer_ai import DisabledLlmRuleRunner, LlmRuleRunner


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
    llm_runner = llm_rule_runner or DisabledLlmRuleRunner()

    for policy_rule in policy.rules:
        if not policy_rule.enabled:
            continue
        if policy_rule.type == "llm":
            try:
                findings.extend(llm_runner.evaluate(rule=policy_rule, review_input=review_input))
            except Exception as exc:
                findings.append(_llm_failure_finding(policy_rule, exc))
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
