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
