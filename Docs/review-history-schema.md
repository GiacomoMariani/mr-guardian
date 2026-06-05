# Review History JSON Schema

MR Guardian stores review history in SQLite and exposes it through typed Python models. The main application shape is `ReviewRunRecord`.

SQLite may store nested values across related tables or columns, while application code exposes them as one typed object. Use `GET /reviews/schema` to read the generated JSON schema for the current stored review record model.

## Current Stored Review Shape

```json
{
  "review_id": 12,
  "timestamp": "2026-05-29T10:57:04+00:00",
  "review_scope": "gitlab-webhook",
  "branch_name": "main",
  "developer_id": "Jane Developer",
  "ticket_key": "TK-234",
  "is_final": true,
  "policy_version": 1,
  "risk": "blocking",
  "blocking_count": 1,
  "high_count": 0,
  "warning_count": 4,
  "info_count": 2,
  "changed_file_count": 6,
  "changed_line_count": 229,
  "review_score": 38,
  "findings": [
    {
      "rule_id": "MR-META-001",
      "severity": "blocking",
      "message": "MR metadata is missing required section(s): Test Plan.",
      "source": "unity-policy.yml#MR-META-001",
      "evaluation": "mr_structure",
      "rule_type": "deterministic",
      "file_path": null,
      "line_number": null
    }
  ],
  "triggered_rule_ids": ["MR-META-001"],
  "evaluations": [
    {
      "evaluation": "coding",
      "risk": "info",
      "counts": {
        "blocking": 0,
        "high": 0,
        "warning": 0,
        "info": 2
      },
      "triggered_rule_ids": ["PYTHON-DESIGN-LLM-001"]
    }
  ],
  "llm_metrics": [
    {
      "rule_id": "PYTHON-DESIGN-LLM-001",
      "provider": "openai",
      "model": "gpt-4.1-mini",
      "status": "succeeded",
      "duration_ms": 1420,
      "input_tokens": 1200,
      "output_tokens": 80,
      "total_tokens": 1280,
      "error_message": null
    }
  ],
  "llm_summary": {
    "status": "succeeded",
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "duration_ms": 820,
    "text": "The MR is blocked by missing review metadata.",
    "score": 72,
    "input_tokens": 300,
    "output_tokens": 40,
    "total_tokens": 340,
    "error_message": null
  },
  "developer_profile": {
    "status": "succeeded",
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "duration_ms": 950,
    "lookback_days": 30,
    "text": "Jane's recent reviews show improving readiness with recurring metadata misses.",
    "input_tokens": 500,
    "output_tokens": 60,
    "total_tokens": 560,
    "error_message": null
  },
  "policy_summaries": [
    {
      "policy_path": "sources/yaml/unity-policy.yml",
      "policy_version": 1,
      "enabled_rule_count": 30,
      "disabled_rule_count": 0
    }
  ],
  "generated_review_report": "# MR Guardian Review\n\n...",
  "mr_id": "42",
  "commit_sha": "abc123"
}
```

## Field Reference

| Field | Type | Nullable | Source | Meaning |
|---|---:|:---:|---|---|
| `review_id` | integer | no | derived | SQLite primary key for the stored run. |
| `timestamp` | datetime string | no | derived or supplied | Review storage timestamp. Manual reviews may supply it; otherwise storage sets it. |
| `review_scope` | string | no | supplied | Origin or target of the review, such as `local-all-policies`, `gitlab-webhook`, or `manual-review`. |
| `project_name` | string | legacy | migrated | Older SQLite databases may contain `project_name`; current typed records use `review_scope`. |
| `branch_name` | string | no | supplied | Base branch or branch reference reviewed against. |
| `mr_id` | string | yes | supplied | Merge request ID or IID when available. |
| `commit_sha` | string | yes | supplied | Commit SHA when available. |
| `developer_id` | string | no | supplied | Developer identity associated with the review. GitLab reviews use MR author data. |
| `ticket_key` | string | yes | derived | Ticket key extracted from title, for example `TK-234`. |
| `is_final` | boolean | no | supplied or API-updated | Whether this stored review is the final review for its ticket. At most one ticket-linked review per ticket should be final. |
| `policy_version` | integer | no | supplied | Policy version from the evaluated YAML policy set. |
| `risk` | enum | no | derived or validated | Overall review risk: `none`, `info`, `warning`, `high`, or `blocking`. |
| `review_score` | integer | no | derived | Deterministic score from review counts, constrained to `0..100`. |
| `blocking_count` | integer | no | derived or validated | Count of blocking findings. |
| `high_count` | integer | no | derived or validated | Count of high findings. |
| `warning_count` | integer | no | derived or validated | Count of warning findings. |
| `info_count` | integer | no | derived or validated | Count of info findings. |
| `changed_file_count` | integer | no | derived or supplied | Number of changed files in scope. |
| `changed_line_count` | integer | no | derived or supplied | Number of changed diff lines in scope. |
| `findings` | array | no | derived or supplied | Structured findings with rule ID, severity, message, source, evaluation, type, and optional location. |
| `triggered_rule_ids` | string array | no | derived | Rule IDs that produced findings. |
| `evaluations` | array | no | derived or validated | MR-level summaries for `coding` and `mr_structure`. |
| `llm_metrics` | array | no | LLM-generated metadata | Per-LLM-rule status, duration, token usage, and error details. |
| `llm_summary` | object | yes | LLM-generated | Optional per-review LLM note and score. |
| `llm_summary.score` | integer | yes | LLM-generated | Advisory LLM score for the review, stored in SQLite as `llm_summary_score`. |
| `developer_profile` | object | yes | LLM-generated | Optional profile snapshot for the review's developer over the configured lookback window. |
| `policy_summaries` | array | no | derived | Evaluated policy files and enabled/disabled rule counts. |
| `generated_review_report` | string | no | generated or supplied | Rendered Markdown report stored verbatim. |

## SQLite Mapping Notes

The typed model is the integration contract. SQLite storage uses tables and columns optimized for querying:

- `review_runs` stores scalar review fields, the `is_final` marker, generated report text, LLM summary columns, and developer profile columns.
- `triggered_rules` stores top-level triggered rule IDs.
- `review_findings` stores structured findings.
- `review_policies` stores evaluated policy summaries.
- `review_llm_rule_metrics` stores per-rule LLM runtime and token metadata.
- `review_evaluations` stores coding and MR-structure summary rows.
- `review_evaluation_triggered_rules` stores rule IDs attached to each evaluation summary.
- `weekly_llm_reviews` stores externally supplied weekly LLM dashboard summaries,
  including result, score, weekly counts, risks, actions, tokens, and estimated cost.

Nested values returned by the application are reconstructed from those tables.

## Schema Endpoint

```text
GET /reviews/schema
```

This endpoint returns the generated JSON schema for `ReviewRunRecord`.

Manual review submission uses a different schema:

```text
GET /reviews/manual/schema
```

Weekly LLM dashboard review ingestion uses its own schema:

```text
GET /weekly-llm-reviews/schema
POST /weekly-llm-reviews/manual
```

See `Docs/weekly-llm-review.md` for the weekly payload shape and validation rules.
