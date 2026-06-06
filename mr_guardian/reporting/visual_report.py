"""HTML rendering for Streamlit review reports."""

from html import escape
from pathlib import Path
from typing import Literal

from mr_guardian.models.history import ReviewRunRecord
from mr_guardian.models.policy import Severity
from mr_guardian.models.review import Finding, LlmRuleMetric
from mr_guardian.reporting.design_system import (
    css_variable_block,
    font_face_css,
    primitives_css,
)

VisualReportTheme = Literal["light", "dark"]

SEVERITY_LABELS: dict[Severity, str] = {
    "blocking": "Blocking",
    "high": "High",
    "warning": "Warning",
    "info": "Info",
}
SEVERITY_RANK: dict[Severity, int] = {
    "blocking": 0,
    "high": 1,
    "warning": 2,
    "info": 3,
}
SKIPPED_LLM_STATUSES = {"skipped", "failed", "rate_limited"}
METADATA_MESSAGE_PREFIX = "MR metadata is missing required section(s): "


def render_visual_review_report(
    run: ReviewRunRecord,
    *,
    theme: VisualReportTheme = "light",
    embedded: bool = False,
) -> str:
    """Render one stored review run as a self-contained HTML report.

    Set ``embedded=True`` when showing the report inside the dashboard iframe: the
    page padding is tightened and the sheet fills the available width (standalone
    exported reports keep their centred, padded document look)."""
    verdict = _verdict(run)
    findings = sorted(run.findings, key=_finding_sort_key)
    skipped_findings = [finding for finding in findings if _is_skipped_llm_finding(finding)]
    skipped_metrics = _skipped_llm_metrics(run.llm_metrics)
    skipped_rule_ids = _skipped_rule_ids(skipped_findings, skipped_metrics)
    metadata_findings = [
        finding
        for finding in findings
        if finding.severity in {"blocking", "high", "warning"}
        and _metadata_sections(finding)
    ]

    # When the blocked section already lists the blocking findings as a table, drop
    # them from the findings section (relabelled "Other findings") so the same rows
    # are not shown twice. Metadata-blocked reports show a checklist instead, so the
    # full findings table still adds value there.
    if run.blocking_count and not metadata_findings:
        other_findings = [f for f in findings if f.severity != "blocking"]
        findings_section = (
            _render_findings_section(
                other_findings, skipped_findings, title="Other findings"
            )
            if other_findings or skipped_findings
            else ""
        )
    else:
        findings_section = _render_findings_section(findings, skipped_findings)

    body_class = f"mg-{theme}" + (" mg-embedded" if embedded else "")

    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="UTF-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
            "<title>MR Guardian Review</title>",
            f"<style>{_styles(theme)}</style>",
            "</head>",
            f'<body class="{body_class}">',
            '<div class="sheet">',
            _render_header(run),
            _render_verdict(verdict),
            _render_stats(run),
            _render_scope(run),
            "<main>",
            _render_blocked_section(metadata_findings, findings)
            if run.blocking_count
            else "",
            _render_skipped_section(skipped_rule_ids, skipped_metrics)
            if skipped_rule_ids
            else "",
            findings_section,
            "</main>",
            _render_footer(run, skipped_rule_ids),
            "</div>",
            "</body>",
            "</html>",
        ]
    )


def _styles(theme: VisualReportTheme) -> str:
    return "\n".join(
        [
            _legacy_report_styles(),
            font_face_css(),
            css_variable_block(theme, selector=f"body.mg-{theme}"),
            primitives_css(),
            _report_design_overrides(),
        ]
    )


