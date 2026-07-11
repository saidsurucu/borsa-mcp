"""get_macro_data routes by region, without breaking the callers it already has."""

import inspect

import pytest

from providers.market_router import MarketRouter


def test_region_is_keyword_only():
    """A positional `region` would silently reinterpret an existing
    get_macro_data("inflation", "ufe") call as region="ufe"."""
    sig = inspect.signature(MarketRouter.get_macro_data)
    assert sig.parameters["region"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["region"].default == "tr"


async def test_us_calculate_returns_currency_and_provenance():
    router = MarketRouter()
    out = await router.get_macro_data(
        data_type="calculate", region="us",
        start_year=2010, start_month=1, end_year=2020, end_month=1,
        basket_value=100.0,
    )

    assert out["region"] == "us"
    assert out["currency"] == "USD"
    assert "FRED" in out["source"]
    assert out["series_end"] >= "2026-01"
    assert out["calculation"]["cumulative_inflation"] > 15


async def test_eu_inflation_series_is_served():
    router = MarketRouter()
    out = await router.get_macro_data(
        data_type="inflation", region="eu", limit=12,
    )

    assert out["currency"] == "EUR"
    assert len(out["inflation_data"]) == 12
    assert out["inflation_data"][-1]["rate"] is not None


async def test_inflation_type_is_rejected_for_us_not_silently_ignored():
    """US/EU publish only a headline index. A caller who asked for PPI should
    learn they did not get it, rather than receive CPI plus a warning they had no
    way to avoid."""
    router = MarketRouter()
    with pytest.raises(ValueError, match="inflation_type"):
        await router.get_macro_data(
            data_type="inflation", region="us", inflation_type="ufe",
        )


async def test_year_before_the_series_start_raises_for_eu():
    router = MarketRouter()
    with pytest.raises(ValueError, match="1996"):
        await router.get_macro_data(
            data_type="calculate", region="eu",
            start_year=1980, start_month=1, end_year=2020, end_month=1,
            basket_value=100.0,
        )


async def test_unknown_region_raises():
    router = MarketRouter()
    with pytest.raises(ValueError, match="region"):
        await router.get_macro_data(data_type="inflation", region="jp")


async def test_tr_remains_the_default_and_keeps_its_shape():
    router = MarketRouter()
    out = await router.get_macro_data(
        data_type="calculate",
        start_year=2020, start_month=1, end_year=2024, end_month=12,
        basket_value=100.0,
    )

    assert out["data_type"] == "calculate"
    assert out["region"] == "tr"
    assert out["currency"] == "TRY"
    assert out["calculation"]["final_value"] == pytest.approx(601.31, abs=1.0)


async def test_tr_inflation_still_defaults_to_tufe():
    router = MarketRouter()
    out = await router.get_macro_data(data_type="inflation", limit=3)

    assert out["inflation_type"] == "tufe"
    assert len(out["inflation_data"]) == 3
