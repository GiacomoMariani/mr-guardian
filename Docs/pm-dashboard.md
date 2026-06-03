# PM Dashboard View

The PM dashboard view summarizes review history in terms of delivery status
rather than raw merge request details.

It groups stored reviews by `ticket_key` and treats the latest review for each
ticket as the current state.

## Status Model

- `fail`: latest review risk is `blocking` or `high`
- `pass_with_warnings`: latest review risk is `warning` or `info`
- `pass`: latest review risk is `none`

Reviews without a ticket key are counted as unlinked reviews and excluded from
ticket pass/fail totals.

Pass rate is the percentage of ticket-linked tickets that are not currently
failing: `pass` plus `pass_with_warnings`.

## Approved Or Observed

Each ticket also has a delivery state:

- `Approved`: one stored review for that ticket has been marked final.
- `Observed`: no final review has been marked yet.

Approved/Observed is separate from pass/fail risk. A ticket can still display a
failing latest risk if the latest review is blocking or high-risk. Marking a
review final is intentionally API-only; the dashboard reads the state but does
not mutate it.

For approved tickets, the displayed date is the final review timestamp. For
observed tickets, the displayed date remains the latest review timestamp as a
local approximation until explicit deployment or merge events are persisted.

## Blockers

Recurring blockers are rules that appear in blocking or high-risk review runs
across more than one ticket or more than one review run.

The PM view intentionally stays concise. Detailed findings remain available in
the stored review report section.
