from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.mr_ticket_key import MrTitleTicketKeyRule


def make_rule(
    *,
    title_pattern: str = r"\bTK-\d+\b",
    required_review_scopes: list[str] | None = None,
) -> PolicyRule:
    return PolicyRule(
        id="MR-TICKET-001",
        type="deterministic",
        implementation="mr_title_ticket_key",
        evaluation="mr_structure",
        enabled=True,
        severity="blocking",
        source="unity-policy.yml#MR-TICKET-001",
        description="GitLab MR titles must include a ticket key.",
        parameters={
            "title_pattern": title_pattern,
            "required_review_scopes": required_review_scopes or ["gitlab-webhook"],
        },
    )


def make_context(*, title: str, review_scope: str) -> RuleEvaluationContext:
    return RuleEvaluationContext(
        policy=Policy(version=1, rules=[]),
        review_input=ReviewInput(
            base_ref="main",
            review_scope=review_scope,
            title=title,
            changed_files=[],
        ),
    )


def test_passes_when_gitlab_mr_title_contains_ticket_key() -> None:
    findings = MrTitleTicketKeyRule("MR-TICKET-001").evaluate(
        make_context(title="TK-234 Add player movement", review_scope="gitlab-webhook"),
        make_rule(),
    )

    assert findings == []


def test_fails_when_gitlab_mr_title_missing_ticket_key() -> None:
    findings = MrTitleTicketKeyRule("MR-TICKET-001").evaluate(
        make_context(title="Add player movement", review_scope="gitlab-webhook"),
        make_rule(),
    )

    assert len(findings) == 1
    assert findings[0].rule_id == "MR-TICKET-001"
    assert findings[0].severity == "blocking"
    assert findings[0].source == "unity-policy.yml#MR-TICKET-001"
    assert findings[0].evaluation == "mr_structure"
    assert "MR title must include a ticket key" in findings[0].message


def test_does_not_trigger_for_local_review_scope_by_default() -> None:
    findings = MrTitleTicketKeyRule("MR-TICKET-001").evaluate(
        make_context(title="", review_scope="local-all-policies"),
        make_rule(),
    )

    assert findings == []


def test_uses_yaml_provided_title_pattern() -> None:
    findings = MrTitleTicketKeyRule("MR-TICKET-001").evaluate(
        make_context(title="TK-234 Add player movement", review_scope="gitlab-webhook"),
        make_rule(title_pattern=r"\bBUG-\d+\b"),
    )

    assert len(findings) == 1
    assert "`\\bBUG-\\d+\\b`" in findings[0].message


def test_uses_yaml_provided_required_review_scopes() -> None:
    findings = MrTitleTicketKeyRule("MR-TICKET-001").evaluate(
        make_context(title="", review_scope="manual-review"),
        make_rule(required_review_scopes=["gitlab-webhook"]),
    )

    assert findings == []
