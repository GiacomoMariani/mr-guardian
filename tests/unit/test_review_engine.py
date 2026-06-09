from pathlib import Path

from mr_guardian.core import run_review
from mr_guardian.core.llm_pricing import estimate_cost_usd
from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import ChangedFile, ReviewInput
from mr_guardian.rules import RuleEvaluationContext, RuleRegistry
from mr_guardian.summarizer_ai import LlmRuleExecutionError, LlmRuleRateLimitError, LlmTokenUsage


class FakeRule:
    def __init__(self, rule_id: str, findings: list[Finding]) -> None:
        self._rule_id = rule_id
        self._findings = findings
        self.calls = 0

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        self.calls += 1
        assert context.review_input.base_ref == "main"
        assert rule.id == self._rule_id
        return self._findings


class FakeLlmRuleRunner:
    def __init__(
        self,
        findings: list[Finding],
        *,
        usage: LlmTokenUsage | None = None,
    ) -> None:
        self._findings = findings
        self._usage = usage
        self.calls = 0

    def evaluate(self, *, rule: PolicyRule, review_input: ReviewInput) -> list[Finding]:
        self.calls += 1
        assert review_input.base_ref == "main"
        assert rule.type == "llm"
        return self._findings

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return "gpt-test"

    @property
    def last_token_usage(self) -> LlmTokenUsage | None:
        return self._usage


class FailingLlmRuleRunner:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.calls = 0

    def evaluate(self, *, rule: PolicyRule, review_input: ReviewInput) -> list[Finding]:
        self.calls += 1
        raise self._exc

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return "gpt-test"

    @property
    def last_token_usage(self) -> LlmTokenUsage | None:
        return None


def make_policy(*rules: PolicyRule) -> Policy:
    return Policy(
        version=1,
        rules=list(rules),
    )


def make_rule(rule_id: str, *, enabled: bool = True, severity: str = "warning") -> PolicyRule:
    return PolicyRule(
        id=rule_id,
        type="deterministic",
        implementation="fake_rule",
        evaluation="coding",
        enabled=enabled,
        severity=severity,
        source=f"unity-policy.yml#{rule_id}",
        description="Test rule.",
    )


def make_mr_structure_rule(
    rule_id: str,
    *,
    enabled: bool = True,
    severity: str = "warning",
) -> PolicyRule:
    return make_rule(rule_id, enabled=enabled, severity=severity).model_copy(
        update={"evaluation": "mr_structure"}
    )


def make_review_input() -> ReviewInput:
    return ReviewInput(
        base_ref="main",
        changed_files=[
            ChangedFile(
                path=Path("Assets/Scripts/Player.cs"),
                status="modified",
                hunks=[],
            )
        ],
    )


def make_finding(rule_id: str, *, severity: str = "warning") -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        message="A deterministic finding.",
        source=f"unity-policy.yml#{rule_id}",
        file_path=Path("Assets/Scripts/Player.cs"),
        line_number=12,
    )


def test_runs_review_with_no_rules() -> None:
    result = run_review(
        policy=make_policy(),
        review_input=make_review_input(),
        rule_registry=RuleRegistry(),
    )

    assert result.findings == []
    assert result.counts.blocking == 0
    assert result.counts.high == 0
    assert result.counts.warning == 0
    assert result.counts.info == 0
    assert result.risk == "none"


def test_runs_review_with_one_registered_rule() -> None:
    policy_rule = make_rule("MR-META-001")
    fake_rule = FakeRule("MR-META-001", [make_finding("MR-META-001")])

    result = run_review(
        policy=make_policy(policy_rule),
        review_input=make_review_input(),
        rule_registry=RuleRegistry([fake_rule]),
    )

    assert fake_rule.calls == 1
    assert len(result.findings) == 1


def test_skips_disabled_rules() -> None:
    policy_rule = make_rule("MR-META-001", enabled=False)
    fake_rule = FakeRule("MR-META-001", [make_finding("MR-META-001")])

    result = run_review(
        policy=make_policy(policy_rule),
        review_input=make_review_input(),
        rule_registry=RuleRegistry([fake_rule]),
    )

    assert fake_rule.calls == 0
    assert result.findings == []


def test_skips_llm_rules_when_no_runner_is_configured() -> None:
    policy_rule = PolicyRule(
        id="ARCH-DESIGN-001",
        type="llm",
        enabled=True,
        severity="info",
        source="python-policy.yml#ARCH-DESIGN-001",
        description="Check architecture concerns.",
        prompt="Review the diff.",
        parameters={"inputs": {"include_diff": True}},
    )
    fake_rule = FakeRule("ARCH-DESIGN-001", [make_finding("ARCH-DESIGN-001")])

    result = run_review(
        policy=make_policy(policy_rule),
        review_input=make_review_input(),
        rule_registry=RuleRegistry([fake_rule]),
    )

    assert fake_rule.calls == 0
    assert result.findings == []


