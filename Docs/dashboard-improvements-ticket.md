# Ticket — Dashboard portfolio improvements

Polish/feature work on the Streamlit dashboard ([app/streamlit_app.py](../app/streamlit_app.py))
so it reads as a strong agentic-engineering portfolio piece. Opened 2026-06-05.

Audience is technical producers/devs. The dashboard already opens directly on the
**Agent Review** tab (the agent's verdict report), styled with the custom design
system; this ticket covers the next round of improvements agreed in review.

**Status (2026-06-05):** the three in-scope items below are **implemented and
verified** — `st.cache_data` on the loaders (keyed on DB mtime), the how-it-works
hook at the page foot, and the themed Altair Trends chart + dynamic report-iframe
height. The Deferred and Backlog items remain open.

## In scope — ✅ done 2026-06-05

### 1. "How it works" hook
Give a cold visitor an instant mental model of the agentic pipeline:

> diff → deterministic policy checks + bounded LLM reasoning → one merge verdict

- **Placement: foot of the page for now** (decided against the hero) — render near
  the theme / history-database controls (`_render_bottom_controls`).
- A single line or a small 3-step strip; keep it on-brand with the `mg-*` styles.

### 2. Snappier section nav (caching)
The section nav (`st.radio` in `_render_dashboard_tabs`) reruns and reloads data on
every switch. Wrap the loaders in `st.cache_data` so switching is instant:
- `load_dashboard_data`, `load_pm_dashboard_summary`, `load_lead_dashboard_summary`,
  `load_lead_developer_detail`, `load_latest_weekly_llm_review`, `load_dashboard_eta_note`.
- Key the cache on `database_path` + file mtime so it invalidates when reviews change.

### 3. Smooth the rough edges
- **Trends tab** uses a stock `st.line_chart` (`_render_trends`) that clashes with the
  custom dark design — restyle (Vega theme) or replace with a custom chart.
- **Report iframe** is a fixed `height=1100` (`_render_review_report_tabs`) — short
  reports leave whitespace, long ones scroll inside a box. Make the height dynamic.

## Backlog — separate future ticket (not this one)

### Responsive / mobile
Wide tables (Recent Reviews ~13 columns, via `render_table`), the review pager (up to
12 cells, `_render_review_pager`), and the side-by-side controls (`_render_bottom_controls`)
overflow on narrow screens. Make them responsive — stack columns, horizontal-scroll
tables, compact the pager — so the page holds up when opened on a phone. Noted now;
to become its own ticket.

---

_No GitHub CLI / issue tooling is available in this environment, so this is filed as
an in-repo markdown ticket. The body is issue-ready — paste into a GitHub issue, or
wire up `gh` and it can be filed directly._
