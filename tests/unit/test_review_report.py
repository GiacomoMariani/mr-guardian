from pathlib import Path

from mr_guardian.core.review import PolicyReviewResult, ReviewResult
from mr_guardian.models.review import EngineReviewResult, Finding, FindingCounts
from mr_guardian.models.review_input import ChangedFile, DiffHunk, DiffLine, ReviewInput
from mr_guardian.reporting.report import render_review_report


def make_review_input() -> ReviewInput:
    return ReviewInput(
        base_ref="main",
        changed_files=[
            ChangedFile(
                path=Path("mr_guardian/example.py"),
                status="modified",
                hunks=[
                    DiffHunk(
                        old_start=4,
                        old_count=1,
                        new_start=4,
                        new_count=2,
                        lines=[
                            DiffLine(
                                kind="deletion",
                                content="old_call()\n",
                                old_line_number=4,
                                new_line_number=None,
                            ),
                            DiffLine(
                                kind="addition",
                                content="print('ready')\n",
                                old_line_number=None,
                                new_line_number=4,
                            ),
                            DiffLine(
                                kind="context",
                                content="return True\n",
                                old_line_number=5,
                                new_line_number=5,
                            ),
                        ],
                    )
                ],
            )
        ],
    )


def make_review_result(*findings: Finding) -> ReviewResult:
    counts = FindingCounts(
        blocking=sum(1 for finding in findings if finding.severity == "blocking"),
        high=sum(1 for finding in findings if finding.severity == "high"),
        warning=sum(1 for finding in findings if finding.severity == "warning"),
        info=sum(1 for finding in findings if finding.severity == "info"),
    )
    risk = "warning" if counts.warning else "none"

    return ReviewResult(
        base_ref="main",
        policy_directory=Path("sources/yaml"),
        policy_results=[
            PolicyReviewResult(
                policy_path=Path("sources/yaml/python-policy.yml"),
                policy_version=1,
                enabled_rule_count=1,
                disabled_rule_count=0,
                engine_result=EngineReviewResult(
                    risk=risk,
                    findings=list(findings),
                    counts=counts,
                ),
            )
        ],
        developer_id="Test User",
        review_input=make_review_input(),
        engine_result=EngineReviewResult(
            risk=risk,
            findings=list(findings),
            counts=counts,
        ),
    )


def test_generates_report_with_no_findings() -> None:
    report = render_review_report(make_review_result())

    assert "## MR Guardian Review" in report
    assert "**Risk:** None" in report
    assert "**Developer:** Test User" in report
    assert "- Blocking: 0" in report
    assert "- Changed files: 1" in report
    assert "- Changed lines: 2" in report
    assert "### Reviewer Focus" in report
    assert "No immediate reviewer action required." in report
    assert "### Finding Overview" in report
    assert "No triggered rules." in report
    assert "### Policies" in report
    assert "sources/yaml/python-policy.yml" in report
    assert "No findings were triggered." in report


def test_generates_report_with_findings() -> None:
    report = render_review_report(
        make_review_result(
            Finding(
                rule_id="PYTHON-PRINT-001",
                severity="warning",
                message="print calls should not be introduced.",
                source="python-policy.yml#PYTHON-PRINT-001",
                rule_type="deterministic",
                file_path=Path("mr_guardian/example.py"),
                line_number=4,
            )
        )
    )

    assert "**Risk:** Warning" in report
    assert "- Warning: 1" in report
    assert "#### Warning" in report
    assert "`PYTHON-PRINT-001` - print calls should not be introduced." in report
    assert "Location: mr_guardian/example.py:4" in report
    assert "Source: python-policy.yml#PYTHON-PRINT-001" in report
    assert "Rule type: deterministic" in report


def test_generates_prioritized_reviewer_focus_and_rule_overview() -> None:
    report = render_review_report(
        make_review_result(
            Finding(
                rule_id="PYTHON-PRINT-001",
                severity="warning",
                message="print calls should not be introduced.",
                source="python-policy.yml#PYTHON-PRINT-001",
                rule_type="deterministic",
                file_path=Path("mr_guardian/example.py"),
                line_number=4,
            ),
            Finding(
                rule_id="PYTHON-PRINT-001",
                severity="warning",
                message="print calls should not be introduced.",
                source="python-policy.yml#PYTHON-PRINT-001",
                rule_type="deterministic",
                file_path=Path("mr_guardian/other.py"),
                line_number=9,
            ),
            Finding(
                rule_id="MR-META-001",
                severity="blocking",
                message="MR metadata is missing required section(s): Test Plan.",
                source="unity-policy.yml#MR-META-001",
                rule_type="deterministic",
            ),
        )
    )

    focus_index = report.index("### Reviewer Focus")
    overview_index = report.index("### Finding Overview")
    findings_index = report.index("### Findings")

    assert focus_index < overview_index < findings_index
    assert (
        "- [Blocking] `MR-META-001` - MR metadata is missing required section(s): "
        "Test Plan."
    ) in report
    assert "`PYTHON-PRINT-001`: 2 finding(s), highest severity Warning" in report
    assert "`MR-META-001`: 1 finding(s), highest severity Blocking" in report


def test_reviewer_focus_is_capped() -> None:
    findings = [
        Finding(
            rule_id=f"PYTHON-PRINT-{index:03}",
            severity="warning",
            message=f"Finding {index}.",
            source=f"python-policy.yml#PYTHON-PRINT-{index:03}",
            rule_type="deterministic",
            file_path=Path(f"mr_guardian/example_{index}.py"),
            line_number=index,
        )
        for index in range(1, 8)
    ]

    report = render_review_report(make_review_result(*findings))

    assert "2 lower-priority finding(s) omitted from focus." in report
