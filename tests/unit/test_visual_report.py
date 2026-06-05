from datetime import datetime, timezone
from pathlib import Path

from mr_guardian.models.history import ReviewPolicySummary, ReviewRunRecord
from mr_guardian.models.review import Finding, LlmRuleMetric
from mr_guardian.reporting.visual_report import render_visual_review_report


def make_record(
    *,
    risk: str = "blocking",
    blocking_count: int = 1,
    high_count: int = 0,
    warning_count: int = 1,
    info_count: int = 0,
    findings: list[Finding] | None = None,
    llm_metrics: list[LlmRuleMetric] | None = None,
    developer_id: str = "Test User",
) -> ReviewRunRecord:
    return ReviewRunRecord(
        review_id=1,
        timestamp=datetime(2026, 5, 29, tzinfo=timezone.utc),
        review_scope="local-all-policies",
        branch_name="main",
        developer_id=developer_id,
        policy_version=1,
        risk=risk,
        blocking_count=blocking_count,
        high_count=high_count,
        warning_count=warning_count,
        info_count=info_count,
        changed_file_count=1,
        changed_line_count=12,
        review_score=60,
        findings=findings or [],
        triggered_rule_ids=[finding.rule_id for finding in findings or []],
        llm_metrics=llm_metrics or [],
        policy_summaries=[
            ReviewPolicySummary(
                policy_path="sources/yaml/python-policy.yml",
                policy_version=1,
                enabled_rule_count=2,
                disabled_rule_count=0,
            ),
            ReviewPolicySummary(
                policy_path="sources/yaml/unity-policy.yml",
                policy_version=1,
                enabled_rule_count=30,
                disabled_rule_count=0,
            ),
        ],
        generated_review_report="# MR Guardian Review\n",
    )


def metadata_findings() -> list[Finding]:
    return [
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
    ]


def test_renders_blocked_visual_report_with_metadata_checklist() -> None:
    html = render_visual_review_report(make_record(findings=metadata_findings()))

    assert "<h1>MR Guardian Review</h1>" in html
    assert "Merge blocked - 1 required action" in html
    assert "<span class=\"v-tag\">BLOCKED</span>" in html
    assert "Why this is blocked" in html
    assert "<span class=\"name\">Test Plan</span>" in html
    assert "<span class=\"code\">MR-META-001</span>" in html
    assert "<span class=\"sev\">Blocking</span>" in html
    assert "<span class=\"name\">Summary</span>" in html
    assert "Missing required section: Test Plan" in html
    assert "unity-policy.yml#MR-META-001" in html
    assert "python-policy.yml - 2 rules enabled" in html


def test_renders_passed_visual_report() -> None:
    html = render_visual_review_report(
        make_record(
            risk="none",
            blocking_count=0,
            warning_count=0,
            findings=[],
        )
    )

    assert "Review passed - no required actions" in html
    assert "<span class=\"v-tag\">PASSED</span>" in html
    assert "No findings were triggered." in html
    assert "No immediate action required." in html


def test_renders_dark_visual_report_theme() -> None:
    html = render_visual_review_report(
        make_record(
            risk="none",
            blocking_count=0,
            warning_count=0,
            findings=[],
        ),
        theme="dark",
    )

    assert '<body class="mg-dark">' in html
    assert "body.mg-dark" in html


def test_renders_skipped_llm_checks_as_grouped_callout() -> None:
    findings = [
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
    ]
    html = render_visual_review_report(
        make_record(
            risk="info",
            blocking_count=0,
            warning_count=0,
            info_count=2,
            findings=findings,
            llm_metrics=[
                LlmRuleMetric(
                    rule_id="AI-CODE-LLM-001",
                    provider="openai",
                    model="gpt-4.1-mini",
                    status="rate_limited",
                    duration_ms=100,
                    error_message="LLM provider rate limit reached.",
                )
            ],
        )
    )

    assert "Code analysis was not completed" in html
    assert "OpenAI - gpt-4.1-mini" in html
    assert "AI-CODE-LLM-001" in html
    assert "PYTHON-DESIGN-LLM-001" in html
    assert "Info x2" in html
    assert "LLM rules skipped - provider rate limit reached" in html


def test_renders_all_findings_table() -> None:
    html = render_visual_review_report(
        make_record(
            risk="warning",
            blocking_count=0,
            warning_count=1,
            findings=[
                Finding(
                    rule_id="PYTHON-PRINT-001",
                    severity="warning",
                    message="print calls should be replaced with logging.",
                    source="python-policy.yml#PYTHON-PRINT-001",
                    evaluation="coding",
                    rule_type="deterministic",
                    file_path=Path("mr_guardian/example.py"),
                    line_number=4,
                )
            ],
        )
    )

    assert "<th>Severity</th><th>Rule</th><th>Detail</th><th>Type</th><th>Source</th>" in html
    assert "PYTHON-PRINT-001" in html
    assert "print calls should be replaced with logging. (mr_guardian/example.py:4)" in html
    assert "deterministic" in html
    assert "python-policy.yml#PYTHON-PRINT-001" in html


def test_escapes_user_controlled_html() -> None:
    malicious = "<script>alert('x')</script>"
    html = render_visual_review_report(
        make_record(
            risk="warning",
            blocking_count=0,
            warning_count=1,
            developer_id=malicious,
            findings=[
                Finding(
                    rule_id="RULE-001",
                    severity="warning",
                    message=malicious,
                    source=malicious,
                    evaluation="coding",
                    rule_type="deterministic",
                )
            ],
        )
    )

    assert malicious not in html
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html


def test_blocked_report_does_not_duplicate_findings() -> None:
    findings = [
        Finding(
            rule_id="RULE-BLOCK",
            severity="blocking",
            message="Blocking detail here.",
            source="p.yml#RULE-BLOCK",
            evaluation="coding",
            rule_type="deterministic",
        ),
        Finding(
            rule_id="RULE-HIGH",
            severity="high",
            message="High detail here.",
            source="p.yml#RULE-HIGH",
            evaluation="coding",
            rule_type="deterministic",
        ),
    ]
    html = render_visual_review_report(
        make_record(risk="blocking", blocking_count=1, high_count=1, warning_count=0, findings=findings)
    )

    assert "Why this is blocked" in html
    assert "Other findings" in html  # the second table is relabelled
    assert "<h2>All findings</h2>" not in html
    # the blocking finding appears once (blocked section only), not duplicated
    assert html.count("Blocking detail here.") == 1
    assert "High detail here." in html  # the non-blocking finding is still listed


def test_embedded_report_tightens_padding_and_widens_sheet() -> None:
    record = make_record(risk="none", blocking_count=0, warning_count=0, findings=[])
    embedded = render_visual_review_report(record, embedded=True)
    standalone = render_visual_review_report(record)

    assert '<body class="mg-light mg-embedded">' in embedded
    assert '<body class="mg-light">' in standalone  # default keeps the document look
    assert "body.mg-embedded {" in embedded
    assert "max-width: none" in embedded
    # the embedded sheet fills the iframe so its bottom edge can't float as a stray line
    assert "min-height: calc(100vh" in embedded
