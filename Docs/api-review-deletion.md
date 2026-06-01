# API Review Deletion

MR Guardian exposes an API-only review deletion endpoint for trusted local or integration workflows.

This endpoint is intentionally not available from the dashboard. Use it to remove incorrect, duplicated, imported, or test review records from SQLite history.

## Endpoint

```text
DELETE /reviews/{review_id}
```

Successful response:

```json
{
  "status": "deleted",
  "review_id": 12
}
```

If the review does not exist, the API returns `404`.

If the review ID is not positive, the API returns `400`.

Deleting a review removes the stored review row. Related stored data such as findings, triggered rules, policies, LLM metrics, and evaluation summaries is removed through the history storage layer.

## Optional Admin Token

Set this value in `.env` to protect destructive API endpoints:

```env
MR_GUARDIAN_ADMIN_TOKEN=replace_with_a_private_admin_token
```

When configured, requests must include:

```text
X-MR-Guardian-Admin-Token: replace_with_a_private_admin_token
```

If `MR_GUARDIAN_ADMIN_TOKEN` is empty, deletion remains unprotected for local development. Do not expose an unprotected API service outside your machine or trusted network.
