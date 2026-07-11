"""TCMB's calculator API returns invariant-culture numbers, not Turkish ones.

Observed live on 2026-07-11:

    'yeniSepetDeger': '601.31'        -> dot is the DECIMAL separator
    'sonYilTufe':     '2,684.55000'   -> comma is the THOUSANDS separator

The legacy `tr_to_float` assumed the opposite (Turkish convention: dot groups
thousands, comma is decimal), so it stripped the decimal point and multiplied
every value by ~100. The tool reported "100 TL in 2020-01 is 60,131 TL in
2024-12" -- a 100x overstatement served as fact.

`parse_tcmb_number` resolves the format by the LAST separator in the string,
which is the decimal one in both conventions.
"""

import pytest

from providers.market_router import parse_tcmb_number


class TestInvariantCultureFormat:
    """What TCMB actually sends today."""

    def test_dot_decimal(self):
        assert parse_tcmb_number("601.31") == pytest.approx(601.31)

    def test_comma_thousands_with_dot_decimal(self):
        assert parse_tcmb_number("2,684.55000") == pytest.approx(2684.55)

    def test_trailing_zeros(self):
        assert parse_tcmb_number("446.45000") == pytest.approx(446.45)

    def test_percentage(self):
        assert parse_tcmb_number("44.03") == pytest.approx(44.03)


class TestTurkishFormat:
    """If TCMB ever switches back, the last separator still wins."""

    def test_comma_decimal(self):
        assert parse_tcmb_number("601,31") == pytest.approx(601.31)

    def test_dot_thousands_with_comma_decimal(self):
        assert parse_tcmb_number("2.684,55") == pytest.approx(2684.55)


class TestEdges:
    def test_plain_integer(self):
        assert parse_tcmb_number("100") == pytest.approx(100.0)

    def test_empty_returns_none(self):
        assert parse_tcmb_number("") is None

    def test_none_returns_none(self):
        assert parse_tcmb_number(None) is None

    def test_garbage_raises_rather_than_defaulting_to_zero(self):
        """A silent 0.0 here reads as 'inflation was zero'."""
        with pytest.raises(ValueError):
            parse_tcmb_number("not a number")


async def test_tr_calculation_is_not_inflated_by_100x():
    """End-to-end: 2020-01 -> 2024-12 is roughly +500%, not +50,000%."""
    from providers.market_router import MarketRouter

    router = MarketRouter()
    out = await router.get_macro_data(
        data_type="calculate",
        start_year=2020, start_month=1,
        end_year=2024, end_month=12,
        basket_value=100.0,
    )
    calc = out["calculation"]

    # TÜFE went 446.45 -> 2684.55, a ratio of ~6.01
    assert calc["start_index"] == pytest.approx(446.45, abs=0.1)
    assert calc["end_index"] == pytest.approx(2684.55, abs=0.1)
    assert calc["final_value"] == pytest.approx(601.31, abs=1.0)
    assert 400 < calc["cumulative_inflation"] < 700
    assert 30 < calc["annualized_compound_change"] < 60

    # The exact shape of the old bug.
    assert calc["final_value"] < 1000, "value looks inflated by ~100x again"
