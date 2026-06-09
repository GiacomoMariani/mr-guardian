# API Reset

MR Guardian exposes an admin-only endpoint that deletes **all** stored data in one
call: review runs (and their findings, evaluations, policies, LLM metrics, triggered
rules), weekly LLM reviews, and dashboard ETA notes.

This is intentionally not exposed in the dashboard. Use it to return a deployed instance
to a clean state (after a demo, test run, or re-seed) where no shell is available to run
the `clear-logs` CLI command.

## Endpoint

```text
POST /admin/reset
```

Request body — an explicit confirmation is required because the wipe is irreversible:

```json
{
  "confirm": true
}
```

Successful response (counts removed):

```json
{
  "status": "reset",
  "reviews": 27,
  "weekly_reviews": 1,
  "eta_notes": 3
}
```

## Semantics

- Truncates every application table but keeps the schema (rows deleted, tables remain).
- `reviews` counts removed review runs; their child rows (findings, evaluations,
  policies, LLM metrics, triggered rules) are removed with them.
- `weekly_reviews` and `eta_notes` count the removed weekly LLM reviews and dashboard
  ETA notes (the full note history, not just the current one).
- There is no undo and no automatic backup. Export anything you need first.

## Errors

| Status | Condition |
|---|---|
| `400` | Invalid JSON, non-object payload, or a body without `"confirm": true`. |
| `401` | Invalid admin token when `MR_GUARDIAN_ADMIN_TOKEN` is configured. |

## Optional Admin Token

Set this value in `.env` to protect write endpoints:

```env
MR_GUARDIAN_ADMIN_TOKEN=replace_with_a_private_admin_token
```

When configured, requests must include:

```text
X-MR-Guardian-Admin-Token: replace_with_a_private_admin_token
```

If `MR_GUARDIAN_ADMIN_TOKEN` is empty, this endpoint remains unprotected for local
development. Do not expose an unprotected API service outside your machine or trusted
network. The equivalent local command is `python -m mr_guardian.cli.main clear-logs --yes`.
