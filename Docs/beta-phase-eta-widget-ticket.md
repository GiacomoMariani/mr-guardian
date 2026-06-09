# Ticket — Drive the Beta Phase ETA widget from the weekly review + ETA note history

Make the dashboard "Beta Phase ETA" widget data-driven. Today the phase name is
hard-coded in Streamlit and the readiness % is an unrelated computed metric; source
**both from the weekly LLM review** (the "AI evaluation" the widget's disclaimer already
cites), and keep a **history of the manual ETA notes** (which today overwrite). Opened
2026-06-09.

**Supersedes** the initial draft (`eta-note-phase-history-ticket.md`), which stored the
phase label on the ETA note and kept readiness = pass_rate. Per review with Jack, the
phase and readiness now come from the weekly review.

**Confirmed decisions (Jack):**
- **Readiness %** ← weekly LLM review `score` (1–100), replacing the 30-day `pass_rate`.
- **Phase name** ← a new `phase` field on the weekly LLM review; drop the ETA-note
  `phase_label` idea.
- **Keep ETA-note history** (past notes), single phase (not a multi-phase switcher).
- **No-data fallback:** default phase `Beta Phase` + `—` readiness when no weekly review
  exists (approved).

**Status (2026-06-09): implemented.** `phase` added to the weekly review
(model + `weekly_llm_reviews` column + migration + schema); the ETA widget now sources
its title from `weekly_review.phase` and readiness from `weekly_review.score`
([app/streamlit_app.py](../app/streamlit_app.py)); the singleton ETA note became an
append-only `dashboard_eta_notes` log (current = latest, legacy row migrated in) with
`GET /dashboard/eta-note/history` and a "Previous notes" view. Covered by unit tests in
`test_api.py`, `test_dashboard.py`, `test_review_history_store.py`; docs updated in
[weekly-llm-review.md](weekly-llm-review.md) and [api-eta-note.md](api-eta-note.md).

## Current state

- **"Beta Phase" is hard-coded** in [app/streamlit_app.py](../app/streamlit_app.py): title
  `"Beta Phase ETA"` (~L400), disclaimer "Confirm beta phase dates…" (~L408), empty-state
  (~L416).
- **Readiness % is `pass_rate`, not the weekly score.** `_render_pm_dashboard` returns
  `summary.pass_rate` (~L555); `_readiness_badge` renders it on the ETA widget. Shows `0%`
  because the DB is empty.
- **The weekly review already carries the percentage but not a phase.** `score` is an
  `int 1–100` ([models/weekly_review.py](../mr_guardian/models/weekly_review.py)), shown as
  `{score}/100`. Its `result` field is a *status* (`on_track`/`at_risk`/…), **not** a phase
  name. No `phase` field exists anywhere.
- **The ETA note is a singleton, overwrite-on-write** (`dashboard_eta_note`,
  `id PK CHECK(id=1)`, `ON CONFLICT DO UPDATE`) — prior notes are lost. It has two storage
  implementations on the same table that must stay consistent:
  [core/dashboard_eta.py](../mr_guardian/core/dashboard_eta.py) (API + dashboard) and
  `ReviewHistoryStore.get_eta_note`/`set_eta_note` in
  [storage/history.py](../mr_guardian/storage/history.py).

## In scope

### 1. Add `phase` to the weekly LLM review
- Add `phase: str = "Beta Phase"` to `WeeklyLlmReviewCreate` and `WeeklyLlmReviewRecord`
  ([models/weekly_review.py](../mr_guardian/models/weekly_review.py)), with the same
  trim/non-empty validation as `summary`. Defaulting keeps existing ingestion payloads
  valid.
- Add a `phase` column (default `'Beta Phase'`) to `weekly_llm_reviews`; thread it through
  `store_weekly_llm_review`, `_weekly_llm_review_from_row`, and the
  `weekly_llm_review_payload_schema` storage notes
  ([storage/history.py](../mr_guardian/storage/history.py)).
- `POST /weekly-llm-reviews/manual` accepts it automatically (schema derives from the
  model). Update [Docs/weekly-llm-review.md](weekly-llm-review.md).