def test_runs_enabled_llm_rules_with_configured_runner() -> None:
    policy_rule = PolicyRule(
        id="ARCH-DESIGN-001",
        type="llm",
        evaluation="coding",
        enabled=True,
        severity="info",
        source="python-policy.yml#ARCH-DESIGN-001",
        description="Check architecture concerns.",
        prompt="Review the diff.",
    )
    llm_runner = FakeLlmRuleRunner(
        [
            Finding(
                rule_id="ARCH-DESIGN-001",
                severity="info",
                message="Consider simplifying this abstraction.",
                source="python-policy.yml#ARCH-DESIGN-001",
                rule_type="llm",
            )
        ],
        usage=LlmTokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
    )

    result = run_review(
        policy=make_policy(policy_rule),
        review_input=make_review_input(),
        rule_registry=RuleRegistry(),
        llm_rule_runner=llm_runner,
    )

    assert llm_runner.calls == 1
    assert result.findings[0].rule_type == "llm"
    assert result.findings[0].severity == "info"
    assert result.llm_metrics[0].rule_id == "ARCH-DESIGN-001"
    assert result.llm_metrics[0].status == "succeeded"
    assert result.llm_metrics[0].provider == "openai"
    assert result.llm_metrics[0].model == "gpt-test"
    assert result.llm_metrics[0].duration_ms >= 0
    assert result.llm_metrics[0].input_tokens == 10
    assert result.llm_metrics[0].output_tokens == 5
    assert result.llm_metrics[0].total_tokens == 15
    assert result.llm_metrics[0].estimated_cost_usd is not None
    assert result.llm_metrics[0].estimated_cost_usd == estimate_cost_usd(
        provider="openai",
        model="gpt-test",
        input_tokens=10,
        output_tokens=5,
    )


def test_does_not_run_disabled_llm_rules() -> None:
    policy_rule = PolicyRule(
        id="ARCH-DESIGN-001",
        type="llm",
        enabled=False,
        severity="info",
        source="python-policy.yml#ARCH-DESIGN-001",
        description="Check architecture concerns.",
        prompt="Review the diff.",
    )
    llm_runner = FakeLlmRuleRunner([make_finding("ARCH-DESIGN-001")])

    result = run_review(
        policy=make_policy(policy_rule),
        review_input=make_review_input(),
        rule_registry=RuleRegistry(),
        llm_rule_runner=llm_runner,
    )

    assert llm_runner.calls == 0
    assert result.findings == []


def test_llm_rule_failure_is_reported_without_stopping_review() -> None:
    deterministic_rule = make_rule("MR-META-001", severity="warning")
    llm_rule = PolicyRule(
        id="ARCH-DESIGN-001",
        type="llm",
        evaluation="mr_structure",
        enabled=True,
        severity="info",
        source="python-policy.yml#ARCH-DESIGN-001",
        description="Check architecture concerns.",
        prompt="Review the diff.",
    )
    deterministic_finding = make_finding("MR-META-001")
    llm_runner = FailingLlmRuleRunner(LlmRuleExecutionError("LLM provider request timed out."))

    result = run_review(
        policy=make_policy(deterministic_rule, llm_rule),
        review_input=make_review_input(),
        rule_registry=RuleRegistry([FakeRule("MR-META-001", [deterministic_finding])]),
        llm_rule_runner=llm_runner,
    )

    assert llm_runner.calls == 1
    assert len(result.findings) == 2
    assert result.findings[0].rule_id == "MR-META-001"
    assert result.findings[1].rule_id == "ARCH-DESIGN-001"
    assert result.findings[1].severity == "info"
    assert result.findings[1].evaluation == "mr_structure"
    assert result.findings[1].rule_type == "llm"
    assert result.findings[1].message == "LLM rule skipped: LLM provider request timed out."
    assert result.llm_metrics[0].status == "failed"
    assert result.llm_metrics[0].error_message == "LLM provider request timed out."
    assert result.counts.warning == 1
    assert result.counts.info == 1
    assert result.risk == "warning"


def test_rate_limited_llm_rule_records_rate_limited_metric() -> None:
    llm_rule = PolicyRule(
        id="ARCH-DESIGN-001",
        type="llm",
        enabled=True,
        severity="info",
        source="python-policy.yml#ARCH-DESIGN-001",
        description="Check architecture concerns.",
        prompt="Review the diff.",
    )
    llm_runner = FailingLlmRuleRunner(LlmRuleRateLimitError("LLM provider rate limit reached."))

    result = run_review(
        policy=make_policy(llm_rule),
        review_input=make_review_input(),
        rule_registry=RuleRegistry(),
        llm_rule_runner=llm_runner,
    )

    assert result.llm_metrics[0].status == "rate_limited"
    assert result.llm_metrics[0].input_tokens is None


