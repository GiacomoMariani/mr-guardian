# Manual Review Submission

Manual reviews can be stored in the same SQLite history as automated reviews.
Use this when a reviewer has already written a full review and wants it visible
in MR Guardian logs and dashboard data.

Manual review payloads should live under the ignored local folder:

```text
personal-notes/
```

Do not commit personal review payloads.

## Command

```bash
python -m mr_guardian.cli.main submit-manual-review --file personal-notes/review.json
```

Use `--db` to target a specific history database:

```bash
python -m mr_guardian.cli.main submit-manual-review \
  --file personal-notes/review.json \
  --db .mr-guardian/history.sqlite
```

## JSON Shape

MR Guardian validates JSON structure and stores the report body verbatim. It does
not parse Markdown to infer findings.

```json
{
  "review_scope": "manual-review",
  "branch_name": "feature/example",
  "title": "TK-234 Manual review",
  "developer_id": "Reviewer Name",
  "policy_version": 1,
  "risk": "warning",
  "findings": [
    {
      "rule_id": "MANUAL-CODE-001",
      "severity": "warning",
      "message": "Manual reviewer found a maintainability concern.",
      "source": "manual-review#MANUAL-CODE-001",
      "evaluation": "coding",
      "rule_type": "deterministic",
      "file_path": "Assets/Scripts/Player.cs",
      "line_number": 42
    }
  ],
  "evaluations": [
    {
      "evaluation": "coding",
      "risk": "warning",
      "counts": {
        "blocking": 0,
        "high": 0,
        "warning": 1,
        "info": 0
      },
      "triggered_rule_ids": ["MANUAL-CODE-001"]
    },
    {
      "evaluation": "mr_structure",
      "risk": "none",
      "counts": {
        "blocking": 0,
        "high": 0,
        "warning": 0,
        "info": 0
      },
      "triggered_rule_ids": []
    }
  ],
  "changed_file_count": 3,
  "changed_line_count": 24,
  "generated_review_report": "## Manual Review\n\nReview body goes here.",
  "mr_id": "42",
  "commit_sha": "abc123"
}
```

## Validation

The command recomputes and validates:

- ticket key from `title`, when present
- top-level risk from submitted findings
- severity counts from submitted findings
- top-level triggered rule IDs from submitted findings
- coding and MR-structure evaluation summaries

If the payload is inconsistent, MR Guardian returns an error and does not write
to SQLite.
