"""Reusable Streamlit HTML presentation helpers for the dashboard."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from math import ceil
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
    top_links: Sequence[tuple[str, str]] = (),
) -> str:
    """Render the standalone-style dashboard header."""
    meta_html = "".join(
        f"<span>{_html(label)} <b>{_html(value)}</b></span>"
        for label, value in meta_items
    )
    links_html = (
        '<div class="mg-hero-links">'
        + "".join(
            '<a class="mg-hero-top-link" '
            f'href="{_html(url)}" target="_blank" rel="noreferrer">'
            f"{_html(label)}</a>"
            for label, url in top_links
        )
        + "</div>"
        if top_links
        else ""
    )
    return "\n".join(
        [
            '<section class="mg-app-hero">',
            '<div class="mg-app-hero-top">',
            f'<div class="mg-kicker">{_html(kicker)}</div>',
            links_html,
            "</div>",
            '<div class="mg-brand-row">',
            '<div class="mg-brand-mark">MR</div>',
            f"<h1>{_html(title)}</h1>",
            "</div>",
            f"<p>{_html(body)}</p>",
            f'<div class="mg-hero-meta">{meta_html}</div>' if meta_items else "",
            "</section>",
        ]
    )


def render_section(
    *,
    index: int | None = None,
    title: str,
    body_html: str,
    subtitle: str | None = None,
    eyebrow: str | None = None,
    action_html: str | None = None,
    anchor_id: str | None = None,
) -> str:
    """Render one dashboard panel.

    ``index`` is retained for call-site compatibility, but dashboard panels no
    longer render visible sequence numbers. ``subtitle`` renders muted alongside
    the title in the head.
    """
    eyebrow_html = (
        f'<span class="mg-panel-eyebrow">{_html(eyebrow)}</span>'
        if eyebrow is not None
        else ""
    )
    action = action_html or ""
    section_id = f' id="{_html(anchor_id)}"' if anchor_id else ""
    subtitle_html = (
        f'<span class="mg-panel-subtitle">{_html(subtitle)}</span>'
        if subtitle is not None
        else ""
    )
    return "\n".join(
        [
            f'<section class="mg-dashboard-panel"{section_id}>',
            '<div class="mg-panel-head">',
            "<div>",
            f"<h2>{_html(title)}</h2>",
            subtitle_html,
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

    first_row = rows[0]
    header_html = "".join(
        _render_header_cell(
            header, first_row[index] if index < len(first_row) else None
        )
        for index, header in enumerate(headers)
    )
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


def render_trend_chart(
    points: Sequence[tuple[str, int, int]],
    *,
    empty_message: str = "No trend data is available yet.",
) -> str:
    """Render a responsive design-system trend chart."""
    if not points:
        return "\n".join(
            [
                '<section class="mg-trend-chart-card">',
                '<div class="mg-trend-chart-head">',
                "<h2>Review Risk Trend</h2>",
                '<span class="mg-panel-eyebrow">Findings</span>',
                "</div>",
                render_empty_state(empty_message),
                "</section>",
            ]
        )

    width = 920
    height = 290
    margin_left = 58
    margin_right = 24
    margin_top = 28
    margin_bottom = 54
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    max_count = max(max(blocking, warning) for _, blocking, warning in points)
    max_y = max(1, max_count)
    ticks = _trend_ticks(max_y)
    blocking_points = _svg_points(
        points,
        value_index=1,
        max_y=max_y,
        plot_width=plot_width,
        plot_height=plot_height,
        margin_left=margin_left,
        margin_top=margin_top,
    )
    warning_points = _svg_points(
        points,
        value_index=2,
        max_y=max_y,
        plot_width=plot_width,
        plot_height=plot_height,
        margin_left=margin_left,
        margin_top=margin_top,
    )
    grid_html = "\n".join(
        _trend_grid_line(
            tick,
            max_y=max_y,
            plot_width=plot_width,
            plot_height=plot_height,
            margin_left=margin_left,
            margin_top=margin_top,
        )
        for tick in ticks
    )
    x_labels_html = "\n".join(
        _trend_x_label(
            index,
            point[0],
            point_count=len(points),
            plot_width=plot_width,
            plot_height=plot_height,
            margin_left=margin_left,
            margin_top=margin_top,
        )
        for index, point in enumerate(points)
        if _should_show_x_label(index, len(points))
    )
    return "\n".join(
        [
            '<section class="mg-trend-chart-card">',
            '<div class="mg-trend-chart-head">',
            "<h2>Review Risk Trend</h2>",
            '<div class="mg-trend-legend">',
            '<span><i class="blocking"></i>Blocking</span>',
            '<span><i class="warning"></i>Warnings</span>',
            "</div>",
            "</div>",
            '<div class="mg-trend-chart-body">',
            (
                f'<svg class="mg-trend-svg" viewBox="0 0 {width} {height}" '
                'role="img" aria-label="Blocking and warning findings over time">'
            ),
            grid_html,
            _trend_polyline(blocking_points, "blocking"),
            _trend_polyline(warning_points, "warning"),
            _trend_circles(blocking_points, "blocking"),
            _trend_circles(warning_points, "warning"),
            x_labels_html,
            (
                f'<text class="mg-trend-axis-title" x="16" '
                f'y="{margin_top + plot_height / 2}" transform="rotate(-90 16 '
                f'{margin_top + plot_height / 2})">Findings</text>'
            ),
            "</svg>",
            "</div>",
            "</section>",
        ]
    )


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


def _render_header_cell(header: str, sample_cell: TableValue) -> str:
    # Mirror the column's cell alignment onto its header, so a right-aligned numeric
    # column (e.g. Score, Changed Lines) lines its header up over the values.
    align = sample_cell.align if isinstance(sample_cell, TableCell) else "left"
    align_class = ' class="right"' if align == "right" else ""
    return f"<th{align_class}>{_html(header)}</th>"


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


def _trend_ticks(max_y: int) -> list[int]:
    if max_y <= 4:
        return list(range(0, max_y + 1))
    step = ceil(max_y / 4)
    ticks = list(range(0, max_y + 1, step))
    return ticks if ticks[-1] == max_y else [*ticks, max_y]


def _svg_points(
    points: Sequence[tuple[str, int, int]],
    *,
    value_index: int,
    max_y: int,
    plot_width: int,
    plot_height: int,
    margin_left: int,
    margin_top: int,
) -> list[tuple[float, float]]:
    denominator = max(1, len(points) - 1)
    return [
        (
            margin_left + (index / denominator) * plot_width,
            margin_top + plot_height - (point[value_index] / max_y) * plot_height,
        )
        for index, point in enumerate(points)
    ]


def _trend_grid_line(
    tick: int,
    *,
    max_y: int,
    plot_width: int,
    plot_height: int,
    margin_left: int,
    margin_top: int,
) -> str:
    y = margin_top + plot_height - (tick / max_y) * plot_height
    x_end = margin_left + plot_width
    return "\n".join(
        [
            (
                f'<line class="mg-trend-grid" x1="{margin_left:.2f}" y1="{y:.2f}" '
                f'x2="{x_end:.2f}" y2="{y:.2f}" />'
            ),
            (
                f'<text class="mg-trend-y-label" x="{margin_left - 14}" '
                f'y="{y + 4:.2f}" text-anchor="end">{tick}</text>'
            ),
        ]
    )


def _trend_polyline(points: Sequence[tuple[float, float]], tone: Tone) -> str:
    coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polyline class="mg-trend-line {tone}" points="{coords}" />'


def _trend_circles(points: Sequence[tuple[float, float]], tone: Tone) -> str:
    return "\n".join(
        f'<circle class="mg-trend-point {tone}" cx="{x:.2f}" cy="{y:.2f}" r="4.2" />'
        for x, y in points
    )


def _trend_x_label(
    index: int,
    label: str,
    *,
    point_count: int,
    plot_width: int,
    plot_height: int,
    margin_left: int,
    margin_top: int,
) -> str:
    denominator = max(1, point_count - 1)
    x = margin_left + (index / denominator) * plot_width
    y = margin_top + plot_height + 28
    return (
        f'<text class="mg-trend-x-label" x="{x:.2f}" y="{y}" '
        f'text-anchor="middle">{_html(label)}</text>'
    )


def _should_show_x_label(index: int, point_count: int) -> bool:
    if point_count <= 8:
        return True
    step = ceil(point_count / 8)
    return index == 0 or index == point_count - 1 or index % step == 0
