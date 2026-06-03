# Ticket Key Conventions

GitLab merge request titles should include a ticket key:

```text
TK-234 Add inventory validation
```

MR Guardian uses the ticket key to connect review history to deliverables.

## Why It Matters

PM dashboard views use ticket keys to show:

- pass/fail status
- blocker status
- latest review state
- approved or observed delivery state
- approved date when a final review exists

Lead dashboard views use ticket keys to show:

- review attempts per ticket
- attempts to approval
- developer review trends
- recurring rule patterns
- coding versus MR-structure risk over time

Without a ticket key, a review is still stored, but it becomes an unlinked
review and cannot contribute to ticket-level delivery analytics.

Unlinked reviews can still be marked final at the review level, but they do not
approve any ticket because there is no ticket key to group by.

## Enforcement

The GitLab MR title rule is configured in YAML:

```yaml
parameters:
  title_pattern: "\\bTK-\\d+\\b"
  required_review_scopes:
    - gitlab-webhook
```

Local CLI review is not blocked by default. GitLab-triggered MR review is
expected to include the key because it feeds PM and lead analytics.
