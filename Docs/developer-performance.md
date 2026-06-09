# Developer Performance

MR Guardian can summarize stored review history by developer and ticket.

Each ticket-linked MR must include a ticket key in the MR title:

```text
TK-234 Add inventory validation
```

The runtime extracts only `TK-[number]` from the MR title. It does not infer
ticket keys from branch names, descriptions, file paths, or report text.

## Stored Fields

Every stored review run includes:

- `developer_id`
- `ticket_key`, when the MR title contains a supported ticket key
- `is_final`, when a review has been marked as the final review for that ticket
- `review_score`

The review score is calculated when the review is stored: start at `100`, subtract a
penalty per finding by severity, then clamp the result to `0`–`100`.

| Severity | Penalty per finding |
|---|---:|
| Blocking | −35 |
| High | −15 |
| Warning | −5 |
| Info | −1 |

## Summary Semantics

Developer summaries use stored review timestamps as MR request timestamps.

For each ticket, the summary reports:

- total MR review requests
- first request timestamp
- last request timestamp
- elapsed days between first and last request
- approval state: `Approved` or `Observed`
- approved timestamp, when a final review exists
- attempts to approval, when a final review exists
- observed timestamp, currently the last request timestamp
- average review score for that ticket

Approved tickets use the final review timestamp as the approved date. Observed
tickets use the latest review timestamp as a local approximation until GitLab
merge or deployment events are persisted.
