# Ticket — Surface LLM cost in the frontend

Display the per-review LLM cost that the cost-telemetry ticket persisted but intentionally
left hidden. This is the explicitly-prioritized "surface it" step of the staged
observability rollout (see CLAUDE.md / AGENTS.md "Observability Telemetry"). Opened
2026-06-10.

**Why now:** cost is fully stored (`review_runs.estimated_cost_usd` + per-call columns) and
ported through the loader, but only the **weekly** panel shows any cost. The per-review
report and the PM / lead / developer dashboards show none.

**Status (2026-06-10): implemented — all 4 phases done.**

- **Phase 1 — report:** `_render_cost` adds an "Estimated cost" diffline (total + LLM
  rules / AI summary / developer-profile breakdown) under Scope, hidden when nothing is priced.
- **Phase 2 — PM dashboard:** `PmDashboardSummary.total_estimated_cost_usd` (summed in
  `prepare_pm_dashboard_summary`) shown as an "Estimated Cost" card.
- **Phase 3 — lead dashboard:** `LeadDashboardSummary.total_estimated_cost_usd` shown as an
  "Estimated Cost" card above the developer table.
- **Phase 4 — developer view:** `LeadDeveloperSummary.total_estimated_cost_usd` (per
  developer) shown on the lead drill-down and the developer detail page.

**Refinement (2026-06-10): tokens-first.** Per product direction every surface now leads with
LLM **token usage** and shows estimated cost only as a secondary figure — the report appends
an `est. <cost>` suffix; the dashboards show an "LLM Tokens" card with the cost as a subtitle
(`_format_tokens` + `_cost_detail`). The **per-MR report excludes the developer profile** (a
developer-level artifact, not part of reviewing the MR), so the report's usage/cost = LLM rules
+ AI summary only; the dashboards' aggregate still counts every LLM call (rules + summary +
profile). The generic fallback rate is never flagged; unpriced totals show `-`. Covered by
`test_visual_report.py`, `test_pm_dashboard.py`, `test_lead_dashboard.py`. `pytest`,
`ruff check .`, `mypy mr_guardian` all pass.

## Decisions (from product)

- **Surfaces:** all four — per-review report, PM dashboard, lead dashboard, developer view.
- **Report detail:** review **total + breakdown** (LLM rules vs AI summary vs developer profile).
- **Dashboard metric:** **total spend** only (no per-MR average, per-developer column, or trend this round).
- **Labeling:** everything reads **"Estimated cost"** (matches the weekly panel). A generic
  **fallback** rate is **never** flagged on the frontend — a fallback cost renders as a normal
  cost. Show "—" / "n/a" when a total is `None` (no priced reviews in scope).

## Data already available

- Per review: `ReviewRunRecord.estimated_cost_usd` (+ `currency`) — the rollup.
- Breakdown: `llm_metrics[].estimated_cost_usd` (LLM rules), `llm_summary.estimated_cost_usd`,
  `developer_profile.estimated_cost_usd`.
- Dashboards already receive `list[ReviewRunRecord]`, so **total spend = sum of each review's
  `estimated_cost_usd`, skipping `None`**. The rollup is already per-call-summed, so summing
  rollups does not double-count. Do **not** fold in the weekly-review generation cost (that
  stays in the weekly panel; per AGENTS.md the weekly cost must not include review rollups).

## In scope

### 1. Per-review report — total + breakdown
[mr_guardian/reporting/visual_report.py](../mr_guardian/reporting/visual_report.py): render the
review's `estimated_cost_usd` as an "Estimated cost" figure (e.g. in the header meta beside
Findings, or the scope line), plus a small breakdown — LLM rules `sum(m.estimated_cost_usd)`,
AI summary, developer profile. Omit the block entirely when the total is `None` (no priced
LLM calls), so deterministic-only reviews are unchanged. Snapshot/fragment tests update.

### 2. PM dashboard — total spend
- [models/pm_dashboard.py](../mr_guardian/models/pm_dashboard.py): add
  `total_estimated_cost_usd: float | None` (+ `currency: str = "USD"`) to `PmDashboardSummary`.
- [core/pm_dashboard.py](../mr_guardian/core/pm_dashboard.py) `prepare_pm_dashboard_summary`:
  sum the window's review costs (None-safe).
- [app/streamlit_app.py](../app/streamlit_app.py): render an "Estimated cost" metric card.

### 3. Lead dashboard — total spend
- [models/lead_dashboard.py](../mr_guardian/models/lead_dashboard.py): add the total to
  `LeadDashboardSummary` (overall headline).
- [core/lead_dashboard.py](../mr_guardian/core/lead_dashboard.py)
  `prepare_lead_dashboard_summary`: sum across the window.
- Render the headline "Estimated cost" on the lead dashboard. (A per-developer cost **column**
  is out of scope — metric choice was total spend only.)

### 4. Developer view — that developer's total spend
- Add `total_estimated_cost_usd` to `LeadDeveloperSummary`
  ([models/lead_dashboard.py:53](../mr_guardian/models/lead_dashboard.py)), computed in
  `prepare_lead_developer_detail` / `prepare_lead_dashboard_summary` from the developer's
  review runs.
- Render an "Estimated cost" figure on the developer detail view in
  [app/streamlit_app.py](../app/streamlit_app.py).

### 5. Shared formatting
A single cost formatter (mirror `_weekly_cost`: `f"{cost:.4f} {currency}"`, "—" when `None`),
reused by the report and the dashboards so the wording/precision stay consistent. Consider
placing it in [app/streamlit_components.py](../app/streamlit_components.py) for the dashboards;
the report keeps its own (self-contained HTML).

## Tests

- [test_visual_report.py](../tests/unit/test_visual_report.py): report shows the total +
  breakdown when priced; shows nothing when all costs are `None` (snapshot/fragment).
- [test_pm_dashboard.py](../tests/unit/test_pm_dashboard.py),
  [test_lead_dashboard.py](../tests/unit/test_lead_dashboard.py),
  [test_dashboard.py](../tests/unit/test_dashboard.py): prepare functions total cost correctly,
  skip `None`, and return `None` when nothing is priced.
- Confirm the fallback rate is never surfaced (no "estimated/fallback" qualifier beyond the
  uniform "Estimated cost" label).
- Run `pytest`, `ruff check .`, `mypy mr_guardian`.

## Out of scope

- Per-MR average, per-developer cost column, and spend-trend charts (not selected).
- Cost in the report's API/JSON beyond what the record already carries.
- Multi-currency aggregation — totals assume a single currency (USD today).
- Re-pricing historical reviews (pre-cost rows stay `None` and render as "—").

## Touch points

- [mr_guardian/reporting/visual_report.py](../mr_guardian/reporting/visual_report.py)
- [mr_guardian/models/pm_dashboard.py](../mr_guardian/models/pm_dashboard.py),
  [mr_guardian/core/pm_dashboard.py](../mr_guardian/core/pm_dashboard.py)
- [mr_guardian/models/lead_dashboard.py](../mr_guardian/models/lead_dashboard.py),
  [mr_guardian/core/lead_dashboard.py](../mr_guardian/core/lead_dashboard.py)
- [app/streamlit_app.py](../app/streamlit_app.py),
  [app/streamlit_components.py](../app/streamlit_components.py)
- Tests as above.
- Related: [llm-cost-telemetry-ticket.md](llm-cost-telemetry-ticket.md) (storage),
  [render-loader-cost-port-ticket.md](render-loader-cost-port-ticket.md) (porting).
