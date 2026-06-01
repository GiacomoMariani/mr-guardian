from pathlib import Path

from mr_guardian.core.review import PolicyReviewResult, ReviewResult
from mr_guardian.models.review import (
    EngineReviewResult,
    Finding,
    FindingCounts,
    LlmReviewSummary,
    LlmRuleMetric,
)
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


def make_review_result(
    *findings: Finding,
    llm_metrics: list[LlmRuleMetric] | None = None,
    llm_summary: LlmReviewSummary | None = None,
) -> ReviewResult:
    counts = FindingCounts(
        blocking=sum(1 for finding in findings if finding.severity == "blocking"),
        high=sum(1 for finding in findings if finding.severity == "high"),
        warning=sum(1 for finding in findings if finding.severity == "warning"),
        info=sum(1 for finding in findings if finding.severity == "info"),
    )
    if counts.blocking:
        risk = "blocking"
    elif counts.high:
        risk = "high"
    elif counts.warning:
        risk = "warning"
    elif counts.info:
        risk = "info"
    else:
        risk = "none"

    return ReviewResult(
        base_ref="main",
        policy_directory=Path("sources/yaml"),
        policy_results=[
            PolicyReviewResult(
                policy_path=Path("sources/yaml/python-policy.yml"),
                policy_version=1,
                enabled_rule_count=2,
                disabled_rule_count=1,
                engine_result=EngineReviewResult(
                    risk=risk,
                    findings=list(findings),
                    counts=counts,
                    llm_metrics=llm_metrics or [],
                ),
            )
        ],
        developer_id="Test User",
        review_input=make_review_input(),
        engine_result=EngineReviewResult(
            risk=risk,
            findings=list(findings),
            counts=counts,
            llm_metrics=llm_metrics or [],
        ),
        llm_summary=llm_summary,
    )


def test_generates_passed_report_with_no_findings() -> None:
    report = render_review_report(make_review_result())

    assert "# MR Guardian Review" in report
    assert "Verdict: `PASSED`" in report
    assert "Developer: `Test User`" in report
    assert "Files changed: **1**" in report
    assert "Lines: **2**" in report
    assert "Findings: **0**" in report
    assert "| 0 | 0 | 0 | 0 |" in report
    assert "## 01 - All findings" in report
    assert "No findings were triggered." in report
    assert "## Next steps" in report
    assert "1. No immediate action required." in report
    assert "`python-policy.yml` (2 rules enabled, 1 disabled)" in report


def test_generates_blocked_report_with_metadata_findings() -> None:
    report = render_review_report(
        make_review_result(
            Finding(
                rule_id="MR-META-001",
                severity="blocking",
                message="MR metadata is missing required section(s): Test Plan.",
                source="unity-policy.yml#MR-META-001",
                evaluation="mr_structure",
                rule_type="deterministic",
            ),
            Finding(
                rule_id="MR-META-002",
                severity="warning",
                message="MR metadata is missing required section(s): Summary.",
                source="unity-policy.yml#MR-META-002",
                evaluation="mr_structure",
                rule_type="deterministic",
            ),
        )
    )

    assert "Verdict: `BLOCKED`" in report
    assert "| **1** | 0 | **1** | 0 |" in report
    assert "## 01 - Why this is blocked" in report
    assert "missing MR metadata sections" in report
    assert "| Test Plan | `MR-META-001` | Blocking | `unity-policy.yml#MR-META-001` |" in report
    assert "| Summary | `MR-META-002` | Warning | `unity-policy.yml#MR-META-002` |" in report
    assert "| `Blocking` | `MR-META-001` | Missing required section: Test Plan" in report
    assert "| `Warning` | `MR-META-002` | Missing required section: Summary" in report
    assert "deterministic" in report
    assert "Add the Test Plan section to the MR description to unblock the merge." in report
    assert "Add the Summary section to clear the metadata warnings." in report


def test_generates_needs_review_report_with_warning_findings() -> None:
    report = render_review_report(
        make_review_result(
            Finding(
                rule_id="PYTHON-PRINT-001",
                severity="warning",
                message="print calls should not be introduced.",
                source="python-policy.yml#PYTHON-PRINT-001",
                evaluation="coding",
                rule_type="deterministic",
                file_path=Path("mr_guardian/example.py"),
                line_number=4,
            )
        )
    )

    assert "Verdict: `NEEDS REVIEW`" in report
    assert "| 0 | 0 | **1** | 0 |" in report
    assert "## 01 - All findings" in report
    assert (
        "| `Warning` | `PYTHON-PRINT-001` | print calls should not be introduced. "
        "(mr_guardian/example.py:4) | deterministic | "
        "`python-policy.yml#PYTHON-PRINT-001` |"
    ) in report
    assert "1. Resolve or explicitly acknowledge the high and warning findings." in report


