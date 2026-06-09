# Weekly LLM Review

MR Guardian can display one stored weekly LLM review on the first dashboard tab.
This is separate from per-MR LLM summaries: page load only reads the latest stored
weekly record and never regenerates it.

## Purpose

Use the weekly review to summarize the current delivery window in plain language:

- whether the week is `optimal`, `on_track`, `needs_attention`, `at_risk`, or `blocked`
- an LLM-calculated score from `1` to `100`
- the delivery `phase` it assesses (e.g. `Beta Phase`)
- MR, developer, and ticket counts for the week
- blocking, high-risk, warning, and info review counts
- top risks and recommended actions
- token usage and estimated provider cost

## API

Read the accepted JSON schema:

```text
GET /weekly-llm-reviews/schema
```

Store a manually generated weekly LLM review:

```text
POST /weekly-llm-reviews/manual
```

If `MR_GUARDIAN_ADMIN_TOKEN` is configured, the POST request must include:

```text
x-mr-guardian-admin-token: <token>
```

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
