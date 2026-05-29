from app.streamlit_components import (
    cell_link,
    render_raw_markdown_block,
    render_table,
)


def test_streamlit_custom_table_escapes_user_controlled_values() -> None:
    html = render_table(
        ["Developer"],
        [["<script>bad()</script>"]],
    )

    assert '<table class="mg-dashboard-table">' in html
    assert "<script>bad()</script>" not in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html


def test_streamlit_custom_table_link_cell_escapes_label_and_href() -> None:
    html = render_table(
        ["Developer"],
        [[cell_link('<bad "label">', 'javascript:"bad"')]],
    )

    assert '<bad "label">' not in html
    assert 'href="javascript:&quot;bad&quot;"' in html
    assert "&lt;bad &quot;label&quot;&gt;" in html


def test_raw_markdown_report_block_is_escaped() -> None:
    html = render_raw_markdown_block("## Report\n<script>bad()</script>")

    assert "mg-raw-md" in html
    assert "<script>bad()</script>" not in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
