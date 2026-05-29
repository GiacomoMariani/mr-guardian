from mr_guardian.reporting.design_system import (
    css_variable_block,
    design_system_css,
    palette_for_theme,
    render_data_table,
)


def test_design_system_css_uses_standalone_tokens_and_local_fonts() -> None:
    css = design_system_css("light")

    assert "--paper: #F1EBDD;" in css
    assert "--surface: #FBF7EE;" in css
    assert "Hanken Grotesk" in css
    assert "JetBrains Mono" in css
    assert "data:font/woff2;base64," in css
    assert "https://" not in css
    assert "http://" not in css


def test_design_system_css_supports_dark_theme() -> None:
    css = css_variable_block("dark")
    palette = palette_for_theme("dark")

    assert palette.paper == "#15120D"
    assert "--paper: #15120D;" in css
    assert "--accent: #6E8FC9;" in css
    assert "--mg-sans: 'Hanken Grotesk'" in css


def test_render_data_table_escapes_user_controlled_values() -> None:
    html = render_data_table(
        ["Developer", "Finding"],
        [["<script>bad()</script>", "MR-META-001"]],
        active_row_index=0,
    )

    assert '<table class="mg-data-table">' in html
    assert 'data-active="true"' in html
    assert "<script>bad()</script>" not in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html


def test_render_data_table_empty_state_is_escaped() -> None:
    html = render_data_table(
        ["Rule"],
        [],
        empty_message="<b>No rules</b>",
    )

    assert '<div class="mg-empty-state">' in html
    assert "<b>No rules</b>" not in html
    assert "&lt;b&gt;No rules&lt;/b&gt;" in html
