# Ticket — A separate feed (write) endpoint per DB data item

Give every data item persisted in the history SQLite its **own dedicated API endpoint**
to feed it, instead of only the bundled [`POST /reviews/import`](../app/api.py) path.
Opened 2026-06-09.

**Status (2026-06-09): implemented.** Added `POST /reviews` plus seven per-component
feeds (findings, triggered-rules, evaluations, policies, llm-metrics, llm-summary,
developer-profile) in [app/api.py](../app/api.py), backed by `replace_*` / `set_*`
methods on `ReviewHistoryStore` and a [`review_components`](../mr_guardian/core/review_components.py)
core module. Covered by unit tests in [tests/unit/test_api.py](../tests/unit/test_api.py)
and documented in [Docs/api-review-feeds.md](api-review-feeds.md). Decisions below
resolved: **idempotent replace** for list feeds; **caller-owns** parent counts/score.

**Why now:** an audit of the FastAPI service ([app/api.py](../app/api.py)) against the
live database ([.mr-guardian/history.sqlite](../.mr-guardian/history.sqlite), 9 app
tables) confirmed that *every* table can already be written — but for a review and its
six child tables that happens **only** through one monolithic, admin-only request
(`/reviews/import`, backed by `ReviewHistoryStore.store_review_run` in
[mr_guardian/storage/history.py:218](../mr_guardian/storage/history.py)). There is no way
to feed a review's findings, evaluations, policies, LLM metrics, LLM summary, or
developer profile **on their own** — e.g. to attach a developer profile to an existing
review, or to backfill one child table — without re-posting the entire review run. We
want one endpoint per item, separated.

**Scope:** additive HTTP routes + thin `ReviewHistoryStore` methods. No schema change, no
new tables. `POST /reviews/import` stays as the efficient full-port path (see Decisions).

## Current feed coverage

| # | Data item (table / column group) | Today's feed | Separated endpoint exists? |
|---|---|---|---|
| 1 | `review_runs` (core scalar row) | `POST /reviews/import`, `POST /reviews/manual` (bundled) | ❌ only bundled |
| 2 | `review_findings` | bundled in `store_review_run` | ❌ |
| 3 | `triggered_rules` | bundled | ❌ |
| 4 | `review_evaluations` (+ `review_evaluation_triggered_rules`) | bundled | ❌ |
| 5 | `review_policies` | bundled | ❌ |
| 6 | `review_llm_rule_metrics` | bundled | ❌ |
| 7 | `llm_summary` (columns on `review_runs`) | bundled | ❌ |
| 8 | `developer_profile` (columns on `review_runs`) | bundled + internal `update_developer_profile` | ❌ (no route) |
| 9 | `weekly_llm_reviews` | `POST /weekly-llm-reviews/manual` | ✅ |
| 10 | `dashboard_eta_note` | `POST /dashboard/eta-note` | ✅ |

Items 9 and 10 are already separated — no work. Items 1–8 are the gap.

## In scope — one endpoint per item

All new write routes are **admin-gated** (`_verify_admin_token`, matching
`/reviews/import`) and reuse the existing typed models, so payload shapes match the
nested objects in `ReviewRunCreate` ([mr_guardian/models/history.py:28](../mr_guardian/models/history.py)).

### 1. Core review row — `POST /reviews`
Create just the `review_runs` row from the scalar fields of `ReviewRunCreate` (scope,
branch, developer_id, ticket_key, counts, score, report, etc.) with **empty** child
collections. Returns the new `review_id` so the sub-resource calls below can target it.
*Storage:* `store_review_run` already handles empty child lists — expose a `create_review_row`
wrapper, or just document posting `ReviewRunCreate` with empty arrays.

### 2. Findings — `POST /reviews/{review_id}/findings`
Body: `list[Finding]`. Appends to `review_findings` for an existing review.
*Storage:* new public `add_findings(review_id, findings)` wrapping `_insert_findings`
([history.py:768](../mr_guardian/storage/history.py)) + a review-exists check + commit.

### 3. Triggered rules — `POST /reviews/{review_id}/triggered-rules`
Body: `list[str]`. *Storage:* `add_triggered_rules` wrapping `_insert_triggered_rules`.

