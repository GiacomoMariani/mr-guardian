# Ticket — Biweekly developer LLM review: backend + data

Replace the per-review `LlmDeveloperProfile` with a **biweekly (2-week) per-developer LLM
review**, modeled on the weekly LLM review. This ticket covers the model, storage, ingestion
API, the demo-data feed, and the AGENTS.md data-feed note. Display is a **separate ticket**
([biweekly-developer-review-display-ticket.md](biweekly-developer-review-display-ticket.md)).
Opened 2026-06-10.

**Why now:** today the developer profile is a per-review snapshot stored on each `review_runs`
row — it accumulates one per review (Jack has 2, others 1) with no clean cadence or history,
and only the latest is shown. Product wants a periodic, per-developer LLM review on a fixed
2-week cadence, fed externally like the weekly review, with cost/token telemetry.

**Status (2026-06-10): backend implemented (additive).** New `developer_llm_reviews` table +
models (`DeveloperLlmReviewCreate`/`Record` in `models/developer_review.py`),
`core/developer_review.py` helpers, and admin-gated `POST` + `GET /developer-llm-reviews*`
endpoints — mirroring the weekly review, with cost/tokens. Covered by `test_developer_review.py`
+ `test_api.py`; `pytest` / `ruff check .` / `mypy mr_guardian` all pass; AGENTS.md data-feed
note added.

**§5 now implemented (2026-06-10).** The per-review `LlmDeveloperProfile` generation is removed:
`store_review_result` no longer takes a profile runner, `core/developer_profile.py` is deleted,
and the CLI / GitLab / API wiring + the `developer_profile_*` settings are gone. The
`review_runs.developer_profile_*` columns, the `LlmDeveloperProfile` model, the storage
read / `update_developer_profile` / import (`PUT .../developer-profile`) path, and the
`summarizer_ai` profile **runner** are kept for back-compat reads of historical rows — their
removal plus the column drop is the remaining "later cleanup". The bloomkeeper "every dev has a
profile" invariant is replaced by the biweekly-review invariant. `pytest` / `ruff check .` /
`mypy mr_guardian` pass.

## Decisions (from product)

- **Replace** the per-review `LlmDeveloperProfile` (stop generating it; the biweekly review
  supersedes it).
- **Externally fed**, exactly like the weekly LLM review — new table + manual ingestion API;
  the demo drip fabricates them. **No scheduler.**
- **Mirror the weekly review** shape, scoped to one developer + a 2-week window.
- Cost/tokens stored like weekly (`estimated_cost_usd` + `currency`); display is **token-first**
  (handled in the display ticket).

## Reference (template to mirror)

`weekly_llm_reviews` table; `WeeklyLlmReviewCreate`/`WeeklyLlmReviewRecord`
([models/weekly_review.py](../mr_guardian/models/weekly_review.py));
[core/weekly_llm_review.py](../mr_guardian/core/weekly_llm_review.py); the weekly storage
methods + `POST /weekly-llm-reviews/manual` + GET endpoints ([app/api.py](../app/api.py)).

## In scope

### 1. Models — `mr_guardian/models/developer_review.py` (new)
`DeveloperLlmReviewCreate` (`extra="forbid"`, frozen) + `DeveloperLlmReviewRecord` +
`developer_llm_review_payload_schema()`, mirroring `weekly_review.py`. Fields:
- `developer_id: str`
- `period_start: date` (a Monday), `period_end: date` (the Sunday 13 days later — a 2-week window)
- `created_at: datetime | None`
- `result` (reuse the weekly enum: `optimal` / `on_track` / `needs_attention` / `at_risk` / `blocked`)
- `score: int` (1–100), `summary: str`
- `review_request_count`, `ticket_count`, `approved_ticket_count`, `observed_ticket_count`
- `blocking_review_count`, `high_risk_review_count`, `warning_review_count`, `info_review_count`
- `top_risks: list[str]`, `recommended_actions: list[str]`
- `provider`, `model`, `input_tokens`, `output_tokens`, `total_tokens`
- `estimated_cost_usd: float | None`, `currency: str = "USD"`

Validators mirror weekly: `period_start` is a Monday; `period_end == period_start + 13 days`;
token totals consistent; three-letter currency; non-empty text fields. _(The weekly `phase`
field is intentionally omitted — developer-scoped, not a delivery milestone. Confirm.)_

