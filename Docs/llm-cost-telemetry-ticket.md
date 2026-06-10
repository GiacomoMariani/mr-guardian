# Ticket — Store per-review LLM cost telemetry

Persist an estimated USD **cost** for every LLM call made during a review — the LLM rule
checks, the AI summary, and the developer profile — plus a rolled-up per-review total,
mirroring how `weekly_llm_reviews` already stores `estimated_cost_usd` + `currency`.
Opened 2026-06-09.

**Storage only.** This ticket writes cost to the database; it does **not** surface cost in
the review report, dashboards, or any UI. Display is deferred (see the staged-observability
note in [In scope §7](#7-guidance-note--both-claudemd-and-agentsmd)).

**Why now:** the README roadmap item *"richer observability for rule execution, prompt
size, provider latency, token usage, and review outcomes"* is partly delivered — per-LLM
call we persist tokens (`input/output/total`), latency (`duration_ms`), and status — but we
never convert tokens into a cost. The weekly LLM review already carries an estimated cost;
individual reviews do not, so the per-review review-cost question can't be answered from the
stored data.

**Status (2026-06-09): implemented (storage only).** Added `mr_guardian/core/llm_pricing.py`
(typed `provider -> model` rates per 1M tokens, generic fallback logged server-side, `None`
when both token counts are missing). `estimated_cost_usd` now lives on `LlmRuleMetric`,
`LlmReviewSummary`, `LlmDeveloperProfile`; the engine/summary/profile builders compute it
from token usage. `review_runs` gained `estimated_cost_usd` (a rollup recomputed from the
per-call costs by `_recompute_review_cost`) + `currency`, and per-call cost columns; all are
added by additive migration on existing DBs. Covered by `test_llm_pricing.py`, engine +
storage round-trip/rollup/migration tests; documented in
[api-review-feeds.md](api-review-feeds.md) + [review-history-schema.md](review-history-schema.md);
staged-observability note added to CLAUDE.md and AGENTS.md. **No UI surfaces cost** (report
and dashboards untouched), per the staged rollout. `pytest`, `ruff check .`, `mypy
mr_guardian` all pass.

Implementation note vs. the original scope: the review-level total is **derived** (recomputed
from the stored per-call costs) rather than supplied verbatim on `POST /reviews`, so cost is
never accepted as a free-standing review-level input — it always reflects the per-call rows.

## Current state

- **Tokens are already persisted per LLM call, but no cost:**
  - `review_llm_rule_metrics` stores per-rule `provider`, `model`, `status`, `duration_ms`,
    `input_tokens`, `output_tokens`, `total_tokens`, `error_message`
    ([history.py:1030](../mr_guardian/storage/history.py)) — no cost column.
  - `review_runs` stores `llm_summary_*` and `developer_profile_*` token + duration columns
    ([history.py:60](../mr_guardian/storage/history.py),
    [history.py:69](../mr_guardian/storage/history.py)) — no cost columns.
  - The typed models `LlmRuleMetric`, `LlmReviewSummary`, `LlmDeveloperProfile`
    ([models/review.py:42](../mr_guardian/models/review.py)) carry tokens, no cost.
- **The only cost in the system today** is `estimated_cost_usd` + `currency` on
  `weekly_llm_reviews` ([history.py:203](../mr_guardian/storage/history.py);
  model [weekly_review.py:45](../mr_guardian/models/weekly_review.py)). It is **supplied
  externally** (manual payload / demo drip), not computed from tokens.
- **No pricing table exists anywhere** — there is nothing to convert tokens → dollars.
  (`grep -i "cost|price|pricing"` finds only the weekly field, docs, and the unrelated
  hosting notes.)
- **The report shows none of this telemetry** (no tokens/latency/cost) —
  [visual_report.py](../mr_guardian/reporting/visual_report.py). This ticket leaves it that
  way.

## In scope

### 1. Pricing module (Python)
New `mr_guardian/core/llm_pricing.py` (provider-agnostic reference data + a pure function;
**not** YAML — the YAML-only rule applies to *rules*, not pricing):

- `ModelPricing(input_per_million: float, output_per_million: float)` — rates per
  **1,000,000 tokens** (matches provider price sheets).
- `PRICING: dict[str, dict[str, ModelPricing]]` keyed `provider -> model`, seeded with the
  models actually used (at minimum `openai` / `gpt-4.1-mini`, plus the other OpenAI models
  the deployment may select).
- `GENERIC_FALLBACK: ModelPricing` — a single standard fallback rate.
- `estimate_cost_usd(*, provider: str, model: str, input_tokens: int | None,
  output_tokens: int | None) -> float | None` — pure function:
  - Look up `provider`/`model`; on a miss, use `GENERIC_FALLBACK` **and emit a server-side
    `logging.warning`** naming the unpriced provider/model (so the fallback is recorded, not
    silently swallowed). The fallback must **never** be flagged to the frontend.
  - `cost = input_tokens/1e6 * input_per_million + output_tokens/1e6 * output_per_million`,
    rounded to a fixed precision (e.g. 6 d.p.).
  - If **both** token counts are `None`, return `None` (no quantity to price — distinct from
    an unknown rate). A missing single component is treated as `0`.

### 2. Models (`models/review.py`)
- Add `estimated_cost_usd: float | None = None` to `LlmRuleMetric`, `LlmReviewSummary`,
  `LlmDeveloperProfile` (the per-call amount, beside the existing token fields).
- Add review-level rollup to `ReviewRunCreate` **and** `ReviewRunRecord`
  ([models/history.py:28](../mr_guardian/models/history.py)):
  `estimated_cost_usd: float | None = None` and `currency: str = "USD"`.
- `currency` lives **once** at the review level (mirroring weekly's cost+currency pairing);
  per-call rows carry only the amount, implicitly in the review currency. _(Alternative:
  replicate `currency` on every component as weekly does — see Decisions.)_

### 3. Compute cost at construction time
Cost is computed when each artifact is built, then persisted (not recomputed on read), so a
stored row keeps the price in effect at review time — same principle as the weekly fixed
cost.

- Per-rule: `_llm_metric` in [engine.py:116](../mr_guardian/core/engine.py) — call
  `estimate_cost_usd` from the runner's `provider_name`/`model_name` + token usage.
- AI summary: `LlmReviewSummary(...)` in [review.py:238](../mr_guardian/core/review.py).
- Developer profile: `LlmDeveloperProfile(...)` in
  [developer_profile.py:131](../mr_guardian/core/developer_profile.py).
- **Review-level rollup:** where `ReviewRunCreate` is assembled
  ([review_history.py:37](../mr_guardian/core/review_history.py)) set
  `estimated_cost_usd = sum(non-null component costs)` (or `None` if no priced component)
  and `currency`. For manual imports
  ([manual_review.py:108](../mr_guardian/core/manual_review.py)) cost stays whatever the
  payload supplies (else `None`); do not fabricate.

### 4. Storage (`storage/history.py`)
Add columns + **additive `ALTER TABLE … ADD COLUMN` migrations**, mirroring the existing
`_ensure_*` column-migration pattern ([history.py:1355](../mr_guardian/storage/history.py)):

- `review_llm_rule_metrics`: `estimated_cost_usd REAL`.
- `review_runs`: `estimated_cost_usd REAL`, `currency TEXT NOT NULL DEFAULT 'USD'`,
  `llm_summary_estimated_cost_usd REAL`, `developer_profile_estimated_cost_usd REAL`.
- Update the inserts (`_insert_llm_metrics`, the `review_runs` insert, the
  summary/profile writers) and the read builders (`_optional_float` round-trip at
  [history.py:1538](../mr_guardian/storage/history.py), the
  `LlmReviewSummary`/`LlmDeveloperProfile` builders at
  [history.py:1554](../mr_guardian/storage/history.py)) to carry cost both ways.
- Reuse the weekly `estimated_cost_usd`/`currency` handling as the template.

### 5. Schema + JSON
- Extend `review_run_record_schema()` `x-sqlite-columns`
  ([models/history.py:116](../mr_guardian/models/history.py)) with the new columns and add an
  `x-storage-notes` line for cost.

### 6. "How to load data to the DB" docs (add cost instructions)
The existing DB-loading instructions must explain the new cost fields:

- [Docs/api-review-feeds.md](api-review-feeds.md): the `POST /reviews/{id}/llm-metrics`,
  `PUT /reviews/{id}/llm-summary`, and `PUT /reviews/{id}/developer-profile` payloads now
  accept an optional per-call `estimated_cost_usd`; `POST /reviews` accepts review-level
  `currency`. The review-level total is derived (recomputed from the per-call costs), not
  accepted directly.
- [Docs/review-history-schema.md](review-history-schema.md): add the cost fields to the
  Field Reference and the SQLite Mapping Notes.
- **AGENTS.md → "Bloomkeeper Weekly MR Drip"**: the demo-data loader must fabricate a
  per-review cost for each posted MR (consistent with how it already fabricates the weekly
  `estimated_cost_usd`), so seeded/dripped reviews carry cost like real ones. (Generators
  live in git-ignored `personal-notes/`; update the instructions there too when implementing.)

### 7. Guidance note — BOTH CLAUDE.md and AGENTS.md
Add a short **staged-observability** convention to *both* files:

> Observability telemetry (LLM cost, prompt size, provider latency, token usage, …) is
> **persisted to the history DB first**. Surfacing it in the review report or dashboards is a
> **separate step, undertaken only when explicitly prioritized** — storing a metric does not
> imply showing it. (e.g. per-review LLM cost is stored as of this ticket but intentionally
> not displayed.)

### 8. Tests (per AGENTS.md testing rules)
- `tests/unit/test_llm_pricing.py` (new): known model rate; **fallback** used for an unknown
  model (and a warning is logged); `None` when both token counts are absent; rounding.
- Engine: a succeeded LLM rule metric carries a computed `estimated_cost_usd`; the
  review-level rollup equals the sum of component costs
  ([test_review_engine.py](../tests/unit/test_review_engine.py) / review flow tests).
- Storage round-trip: cost persists and reloads on metrics, summary, profile, and the review
  rollup; **migration** adds the columns to an older DB created without them
  ([test_review_history_store.py](../tests/unit/test_review_history_store.py)).
- API feeds: the `/reviews*` write payloads accept and echo `estimated_cost_usd`
  ([test_api.py](../tests/unit/test_api.py)).
- Confirm **no** report/visual-report test changes are needed (display is out of scope).

Before marking complete, run `pytest`, `ruff check .`, `ruff format .`, `mypy mr_guardian`.

## Decisions

- **Granularity = all LLM calls + a review-level rollup** (per product decision). Per-call
  rows store the cost amount; `currency` is stored once on `review_runs` alongside the
  rollup, mirroring weekly's cost+currency pairing at the review level. _(Alternative:
  replicate `currency` on every component table like weekly — rejected as redundant; revisit
  if multi-currency per review is ever needed.)_
- **Pricing source = a typed Python module** (per decision), not YAML or env-configurable.
  The YAML-only-source-of-truth rule governs *rules*, not pricing reference data.
- **Unknown / unpriced model = a standard generic fallback rate**, computed and stored like
  any other cost, with a **server-side log** of the fallback (not silent) and **no frontend
  signal** that a fallback was used (per decision). Missing token *counts* → `NULL` cost
  (cannot price an absent quantity). _Implemented per this reading of "store a standard
  generic fallback without silently / do not tell anyone, especially on the frontend."_
- **Rates per 1,000,000 tokens**; cost rounded to a fixed precision.
- **Compute-then-store** (not compute-on-read) so historical rows keep their as-of price,
  matching the weekly model.

## Out of scope

- **Any UI/report/dashboard display of cost** — [visual_report.py](../mr_guardian/reporting/visual_report.py)
  and the Streamlit app are untouched. Deferred per the staged-observability note (§7).
- **Prompt-size telemetry** (the other identified observability gap) — separate ticket.
- **Backfilling** cost onto already-stored historical reviews — older rows keep `NULL` cost;
  the migration only adds the columns.
- **Configurable/overridable pricing** (env vars, YAML, per-deployment overrides) — the
  Python table is the single source for now.

## Touch points

- [mr_guardian/core/llm_pricing.py](../mr_guardian/core/llm_pricing.py) — **new** pricing
  module.
- [mr_guardian/models/review.py](../mr_guardian/models/review.py) — cost on `LlmRuleMetric`,
  `LlmReviewSummary`, `LlmDeveloperProfile`.
- [mr_guardian/models/history.py](../mr_guardian/models/history.py) — review-level
  `estimated_cost_usd`/`currency` on `ReviewRunCreate`/`ReviewRunRecord`; schema columns.
- [mr_guardian/core/engine.py](../mr_guardian/core/engine.py) — per-rule cost in `_llm_metric`.
- [mr_guardian/core/review.py](../mr_guardian/core/review.py) — summary cost.
- [mr_guardian/core/developer_profile.py](../mr_guardian/core/developer_profile.py) — profile cost.
- [mr_guardian/core/review_history.py](../mr_guardian/core/review_history.py) — review rollup.
- [mr_guardian/core/manual_review.py](../mr_guardian/core/manual_review.py) — manual-import cost passthrough.
- [mr_guardian/storage/history.py](../mr_guardian/storage/history.py) — columns, migrations, insert/read.
- Docs: [api-review-feeds.md](api-review-feeds.md), [review-history-schema.md](review-history-schema.md).
- Guidance: CLAUDE.md **and** AGENTS.md (staged-observability note; drip data-loading note).
- Tests: [test_llm_pricing.py](../tests/unit/test_llm_pricing.py) (new),
  [test_review_engine.py](../tests/unit/test_review_engine.py),
  [test_review_history_store.py](../tests/unit/test_review_history_store.py),
  [test_api.py](../tests/unit/test_api.py).
