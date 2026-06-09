# Ticket — API endpoint to reset all stored data

Add an admin-gated API endpoint that wipes **all** stored data in the history database
in one call. Today this is only possible from a shell, and even then incompletely.
Opened 2026-06-09.

**Why now:** on a deployed instance (e.g. Render) only the API and dashboard are
reachable — there is no shell to run the CLI. After demos, test runs, or a re-seed via
the feed endpoints, there is no way to return the instance to a clean state over the API.

**Status (2026-06-09): implemented.** `ReviewHistoryStore.reset_all()` truncates every
table (reviews + children + weekly reviews + ETA history + legacy singleton) and returns
per-group counts; `clear_history()` now delegates to it (fixing the CLI ETA gap). Exposed
as admin-gated `POST /admin/reset` (requires `{"confirm": true}`) via the
[history_reset](../mr_guardian/core/history_reset.py) core module. Covered by tests in
`test_api.py` + `test_review_history_store.py`; documented in [api-reset.md](api-reset.md).
Decisions confirmed as proposed: `POST /admin/reset`, and double confirmation (admin
token + `confirm: true`).

## Current state

- The only delete over the API is `DELETE /reviews/{review_id}` — a **single** review.
  No bulk/reset route exists (verified against all routes in [app/api.py](../app/api.py)).
- `ReviewHistoryStore.clear_history()` ([mr_guardian/storage/history.py:874](../mr_guardian/storage/history.py))
  deletes `review_runs` + its six child tables + `weekly_llm_reviews`, **but**:
  - it is **not exposed via the API** (only the CLI `clear-logs --yes` calls it), and
  - it does **not** clear `dashboard_eta_note` (legacy) or `dashboard_eta_notes` (the
    history table), so it is **not a true "reset all"** — ETA notes survive.
- The dashboard intentionally has **no** destructive UI
  (`test_streamlit_has_no_review_delete_ui`); a reset must stay API/CLI/admin-only.

## In scope

### 1. A complete reset in the storage layer
Add `ReviewHistoryStore.reset_all()` that truncates **every** application table — the
review tables, `weekly_llm_reviews`, **and** `dashboard_eta_notes` + the legacy
`dashboard_eta_note`. Return per-group removed counts (reviews, weekly reviews, eta
notes). Either fold `clear_history()` into it or have `clear_history()` delegate, and
**fix the CLI `clear-logs` ETA gap** so the CLI and API agree.

### 2. An admin-gated reset endpoint
```text
POST /admin/reset
```
- Requires `X-MR-Guardian-Admin-Token` (same gate as `/reviews/import`, delete, finality).
- Requires an explicit confirmation in the body — `{"confirm": true}` — mirroring the
  CLI's `--yes`, since the operation is irreversible.
- Returns the removed counts, e.g. `{"status": "reset", "reviews": 27, "weekly_reviews": 1, "eta_notes": 3}`.
- `400` without `confirm: true`; `401` on bad/missing admin token.

### 3. Docs + tests
- New `Docs/api-reset.md` (mirror [api-review-finality.md](api-review-finality.md) style),
  cross-link from [api-eta-note.md](api-eta-note.md) / the feed-endpoints docs.
- Tests in [tests/unit/test_api.py](../tests/unit/test_api.py) (reset wipes all tables incl.
  ETA notes; `confirm`/admin-token guards) and
  [tests/unit/test_review_history_store.py](../tests/unit/test_review_history_store.py)
  (`reset_all` clears every table and reports counts).

## Decisions

- **Endpoint:** `POST /admin/reset` — the data spans reviews + weekly reviews + ETA notes,
  so a neutral `/admin` namespace reads better than overloading `DELETE /reviews`.
  _(Alternatives: `DELETE /admin/data`, `POST /maintenance/reset` — confirm.)_
- **Double confirmation:** admin token **and** a `confirm: true` body flag, because the
  wipe is irreversible and there is no undo/backup.
- **Truncate rows, not the file:** delete all rows but keep the schema (no DB-file drop),
  matching how `clear_history()` works today.
- **Reset means everything**, including ETA notes — that is the gap that makes the current
  `clear_history()` not a true reset.

## Out of scope

- Selective/per-table reset (could be a later `?scope=` flag).
- Backups, export-before-wipe, or undo.
- Exposing reset in the dashboard UI (keep destructive ops out of the UI, per the existing
  no-delete-UI rule).

## Touch points

- [mr_guardian/storage/history.py](../mr_guardian/storage/history.py) (`clear_history` →
  `reset_all`, incl. ETA tables).
- [app/api.py](../app/api.py) (new admin-gated route).
- [mr_guardian/cli/main.py](../mr_guardian/cli/main.py) (`clear-logs` parity — clear ETA
  notes too).
- Docs + tests as above.
