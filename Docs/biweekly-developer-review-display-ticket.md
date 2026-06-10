# Ticket — Biweekly developer LLM review: lead-dashboard display

Surface the biweekly developer LLM review (from the backend ticket) on the lead dashboard —
**token-first, with cost** — and switch the developer views off the deprecated per-review
profile. Opened 2026-06-10. **Depends on**
[biweekly-developer-review-backend-ticket.md](biweekly-developer-review-backend-ticket.md).

**Why now:** the backend ticket replaces the per-review `LlmDeveloperProfile` with a periodic
per-developer review; the "Latest LLM Developer Profile" UI must move to the new artifact, and
its cost/tokens should be surfaced like everywhere else (token-first).

**Status (2026-06-10): implemented (display + demo data).** Added `_developer_llm_review_panel`
(token-first: result/score/period/summary/top-risks/actions + an "LLM Tokens" card with an
`est. cost` subtitle) + `_developer_llm_review_badge` + a cached `_cached_recent_developer_reviews`
loader. The developer **detail page** now shows it (with a period selector) in place of the
"Latest LLM Developer Profile" section. Demo: the seed fabricates a biweekly developer review
per developer (relabel relabels/reprices them; a new bloomkeeper invariant requires one per
dev); the local DB was regenerated so the panel is populated. Covered by `test_dashboard.py`;
`pytest` / `ruff check .` / `mypy mr_guardian` pass.

**Done (2026-06-10):** the **product-engine generation rip-out** — `store_review_result` no
longer generates a per-review profile, `core/developer_profile.py` is deleted, the CLI / GitLab
/ API wiring + the `developer_profile_*` and (orphaned) `score_target_*` settings are removed,
the dead UI helpers (`_developer_profile_panel` / `_latest_developer_profile_run` / `_score_card`
/ `_mean_score` / `_llm_status_pill`) are gone, and the bloomkeeper "every dev has a profile"
invariant is replaced by the biweekly-review one. The biweekly review panel is now shown in
**both** the developer detail page and the lead "Selected Developer" drill-down (the selected
developer's latest fortnight). **Still deferred:** the deeper back-compat cleanup — dropping the
`developer_profile_*` columns, the `LlmDeveloperProfile` model, and the now-unused
`summarizer_ai` profile runner.

## Decisions

- **Token-first display with cost**, consistent with the MR report, the PM/lead/developer
  dashboards, and the weekly panel (tokens lead; `est. <cost>` is secondary). Reuse
  `_format_tokens` / `_cost_detail`.
- **Replace** the developer detail page's "Latest LLM Developer Profile" section with a
  biweekly developer review panel.

## In scope

### 1. Developer review panel
A panel mirroring `_weekly_llm_review_panel` ([app/streamlit_app.py](../app/streamlit_app.py))
but per developer: result badge, score, the period (`period_start`–`period_end`), summary,
top risks, recommended actions, plus a **token-first "LLM Tokens" card** (value = total
tokens, subtitle = `est. <cost>`) and the provenance footer (provider / model / tokens / cost).

### 2. Lead dashboard
- Show the **selected developer's latest** biweekly review — in the "Selected Developer"
  drill-down and on the developer detail page.
- Optional **period selector** (like the weekly week-picker) to browse prior fortnights, fed by
  a DB-mtime-cached `recent_developer_llm_reviews(developer_id=...)` loader.

### 3. Retire the per-review profile UI
- Replace the developer detail page's "Latest LLM Developer Profile" section
  (`_developer_profile_panel` / `_latest_developer_profile_run`) with the new panel.
- Remove `_developer_profile_panel` / `_latest_developer_profile_run` once nothing else uses
  them.

### 4. Tests
- Panel renders result / score / period / summary / risks / actions + the token-first card +
  `est. <cost>` subtitle.
- Empty state when a developer has no biweekly review yet.
- Confirm the old "Latest LLM Developer Profile" section is gone.

## Out of scope
- Backend / model / API / data feed (backend ticket).
- Lead dashboard's developer **table** columns (unchanged unless a follow-up asks).

## Touch points
- [app/streamlit_app.py](../app/streamlit_app.py) — new developer-review panel, lead drill-down
  + developer detail page, cached loader; remove the old profile panel.
- tests: [tests/unit/test_dashboard.py](../tests/unit/test_dashboard.py)
- Depends on: [biweekly-developer-review-backend-ticket.md](biweekly-developer-review-backend-ticket.md);
  mirrors [weekly-review-history-ticket.md](weekly-review-history-ticket.md).