### 2. Drive the ETA widget from the latest weekly review
- **Phase** → widget title `f"{review.phase} ETA"`, plus the disclaimer and empty-state
  text, from the latest weekly review.
- **Readiness %** → `_readiness_badge(review.score)` from the latest weekly review;
  remove the `pass_rate` plumbing (`_render_pm_dashboard` no longer needs to return it —
  `pass_rate` stays as the "Pass Rate" card on Delivery Health, just not as readiness).
- Rewire `_render_eta_note` to read the latest weekly review (reuse the existing
  `_cached_weekly_review`) for both phase and readiness; the ETA note still supplies the
  manual message + target date.
- **Fallbacks when no weekly review exists:** phase falls back to a default
  (`"Beta Phase"`, optionally `MR_GUARDIAN_DEFAULT_PHASE_LABEL`); readiness shows `—`
  (not `0%`, which would misread as "0% ready").

### 3. Keep ETA note history
The `CHECK (id = 1)` constraint blocks appends, so add an append-only log instead of
mutating the constrained table:
- New table `dashboard_eta_notes`: `eta_note_id PK AUTOINCREMENT, message, target_date,
  created_at`. **Current note = newest row.** `set_*` INSERTs (drop the upsert);
  `load_*`/`get_eta_note` return the latest. The ETA note stays manual message + target
  only — **no `phase_label`** (phase now lives on the weekly review).
- **Migration:** on first init, if the legacy singleton has a row and the new table is
  empty, copy it across; leave the legacy table dormant (no destructive drop).
- Add `recent_eta_notes(*, limit)` (core + storage), `GET /dashboard/eta-note/history`,
  and a collapsed "Previous notes" view under the widget.

## Decisions

- **Weekly review is the source of truth** for the widget's phase + readiness. The ETA
  note is purely the human annotation (message, target, history).
- **`phase` defaults to `"Beta Phase"`** on the weekly-review model for backward
  compatibility; make it required only if every ingestion path will always set it.
- **No-data fallbacks:** default phase label + `—` readiness when no weekly review exists.
- **Reconcile the two ETA-note storage paths** — prefer routing
  `ReviewHistoryStore.get_eta_note`/`set_eta_note` through `core/dashboard_eta.py` (single
  source) if the `ReviewHistoryStore` variant has no production caller beyond tests.
  _(Confirm.)_
- **Stale weekly review:** always use the latest stored review regardless of week; no
  freshness gate. _(Confirm.)_

## Out of scope

- `pass_rate` as the readiness source (replaced; still shown as the "Pass Rate" card on
  Delivery Health).
- Multiple simultaneous phases / a phase switcher.
- Surfacing previous **weekly reviews** in the dashboard (only the latest drives the
  widget; weekly-review history is a separate ticket).

## Touch points

- Weekly review: [models/weekly_review.py](../mr_guardian/models/weekly_review.py),
  [storage/history.py](../mr_guardian/storage/history.py)
  (`weekly_llm_reviews` schema, `store_weekly_llm_review`, `_weekly_llm_review_from_row`),
  [app/api.py](../app/api.py) (`/weekly-llm-reviews/manual` — schema only),
  [Docs/weekly-llm-review.md](weekly-llm-review.md).
- ETA widget: [app/streamlit_app.py](../app/streamlit_app.py) (`_render_eta_note`,
  `_eta_note_panel`, `_readiness_badge`, `_render_pm_dashboard` return, ~L344–443).
- ETA note history: [core/dashboard_eta.py](../mr_guardian/core/dashboard_eta.py),
  [storage/history.py](../mr_guardian/storage/history.py), [app/api.py](../app/api.py),
  [Docs/api-eta-note.md](api-eta-note.md).
- Tests: [tests/unit/test_api.py](../tests/unit/test_api.py),
  [tests/unit/test_dashboard.py](../tests/unit/test_dashboard.py)
  (`test_beta_phase_eta_uses_readiness_eyebrow` and the hard-coded-string asserts will need
  updating to the weekly-review-driven phase/readiness).