def _legacy_report_styles() -> str:
    return """
:root{
  --ink:#1a1d21;--ink-soft:#4b5159;--ink-faint:#8b929b;
  --paper:#f4f1ea;--card:#fffdf8;--line:#e2ddd1;--line-strong:#cfc8b8;
  --block:#b3261e;--block-bg:#fbe9e7;--block-line:#f0c4bf;
  --warn:#b06b00;--warn-bg:#fbf1dd;--warn-line:#f0d9ac;
  --info:#2f5d8c;--info-bg:#e8f0f8;--info-line:#c4d7ea;
  --pass:#2f6f4f;--pass-bg:#e6f2ea;--pass-line:#bfe0cd;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:Inter,Segoe UI,system-ui,sans-serif;--display:Georgia,serif;
}
body.mg-dark{
  --ink:#f3eee5;--ink-soft:#c7c0b4;--ink-faint:#8f97a3;
  --paper:#0e1117;--card:#171a21;--line:#2b303a;--line-strong:#3b414d;
  --block-bg:#331817;--block-line:#5a2926;
  --warn-bg:#332514;--warn-line:#5c421e;
  --info-bg:#142333;--info-line:#243e59;
  --pass-bg:#14291d;--pass-line:#28553b;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--sans);color:var(--ink);background:var(--paper);
  line-height:1.55;padding:32px 16px 56px}
.sheet{max-width:860px;margin:0 auto;background:var(--card);
  border:1px solid var(--line);border-radius:14px;overflow:hidden;
  box-shadow:0 1px 0 rgba(255,255,255,.08) inset,
    0 24px 60px -28px rgba(26,29,33,.38)}
header{padding:30px 38px 26px;border-bottom:1px solid var(--line);
  display:flex;justify-content:space-between;align-items:flex-start;
  gap:24px;flex-wrap:wrap;background:var(--card)}
.brand{display:flex;align-items:center;gap:13px}
.shield{width:38px;height:42px;flex:none;background:var(--ink);
  clip-path:polygon(50% 0,100% 18%,100% 62%,50% 100%,0 62%,0 18%);
  display:grid;place-items:center;color:#fff;font-family:var(--mono);
  font-weight:600;font-size:18px}
.brand h1{font-family:var(--display);font-size:25px;font-weight:600;line-height:1.1}
.sub{font-family:var(--mono);font-size:11px;color:var(--ink-faint);
  letter-spacing:.08em;text-transform:uppercase;margin-top:3px}
.meta{font-family:var(--mono);font-size:12px;color:var(--ink-soft);
  text-align:right;line-height:1.9}.meta b{color:var(--ink)}
.verdict{padding:22px 38px;display:flex;align-items:center;gap:18px;
  border-bottom:1px solid var(--line)}
.verdict.blocked{background:var(--block-bg);border-color:var(--block-line)}
.verdict.needs-review{background:var(--warn-bg);border-color:var(--warn-line)}
.verdict.passed{background:var(--pass-bg);border-color:var(--pass-line)}
.dot{width:13px;height:13px;border-radius:50%;flex:none}.blocked .dot{background:var(--block)}
.needs-review .dot{background:var(--warn)}.passed .dot{background:var(--pass)}
.v-text{flex:1}.v-label{font-family:var(--mono);font-size:11px;letter-spacing:.12em;
  text-transform:uppercase;font-weight:600}.blocked .v-label{color:var(--block)}
.needs-review .v-label{color:var(--warn)}.passed .v-label{color:var(--pass)}
.v-headline{font-family:var(--display);font-size:22px;font-weight:600;margin-top:1px}
.v-tag{font-family:var(--mono);font-size:12px;font-weight:600;color:#fff;
  padding:7px 14px;border-radius:999px;letter-spacing:.05em}
.blocked .v-tag{background:var(--block)}.needs-review .v-tag{background:var(--warn)}
.passed .v-tag{background:var(--pass)}
.stats{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--line)}
.stat{padding:20px 22px;border-right:1px solid var(--line)}.stat:last-child{border-right:0}
.n{font-family:var(--display);font-size:34px;font-weight:600;line-height:1}
.l{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-faint);margin-top:7px}.stat.block .n{color:var(--block)}
.stat.warn .n{color:var(--warn)}.stat.info .n{color:var(--info)}
.stat.muted .n{color:var(--ink-soft)}
.diffline{padding:11px 38px;font-family:var(--mono);font-size:12px;
  color:var(--ink-soft);border-bottom:1px solid var(--line);background:#fbf9f3}
.diffline b{color:var(--ink)}main{padding:34px 38px 8px}section{margin-bottom:38px}
.s-head{display:flex;align-items:baseline;gap:12px;margin-bottom:16px}
.s-head h2{font-family:var(--display);font-size:18px;font-weight:600}
.s-num{font-family:var(--mono);font-size:12px;color:var(--ink-faint)}
.rule-tag{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--ink-faint);
  border:1px solid var(--line-strong);padding:3px 9px;border-radius:6px}
.lede{color:var(--ink-soft);font-size:14.5px;margin-bottom:18px;max-width:62ch}
.check{list-style:none;border:1px solid var(--line);border-radius:10px;overflow:hidden}
.check li{display:flex;align-items:center;gap:14px;padding:13px 16px;
  border-bottom:1px solid var(--line);font-size:14px}.check li:last-child{border-bottom:0}
.mk{width:22px;height:22px;border-radius:6px;flex:none;display:grid;place-items:center;
  font-family:var(--mono);font-weight:600;font-size:13px;color:#fff}
.x .mk{background:var(--block)}.w .mk{background:var(--warn)}
.name{font-weight:500}.code{margin-left:auto;font-family:var(--mono);
  font-size:11.5px;color:var(--ink-faint)}
.sev{font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.06em;
  text-transform:uppercase;padding:3px 8px;border-radius:5px}
.x .sev{color:var(--block);background:var(--block-bg);border:1px solid var(--block-line)}
.w .sev{color:var(--warn);background:var(--warn-bg);border:1px solid var(--warn-line)}
.callout{border:1px solid var(--info-line);background:var(--info-bg);border-radius:10px;
  padding:18px 20px;display:flex;gap:15px}
.ic{width:26px;height:26px;border-radius:50%;flex:none;background:var(--info);
  color:#fff;display:grid;place-items:center;font-family:var(--display);font-weight:600}
.callout p{font-size:14px;color:#2a4258}.callout p b{color:var(--info)}
.skipped{margin-top:12px;display:flex;flex-wrap:wrap;gap:7px}
.skipped span{font-family:var(--mono);font-size:11px;color:var(--info);background:#fff;
  border:1px solid var(--info-line);padding:4px 9px;border-radius:6px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
thead th{text-align:left;font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-faint);font-weight:600;padding:0 12px 9px;
  border-bottom:1px solid var(--line-strong)}
tbody td{padding:12px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:last-child td{border-bottom:0}.rid{font-family:var(--mono);font-size:12.5px;
  font-weight:500}.sevcol{white-space:nowrap}
.pill{font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.05em;
  text-transform:uppercase;padding:3px 9px;border-radius:999px;display:inline-block}
.pill.block{color:var(--block);background:var(--block-bg);border:1px solid var(--block-line)}
.pill.warn{color:var(--warn);background:var(--warn-bg);border:1px solid var(--warn-line)}
.pill.info{color:var(--info);background:var(--info-bg);border:1px solid var(--info-line)}
.pill.pass{color:var(--pass);background:var(--pass-bg);border:1px solid var(--pass-line)}
.type{font-family:var(--mono);font-size:11px;color:var(--ink-faint)}
footer{padding:22px 38px 30px;border-top:1px solid var(--line);background:#fbf9f3;
  display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;
  font-family:var(--mono);font-size:11.5px;color:var(--ink-faint)}
footer b{color:var(--ink-soft);font-weight:600}.pol{line-height:1.9}.right{text-align:right}
@media(max-width:680px){body{padding:18px 10px 50px}header,.verdict,main,footer,
  .diffline{padding-left:22px;padding-right:22px}.stats{grid-template-columns:repeat(2,1fr)}
  .stat:nth-child(2){border-right:0}.n{font-size:28px}.meta{text-align:left}}
"""


