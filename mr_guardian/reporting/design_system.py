"""Shared visual design helpers for MR Guardian HTML surfaces."""

from __future__ import annotations

from base64 import b64encode
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Literal

DesignTheme = Literal["light", "dark"]

LATIN_RANGE = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, "
    "U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, "
    "U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"
)
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"


@dataclass(frozen=True)
class DesignPalette:
    """Standalone app palette tokens."""

    paper: str
    surface: str
    surface_2: str
    surface_2s: str
    surface_3: str
    ink: str
    ink_2: str
    ink_3: str
    line: str
    line_2: str
    line_strong: str
    block: str
    block_bg: str
    block_line: str
    warn: str
    warn_bg: str
    warn_line: str
    info: str
    info_bg: str
    info_line: str
    pass_color: str
    pass_bg: str
    pass_line: str
    accent: str
    accent_bg: str
    accent_ink: str
    shadow_sm: str
    shadow_md: str
    grid_line: str
    inner_shadow: str


DARK_PALETTE = DesignPalette(
    paper="#15120D",
    surface="#1D1913",
    surface_2="#25201827",
    surface_2s="#272118",
    surface_3="#2E2719",
    ink="#ECE4D4",
    ink_2="#ADA28C",
    ink_3="#7C7261",
    line="#322B20",
    line_2="#3F3727",
    line_strong="#4C4231",
    block="#E2725B",
    block_bg="rgba(226,114,91,.13)",
    block_line="rgba(226,114,91,.32)",
    warn="#D9A23A",
    warn_bg="rgba(217,162,58,.13)",
    warn_line="rgba(217,162,58,.30)",
    info="#8FA6BA",
    info_bg="rgba(143,166,186,.12)",
    info_line="rgba(143,166,186,.28)",
    pass_color="#87A86A",
    pass_bg="rgba(135,168,106,.13)",
    pass_line="rgba(135,168,106,.30)",
    accent="#6E8FC9",
    accent_bg="rgba(110,143,201,.14)",
    accent_ink="#0E1118",
    shadow_sm="0 1px 2px rgba(0,0,0,.4)",
    shadow_md="0 4px 18px -6px rgba(0,0,0,.55)",
    grid_line="rgba(255,255,255,.045)",
    inner_shadow="rgba(255,255,255,.05)",
)

LIGHT_PALETTE = DesignPalette(
    paper="#F1EBDD",
    surface="#FBF7EE",
    surface_2="#EDE6D622",
    surface_2s="#EBE3D2",
    surface_3="#E3DAC6",
    ink="#2B2519",
    ink_2="#6A6151",
    ink_3="#978C76",
    line="#E0D8C6",
    line_2="#D4CAB4",
    line_strong="#C3B69C",
    block="#BC4636",
    block_bg="rgba(188,70,54,.10)",
    block_line="rgba(188,70,54,.26)",
    warn="#9C6F12",
    warn_bg="rgba(156,111,18,.12)",
    warn_line="rgba(156,111,18,.28)",
    info="#566B7C",
    info_bg="rgba(86,107,124,.10)",
    info_line="rgba(86,107,124,.24)",
    pass_color="#51723E",
    pass_bg="rgba(81,114,62,.12)",
    pass_line="rgba(81,114,62,.28)",
    accent="#2C4A7E",
    accent_bg="rgba(44,74,126,.10)",
    accent_ink="#FBF7EE",
    shadow_sm="0 1px 2px rgba(70,56,30,.08)",
    shadow_md="0 6px 22px -10px rgba(70,56,30,.22)",
    grid_line="rgba(43,37,25,.05)",
    inner_shadow="rgba(255,255,255,.72)",
)


def palette_for_theme(theme: DesignTheme) -> DesignPalette:
    """Return design tokens for a theme."""
    if theme == "dark":
        return DARK_PALETTE
    return LIGHT_PALETTE


def design_system_css(theme: DesignTheme, *, include_fonts: bool = True) -> str:
    """Return reusable CSS from the standalone MR Guardian design."""
    css_parts = [
        font_face_css() if include_fonts else "",
        css_variable_block(theme),
        primitives_css(),
    ]
    return "\n".join(part for part in css_parts if part)


