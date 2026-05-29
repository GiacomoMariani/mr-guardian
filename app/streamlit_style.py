"""Shared Streamlit styling for the MR Guardian dashboard."""

from typing import Literal

from mr_guardian.reporting.design_system import design_system_css

DashboardTheme = Literal["light", "dark"]

THEME_LABELS: dict[str, DashboardTheme] = {
    "Light": "light",
    "Dark": "dark",
}


def theme_from_label(label: str) -> DashboardTheme:
    """Return a dashboard theme from a UI label."""
    return THEME_LABELS.get(label, "light")


def dashboard_css(theme: DashboardTheme) -> str:
    """Return CSS that aligns Streamlit chrome with MR Guardian reports."""
    return f"""
<style>
{design_system_css(theme)}

.stApp {{
  background:
    radial-gradient(circle at 12% -5%, var(--surface-3) 0%, transparent 42%),
    var(--mg-paper);
  color: var(--mg-ink);
  font-family: var(--mg-sans);
}}

[data-testid="stHeader"] {{
  background: transparent;
}}

[data-testid="stSidebar"] {{
  background: var(--mg-card);
  border-right: 1px solid var(--mg-line);
}}

[data-testid="stSidebar"] * {{
  color: var(--mg-ink);
}}

.block-container {{
  max-width: 1280px;
  padding-top: 2.2rem;
  padding-bottom: 4rem;
}}

h1, h2, h3 {{
  color: var(--mg-ink);
  font-family: var(--mg-display);
  letter-spacing: 0;
}}

p, label, span {{
  color: inherit;
}}

a {{
  color: var(--mg-info);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}}

.mg-kicker {{
  color: var(--mg-ink-faint);
  font-family: var(--mg-mono);
  font-size: 11px;
  letter-spacing: .09em;
  margin-bottom: 6px;
  text-transform: uppercase;
}}

.mg-back-link {{
  font-family: var(--mg-mono);
  font-size: 12px;
  margin: 0 0 14px;
}}

.mg-app-hero {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: 0 1px 0 var(--inner-shadow) inset, var(--shadow-md);
  margin: 0 0 22px;
  padding: 26px 30px;
}}

.mg-brand-row {{
  align-items: center;
  display: flex;
  gap: 13px;
}}

.mg-brand-mark {{
  align-items: center;
  background: var(--ink);
  border-radius: 9px;
  color: var(--paper);
  display: inline-flex;
  font-family: var(--mg-mono);
  font-size: 13px;
  font-weight: 700;
  height: 34px;
  justify-content: center;
  letter-spacing: .04em;
  width: 34px;
}}

.mg-app-hero h1 {{
  color: var(--ink);
  font-family: var(--mg-display);
  font-size: 34px;
  font-weight: 800;
  line-height: 1.05;
  margin: 0;
}}

.mg-app-hero p {{
  color: var(--ink-2);
  font-size: 14px;
  line-height: 1.6;
  margin: 16px 0 0;
  max-width: 78ch;
}}

.mg-hero-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}}

.mg-hero-meta span {{
  background: var(--surface-2s);
  border: 1px solid var(--line);
  border-radius: 7px;
  color: var(--ink-2);
  font-family: var(--mg-mono);
  font-size: 11px;
  padding: 5px 10px;
}}

.mg-hero-meta b {{
  color: var(--ink);
  font-weight: 600;
}}

.mg-dashboard-panel {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: var(--shadow-sm);
  margin: 0 0 18px;
  overflow: hidden;
}}

.mg-panel-head {{
  align-items: center;
  background: var(--surface-2s);
  border-bottom: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  padding: 14px 18px;
}}

.mg-panel-head h2 {{
  color: var(--ink);
  font-family: var(--mg-display);
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 0;
  line-height: 1.2;
  margin: 0;
}}

.mg-panel-num,
.mg-panel-eyebrow {{
  color: var(--ink-3);
  font-family: var(--mg-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .11em;
  text-transform: uppercase;
}}

.mg-panel-num {{
  display: inline-block;
  margin-bottom: 3px;
}}

.mg-panel-eyebrow {{
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 4px 9px;
}}

.mg-metric-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
}}

.mg-metric-card {{
  background: var(--surface);
  border-right: 1px solid var(--line);
  min-height: 104px;
  padding: 18px 18px 16px;
}}

.mg-metric-card:last-child {{
  border-right: 0;
}}

.mg-metric-value {{
  color: var(--ink);
  font-family: var(--mg-display);
  font-size: 32px;
  font-variant-numeric: tabular-nums;
  font-weight: 800;
  line-height: 1;
}}

.mg-metric-label {{
  color: var(--ink-3);
  font-family: var(--mg-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .08em;
  margin-top: 8px;
  text-transform: uppercase;
}}

.mg-metric-detail {{
  color: var(--ink-2);
  font-size: 12px;
  margin-top: 8px;
}}

.mg-metric-card.blocking .mg-metric-value,
.mg-metric-card.high .mg-metric-value {{
  color: var(--block);
}}

.mg-metric-card.warning .mg-metric-value {{
  color: var(--warn);
}}

.mg-metric-card.info .mg-metric-value,
.mg-metric-card.accent .mg-metric-value {{
  color: var(--accent);
}}

.mg-metric-card.pass .mg-metric-value {{
  color: var(--pass);
}}

.mg-table-wrap {{
  overflow-x: auto;
}}

.mg-dashboard-table {{
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
}}

.mg-dashboard-table thead th {{
  background: var(--surface-2s);
  border-bottom: 1px solid var(--line);
  color: var(--ink-3);
  font-family: var(--mg-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .08em;
  padding: 10px 14px;
  text-align: left;
  text-transform: uppercase;
  white-space: nowrap;
}}

.mg-dashboard-table tbody td {{
  border-bottom: 1px solid var(--line);
  color: var(--ink-2);
  padding: 11px 14px;
  vertical-align: middle;
}}

.mg-dashboard-table tbody tr:last-child td {{
  border-bottom: 0;
}}

.mg-dashboard-table tbody tr.row-hover:hover {{
  background: var(--surface-2s);
}}

.mg-dashboard-table tbody tr[data-active="true"] {{
  background: var(--accent-bg);
}}

.mg-dashboard-table tbody tr[data-active="true"] td:first-child {{
  box-shadow: inset 3px 0 0 var(--accent);
}}

.mg-table-cell.right {{
  text-align: right;
}}

.mg-cell-mono {{
  color: var(--ink-2);
  font-family: var(--mg-mono);
  font-size: 12px;
}}

.mg-table-link {{
  color: var(--accent);
  font-weight: 700;
  text-decoration: none;
}}

.mg-table-link:hover {{
  text-decoration: underline;
  text-underline-offset: 2px;
}}

.mg-chip-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}}

.mg-chip {{
  background: var(--surface-2s);
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--ink-2);
  display: inline-block;
  font-family: var(--mg-mono);
  font-size: 10.5px;
  padding: 3px 7px;
  white-space: nowrap;
}}

.mg-empty-state {{
  background: var(--surface);
  color: var(--ink-2);
  font-size: 13px;
  padding: 18px 20px;
}}

.mg-raw-md {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  color: var(--ink-2);
  font-family: var(--mg-mono);
  font-size: 12.5px;
  line-height: 1.7;
  margin: 0;
  overflow-x: auto;
  padding: 22px 24px;
  white-space: pre-wrap;
}}

.mg-report-shell {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  padding: 0;
}}

[data-testid="stMetric"] {{
  background: var(--mg-card);
  border: 1px solid var(--mg-line);
  border-radius: 10px;
  box-shadow: 0 1px 0 var(--inner-shadow) inset;
  padding: 16px 18px;
}}

[data-testid="stMetricLabel"] p {{
  color: var(--mg-ink-faint);
  font-family: var(--mg-mono);
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
}}

[data-testid="stMetricValue"] {{
  color: var(--mg-ink);
  font-family: var(--mg-display);
  font-size: 30px;
  font-weight: 700;
}}

[data-testid="stDataFrame"],
[data-testid="stTable"],
[data-testid="stVegaLiteChart"] {{
  background: var(--mg-card);
  border: 1px solid var(--mg-line);
  border-radius: 8px;
  box-shadow: 0 1px 0 var(--inner-shadow) inset;
  overflow: hidden;
}}

[data-testid="stAlert"] {{
  border-radius: 10px;
  border: 1px solid var(--mg-line);
}}

[data-baseweb="input"],
[data-baseweb="select"] > div,
[data-baseweb="textarea"] {{
  background: var(--mg-card-soft);
  border-color: var(--mg-line);
  color: var(--mg-ink);
}}

[data-baseweb="tab-list"] {{
  border-bottom: 1px solid var(--mg-line);
  gap: 6px;
}}

[data-baseweb="tab"] {{
  color: var(--mg-ink-soft);
  font-family: var(--mg-mono);
  font-size: 12px;
}}

[aria-selected="true"][data-baseweb="tab"] {{
  color: var(--mg-block);
}}

hr {{
  border-color: var(--mg-line);
}}
</style>
"""