def _report_design_overrides() -> str:
    return """
body {
  background:
    radial-gradient(circle at 12% -5%, var(--surface-3) 0%, transparent 42%),
    var(--paper);
  color: var(--ink);
  font-family: var(--mg-sans);
}

.sheet {
  background: var(--surface);
  border-color: var(--line);
  border-radius: 10px;
  box-shadow: 0 1px 0 var(--inner-shadow) inset, var(--shadow-md);
}

header {
  background: var(--surface);
}

.brand h1,
.v-headline,
.n,
.s-head h2 {
  letter-spacing: 0;
}

.diffline,
footer {
  background: var(--surface-2s);
}

.callout p {
  color: var(--ink-2);
}

.skipped span {
  background: var(--surface);
}

thead th {
  background: var(--surface-2s);
  padding-top: 10px;
}

body.mg-embedded {
  padding: 6px 10px 6px;
}

/* Embedded in the dashboard the report should read as a flush panel, not a floating
   document. The iframe height is a fixed estimate, so let the sheet fill it: its bottom
   edge then sits at the iframe's end instead of floating as a stray line in the slack
   below the report (any leftover height becomes a little card padding). Drop the
   page-style drop shadow too, so there's no halo hanging in that gap. */
body.mg-embedded .sheet {
  max-width: none;
  min-height: calc(100vh - 12px);
  box-shadow: 0 1px 0 var(--inner-shadow) inset;
}
"""


