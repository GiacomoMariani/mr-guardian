# API Review Finality

MR Guardian exposes an API-only endpoint for marking which stored review is the
final review for a ticket.

This is intentionally not exposed in the dashboard. The dashboard reads finality
and displays tickets as `Approved` or `Observed`, but trusted automation or a
local script decides when a review becomes final.

## Endpoint

```text
POST /reviews/{review_id}/finality
```

Request body:

```json
{
  "final": true
}
```

Successful response:

```json
{
  "status": "updated",
  "review_id": 12,
  "is_final": true,
  "ticket_key": "TK-234",
  "cleared_review_ids": [10]
}
```

## Semantics

- `final: true` marks the review as final.
- `final: false` removes the final marker from that review.
- If the review has a `ticket_key`, marking it final clears the final marker
  from any other stored review with the same ticket key.
- If the review has no `ticket_key`, only that review row is changed.
- Blocking or high-risk reviews can still be marked final. Finality represents
  the accepted final review state, not a pass/fail override.

## Errors

- `400`: invalid JSON, non-object payload, missing or non-boolean `final`, or a
  non-positive review ID.
- `401`: invalid admin token when `MR_GUARDIAN_ADMIN_TOKEN` is configured.
- `404`: review ID does not exist.

## Optional Admin Token

Set this value in `.env` to protect write endpoints:

```env
MR_GUARDIAN_ADMIN_TOKEN=replace_with_a_private_admin_token
```

When configured, requests must include:

```text
X-MR-Guardian-Admin-Token: replace_with_a_private_admin_token
```

If `MR_GUARDIAN_ADMIN_TOKEN` is empty, finality updates remain unprotected for
local development. Do not expose an unprotected API service outside your machine
or trusted network.
