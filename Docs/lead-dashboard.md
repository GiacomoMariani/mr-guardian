# Lead Dashboard View

The lead dashboard view summarizes review iteration patterns by developer and
ticket.

It is intended for technical leads and senior reviewers who need to understand:

- how many review attempts each ticket needs
- whether review score is improving or declining
- which rules recur for each developer
- whether repeated review risk is coding-related or MR-structure-related

## Attempt Model

Each stored review run counts as one review attempt.

Attempts are grouped by:

- `developer_id`
- `ticket_key`

Reviews without a ticket key are excluded from per-ticket attempt averages and
reported separately as unlinked reviews.

## Trend Model

Trend direction is conservative:

- fewer than four review runs: `insufficient_data`
- later average score more than two points above earlier average: `improving`
- later average score more than two points below earlier average: `declining`
- otherwise: `stable`

## Evaluation Dimensions

When review evaluations are stored, the view summarizes:

- coding risk
- MR-structure risk

These dimensions help leads separate implementation issues from review-process
issues.