### 4. Evaluations — `POST /reviews/{review_id}/evaluations`
Body: `list[ReviewEvaluation]` (carries per-evaluation triggered rule IDs).
*Storage:* `add_evaluations` wrapping `_insert_evaluations` (handles the
`review_evaluation_triggered_rules` child too).

### 5. Policy summaries — `POST /reviews/{review_id}/policies`
Body: `list[ReviewPolicySummary]`. *Storage:* `add_policy_summaries` wrapping
`_insert_policy_summaries`.

### 6. LLM rule metrics — `POST /reviews/{review_id}/llm-metrics`
Body: `list[LlmRuleMetric]`. *Storage:* `add_llm_metrics` wrapping `_insert_llm_metrics`.

### 7. LLM summary — `PUT /reviews/{review_id}/llm-summary`
Body: `LlmReviewSummary`. Idempotent set of the `llm_summary*` columns.
*Storage:* new `set_llm_summary(review_id, summary)` — mirror the existing
`update_developer_profile` `UPDATE` pattern.

### 8. Developer profile — `PUT /reviews/{review_id}/developer-profile`
Body: `LlmDeveloperProfile`. **Lowest-hanging fruit** — the storage method
`update_developer_profile` ([history.py:366](../mr_guardian/storage/history.py)) already
exists and is exercised internally by
`maybe_update_developer_profile_snapshot` ([mr_guardian/core/developer_profile.py:17](../mr_guardian/core/developer_profile.py)).
This route only needs to wire it to HTTP, unlocking "attach/refresh a profile on an
existing review" without re-importing the whole run.

Each sub-resource route returns `404` when `review_id` is unknown and `401` without the
admin token, consistent with `delete_review` / `set_review_finality`.

## Decisions

- **Keep `POST /reviews/import`.** It stays as the one-shot verbatim full-port path; the
  separated endpoints are the granular complement, not a replacement. (`POST /reviews/manual`
  also stays — note it is intentionally *lossy*: it re-derives the ticket key and drops LLM
  annotations.)
- **Child feeds do NOT recompute the parent (resolved: caller-owns).** `review_runs`
  stores denormalized `blocking_count` / `high_count` / `warning_count` / `info_count` /
  `review_score`. Those are set by `POST /reviews` from the payload (as today for import)
  and are **not** recalculated when findings/evaluations are fed afterward — matching the
  verbatim-import philosophy. The caller owns parent/child consistency.
- **Sub-resources are idempotent, parented by `review_id` (resolved: replace).** They
  require the review row to exist first (FK `ON DELETE CASCADE` already in schema). `POST`
  on a list feed (findings, rules, evaluations, policies, metrics) **replaces the full
  set** for that review — re-feeding never duplicates, and an empty array clears it; `PUT`
  overwrites the single column-group items (llm-summary, developer-profile).
- **Admin-gated.** All writes require `X-MR-Guardian-Admin-Token`.

## Out of scope

- Bulk / multi-record import, and any **read/export** (GET) endpoint to pull reviews back
  out over the API (the dashboard reads SQLite directly today). Track separately if the
  Render-deployment porting workflow needs an API round-trip.
- Auto-recomputing parent counts/score from fed children (see Decisions).
- Any new tables or schema migration.

## Touch points

- Routes: [app/api.py](../app/api.py) (add beside the existing `/reviews*` writers).
- Storage: [mr_guardian/storage/history.py](../mr_guardian/storage/history.py) (promote
  the `_insert_*` helpers to public `add_*` methods + add `set_llm_summary`).
- Models reused: `Finding`, `ReviewEvaluation`, `LlmRuleMetric`, `LlmReviewSummary`,
  `LlmDeveloperProfile` ([mr_guardian/models/review.py](../mr_guardian/models/review.py)),
  `ReviewPolicySummary` ([mr_guardian/models/history.py](../mr_guardian/models/history.py)).
- Docs to mirror the per-endpoint style of [Docs/api-eta-note.md](api-eta-note.md),
  [Docs/api-review-finality.md](api-review-finality.md).
- Tests: extend the API tests under [tests/unit](../tests/unit).
