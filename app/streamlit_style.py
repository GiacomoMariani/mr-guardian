"""Shared Streamlit styling for the MR Guardian dashboard."""

from typing import Literal

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
    palette = _theme_palette(theme)
    return f"""
<style>
:root {{
  --mg-ink: {palette.ink};
  --mg-ink-soft: {palette.ink_soft};
  --mg-ink-faint: {palette.ink_faint};
  --mg-paper: {palette.paper};
  --mg-card: {palette.card};
  --mg-card-soft: {palette.card_soft};
  --mg-line: {palette.line};
  --mg-line-strong: {palette.line_strong};
  --mg-block: #b3261e;
  --mg-block-bg: {palette.block_bg};
  --mg-warn: #b06b00;
  --mg-warn-bg: {palette.warn_bg};
  --mg-info: #2f5d8c;
  --mg-info-bg: {palette.info_bg};
  --mg-pass: #2f6f4f;
  --mg-pass-bg: {palette.pass_bg};
  --mg-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --mg-sans: Inter, Segoe UI, system-ui, sans-serif;
  --mg-display: Georgia, serif;
}}

.stApp {{
  background:
    radial-gradient(circle at 12% -5%, {palette.glow} 0%, transparent 42%),
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

.mg-page-heading {{
  background: var(--mg-card);
  border: 1px solid var(--mg-line);
  border-radius: 14px;
  box-shadow: 0 1px 0 {palette.inner_shadow} inset,
    0 24px 60px -36px rgba(26, 29, 33, .34);
  padding: 28px 32px;
  margin: 0 0 22px;
}}

.mg-kicker {{
  color: var(--mg-ink-faint);
  font-family: var(--mg-mono);
  font-size: 11px;
  letter-spacing: .09em;
  margin-bottom: 6px;
  text-transform: uppercase;
}}

.mg-page-heading h1 {{
  color: var(--mg-ink);
  font-family: var(--mg-display);
  font-size: 30px;
  font-weight: 700;
  line-height: 1.15;
  margin: 0;
}}

.mg-page-heading p {{
  color: var(--mg-ink-soft);
  font-size: 14px;
  line-height: 1.55;
  margin: 10px 0 0;
  max-width: 76ch;
}}

.mg-back-link {{
  font-family: var(--mg-mono);
  font-size: 12px;
  margin: 0 0 14px;
}}

.mg-section-label {{
  align-items: center;
  border-top: 1px solid var(--mg-line);
  display: flex;
  gap: 12px;
  margin: 26px 0 14px;
  padding-top: 24px;
}}

.mg-section-label span {{
  color: var(--mg-ink-faint);
  font-family: var(--mg-mono);
  font-size: 12px;
}}

.mg-section-label h2 {{
  color: var(--mg-ink);
  font-family: var(--mg-display);
  font-size: 21px;
  line-height: 1.2;
  margin: 0;
}}

[data-testid="stMetric"] {{
  background: var(--mg-card);
  border: 1px solid var(--mg-line);
  border-radius: 10px;
  box-shadow: 0 1px 0 {palette.inner_shadow} inset;
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
  box-shadow: 0 1px 0 {palette.inner_shadow} inset;
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


def section_heading(index: int, title: str) -> str:
    """Return a styled section heading."""
    return (
        '<div class="mg-section-label">'
        f"<span>{index:02}</span>"
        f"<h2>{title}</h2>"
        "</div>"
    )


class _Palette:
    def __init__(
        self,
        *,
        ink: str,
        ink_soft: str,
        ink_faint: str,
        paper: str,
        card: str,
        card_soft: str,
        line: str,
        line_strong: str,
        glow: str,
        inner_shadow: str,
        block_bg: str,
        warn_bg: str,
        info_bg: str,
        pass_bg: str,
    ) -> None:
        self.ink = ink
        self.ink_soft = ink_soft
        self.ink_faint = ink_faint
        self.paper = paper
        self.card = card
        self.card_soft = card_soft
        self.line = line
        self.line_strong = line_strong
        self.glow = glow
        self.inner_shadow = inner_shadow
        self.block_bg = block_bg
        self.warn_bg = warn_bg
        self.info_bg = info_bg
        self.pass_bg = pass_bg


def _theme_palette(theme: DashboardTheme) -> _Palette:
    if theme == "dark":
        return _Palette(
            ink="#f3eee5",
            ink_soft="#c7c0b4",
            ink_faint="#8f97a3",
            paper="#0e1117",
            card="#171a21",
            card_soft="#20232b",
            line="#2b303a",
            line_strong="#3b414d",
            glow="#23201b",
            inner_shadow="rgba(255,255,255,.04)",
            block_bg="#331817",
            warn_bg="#332514",
            info_bg="#142333",
            pass_bg="#14291d",
        )
    return _Palette(
        ink="#1a1d21",
        ink_soft="#4b5159",
        ink_faint="#8b929b",
        paper="#f4f1ea",
        card="#fffdf8",
        card_soft="#fbf9f3",
        line="#e2ddd1",
        line_strong="#cfc8b8",
        glow="#fbf9f3",
        inner_shadow="#fff",
        block_bg="#fbe9e7",
        warn_bg="#fbf1dd",
        info_bg="#e8f0f8",
        pass_bg="#e6f2ea",
    )
