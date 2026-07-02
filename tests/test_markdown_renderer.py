"""Tests for the markdown/TSV tool-output renderer."""
from providers.markdown_renderer import render_markdown, fmt_number


# --- fmt_number ---

def test_fmt_number_strips_float_noise():
    assert fmt_number(45.79999999999999) == "45.8"


def test_fmt_number_max_4_decimals():
    assert fmt_number(1.123456789) == "1.1235"


def test_fmt_number_integers_untouched():
    assert fmt_number(12500000) == "12500000"


def test_fmt_number_ratio_keys_get_2_decimals():
    assert fmt_number(3.14159, key="fk_orani") == "3.14"
    assert fmt_number(5.0, key="dividendYield") == "5"
    assert fmt_number(1.239, key="pct_change") == "1.24"


def test_fmt_number_tiny_floats_keep_significance():
    # crypto micro-prices must not collapse to "0"
    assert fmt_number(0.00001234) != "0"


def test_fmt_number_non_numeric_passthrough():
    assert fmt_number("GARAN") == "GARAN"
    assert fmt_number(True) == "True"


# --- flat dict rendering ---

def test_render_scalar_fields_as_key_value_lines():
    out = render_markdown({"symbol": "GARAN", "price": 45.79999999999999, "volume": 12500000})
    assert "symbol: GARAN" in out
    assert "price: 45.8" in out
    assert "volume: 12500000" in out


def test_render_empty_payload():
    assert render_markdown({}) == "Sonuç bulunamadı."


def test_render_never_raises():
    class Weird:
        def __str__(self):
            raise RuntimeError("boom")
    out = render_markdown({"x": Weird()})
    assert isinstance(out, str)


# --- TSV tables and containers ---

def test_list_of_dicts_renders_tsv_block():
    out = render_markdown({"data_points": [
        {"date": "2026-06-30", "close": 45.8, "volume": 12500000},
        {"date": "2026-07-01", "close": 46.2, "volume": 9800000},
    ]})
    assert "```tsv" in out
    assert "date\tclose\tvolume" in out
    assert "2026-06-30\t45.8\t12500000" in out
    assert out.count("```") == 2


def test_table_columns_are_union_of_keys():
    out = render_markdown({"rows": [
        {"a": 1, "b": 2},
        {"a": 3, "c": 4},
    ]})
    assert "a\tb\tc" in out
    # missing values are empty cells
    assert "3\t\t4" in out


def test_table_cells_sanitize_tabs_and_newlines():
    out = render_markdown({"rows": [
        {"name": "line1\nline2", "note": "tab\there"},
        {"name": "x", "note": "y"},
    ]})
    assert "line1 line2\ttab here" in out


def test_single_dict_list_renders_as_nested_not_table():
    out = render_markdown({"results": [{"symbol": "GARAN", "price": 45.8}]})
    assert "```tsv" not in out
    assert "symbol: GARAN" in out


def test_scalar_list_renders_inline():
    out = render_markdown({"tickers": ["GARAN", "AKBNK", "THYAO"]})
    assert "tickers: GARAN, AKBNK, THYAO" in out


def test_empty_list_renders_empty_marker():
    out = render_markdown({"results": []})
    assert "results: Sonuç bulunamadı." in out


def test_nested_dict_renders_subheading():
    out = render_markdown({"symbol": "GARAN", "valuation": {"pe": 5.2, "pb": 1.1}})
    assert "## valuation" in out
    assert "pe: 5.2" in out


def test_deep_nesting_increases_heading_level():
    out = render_markdown({"a": {"b": {"c": 1}}})
    assert "## a" in out
    assert "### b" in out
    assert "c: 1" in out


# --- meta / warnings / special cases ---

def test_meta_and_warnings_become_trailing_blockquotes():
    out = render_markdown({
        "symbol": "GARAN",
        "meta": {"truncated": True, "guidance": "Narrow the date range."},
        "warnings": ["ISCTR: boom"],
    })
    lines = out.splitlines()
    assert "> Not: Narrow the date range." in lines
    assert "> Not: ISCTR: boom" in lines
    # blockquotes come last
    assert lines[-1].startswith("> Not:")
    assert "## meta" not in out


def test_long_content_field_renders_as_body():
    body = "# ASELSAN\n\nŞirketimiz sözleşme imzalamıştır. " + "x" * 300
    out = render_markdown({"title": "ASELSAN KAP", "content": body, "total_pages": 1})
    assert "title: ASELSAN KAP" in out
    assert "content:" not in out
    assert "Şirketimiz sözleşme imzalamıştır." in out
    # body keeps its newlines (not cell-sanitized)
    assert "# ASELSAN\n" in out


def test_financial_statements_render_as_period_matrix():
    out = render_markdown({"statements": [{
        "symbol": "GARAN",
        "statement_type": "balance_sheet",
        "periods": ["2024", "2023"],
        "data": {
            "Total Assets": [100.0, 90.0],
            "Cash": [50.5, None],
        },
    }]})
    assert "Kalem\t2024\t2023" in out
    assert "Total Assets\t100\t90" in out
    assert "Cash\t50.5\t" in out
    assert "symbol: GARAN" in out