### 2. Storage — `storage/history.py`
- New `developer_llm_reviews` table (autoincrement id + the fields above), index on
  `(developer_id, period_start DESC)`. `CREATE TABLE IF NOT EXISTS` (new table → no column
  migration; add a `_ensure_*` only if fields evolve later).
- Methods mirroring weekly: `store_developer_llm_review`,
  `latest_developer_llm_review(developer_id)`,
  `recent_developer_llm_reviews(*, developer_id=None, limit=20)`,
  `find_developer_llm_review(review_id)`.
- Cost columns `estimated_cost_usd REAL`, `currency TEXT NOT NULL DEFAULT 'USD'` like weekly.

### 3. Core — `mr_guardian/core/developer_review.py` (new)
Store/load helpers mirroring [core/weekly_llm_review.py](../mr_guardian/core/weekly_llm_review.py):
`store_developer_llm_review_payload`, `load_latest_developer_llm_review`,
`load_recent_developer_llm_reviews`, `load_developer_llm_review`,
`manual_developer_llm_review_payload_schema`.

### 4. API — `app/api.py` (admin-gated, mirroring weekly)
- `POST /developer-llm-reviews/manual` — ingest one (schema-validated).
- `GET /developer-llm-reviews/schema`
- `GET /developer-llm-reviews?developer=<id>&limit=N` — recent, newest first.
- `GET /developer-llm-reviews/{review_id}` — one stored review (`404` if missing).

### 5. Replace the per-review profile
- Stop generating `LlmDeveloperProfile` per review: remove the
  `maybe_update_developer_profile_snapshot` call from
  [core/review_history.py](../mr_guardian/core/review_history.py) `store_review_result`, and
  retire the generation path in [core/developer_profile.py](../mr_guardian/core/developer_profile.py).
- Keep the `review_runs.developer_profile_*` columns nullable for back-compat **reads** of
  existing rows, but stop writing them. (Full column removal is a later cleanup.)
- The UI switch (dev detail page + lead drill-down) is in the display ticket — **land both
  together** so there's no gap where neither shows.

### 6. Demo feed + AGENTS.md note
- The demo drip ([personal-notes/post_weekly_mr.py](../personal-notes/post_weekly_mr.py),
  git-ignored) fabricates a biweekly developer review per developer per 2-week window, with
  fabricated cost priced like the engine — same approach as the weekly review. Fabrication
  specifics stay in `personal-notes/`.
- **AGENTS.md:** add a data-feed note for the biweekly developer review **contract** (per
  developer, 2-week window, the fields, cost stored like weekly), as a sibling to the existing
  weekly-review / cost notes. Contract only — no demo-fabrication/relabel specifics in tracked files.
- The git-ignored loader ([load_to_render.py](../personal-notes/load_to_render.py)) carries
  developer reviews to a deployment (feed endpoint above).

### 7. Tests
- Model validation: period boundaries (Monday / +13 days), token totals, currency, extra-forbid.
- Storage round-trip incl. cost; latest / recent / by-id; per-developer filtering.
- API: ingest + schema + reads; admin gate; `404`.

## Out of scope
- All display (separate ticket).
- Auto-generation / scheduler (externally fed, by decision).
- Removing the `developer_profile_*` columns (later cleanup).

## Touch points
- **new:** `mr_guardian/models/developer_review.py`, `mr_guardian/core/developer_review.py`
- [mr_guardian/storage/history.py](../mr_guardian/storage/history.py), [app/api.py](../app/api.py)
- [mr_guardian/core/review_history.py](../mr_guardian/core/review_history.py),
  [mr_guardian/core/developer_profile.py](../mr_guardian/core/developer_profile.py) (stop per-review generation)
- AGENTS.md (data-feed note)
- `personal-notes/post_weekly_mr.py`, `personal-notes/load_to_render.py` (git-ignored demo feed)
- tests: new `tests/unit/test_developer_review.py`, plus `test_api.py`, `test_review_history_store.py`
- Related: [weekly-review-history-ticket.md](weekly-review-history-ticket.md),
  [llm-cost-telemetry-ticket.md](llm-cost-telemetry-ticket.md).
