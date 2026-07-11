"""Purchasing-power maths on a monthly index.

The rules that keep a confident wrong number from reaching the caller:
endpoints must be present exactly (no snapping to a neighbouring month), the
interval may not contain a gap, and the annualized figure is withheld below 12
months because annualizing a non-seasonally-adjusted index annualizes
seasonality along with inflation.
"""

import pytest

from providers.fred_cpi_provider import FredCpiProvider, IndexSeries


@pytest.fixture
def provider_with(monkeypatch):
    def _make(values, degraded=False):
        p = FredCpiProvider()

        async def fake_get_index_series(region, today=None):
            return IndexSeries(
                region=region,
                source="Fallback" if degraded else "FRED (test)",
                values=values,
                degraded=degraded,
            )

        monkeypatch.setattr(p, "get_index_series", fake_get_index_series)
        return p

    return _make


# 1% per month, compounding, Jan 2020 through Jan 2021.
FLAT = {f"2020-{m:02d}": 100.0 * (1.01 ** (m - 1)) for m in range(1, 13)}
FLAT["2021-01"] = 100.0 * (1.01 ** 12)


async def test_calculate_uses_the_index_ratio(provider_with):
    values = {"2010-01": 200.0, **FLAT, "2020-01": 300.0}
    p = provider_with(values)
    # Fill the interval so the gap check passes.
    for y in range(2010, 2021):
        for m in range(1, 13):
            values.setdefault(f"{y}-{m:02d}", 250.0)
    values["2010-01"] = 200.0
    values["2020-01"] = 300.0

    out = await p.calculate_inflation("us", 2010, 1, 2020, 1, basket_value=100.0)
    calc = out["calculation"]

    assert calc["final_value"] == pytest.approx(150.0)
    assert calc["cumulative_inflation"] == pytest.approx(50.0)
    assert calc["start_index"] == 200.0
    assert calc["end_index"] == 300.0
    assert calc["period_months"] == 120


async def test_annualized_change_emitted_for_a_full_year(provider_with):
    p = provider_with(dict(FLAT))
    out = await p.calculate_inflation("us", 2020, 1, 2021, 1, basket_value=100.0)
    calc = out["calculation"]

    assert calc["period_months"] == 12
    # 1% compounded monthly for 12 months ~= 12.68% annualized
    assert calc["annualized_compound_change"] == pytest.approx(12.68, abs=0.01)


async def test_annualized_change_suppressed_below_twelve_months(provider_with):
    """Annualizing an NSA index over 3 months annualizes seasonality too."""
    p = provider_with(dict(FLAT))
    out = await p.calculate_inflation("us", 2020, 1, 2020, 4, basket_value=100.0)

    assert out["calculation"]["annualized_compound_change"] is None
    assert any("12 months" in w for w in out["warnings"])


async def test_seasonality_warning_when_calendar_months_differ(provider_with):
    values = dict(FLAT)
    for m in range(2, 13):
        values[f"2021-{m:02d}"] = 115.0
    for m in range(1, 7):
        values[f"2022-{m:02d}"] = 130.0
    p = provider_with(values)

    out = await p.calculate_inflation("us", 2020, 1, 2022, 6, basket_value=100.0)
    assert any("seasonal" in w.lower() for w in out["warnings"])


async def test_missing_endpoint_raises_instead_of_snapping_to_a_neighbour(provider_with):
    p = provider_with(dict(FLAT))
    with pytest.raises(ValueError, match="not available"):
        await p.calculate_inflation("us", 1975, 3, 2020, 12, basket_value=100.0)


async def test_gap_inside_the_interval_warns_but_still_computes(provider_with):
    """The ratio never touches the interior, so a hole there cannot corrupt it.

    And the holes are real: BLS never published the October 2025 CPI (the US
    government shutdown), so it is permanently absent from the official series.
    Raising would block every legitimate 2010 -> today query over data the
    calculation does not use.
    """
    values = {"2020-01": 100.0, "2020-02": 101.0, "2021-01": 110.0}  # Mar-Dec missing
    p = provider_with(values)

    out = await p.calculate_inflation("us", 2020, 1, 2021, 1, basket_value=100.0)

    assert out["calculation"]["final_value"] == pytest.approx(110.0)
    assert any("no observation" in w.lower() for w in out["warnings"])
    assert any("2020-03" in w for w in out["warnings"])


async def test_inverted_range_raises(provider_with):
    p = provider_with(dict(FLAT))
    with pytest.raises(ValueError, match="before"):
        await p.calculate_inflation("us", 2021, 1, 2020, 1, basket_value=100.0)


async def test_nonpositive_basket_raises(provider_with):
    p = provider_with(dict(FLAT))
    with pytest.raises(ValueError, match="greater than 0"):
        await p.calculate_inflation("us", 2020, 1, 2021, 1, basket_value=0.0)


async def test_monthly_average_semantics_are_stated(provider_with):
    p = provider_with(dict(FLAT))
    out = await p.calculate_inflation("us", 2020, 1, 2021, 1, basket_value=100.0)
    assert any("monthly average" in w.lower() for w in out["warnings"])


async def test_inflation_data_reports_yoy_as_rate_and_mom_as_change(provider_with):
    values = {f"2020-{m:02d}": 100.0 for m in range(1, 12)}
    values["2020-12"] = 110.0
    values["2021-12"] = 121.0
    for m in range(1, 12):
        values[f"2021-{m:02d}"] = 110.0
    p = provider_with(values)

    out = await p.get_inflation_data("us")
    by_month = {d["date"]: d for d in out["inflation_data"]}

    assert by_month["2021-12"]["rate"] == pytest.approx(10.0)    # YoY vs 2020-12
    assert by_month["2020-12"]["change"] == pytest.approx(10.0)  # MoM vs 2020-11


async def test_inflation_data_respects_limit(provider_with):
    p = provider_with(dict(FLAT))
    out = await p.get_inflation_data("us", limit=3)
    assert len(out["inflation_data"]) == 3
    assert out["inflation_data"][-1]["date"] == "2021-01"


async def test_live_golden_values():
    """The whole point of the feature, checked against the real series.

    If the euro figure comes back as ~144.91 instead of ~145.01, the wrong (EA19,
    frozen-geography) series has been wired up.
    """
    p = FredCpiProvider()

    us = await p.get_index_series("us")
    out = await p.calculate_inflation(
        "us", 2010, 1, int(us.last_month[:4]), int(us.last_month[5:7]), 100.0
    )
    assert out["calculation"]["final_value"] == pytest.approx(154.66, abs=1.0)

    # BLS never published the October 2025 CPI (US government shutdown), so any
    # interval spanning it must still compute -- and say so.
    assert any("2025-10" in w for w in out["warnings"])

    eu = await p.get_index_series("eu")
    out = await p.calculate_inflation(
        "eu", 2010, 1, int(eu.last_month[:4]), int(eu.last_month[5:7]), 100.0
    )
    assert out["calculation"]["final_value"] == pytest.approx(145.01, abs=1.0)
    assert out["currency"] == "EUR"


async def test_degraded_source_is_reported(provider_with):
    values = dict(FLAT)
    p = provider_with(values, degraded=True)
    out = await p.calculate_inflation("us", 2020, 1, 2021, 1, basket_value=100.0)

    assert any(
        "fallback" in w.lower() or "degraded" in w.lower() for w in out["warnings"]
    )
    assert out["source"] == "Fallback"
