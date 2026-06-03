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

The review score is calculated when the review is stored:

- start from `100`
- subtract `35` per blocking finding
- subtract `15` per high finding
- subtract `5` per warning finding
- subtract `1` per info finding
- clamp between `0` and `100`

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
