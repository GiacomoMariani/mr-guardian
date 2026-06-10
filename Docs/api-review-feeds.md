# API Review Feeds

MR Guardian exposes a dedicated write endpoint for **each item** persisted with a
review run, so a review and its component data can be fed into the history database
independently. This complements `POST /reviews/import`, which writes a whole review in
one verbatim bundle.

All endpoints below are admin-only when `MR_GUARDIAN_ADMIN_TOKEN` is configured (see
[Optional Admin Token](#optional-admin-token)). The dashboard reads this data; it does
not write it.

## Create a review run

```http
POST /reviews
```

Creates one `review_runs` row from a verbatim [`ReviewRunCreate`](review-history-schema.md)
payload and returns the assigned `review_id`. Child collections may be supplied inline
or left empty and fed afterward through the per-component endpoints below.

Request body (minimal — child collections omitted):

```json
{
  "review_scope": "import-review",
  "branch_name": "feature/TK-900-import",
  "developer_id": "Import Bot",
  "ticket_key": "TK-900",
  "policy_version": 1,
  "risk": "none",
  "blocking_count": 0,
  "high_count": 0,
  "warning_count": 0,
  "info_count": 0,
  "changed_file_count": 1,
  "changed_line_count": 5,
  "triggered_rule_ids": [],
  "generated_review_report": "# Imported review\n\nVerbatim body."
}
```

Response:

```json
{
  "status": "created",
  "review_id": 1,
  "ticket_key": "TK-900",
  "risk": "none",
  "score": 100,
  "is_final": false
}
```

`POST /reviews/import` is the same operation, retained as the named entry point for
porting an existing history database into a fresh deployment (it responds with
`"status": "imported"`).

## Per-component feeds

Each endpoint targets an existing `review_id`. The schema of each body matches the
corresponding field on [`ReviewRunCreate`](review-history-schema.md).

| Endpoint | Method | Body | Response count field |
|---|---|---|---|
| `/reviews/{review_id}/findings` | `POST` | array of `Finding` | `finding_count` |
| `/reviews/{review_id}/triggered-rules` | `POST` | array of strings | `triggered_rule_count` |
| `/reviews/{review_id}/evaluations` | `POST` | array of `ReviewEvaluation` | `evaluation_count` |
| `/reviews/{review_id}/policies` | `POST` | array of `ReviewPolicySummary` | `policy_count` |
| `/reviews/{review_id}/llm-metrics` | `POST` | array of `LlmRuleMetric` | `llm_metric_count` |
| `/reviews/{review_id}/llm-summary` | `PUT` | one `LlmReviewSummary` object | — |
| `/reviews/{review_id}/developer-profile` | `PUT` | one `LlmDeveloperProfile` object | — |

### Example — findings

```http
POST /reviews/1/findings
```

```json
[
  {
    "rule_id": "RULE-1",
    "severity": "warning",
    "message": "Avoid GetComponent in Update.",
    "source": "import#RULE-1",
    "evaluation": "coding",
    "rule_type": "deterministic",
    "file_path": "Assets/Scripts/Player.cs",
    "line_number": 42
  }
]
```

```json
{ "status": "stored", "review_id": 1, "finding_count": 1 }
```

### Example — developer profile

```http
PUT /reviews/1/developer-profile
```

```json
{
  "status": "succeeded",
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "duration_ms": 400,
  "lookback_days": 30,
  "text": "Strong, consistent contributor."
}
```

```json
{ "status": "updated", "review_id": 1, "developer_profile_status": "succeeded" }
```

## Semantics

- **Idempotent replace.** The `POST` list feeds (findings, triggered-rules,
  evaluations, policies, llm-metrics) replace the entire stored set for that review on
  each call — re-feeding the same review is safe and never duplicates rows. An empty
  array clears that item. The `PUT` feeds (llm-summary, developer-profile) overwrite the
  single stored value.
- **Caller owns the parent totals.** The denormalized counts (`blocking_count`,
  `high_count`, `warning_count`, `info_count`) and `review_score` on the `review_runs`
  row are set only when the review is created (`POST /reviews` / `/reviews/import`).
  Feeding findings or evaluations afterward does **not** recompute them — keep the
  parent totals consistent in the creation payload.
- **Replacing evaluations** also clears their `triggered_rule_ids` children.
- **LLM cost.** Each LLM component payload may carry an optional `estimated_cost_usd`: items
  in `llm-metrics`, and the `llm-summary` / `developer-profile` objects. The review-level
  `estimated_cost_usd` on `review_runs` is **derived** — recomputed as the sum of the stored
  per-call costs whenever any LLM component is fed — so it is not read from the `POST
  /reviews` body. `currency` (default `USD`) is stored at the review level. These costs are
  persisted but not shown in any UI.

## Errors

| Status | Condition |
|---|---|
| `400` | Invalid JSON; wrong container type (`Expected JSON array payload.` / `Expected JSON object payload.`); a body that fails model validation (`Invalid <item> structure: ...`); or a non-positive review ID (`Review ID must be a positive integer.`). |
| `401` | Invalid admin token when `MR_GUARDIAN_ADMIN_TOKEN` is configured. |
| `404` | The target review ID does not exist. |

## Optional Admin Token

Set this value in `.env` to protect write endpoints:

```env
MR_GUARDIAN_ADMIN_TOKEN=replace_with_a_private_admin_token
```

When configured, requests must include:

```text
X-MR-Guardian-Admin-Token: replace_with_a_private_admin_token
```

If `MR_GUARDIAN_ADMIN_TOKEN` is empty, these write endpoints remain unprotected for
local development. Do not expose an unprotected API service outside your machine or
trusted network.
