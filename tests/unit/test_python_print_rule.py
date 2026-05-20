from pathlib import Path

import pytest

from mr_guardian.core import run_review
from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review_input import ChangedFile, DiffHunk, DiffLine, ReviewInput
from mr_guardian.rules import default_rule_registry


@pytest.fixture
def passing_review_input() -> ReviewInput:
    return make_review_input("        logger.info('ready')\n")


@pytest.fixture
def failing_review_input() -> ReviewInput:
    return make_review_input("        print('ready')\n")


def make_policy(*, enabled: bool = True) -> Policy:
    return Policy(
        version=1,
        rules=[
            PolicyRule(
                id="PYTHON-PRINT-001",
                type="deterministic",
                enabled=enabled,
                severity="warning",
                source="python-policy.yml#PYTHON-PRINT-001",
                description="Python code should use logging instead of print calls.",
            )
        ],
    )


def make_review_input(added_line: str) -> ReviewInput:
    return ReviewInput(
        base_ref="main",
        changed_files=[
            ChangedFile(
                path=Path("mr_guardian/example.py"),
                status="modified",
                hunks=[
                    DiffHunk(
                        old_start=5,
                        old_count=0,
                        new_start=5,
                        new_count=1,
                        lines=[
                            DiffLine(
                                kind="addition",
                                content=added_line,
                                old_line_number=None,
                                new_line_number=5,
                            )
                        ],
                    )
                ],
            )
        ],
    )


def test_python_print_rule_does_not_trigger_for_passing_fixture(
    passing_review_input: ReviewInput,
) -> None:
    result = run_review(
        policy=make_policy(),
        review_input=passing_review_input,
        rule_registry=default_rule_registry(),
    )

    assert result.findings == []


def test_python_print_rule_triggers_for_failing_fixture(
    failing_review_input: ReviewInput,
) -> None:
    result = run_review(
        policy=make_policy(),
        review_input=failing_review_input,
        rule_registry=default_rule_registry(),
    )

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.rule_id == "PYTHON-PRINT-001"
    assert finding.severity == "warning"
    assert finding.file_path == Path("mr_guardian/example.py")
    assert finding.line_number == 5


def test_python_print_rule_does_not_trigger_when_policy_rule_is_disabled(
    failing_review_input: ReviewInput,
) -> None:
    result = run_review(
        policy=make_policy(enabled=False),
        review_input=failing_review_input,
        rule_registry=default_rule_registry(),
    )

    assert result.findings == []
