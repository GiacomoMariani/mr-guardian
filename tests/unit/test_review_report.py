from pathlib import Path

from mr_guardian.core.review import ReviewResult
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
        policy_path=Path("sources/yaml/python-policy.yml"),
        policy_version=1,
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
    assert "- Blocking: 0" in report
    assert "- Changed files: 1" in report
    assert "- Changed lines: 2" in report
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
