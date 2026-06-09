# Ticket — Access previous weekly LLM reviews

Let the dashboard surface **previous** weekly LLM reviews, not just the latest. The
reviews are all stored, but today only the most recent one is reachable. Opened
2026-06-09.

**Why now:** the "Weekly LLM Review" panel shows only the current week; there is no way
to look back at prior weeks to see how the assessment trended. (Deferred here from the
beta-phase ETA widget ticket, which marked weekly-review history out of scope.)

**Status (2026-06-09): implemented.** Added `ReviewHistoryStore.recent_weekly_llm_reviews()`
and `find_weekly_llm_review()` (with `weekly_llm_review()` delegating to it), core loaders
`load_recent_weekly_llm_reviews` / `load_weekly_llm_review`, the read endpoints
`GET /weekly-llm-reviews` and `GET /weekly-llm-reviews/{id}`, and a **week selector** under
the dashboard panel (latest stays the default). Covered by tests in `test_api.py`,
`test_review_history_store.py`, `test_dashboard.py`; documented in
[weekly-llm-review.md](weekly-llm-review.md). UX confirmed: week-picker selectbox.

## Current state

- **Dashboard:** `_render_weekly_llm_review` reads `_cached_weekly_review` →
  `load_latest_weekly_llm_review` ([app/streamlit_app.py](../app/streamlit_app.py)) — the
  latest row only.
- **Storage:** `ReviewHistoryStore` has `latest_weekly_llm_review()` and
  `weekly_llm_review(weekly_review_id)` ([mr_guardian/storage/history.py](../mr_guardian/storage/history.py)),
  but **no list/recent** method — and the by-id fetch is unusable without a way to
  discover IDs.
- **API:** only `GET /weekly-llm-reviews/schema` and `POST /weekly-llm-reviews/manual`
  ([app/api.py](../app/api.py)) — no read endpoint for stored reviews.
- All weekly reviews persist in `weekly_llm_reviews` (autoincrement, never overwritten),
  so the data is already there — only read paths are missing.

## In scope

### 1. Storage — list recent reviews
Add `recent_weekly_llm_reviews(*, limit: int = 20) -> list[WeeklyLlmReviewRecord]`,
newest first (`ORDER BY week_start DESC, created_at DESC, weekly_review_id DESC`),
mirroring `recent_eta_notes` / `recent_review_runs`.

### 2. Core — loader
Add `load_recent_weekly_llm_reviews(database_path, *, limit)` to
[mr_guardian/core/weekly_llm_review.py](../mr_guardian/core/weekly_llm_review.py),
beside `load_latest_weekly_llm_review`.

### 3. API — read endpoints
- `GET /weekly-llm-reviews` — recent reviews, newest first (`?limit=N`, default 20).
- `GET /weekly-llm-reviews/{weekly_review_id}` — one stored review (`404` if missing).

### 4. Dashboard — pick a previous week
Under the Weekly LLM Review panel, add a **week selector** (`st.selectbox` labelled
`week_start → week_end`, default = latest) that re-renders the existing
`_weekly_llm_review_panel` / `_weekly_llm_result_badge` for the chosen review. A
DB-mtime-keyed cached `recent_weekly_llm_reviews` loader feeds the selector. Selecting the
latest reproduces today's behavior, so nothing regresses.

## Decisions

- **Dashboard UX = week selector** (pick a week → full panel), not a collapsed summary
  list — each weekly review is a rich panel, and a selector gives full fidelity for any
  past week while defaulting to the latest. _(Confirm vs. an expander list.)_
- **Ordering:** newest first, matching the existing weekly/eta/recent-review reads.
- **Read-only:** browsing only; no edit/delete of past reviews.

## Out of scope

- Editing or deleting stored weekly reviews.
- Trend charts across weekly scores (could follow once history is browsable).
- Pagination beyond a simple `limit`.

## Touch points

- [mr_guardian/storage/history.py](../mr_guardian/storage/history.py) (`recent_weekly_llm_reviews`).
- [mr_guardian/core/weekly_llm_review.py](../mr_guardian/core/weekly_llm_review.py) (loader).
- [app/api.py](../app/api.py) (list + by-id GET routes).
- [app/streamlit_app.py](../app/streamlit_app.py) (`_render_weekly_llm_review` + selector,
  cached recent loader).
- [Docs/weekly-llm-review.md](weekly-llm-review.md) (document the read endpoints + selector).
- Tests: [tests/unit/test_api.py](../tests/unit/test_api.py),
  [tests/unit/test_review_history_store.py](../tests/unit/test_review_history_store.py),
  [tests/unit/test_dashboard.py](../tests/unit/test_dashboard.py).
