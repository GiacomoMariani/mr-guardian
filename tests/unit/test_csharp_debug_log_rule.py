from pathlib import Path

import pytest

from mr_guardian.core import run_review
from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review_input import ChangedFile, DiffHunk, DiffLine, ReviewInput
from mr_guardian.rules import default_rule_registry


@pytest.fixture
def passing_review_input() -> ReviewInput:
    return make_review_input("        transform.position += Vector3.right;\n")


@pytest.fixture
def failing_review_input() -> ReviewInput:
    return make_review_input('        Debug.Log("moving player");\n')


def make_policy(*, enabled: bool = True) -> Policy:
    return Policy(
        version=1,
        rules=[
            PolicyRule(
                id="CSHARP-DEBUG-001",
                type="deterministic",
                implementation="csharp_debug_log",
                enabled=enabled,
                severity="warning",
                source="unity-policy.yml#CSHARP-DEBUG-001",
                description=(
                    "Debug.Log statements should not be introduced in production code "
                    "unless explicitly allowed."
                ),
                parameters={
                    "match": {
                        "changed_files": ["Assets/**/*.cs"],
                        "added_lines_contain": ["Debug.Log", "print("],
                    },
                },
            )
        ],
    )


def make_review_input(added_line: str) -> ReviewInput:
    return ReviewInput(
        base_ref="main",
        changed_files=[
            ChangedFile(
                path=Path("Assets/Scripts/PlayerController.cs"),
                status="modified",
                hunks=[
                    DiffHunk(
                        old_start=10,
                        old_count=0,
                        new_start=10,
                        new_count=1,
                        lines=[
                            DiffLine(
                                kind="addition",
                                content=added_line,
                                old_line_number=None,
                                new_line_number=10,
                            )
                        ],
                    )
                ],
            )
        ],
    )


def test_csharp_debug_log_rule_does_not_trigger_for_passing_fixture(
    passing_review_input: ReviewInput,
) -> None:
    result = run_review(
        policy=make_policy(),
        review_input=passing_review_input,
        rule_registry=default_rule_registry(),
    )

    assert result.findings == []


def test_csharp_debug_log_rule_triggers_for_failing_fixture(
    failing_review_input: ReviewInput,
) -> None:
    result = run_review(
        policy=make_policy(),
        review_input=failing_review_input,
        rule_registry=default_rule_registry(),
    )

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.rule_id == "CSHARP-DEBUG-001"
    assert finding.severity == "warning"
    assert finding.file_path == Path("Assets/Scripts/PlayerController.cs")
    assert finding.line_number == 10
    assert finding.source == "unity-policy.yml#CSHARP-DEBUG-001"


def test_csharp_debug_log_rule_does_not_trigger_when_policy_rule_is_disabled(
    failing_review_input: ReviewInput,
) -> None:
    result = run_review(
        policy=make_policy(enabled=False),
        review_input=failing_review_input,
        rule_registry=default_rule_registry(),
    )

    assert result.findings == []
