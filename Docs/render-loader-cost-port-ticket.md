# Ticket — Port per-review LLM cost through the Render loader

`personal-notes/load_to_render.py` (local `history.sqlite` → live deployment) does not carry
the per-review LLM `estimated_cost_usd` added by the cost-telemetry ticket, so porting a
database silently drops per-review cost. Add it. Opened 2026-06-10.

**Why now:** running the loader after the cost-telemetry work imports reviews with **no
cost** — the server recomputes the review-level rollup from the per-call costs, and the
loader sends none, so every ported review stores `NULL`. Surfaced alongside a separate
weekly `400` that is a stale-deploy issue, not a code bug (see **Non-issue** below).

**Status (2026-06-10): open — not started.** Scope below; awaiting go-ahead.

## Current state

- `build_review_payload` omits `estimated_cost_usd` everywhere it appears on the models:
  - `llm_metrics` items ([load_to_render.py:139](../personal-notes/load_to_render.py)),
  - `_llm_summary` ([load_to_render.py:46](../personal-notes/load_to_render.py)),
  - `_developer_profile` ([load_to_render.py:63](../personal-notes/load_to_render.py)),
  - and the review-level `currency` ([load_to_render.py:166](../personal-notes/load_to_render.py)).
- The **weekly** payload already carries `estimated_cost_usd` + `currency` + `phase`
  ([load_to_render.py:195](../personal-notes/load_to_render.py)), so it needs no change.
- On import (`POST /reviews/import` → `store_review_run` → `_recompute_review_cost`), the
  review-level rollup is **derived from the per-call costs**. Sending the per-call costs is
  therefore sufficient and correct; review-level `estimated_cost_usd` is not a
  `ReviewRunCreate` input.

## In scope

Update `personal-notes/load_to_render.py` review payload builders to carry cost, reading with
`.get(...)` so a pre-cost local DB degrades to `None` instead of raising `KeyError`:

1. `llm_metrics` items → add `"estimated_cost_usd": m.get("estimated_cost_usd")`.
2. `_llm_summary` → add `"estimated_cost_usd": run.get("llm_summary_estimated_cost_usd")`.
3. `_developer_profile` → add `"estimated_cost_usd": run.get("developer_profile_estimated_cost_usd")`.
4. Review payload → add `"currency": run.get("currency") or "USD"` for fidelity (the rollup
   itself stays server-derived; do **not** send a review-level `estimated_cost_usd` — it is
   ignored as a non-input).

## Verification

- `python personal-notes/load_to_render.py --dry-run --dump /tmp/payloads.json`, then confirm
  the dumped review payloads now include `estimated_cost_usd` on metrics/summary/profile.
- After a Render **redeploy** (see Non-issue), a real run preserves per-review cost; spot-check
  one ported review via the API/DB.
- No tracked unit test: `personal-notes/` is git-ignored and AGENTS.md forbids tracked
  fixtures/tests there, so the `--dry-run` dump is the verification.

## Non-issue — weekly `phase` 400 (no code change, per decision)

```
weekly review: 400 ... phase  Extra inputs are not permitted [type=extra_forbidden]
```

This is **deploy skew**: the live Render instance runs older code whose
`WeeklyLlmReviewCreate` predates the `phase` field, while the loader (correctly) sends
`phase`. The current model already defines `phase`
([weekly_review.py:28](../mr_guardian/models/weekly_review.py)). **Resolved by redeploying
Render** to current code — which also brings the new cost columns/fields live. Per decision,
we are **not** relaxing the weekly model's `extra="forbid"` or adding loader skew-tolerance;
the deploy just needs to be current before porting.

## Out of scope (declined)

- Relaxing `WeeklyLlmReviewCreate`'s `extra="forbid"` or other model changes.
- Loader schema self-checks, model-driven payload generation, or drift guards.
- Any tracked test for the loader (git-ignored personal tooling).

## Touch points

- [personal-notes/load_to_render.py](../personal-notes/load_to_render.py) — review payload
  builders (git-ignored).
- Optional: a one-line reminder in the loader docstring / deployment notes to **redeploy
  before porting** after any model change, since `phase`-style skew is a deploy concern.
- Related: [llm-cost-telemetry-ticket.md](llm-cost-telemetry-ticket.md) (the source of the
  per-call cost fields this loader now needs to carry).
