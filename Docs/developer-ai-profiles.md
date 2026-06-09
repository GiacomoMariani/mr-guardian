# Developer AI Profiles

MR Guardian can store an advisory LLM profile snapshot for the developer who submitted a stored review.

The profile is generated after the review is stored, uses only that developer's recent review history, and is written back to the same review run. It does not change risk, findings, scores, or blocking status.

## Configuration

```env
MR_GUARDIAN_DEVELOPER_PROFILE_ENABLED=false
MR_GUARDIAN_DEVELOPER_PROFILE_LOOKBACK_DAYS=30
MR_GUARDIAN_DEVELOPER_PROFILE_MAX_CHARS=900
```

The profile uses the same LLM provider settings as review summaries, including `MR_GUARDIAN_LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, timeout, and retry settings.

## Stored Context

The LLM receives a compact developer history window:

- developer ID
- review count and ticket count
- average review score
- average attempts per ticket
- latest review timestamp
- trend direction
- repeated rules
- coding and MR-structure evaluation summaries
- recent ticket attempts
- recent review risk, counts, changed files, changed lines, and triggered rules

## Dashboard

The developer detail page shows the latest available profile snapshot for that developer, including status, provider, model, lookback window, duration, and token usage when available.

![Latest LLM Developer Profile — average, coding, and MR-structure score cards above the AI-generated narrative](assets/developer-ai-profile.png)

When profile generation is disabled, unavailable, malformed, failed, or rate-limited, MR Guardian keeps the review result and stores profile status metadata when generation was attempted.