def _render_header(run: ReviewRunRecord) -> str:
    return f"""
<header>
  <div class="brand">
    <div class="shield">MR</div>
    <div>
      <h1>MR Guardian Review</h1>
      <div class="sub">Automated Merge Request Gate</div>
    </div>
  </div>
  <div class="meta">
    Developer&nbsp;-&nbsp;<b>{_html(run.developer_id)}</b><br>
    Files changed&nbsp;-&nbsp;<b>{run.changed_file_count}</b>
    &nbsp;/&nbsp;Lines&nbsp;-&nbsp;<b>{run.changed_line_count}</b><br>
    Findings&nbsp;-&nbsp;<b>{_total_findings(run)}</b>
  </div>
</header>
"""


def _render_verdict(verdict: tuple[str, str, str]) -> str:
    css_class, headline, tag = verdict
    return f"""
<div class="verdict {css_class}">
  <span class="dot"></span>
  <div class="v-text">
    <div class="v-label">Verdict</div>
    <div class="v-headline">{_html(headline)}</div>
  </div>
  <span class="v-tag">{_html(tag)}</span>
</div>
"""


def _render_stats(run: ReviewRunRecord) -> str:
    return f"""
<div class="stats">
  <div class="stat block">
    <div class="n">{run.blocking_count}</div><div class="l">Blocking</div>
  </div>
  <div class="stat muted"><div class="n">{run.high_count}</div><div class="l">High</div></div>
  <div class="stat warn">
    <div class="n">{run.warning_count}</div><div class="l">Warning</div>
  </div>
  <div class="stat info"><div class="n">{run.info_count}</div><div class="l">Info</div></div>
</div>
"""


def _render_scope(run: ReviewRunRecord) -> str:
    return (
        '<div class="diffline">'
        f"Scope&nbsp;&nbsp;<b>{run.changed_file_count} file(s) changed</b>"
        f"&nbsp;&nbsp;-&nbsp;&nbsp;{run.changed_line_count} line(s)"
        f"&nbsp;&nbsp;-&nbsp;&nbsp;Policies: {_html(_policy_scope(run))}"
        "</div>"
    )


def _render_blocked_section(
    metadata_findings: list[Finding],
    findings: list[Finding],
) -> str:
    actionable_findings = [
        finding
        for finding in findings
        if finding.severity in {"blocking", "high", "warning"}
    ]
    if actionable_findings and len(metadata_findings) == len(actionable_findings):
        lede = (
            "Every blocking and warning finding comes from missing MR metadata "
            "sections - not from the code itself. Add the required sections to "
            "the merge request description to clear the gate."
        )
    else:
        lede = "This merge request has blocking findings that must be resolved before merge."

    if metadata_findings:
        checklist = _render_metadata_checklist(metadata_findings)
    else:
        checklist = _render_blocking_table(findings)

    return f"""
<section>
  <div class="s-head">
    <h2>Why this is blocked</h2>
    <span class="rule-tag">{_html(_rule_range(actionable_findings))}</span>
  </div>
  <p class="lede">{_html(lede)}</p>
  {checklist}
</section>
"""


def _render_metadata_checklist(findings: list[Finding]) -> str:
    rows: list[str] = []
    for finding in sorted(findings, key=_finding_sort_key):
        css_class = "x" if finding.severity == "blocking" else "w"
        mark = "X" if finding.severity == "blocking" else "!"
        for section in _metadata_sections(finding):
            rows.append(
                f"""
<li class="{css_class}">
  <span class="mk">{mark}</span>
  <span class="name">{_html(section)}</span>
  <span class="code">{_html(finding.rule_id)}</span>
  <span class="sev">{_html(SEVERITY_LABELS[finding.severity])}</span>
</li>
"""
            )
    return '<ul class="check">' + "".join(rows) + "</ul>"


def _render_blocking_table(findings: list[Finding]) -> str:
    blocking_findings = [
        finding for finding in findings if finding.severity == "blocking"
    ]
    return _render_findings_table(blocking_findings)


def _render_skipped_section(
    skipped_rule_ids: list[str],
    skipped_metrics: list[LlmRuleMetric],
) -> str:
    provider = _provider_model(skipped_metrics)
    reason = _skipped_reason(skipped_metrics)
    chips = "".join(f"<span>{_html(rule_id)}</span>" for rule_id in skipped_rule_ids)
    return f"""
<section>
  <div class="s-head">
    <h2>Code analysis was not completed</h2>
  </div>
  <div class="callout">
    <div class="ic">i</div>
    <div>
      <p>
        {len(skipped_rule_ids)} LLM-based check(s) did not complete because the
        provider (<b>{_html(provider)}</b>) returned {_html(reason)}. A clean result
        here does <b>not</b> mean the changed code passed review; these rules
        should be re-run before merge.
      </p>
      <div class="skipped">{chips}</div>
    </div>
  </div>
</section>
"""


