"""compare_assets: put a stock, a metal, a currency and a fund in one honest table.

The arithmetic here is the whole point. Getting it wrong produces a number that looks
entirely reasonable — which is why every rule below is pinned by a test.
"""
import pytest

from providers.canonical_series import Bar, CanonicalSeries, SeriesMeta
from providers.compare import compute_comparison, AssetWindow


def _series(symbol, market, currency, rows, basis="last", adjustment="split"):
    return CanonicalSeries(
        meta=SeriesMeta(symbol=symbol, market=market, currency=currency,
                        price_basis=basis, adjustment=adjustment, source="test"),
        bars=[Bar(date=d, close=c) for d, c in rows],
    )


# A flat 10-day window. USDTRY doubles: 40 -> 80.
FX_ROWS = [("2026-01-02", 40.0), ("2026-07-10", 80.0)]


def _usdtry():
    return _series("USD", "fx", "TRY", FX_ROWS, basis="ask", adjustment="n/a")


def test_a_try_asset_that_doubles_in_lira_is_flat_in_dollars():
    # ASELS 100 -> 200 TRY while the dollar also doubles: +100% TRY, 0% USD.
    asels = _series("ASELS", "bist", "TRY",
                    [("2026-01-02", 100.0), ("2026-07-10", 200.0)])

    rows = compute_comparison(
        [AssetWindow(asels)], _usdtry(),
        start_date="2026-01-02", end_date="2026-07-10",
    )

    r = rows[0]
    assert r["return_try"] == pytest.approx(1.0)
    assert r["return_usd"] == pytest.approx(0.0, abs=1e-9)


def test_holding_dollars_returns_exactly_zero_in_dollars():
    """The output's own sanity check: list USD as an asset and its USD return must be
    0 by definition. If it is not, the currency maths is wrong somewhere."""
    rows = compute_comparison(
        [AssetWindow(_usdtry())], _usdtry(),
        start_date="2026-01-02", end_date="2026-07-10",
    )

    r = rows[0]
    assert r["return_try"] == pytest.approx(1.0)      # the lira halved
    assert r["return_usd"] == pytest.approx(0.0, abs=1e-12)


def test_a_natively_usd_asset_is_not_divided_by_usdtry():
    """BTC-USD is quoted in dollars already. Dividing a USD price by USDTRY would
    report a 50% loss on an asset that did not move."""
    btc = _series("BTC-USD", "crypto_global", "USD",
                  [("2026-01-02", 60000.0), ("2026-07-10", 60000.0)],
                  adjustment="n/a")

    rows = compute_comparison(
        [AssetWindow(btc)], _usdtry(),
        start_date="2026-01-02", end_date="2026-07-10",
    )

    r = rows[0]
    assert r["return_usd"] == pytest.approx(0.0, abs=1e-9), "flat in USD"
    assert r["return_try"] == pytest.approx(1.0), "the lira halved, so +100% in TRY"


def test_the_start_endpoint_is_the_first_bar_on_or_after_the_request():
    # 2026-07-04 is a Saturday; an investor buys at Monday's session.
    s = _series("X", "bist", "TRY",
                [("2026-07-03", 100.0), ("2026-07-06", 110.0), ("2026-07-10", 120.0)])
    fx = _series("USD", "fx", "TRY",
                 [("2026-07-03", 40.0), ("2026-07-06", 40.0), ("2026-07-10", 40.0)],
                 basis="ask", adjustment="n/a")

    rows = compute_comparison([AssetWindow(s)], fx,
                              start_date="2026-07-04", end_date="2026-07-10")

    r = rows[0]
    assert r["start_date"] == "2026-07-06", "must not buy at Friday's passed close"
    assert r["end_date"] == "2026-07-10"
    assert r["return_try"] == pytest.approx(120.0 / 110.0 - 1)


def test_fx_is_aligned_to_each_asset_s_own_endpoint_dates():
    """The conversion rate must be read on the day the asset actually traded, not on
    the day that was requested. A fund's endpoints sit a day earlier than a stock's."""
    stock = _series("X", "bist", "TRY",
                    [("2026-07-06", 100.0), ("2026-07-10", 100.0)])
    fund = _series("F", "fund", "TRY",
                   [("2026-07-06", 100.0), ("2026-07-09", 100.0)])
    fx = _series("USD", "fx", "TRY",
                 [("2026-07-06", 40.0), ("2026-07-09", 50.0), ("2026-07-10", 80.0)],
                 basis="ask", adjustment="n/a")

    rows = compute_comparison([AssetWindow(stock), AssetWindow(fund)], fx,
                              start_date="2026-07-06", end_date="2026-07-10")

    by = {r["asset"]: r for r in rows}
    # Both are flat in lira, but they exit on different days, so their USD returns differ.
    assert by["X"]["return_usd"] == pytest.approx(40.0 / 80.0 - 1)   # exits at 80
    assert by["F"]["return_usd"] == pytest.approx(40.0 / 50.0 - 1)   # exits at 50
    assert by["F"]["end_date"] == "2026-07-09"


def test_initial_amount_produces_end_values_in_both_currencies():
    asels = _series("ASELS", "bist", "TRY",
                    [("2026-01-02", 100.0), ("2026-07-10", 200.0)])

    rows = compute_comparison([AssetWindow(asels)], _usdtry(),
                              start_date="2026-01-02", end_date="2026-07-10",
                              initial_amount=100_000.0)

    r = rows[0]
    assert r["end_value_try"] == pytest.approx(200_000.0)
    # 100,000 TRY at 40 = 2,500 USD; flat in dollars, so 2,500 USD at the end.
    assert r["end_value_usd"] == pytest.approx(2_500.0)


def test_rows_are_sorted_by_the_base_currency_return():
    a = _series("A", "bist", "TRY", [("2026-01-02", 100.0), ("2026-07-10", 110.0)])
    b = _series("B", "bist", "TRY", [("2026-01-02", 100.0), ("2026-07-10", 300.0)])

    rows = compute_comparison([AssetWindow(a), AssetWindow(b)], _usdtry(),
                              start_date="2026-01-02", end_date="2026-07-10")

    assert [r["asset"] for r in rows] == ["B", "A"]


def test_each_row_declares_its_price_basis():
    gold = _series("gram-altin", "fx", "TRY",
                   [("2026-01-02", 6000.0), ("2026-07-10", 6200.0)],
                   basis="ask", adjustment="n/a")

    rows = compute_comparison([AssetWindow(gold)], _usdtry(),
                              start_date="2026-01-02", end_date="2026-07-10")

    assert rows[0]["price_basis"] == "ask"
    assert rows[0]["currency"] == "TRY"


def test_a_fund_carries_its_total_return_asymmetry_as_a_warning():
    fund = _series("TI2", "fund", "TRY",
                   [("2026-01-02", 1.0), ("2026-07-10", 1.2)], basis="nav",
                   adjustment="n/a")
    fund.meta.warnings.append("Fund NAV accrues its holdings' dividends, so a fund is "
                              "a total return while the stocks beside it are a price return.")

    rows = compute_comparison([AssetWindow(fund)], _usdtry(),
                              start_date="2026-01-02", end_date="2026-07-10")

    assert any("total return" in w.lower() for w in rows[0]["warnings"])