def test_collects_findings_from_rule() -> None:
    policy_rule = make_rule("MR-META-001")
    finding = make_finding("MR-META-001")

    result = run_review(
        policy=make_policy(policy_rule),
        review_input=make_review_input(),
        rule_registry=RuleRegistry([FakeRule("MR-META-001", [finding])]),
    )

    assert result.findings[0].message == "A deterministic finding."
    assert result.findings[0].file_path == Path("Assets/Scripts/Player.cs")
    assert result.findings[0].line_number == 12


def test_preserves_rule_id_and_severity_from_policy_in_findings() -> None:
    policy_rule = make_rule("MR-META-001", severity="blocking")
    finding = make_finding("SOME-OTHER-001", severity="info")

    result = run_review(
        policy=make_policy(policy_rule),
        review_input=make_review_input(),
        rule_registry=RuleRegistry([FakeRule("MR-META-001", [finding])]),
    )

    assert result.findings[0].rule_id == "MR-META-001"
    assert result.findings[0].severity == "blocking"
    assert result.findings[0].source == "unity-policy.yml#MR-META-001"


def test_computes_finding_counts() -> None:
    policy = make_policy(
        make_rule("BLOCKING-TEST-001", severity="blocking"),
        make_rule("HIGH-TEST-001", severity="high"),
        make_rule("WARNING-TEST-001", severity="warning"),
        make_rule("INFO-TEST-001", severity="info"),
    )
    registry = RuleRegistry(
        [
            FakeRule("BLOCKING-TEST-001", [make_finding("BLOCKING-TEST-001")]),
            FakeRule("HIGH-TEST-001", [make_finding("HIGH-TEST-001")]),
            FakeRule("WARNING-TEST-001", [make_finding("WARNING-TEST-001")]),
            FakeRule("INFO-TEST-001", [make_finding("INFO-TEST-001")]),
        ]
    )

    result = run_review(
        policy=policy,
        review_input=make_review_input(),
        rule_registry=registry,
    )

    assert result.counts.blocking == 1
    assert result.counts.high == 1
    assert result.counts.warning == 1
    assert result.counts.info == 1


def test_computes_evaluation_summaries() -> None:
    coding_rule = make_rule("CODE-TEST-001", severity="warning")
    structure_rule = make_mr_structure_rule("MR-STRUCTURE-001", severity="high")
    registry = RuleRegistry(
        [
            FakeRule("CODE-TEST-001", [make_finding("CODE-TEST-001")]),
            FakeRule("MR-STRUCTURE-001", [make_finding("MR-STRUCTURE-001")]),
        ]
    )

    result = run_review(
        policy=make_policy(coding_rule, structure_rule),
        review_input=make_review_input(),
        rule_registry=registry,
    )

    evaluation_by_name = {
        evaluation.evaluation: evaluation for evaluation in result.evaluations
    }

    assert result.risk == "high"
    assert evaluation_by_name["coding"].risk == "warning"
    assert evaluation_by_name["coding"].counts.warning == 1
    assert evaluation_by_name["coding"].triggered_rule_ids == ["CODE-TEST-001"]
    assert evaluation_by_name["mr_structure"].risk == "high"
    assert evaluation_by_name["mr_structure"].counts.high == 1
    assert evaluation_by_name["mr_structure"].triggered_rule_ids == ["MR-STRUCTURE-001"]


def test_computes_risk_level_from_findings() -> None:
    warning_policy = make_policy(make_rule("WARNING-TEST-001", severity="warning"))
    high_policy = make_policy(make_rule("HIGH-TEST-001", severity="high"))
    blocking_policy = make_policy(make_rule("BLOCKING-TEST-001", severity="blocking"))

    warning_result = run_review(
        policy=warning_policy,
        review_input=make_review_input(),
        rule_registry=RuleRegistry(
            [FakeRule("WARNING-TEST-001", [make_finding("WARNING-TEST-001")])]
        ),
    )
    high_result = run_review(
        policy=high_policy,
        review_input=make_review_input(),
        rule_registry=RuleRegistry([FakeRule("HIGH-TEST-001", [make_finding("HIGH-TEST-001")])]),
    )
    blocking_result = run_review(
        policy=blocking_policy,
        review_input=make_review_input(),
        rule_registry=RuleRegistry(
            [FakeRule("BLOCKING-TEST-001", [make_finding("BLOCKING-TEST-001")])]
        ),
    )

    assert warning_result.risk == "warning"
    assert high_result.risk == "high"
    assert blocking_result.risk == "blocking"
