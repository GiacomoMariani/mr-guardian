# Ticket — Single review report: LLM note, next-step copy, "Verdict" rename

Enhancements to the **single review (visual) report** ([mr_guardian/reporting/visual_report.py](../mr_guardian/reporting/visual_report.py))
— the dashboard's headline "Agent Review" artifact. Opened 2026-06-08. **All three items
implemented and verified 2026-06-08** (LLM note under the renamed "Outcome" band, severity-
aware next step, "Verdict"→"Outcome"); verified no-scroll across all 10 demo reviews after
re-calibrating the iframe height (per-finding 46→56 + an 80px note allowance).

**Why:** the report currently shows only the *deterministic* half (the findings table)
and a generic next-step. We surface the **LLM half** (already stored per review) and make
the guidance severity-aware, so a developer reading their own report knows exactly what
happens next.

## 1. LLM review note

Every review already stores an `llm_summary` (`LlmReviewSummary`, populated for all demo
reviews — `.text` ≈ 85–210 chars) — it is **never rendered** in the visual report today.

- Render `run.llm_summary.text` as a short, clearly **LLM-attributed** note (label /
  small accent), placed **directly under the verdict band** (above the stats/findings).
- Graceful fallback when there's no summary / a failed generation — hide the note (or a
  small "—"), don't break the layout.
- Keep it a *synthesis*, not a restatement of the findings table (the stored notes
  already are).
- Re-calibrate `_review_report_height` for the added block.

## 2. Severity-aware "next step"

Replace the generic `_next_steps` copy with a **single message for the top severity
present** (decided: "report the top one"):

| Top severity | Message (copy only — no real workflow) |
|---|---|
| **Blocking** | *"Resolve the blocking finding(s) before this can be assigned for review."* (keep the existing metadata-specific *"Add &lt;section&gt; to unblock"* when applicable) |
| **High or Warning** (high is treated as a warning) | *"Warning-level findings will be routed to the lead developer for sign-off."* |
| **Info / none** | *"No immediate action required."* |

- It is **report copy only** — we are **not** building an approval/routing workflow.
- One line for the top tier (not the current per-tier list). The skipped-LLM-rules note
  ("Re-run when the provider is available") can still append.

## 3. Rename "Verdict"

The big **VERDICT** label reads as harsh for an automated gate. Rename it — proposed
**"Outcome"** (alternatives: *Result · Assessment · Decision*; confirm at implementation).
Single label change in `_render_verdict` / its eyebrow; the verdict logic itself is
unchanged.

## Effort & scope

- All three live in `visual_report.py` (+ `test_visual_report.py`). #1 and #2 are
  **small** (data exists / copy + branch on top severity); #3 is **trivial**.
- **Out of scope:** any real lead-approval / routing system — #2 is messaging only.

## Decisions (agreed 2026-06-08)
- High is treated as a warning (→ lead sign-off), and is reported.
- "Lead sign-off" / "routed to the lead" is **copy**, not a workflow.
- Next step shows the **top severity** only.
- LLM note goes **under the verdict**.
- "Verdict" → a softer name (proposed "Outcome").

---

_No GitHub CLI / issue tooling in this environment — filed as an in-repo markdown ticket;
the body is issue-ready._
