# Ticket — Developer detail page polish

Polish the **developer detail view** (`?view=developer` → `_render_developer_detail_page`
in [app/streamlit_app.py](../app/streamlit_app.py)) so it holds up as a portfolio
surface. Opened 2026-06-08.

**Why now:** the visual review report header now links the developer name through to
this page (every review type), so a cold portfolio visitor will land here. Today it
reads like a raw data dump — machine values leak into the UI, the metric grid is
ragged, and the strongest artifact (the LLM developer profile) is buried at the
bottom.

**Status (2026-06-08): all four items done** — #1 humanize values, #2 grid re-balance,
#3 score targets (now env-configurable per dimension, default 80), #4 elevate the AI
profile. The developer page now leads with the LLM profile (scores + AI write-up,
explicitly labelled), then the activity metrics.

## In scope

### 1. Humanize the raw machine values _(quick win)_ — ✅ done 2026-06-08
Done via shared helpers, so the fixes land **dashboard-wide**, not just this page:
`_format_datetime` now renders `2026-06-02 10:53` (not raw ISO); `_score` drops the
trailing `.0` on whole numbers (`75.0`→`75`); a shared `_trend_label_tone` maps the
`TrendDirection` enum to a label + colour (low-data → `-`, per #2), reused by both the
metric cards and the table pills; and "Avg Attempts" now routes through `_score`
(`1.00`→`1`). Original spec below.
The page renders several values straight from the model with no display formatting:

- **Trend** — `MetricCard("Trend", developer.trend_direction)` passes the raw
  `TrendDirection` literal (`improving` / `declining` / `stable` / `insufficient_data`).
  `insufficient_data` shows verbatim and word-wraps into "insuffici / ent_dat / a".
  Map to a display label ("Improving / Declining / Stable / Not enough data"), ideally
  with a direction arrow + pass/warn/muted color.
- **Latest Review** — `_format_datetime` returns `value.isoformat(timespec="seconds")`
  → `2026-06-02T10:53:25+00:00`, which wraps across four lines. Format as a short human
  date (e.g. `Jun 2, 2026` or `2026-06-02 10:53`).
- **Number formatting** — `_score` gives one decimal, but `Avg Attempts`
  (`average_attempts_per_ticket`) bypasses it and shows `1.00` while `Avg Approval`
  shows `1.0`. Route all averages through one formatter; consider trimming trailing
  `.0` on whole numbers.

(The low-data trend state — #5 from review — folds in here: a friendly "Not enough
history yet" rather than the leaked enum.)

### 2. Re-balance and group the metric grid — ✅ done 2026-06-08 (per Jack's directives)
The top "Developer Metrics" grid was 12 `MetricCard`s in a ragged 7-wide grid. Jack
specified the trim directly:

- Top grid reduced to **one row of 5**: Review Requests · Tickets · Avg Attempts ·
  Approved Tickets · Trend. (`auto-fit minmax(145px,1fr)` makes 5 cards fill one row —
  no CSS change needed.)
- Removed the absence/noise + redundant cards: **Avg Approval Attempts, Repeated Rules,
  Unlinked Reviews, Latest Review** (its date already shows in the profile sub-line).
- **Scores moved into the "Latest Developer Profile" section** — Average / Coding /
  MR Structure now sit together as a 3-card row above the profile card (grouping the
  average with the coding + structure it summarises). _(This also partly addresses #4 —
  the profile section now leads with the scores; elevating the narrative itself is still
  open.)_
- Low-data **Trend** now shows `-` (not a wrapped sentence) — Jack's "if we have no
  data add a `-`, not the full text".

Original spec below.

- Use a column count that divides evenly (6×2 or 4×3), **or** group into labelled
  sub-sections — e.g. *Activity · Quality · Cadence*.
- De-emphasize or conditionally hide absence-of-problem metrics that are noise at zero
  ("Repeated Rules **0**", "Unlinked Reviews **0**"), so the scores and trend lead.

## Decisions

### 3. Give the scores a reference — ✅ done 2026-06-08 (fixed target)
Jack chose the **fixed-target** option (over team-average). Added `_SCORE_TARGET = 80`
(scores are out of 100) and a `_score_card(label, value)` helper: the card is **green
(`pass`) when the score meets the target, amber (`warning`) when below**, with a
**"Target 80"** detail line. Applied to the three profile-section scores. The target is
a one-line constant — change `_SCORE_TARGET` to retune.

## Decisions

### 4. Lead with the AI profile — ✅ done 2026-06-08
Jack chose: make the profile the **top item**. The whole profile section (scores + the
LLM write-up) now renders **above** the Developer Metrics, titled **"Latest LLM Developer
Profile"** with an **"AI-generated"** eyebrow (the redundant outer "Latest Developer
Profile" wrapper was dropped — `_developer_profile_panel(show_title=False)`), so LLM
provenance is explicit (title + eyebrow + the provider/model/tokens footer). For a
developer with no profile / a failed generation, the panel shows a **"No info found."**
note rather than collapsing.

Also done same day: the three score targets are now **env-configurable per dimension**
(`MR_GUARDIAN_SCORE_TARGET_AVERAGE` / `_CODING` / `_STRUCTURE`, default 80) via
`Settings`, in `.env` + `.env.example`.

## Backlog — rolls into the responsive/mobile ticket

The wide metric grid and the lookback `number_input` overflow / cramp on narrow
screens — same class of work as the report page's responsive backlog item; fold into
that future ticket rather than this one.

---

_No GitHub CLI / issue tooling is available in this environment, so this is filed as an
in-repo markdown ticket. The body is issue-ready — paste into a GitHub issue, or wire up
`gh` and it can be filed directly._
