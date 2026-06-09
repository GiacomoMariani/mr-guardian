# Weekly LLM Review

MR Guardian displays stored weekly LLM reviews on the first dashboard tab. This is
separate from per-MR LLM summaries: page load only reads stored weekly records and never
regenerates them. The panel shows the latest week by default, with a selector to view
previous weeks.

![Weekly LLM Review panel — result pill, LLM-calculated score, weekly counts, top risks, and recommended actions](assets/weekly-llm-review.png)

## Purpose

Use the weekly review to summarize the current delivery window in plain language: an
overall result, an LLM-calculated score from `1` to `100`, the delivery `phase` it
assesses (e.g. `Beta Phase`), MR/developer/ticket counts, blocking/high/warning/info
review counts, top risks, recommended actions, and token usage with estimated cost.

The overall result is one of five states, shown as a colored pill on the dashboard:

| Result | Dashboard label | Tone |
|---|---|---|
| `optimal` | Optimal | pass |
| `on_track` | On Track | pass |
| `needs_attention` | Needs Attention | warning |
| `at_risk` | At Risk | high |
| `blocked` | Blocked | blocking |

## API

| Endpoint | Purpose |
|---|---|
| `GET /weekly-llm-reviews/schema` | Read the accepted JSON schema. |
| `GET /weekly-llm-reviews` | List recent reviews, newest first (`?limit=N`, default 20). |
| `GET /weekly-llm-reviews/{weekly_review_id}` | Read one stored review by ID. |
| `POST /weekly-llm-reviews/manual` | Store a manually generated weekly LLM review. |

If `MR_GUARDIAN_ADMIN_TOKEN` is configured, the `POST` request must include the
`x-mr-guardian-admin-token: <token>` header.

## Example Payload

```json
{
  "week_start": "2026-06-01",
  "week_end": "2026-06-07",
  "result": "on_track",
  "score": 84,
  "summary": "The week is on track with one high-risk ticket still visible.",
  "phase": "Beta Phase",
  "mr_count": 12,
  "developer_count": 4,
  "ticket_count": 7,
  "approved_ticket_count": 5,
  "observed_ticket_count": 2,
  "blocking_review_count": 0,
  "high_risk_review_count": 1,
  "warning_review_count": 3,
  "info_review_count": 8,
  "top_risks": [
    "One ticket still has a high-risk review before the beta cut."
  ],
  "recommended_actions": [
    "Clear the high-risk ticket before the weekly delivery checkpoint."
  ],
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "input_tokens": 1200,
  "output_tokens": 240,
  "total_tokens": 1440,
  "estimated_cost_usd": 0.0031,
  "currency": "USD"
}
```

`week_start` must be a Monday and `week_end` must be a Sunday. If `created_at`
is omitted, MR Guardian stores the current UTC timestamp. `phase` is optional and
defaults to `Beta Phase`.

## Dashboard ETA widget

The latest weekly review also drives the dashboard's phase-ETA widget: its `phase`
becomes the widget title (e.g. "Beta Phase ETA") and its `score` becomes the
"Readiness" percentage. When no weekly review has been stored, the widget falls back
to the "Beta Phase" label and shows `—` for readiness.