def css_variable_block(theme: DesignTheme, *, selector: str = ":root") -> str:
    """Return CSS variables for one visual theme."""
    palette = palette_for_theme(theme)
    return f"""
{selector} {{
  --paper: {palette.paper};
  --surface: {palette.surface};
  --surface-2: {palette.surface_2};
  --surface-2s: {palette.surface_2s};
  --surface-3: {palette.surface_3};
  --ink: {palette.ink};
  --ink-2: {palette.ink_2};
  --ink-3: {palette.ink_3};
  --line: {palette.line};
  --line-2: {palette.line_2};
  --line-strong: {palette.line_strong};
  --block: {palette.block};
  --block-bg: {palette.block_bg};
  --block-line: {palette.block_line};
  --warn: {palette.warn};
  --warn-bg: {palette.warn_bg};
  --warn-line: {palette.warn_line};
  --info: {palette.info};
  --info-bg: {palette.info_bg};
  --info-line: {palette.info_line};
  --pass: {palette.pass_color};
  --pass-bg: {palette.pass_bg};
  --pass-line: {palette.pass_line};
  --accent: {palette.accent};
  --accent-bg: {palette.accent_bg};
  --accent-ink: {palette.accent_ink};
  --shadow-sm: {palette.shadow_sm};
  --shadow-md: {palette.shadow_md};
  --grid-line: {palette.grid_line};
  --inner-shadow: {palette.inner_shadow};

  --ink-soft: var(--ink-2);
  --ink-faint: var(--ink-3);
  --card: var(--surface);
  --card-soft: var(--surface-2s);

  --mg-ink: var(--ink);
  --mg-ink-soft: var(--ink-2);
  --mg-ink-faint: var(--ink-3);
  --mg-paper: var(--paper);
  --mg-card: var(--surface);
  --mg-card-soft: var(--surface-2s);
  --mg-line: var(--line);
  --mg-line-strong: var(--line-strong);
  --mg-block: var(--block);
  --mg-block-bg: var(--block-bg);
  --mg-warn: var(--warn);
  --mg-warn-bg: var(--warn-bg);
  --mg-info: var(--info);
  --mg-info-bg: var(--info-bg);
  --mg-pass: var(--pass);
  --mg-pass-bg: var(--pass-bg);
  --mg-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --mg-sans: 'Hanken Grotesk', Inter, Segoe UI, system-ui, sans-serif;
  --mg-display: 'Hanken Grotesk', Inter, Segoe UI, system-ui, sans-serif;
  --mono: var(--mg-mono);
  --sans: var(--mg-sans);
  --display: var(--mg-display);
}}
"""


def primitives_css() -> str:
    """Return reusable HTML primitives aligned with the standalone design."""
    return """
* { box-sizing: border-box; }

.mg-mono {
  font-family: var(--mg-mono);
  font-feature-settings: "tnum" 1;
}

.mg-label {
  color: var(--ink-3);
  font-family: var(--mg-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .11em;
  text-transform: uppercase;
}

.mg-display {
  font-family: var(--mg-display);
  font-variant-numeric: tabular-nums;
  font-weight: 800;
  letter-spacing: 0;
}

.mg-shell {
  margin: 0 auto;
  max-width: 1320px;
  padding-left: 28px;
  padding-right: 28px;
}

.mg-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: var(--shadow-sm);
}

.mg-status-pill {
  border-radius: 999px;
  display: inline-block;
  font-family: var(--mg-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .05em;
  padding: 3px 9px;
  text-transform: uppercase;
}

.mg-status-pill.blocking {
  background: var(--block-bg);
  border: 1px solid var(--block-line);
  color: var(--block);
}

.mg-status-pill.warning,
.mg-status-pill.high {
  background: var(--warn-bg);
  border: 1px solid var(--warn-line);
  color: var(--warn);
}

.mg-status-pill.info {
  background: var(--info-bg);
  border: 1px solid var(--info-line);
  color: var(--info);
}

.mg-status-pill.none,
.mg-status-pill.pass {
  background: var(--pass-bg);
  border: 1px solid var(--pass-line);
  color: var(--pass);
}

.mg-data-table {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
}

.mg-data-table thead th {
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
}

.mg-data-table tbody td {
  border-bottom: 1px solid var(--line);
  padding: 11px 14px;
  vertical-align: middle;
}

.mg-data-table tbody tr:last-child td {
  border-bottom: 0;
}

.mg-data-table tbody tr.row-hover:hover {
  background: var(--surface-2s);
}

.mg-data-table tbody tr[data-active="true"] {
  background: var(--accent-bg);
}

.mg-data-table tbody tr[data-active="true"] td:first-child {
  box-shadow: inset 3px 0 0 var(--accent);
}

.mg-empty-state {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  color: var(--ink-2);
  font-size: 13px;
  padding: 18px 20px;
}
"""


def render_data_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    empty_message: str = "No rows to display.",
    active_row_index: int | None = None,
) -> str:
    """Render an escaped HTML table using the shared design classes."""
    if not rows:
        return f'<div class="mg-empty-state">{_html(empty_message)}</div>'

    header_html = "".join(f"<th>{_html(header)}</th>" for header in headers)
    row_html = "\n".join(
        _render_table_row(row, is_active=index == active_row_index)
        for index, row in enumerate(rows)
    )
    return (
        '<table class="mg-data-table">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{row_html}</tbody>"
        "</table>"
    )


def _render_table_row(row: Sequence[str], *, is_active: bool) -> str:
    active_attribute = ' data-active="true"' if is_active else ""
    cells = "".join(f"<td>{_html(cell)}</td>" for cell in row)
    return f'<tr class="row-hover"{active_attribute}>{cells}</tr>'


@lru_cache(maxsize=1)
def font_face_css() -> str:
    """Return local font-face rules as data URLs."""
    hanken = _font_data_url("hanken-grotesk-latin.woff2")
    jetbrains = _font_data_url("jetbrains-mono-latin.woff2")
    return f"""
@font-face {{
  font-family: 'Hanken Grotesk';
  font-style: normal;
  font-weight: 400 800;
  font-display: swap;
  src: url("{hanken}") format('woff2');
  unicode-range: {LATIN_RANGE};
}}

@font-face {{
  font-family: 'JetBrains Mono';
  font-style: normal;
  font-weight: 400 700;
  font-display: swap;
  src: url("{jetbrains}") format('woff2');
  unicode-range: {LATIN_RANGE};
}}
"""


def _font_data_url(filename: str) -> str:
    font_path = FONT_DIR / filename
    encoded = b64encode(font_path.read_bytes()).decode("ascii")
    return f"data:font/woff2;base64,{encoded}"


def _html(value: str) -> str:
    return escape(value, quote=True)