def test_info_only_findings_keep_passed_verdict() -> None:
    report = render_review_report(
        make_review_result(
            Finding(
                rule_id="PYTHON-DESIGN-LLM-001",
                severity="info",
                message="LLM advisory note.",
                source="python-policy.yml#PYTHON-DESIGN-LLM-001",
                evaluation="coding",
                rule_type="llm",
            )
        )
    )

    assert "Verdict: `PASSED`" in report
    assert "| 0 | 0 | 0 | **1** |" in report


def test_collapses_skipped_llm_findings() -> None:
    report = render_review_report(
        make_review_result(
            Finding(
                rule_id="AI-CODE-LLM-001",
                severity="info",
                message="LLM rule skipped: LLM provider rate limit reached.",
                source="unity-policy.yml#AI-CODE-LLM-001",
                evaluation="mr_structure",
                rule_type="llm",
            ),
            Finding(
                rule_id="PYTHON-DESIGN-LLM-001",
                severity="info",
                message="LLM rule skipped: LLM provider rate limit reached.",
                source="python-policy.yml#PYTHON-DESIGN-LLM-001",
                evaluation="coding",
                rule_type="llm",
            ),
            llm_metrics=[
                LlmRuleMetric(
                    rule_id="AI-CODE-LLM-001",
                    provider="openai",
                    model="gpt-4.1-mini",
                    status="rate_limited",
                    duration_ms=380,
                    error_message="LLM provider rate limit reached.",
                ),
                LlmRuleMetric(
                    rule_id="PYTHON-DESIGN-LLM-001",
                    provider="openai",
                    model="gpt-4.1-mini",
                    status="rate_limited",
                    duration_ms=1420,
                    error_message="LLM provider rate limit reached.",
                ),
            ],
        )
    )

    assert "## 01 - Code analysis was not completed" in report
    assert "2 LLM-based check(s) did not complete" in report
    assert "OpenAI - `gpt-4.1-mini`" in report
    assert "A clean code result here does **not** mean the changed code passed review" in report
    assert "Skipped rules: `AI-CODE-LLM-001`, `PYTHON-DESIGN-LLM-001`" in report
    assert "| `AI-CODE-LLM-001` | rate_limited | 0.38s" in report
    assert (
        "| `Info x2` | `LLM skipped checks` | LLM rules skipped - a rate limit | "
        "llm | multiple |"
    ) in report
    assert "Re-run the review once the LLM provider is available" in report


def test_renders_completed_llm_usage_metrics() -> None:
    report = render_review_report(
        make_review_result(
            llm_metrics=[
                LlmRuleMetric(
                    rule_id="PYTHON-DESIGN-LLM-001",
                    provider="openai",
                    model="gpt-4.1-mini",
                    status="succeeded",
                    duration_ms=1420,
                    input_tokens=1200,
                    output_tokens=80,
                    total_tokens=1280,
                )
            ]
        )
    )

    assert "## 01 - LLM usage" in report
    assert "| `PYTHON-DESIGN-LLM-001` | succeeded | 1.42s | 1280 | - |" in report
    assert "## 02 - All findings" in report


def test_renders_llm_review_summary() -> None:
    report = render_review_report(
        make_review_result(
            llm_summary=LlmReviewSummary(
                status="succeeded",
                provider="openai",
                model="gpt-4.1-mini",
                duration_ms=420,
                text="This MR needs reviewer attention on metadata.",
                score=71,
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
            )
        )
    )

    assert "## LLM Summary" in report
    assert "**LLM score:** 71/100" in report
    assert "This MR needs reviewer attention on metadata." in report


def test_renders_llm_review_summary_failure() -> None:
    report = render_review_report(
        make_review_result(
            llm_summary=LlmReviewSummary(
                status="failed",
                provider="openai",
                model="gpt-4.1-mini",
                duration_ms=100,
                error_message="provider unavailable",
            )
        )
    )

    assert "## LLM Summary" in report
    assert "LLM summary unavailable: failed - provider unavailable" in report