def _render_findings_section(
    findings: list[Finding],
    skipped_findings: list[Finding],
    *,
    title: str = "All findings",
) -> str:
    return f"""
<section>
  <div class="s-head">
    <h2>{_html(title)}</h2>
    <span class="rule-tag">{len(findings)} total</span>
  </div>
  {_render_findings_table(findings, skipped_findings)}
</section>
"""


def _render_findings_table(
    findings: list[Finding],
    skipped_findings: list[Finding] | None = None,
) -> str:
    skipped = skipped_findings or []
    normal_findings = [
        finding for finding in findings if not _is_skipped_llm_finding(finding)
    ]
    if not normal_findings and not skipped:
        return '<p class="lede">No findings were triggered.</p>'

    rows = "".join(_render_finding_row(finding) for finding in normal_findings)
    if skipped:
        rows += _render_skipped_findings_row(skipped)
    return f"""
<table>
  <thead>
    <tr><th>Severity</th><th>Rule</th><th>Detail</th><th>Type</th><th>Source</th></tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
"""


def _render_finding_row(finding: Finding) -> str:
    severity_class = _severity_class(finding.severity)
    detail = _finding_detail(finding)
    location = _location(finding)
    if location:
        detail = f"{detail} ({location})"
    return f"""
<tr>
  <td class="sevcol">
    <span class="pill {severity_class}">{_html(SEVERITY_LABELS[finding.severity])}</span>
  </td>
  <td><span class="rid">{_html(finding.rule_id)}</span></td>
  <td>{_html(detail)}</td>
  <td><span class="type">{_html(finding.rule_type or "unknown")}</span></td>
  <td><span class="type">{_html(finding.source)}</span></td>
</tr>
"""


def _render_skipped_findings_row(findings: list[Finding]) -> str:
    return f"""
<tr>
  <td class="sevcol"><span class="pill info">Info x{len(findings)}</span></td>
  <td><span class="rid">LLM skipped checks</span></td>
  <td>LLM rules skipped - {_html(_skipped_reason_from_findings(findings))}</td>
  <td><span class="type">llm</span></td>
  <td><span class="type">multiple</span></td>
</tr>
"""


def _render_footer(run: ReviewRunRecord, skipped_rule_ids: list[str]) -> str:
    policies = "<br>".join(_policy_lines(run))
    next_steps = "<br>".join(_next_steps(run, skipped_rule_ids))
    return f"""
<footer>
  <div class="pol">
    <b>POLICIES EVALUATED</b><br>
    {policies}
  </div>
  <div class="pol right">
    <b>NEXT STEP</b><br>
    {next_steps}
  </div>
</footer>
"""


def _verdict(run: ReviewRunRecord) -> tuple[str, str, str]:
    if run.blocking_count:
        action = "action" if run.blocking_count == 1 else "actions"
        return "blocked", f"Merge blocked - {run.blocking_count} required {action}", "BLOCKED"
    review_count = run.high_count + run.warning_count
    if review_count:
        item = "item" if review_count == 1 else "items"
        return "needs-review", f"Needs review - {review_count} review {item}", "REVIEW"
    return "passed", "Review passed - no required actions", "PASSED"


def _policy_scope(run: ReviewRunRecord) -> str:
    if not run.policy_summaries:
        return f"policy version {run.policy_version}"
    return ", ".join(Path(policy.policy_path).name for policy in run.policy_summaries)


def _policy_lines(run: ReviewRunRecord) -> list[str]:
    if not run.policy_summaries:
        return [_html(f"Policy version {run.policy_version}")]
    return [
        _html(
            f"{Path(policy.policy_path).name} - "
            f"{policy.enabled_rule_count} rules enabled"
        )
        for policy in run.policy_summaries
    ]


