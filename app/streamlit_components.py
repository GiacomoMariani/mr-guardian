"""Reusable Streamlit HTML presentation helpers for the dashboard."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from typing import Literal, TypeAlias

Tone = Literal["neutral", "accent", "blocking", "high", "warning", "info", "pass"]
Alignment = Literal["left", "right"]


@dataclass(frozen=True)
class MetricCard:
    """A compact dashboard metric card."""

    label: str
    value: str | int | float
    tone: Tone = "neutral"
    detail: str | None = None


@dataclass(frozen=True)
class TableCell:
    """An escaped or internally generated table cell."""

    html: str
    align: Alignment = "left"


TableValue: TypeAlias = TableCell | str | int | float | None


def render_page_header(
    *,
    title: str,
    kicker: str,
    body: str,
    meta_items: Sequence[tuple[str, str]] = (),
) -> str:
    """Render the standalone-style dashboard header."""
    meta_html = "".join(
        f"<span>{_html(label)} <b>{_html(value)}</b></span>"
        for label, value in meta_items
    )
    return "\n".join(
        [
            '<section class="mg-app-hero">',
            '<div class="mg-brand-row">',
            '<div class="mg-brand-mark">MR</div>',
            "<div>",
            f'<div class="mg-kicker">{_html(kicker)}</div>',
            f"<h1>{_html(title)}</h1>",
            "</div>",
            "</div>",
            f"<p>{_html(body)}</p>",
            f'<div class="mg-hero-meta">{meta_html}</div>' if meta_items else "",
            "</section>",
        ]
    )


def render_section(
    *,
    index: int,
    title: str,
    body_html: str,
    eyebrow: str | None = None,
    action_html: str | None = None,
) -> str:
    """Render one dashboard panel."""
    eyebrow_html = (
        f'<span class="mg-panel-eyebrow">{_html(eyebrow)}</span>'
        if eyebrow is not None
        else ""
    )
    action = action_html or ""
    return "\n".join(
        [
            '<section class="mg-dashboard-panel">',
            '<div class="mg-panel-head">',
            "<div>",
            f'<span class="mg-panel-num">{index:02}</span>',
            f"<h2>{_html(title)}</h2>",
            "</div>",
            eyebrow_html or action,
            "</div>",
            body_html,
            "</section>",
        ]
    )


def render_metric_grid(cards: Sequence[MetricCard]) -> str:
    """Render a standalone-style metric strip."""
    if not cards:
        return ""

    card_html = "".join(_render_metric_card(card) for card in cards)
    return f'<div class="mg-metric-grid">{card_html}</div>'


def render_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[TableValue]],
    *,
    empty_message: str = "No rows to display.",
    active_row_index: int | None = None,
) -> str:
    """Render a styled custom HTML table."""
    if not rows:
        return render_empty_state(empty_message)

    header_html = "".join(f"<th>{_html(header)}</th>" for header in headers)
    row_html = "\n".join(
        _render_row(row, is_active=index == active_row_index)
        for index, row in enumerate(rows)
    )
    return (
        '<div class="mg-table-wrap">'
        '<table class="mg-dashboard-table">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{row_html}</tbody>"
        "</table>"
        "</div>"
    )


def render_empty_state(message: str) -> str:
    """Render a dashboard empty state."""
    return f'<div class="mg-empty-state">{_html(message)}</div>'


def render_raw_markdown_block(markdown: str) -> str:
    """Render raw Markdown text inside the standalone-style report block."""
    return f'<pre class="mg-raw-md">{_html(markdown)}</pre>'


def cell_text(value: object, *, align: Alignment = "left", mono: bool = False) -> TableCell:
    """Create an escaped text cell."""
    css_class = "mg-cell-mono" if mono else ""
    return TableCell(
        html=f'<span class="{css_class}">{_html(_format_value(value))}</span>',
        align=align,
    )


def cell_link(label: str, href: str) -> TableCell:
    """Create an escaped link cell."""
    return TableCell(
        html=(
            f'<a class="mg-table-link" href="{_html(href)}">'
            f"{_html(label)}</a>"
        )
    )


def cell_pill(label: str, tone: Tone) -> TableCell:
    """Create a severity/status pill cell."""
    return TableCell(
        html=(
            f'<span class="mg-status-pill {tone}">'
            f"{_html(label)}</span>"
        )
    )


def cell_chips(values: Sequence[str], *, empty_label: str = "-") -> TableCell:
    """Create a compact chip list cell."""
    if not values:
        return cell_text(empty_label)
    chip_html = "".join(
        f'<span class="mg-chip">{_html(value)}</span>'
        for value in values
    )
    return TableCell(html=f'<div class="mg-chip-row">{chip_html}</div>')


def _render_metric_card(card: MetricCard) -> str:
    detail = (
        f'<div class="mg-metric-detail">{_html(card.detail)}</div>'
        if card.detail is not None
        else ""
    )
    return "\n".join(
        [
            f'<div class="mg-metric-card {card.tone}">',
            f'<div class="mg-metric-value">{_html(_format_value(card.value))}</div>',
            f'<div class="mg-metric-label">{_html(card.label)}</div>',
            detail,
            "</div>",
        ]
    )


def _render_row(row: Sequence[TableValue], *, is_active: bool) -> str:
    active_attribute = ' data-active="true"' if is_active else ""
    cells = "".join(_render_cell(value) for value in row)
    return f'<tr class="row-hover"{active_attribute}>{cells}</tr>'


def _render_cell(value: TableValue) -> str:
    cell = value if isinstance(value, TableCell) else cell_text(value)
    align_class = " right" if cell.align == "right" else ""
    return f'<td class="mg-table-cell{align_class}">{cell.html}</td>'


def _format_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _html(value: str) -> str:
    return escape(value, quote=True)