def _next_steps(run: ReviewRunRecord, skipped_rule_ids: list[str]) -> list[str]:
    steps: list[str] = []
    blocking_sections = [
        section
        for finding in run.findings
        if finding.severity == "blocking"
        for section in _metadata_sections(finding)
    ]
    if blocking_sections:
        steps.append(f"Add {_format_sections(blocking_sections)} to unblock.")
    elif run.blocking_count:
        steps.append("Resolve blocking findings before merge.")

    if run.high_count or run.warning_count:
        steps.append("Resolve or acknowledge warning-level findings.")
    if skipped_rule_ids:
        steps.append("Re-run when the LLM provider is available.")
    if not steps:
        steps.append("No immediate action required.")
    return [_html(step) for step in steps]


def _format_sections(sections: list[str]) -> str:
    unique_sections: list[str] = []
    seen: set[str] = set()
    for section in sections:
        if section in seen:
            continue
        unique_sections.append(section)
        seen.add(section)
    if len(unique_sections) == 1:
        return f"{unique_sections[0]}"
    if len(unique_sections) == 2:
        return f"{unique_sections[0]} and {unique_sections[1]}"
    return ", ".join(unique_sections[:-1]) + f", and {unique_sections[-1]}"


def _total_findings(run: ReviewRunRecord) -> int:
    if run.findings:
        return len(run.findings)
    return run.blocking_count + run.high_count + run.warning_count + run.info_count


def _rule_range(findings: list[Finding]) -> str:
    rule_ids = [finding.rule_id for finding in findings]
    if not rule_ids:
        return "Blocking"
    if len(rule_ids) <= 2:
        return ", ".join(rule_ids)
    return f"{rule_ids[0]}...{rule_ids[-1]}"


def _severity_class(severity: Severity) -> str:
    if severity == "blocking":
        return "block"
    if severity in {"high", "warning"}:
        return "warn"
    return "info"


def _is_skipped_llm_finding(finding: Finding) -> bool:
    return (
        finding.rule_type == "llm"
        and finding.severity == "info"
        and finding.message.startswith("LLM rule skipped:")
    )


def _skipped_llm_metrics(metrics: list[LlmRuleMetric]) -> list[LlmRuleMetric]:
    return [metric for metric in metrics if metric.status in SKIPPED_LLM_STATUSES]


def _skipped_rule_ids(
    skipped_findings: list[Finding],
    skipped_metrics: list[LlmRuleMetric],
) -> list[str]:
    rule_ids: list[str] = []
    seen: set[str] = set()
    for rule_id in [
        *(metric.rule_id for metric in skipped_metrics),
        *(finding.rule_id for finding in skipped_findings),
    ]:
        if rule_id in seen:
            continue
        seen.add(rule_id)
        rule_ids.append(rule_id)
    return sorted(rule_ids)


def _provider_model(metrics: list[LlmRuleMetric]) -> str:
    if not metrics:
        return "LLM provider"
    metric = metrics[0]
    provider = "OpenAI" if metric.provider.lower() == "openai" else metric.provider
    return f"{provider} - {metric.model}"


def _skipped_reason(metrics: list[LlmRuleMetric]) -> str:
    if any(metric.status == "rate_limited" for metric in metrics):
        return "a rate limit"
    if any(metric.status == "failed" for metric in metrics):
        return "an error"
    return "a skipped result"


def _skipped_reason_from_findings(findings: list[Finding]) -> str:
    if any("rate limit" in finding.message.lower() for finding in findings):
        return "provider rate limit reached"
    return "provider unavailable"


def _metadata_sections(finding: Finding) -> list[str]:
    if METADATA_MESSAGE_PREFIX not in finding.message:
        return []
    raw_sections = finding.message.split(METADATA_MESSAGE_PREFIX, maxsplit=1)[1]
    sections = raw_sections.strip().rstrip(".")
    return [section.strip() for section in sections.split(",") if section.strip()]


def _finding_detail(finding: Finding) -> str:
    sections = _metadata_sections(finding)
    if len(sections) == 1:
        return f"Missing required section: {sections[0]}"
    if len(sections) > 1:
        return f"Missing required sections: {_format_sections(sections)}"
    return finding.message


def _location(finding: Finding) -> str:
    if finding.file_path is None:
        return ""
    location = finding.file_path.as_posix()
    if finding.line_number is not None:
        return f"{location}:{finding.line_number}"
    return location


def _finding_sort_key(finding: Finding) -> tuple[int, str, str, int, str]:
    return (
        SEVERITY_RANK[finding.severity],
        finding.rule_id,
        finding.file_path.as_posix() if finding.file_path is not None else "",
        finding.line_number or 0,
        finding.message,
    )


def _html(value: str) -> str:
    return escape(value, quote=True)
