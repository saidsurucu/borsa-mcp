"""Validation behavior tests for unified tools and EVDS routing."""
import pytest
from fastmcp.exceptions import ToolError

from providers.market_router import market_router
from unified_mcp_server import (
    fund_flags_warning,
    timeframe_warning,
    validate_evds_params,
    validate_screen_params,
)


async def test_evds_datagroups_requires_category_id():
    with pytest.raises(ValueError, match="category_id"):
        await market_router.get_evds_data(action="datagroups")


async def test_evds_series_requires_series_code():
    with pytest.raises(ValueError, match="series_code"):
        await market_router.get_evds_data(action="series")


async def test_evds_unknown_action_raises():
    with pytest.raises(ValueError, match="Unknown EVDS action"):
        await market_router.get_evds_data(action="bogus")


# ---------------------------------------------------------------------------
# Up-front parameter validation (tool-level) — Task 10
# ---------------------------------------------------------------------------

def test_evds_validation_lists_required_params():
    with pytest.raises(ToolError, match="series_code"):
        validate_evds_params("series", {"series_code": None})
    # valid combos pass silently
    validate_evds_params("series", {"series_code": "TP.DK.USD.A.YTL"})
    validate_evds_params("categories", {})


def test_evds_validation_multi_series():
    with pytest.raises(ToolError, match="series_codes"):
        validate_evds_params("multi_series", {"series_codes": None})


def test_evds_validation_dashboard_needs_name_or_id():
    with pytest.raises(ToolError, match="dashboard"):
        validate_evds_params("dashboard", {})
    validate_evds_params("dashboard", {"dashboard_name": "baslica-gostergeler"})


def test_screen_rejects_preset_plus_custom_filters():
    with pytest.raises(ToolError, match="one of"):
        validate_screen_params(preset="value_stocks", custom_filters=[["eq", ["sector", "Technology"]]])
    validate_screen_params(preset="value_stocks", custom_filters=None)
    validate_screen_params(preset=None, custom_filters=[["eq", ["sector", "Technology"]]])


def test_fund_flags_warning_multi_fund():
    w = fund_flags_warning(is_multi=True, include_portfolio=True, include_performance=False)
    assert w is not None and "single-fund" in w
    assert fund_flags_warning(is_multi=False, include_portfolio=True, include_performance=True) is None
    assert fund_flags_warning(is_multi=True, include_portfolio=False, include_performance=False) is None


def test_timeframe_warning_for_stock_markets():
    w = timeframe_warning(market="bist", timeframe="1h")
    assert w is not None and "daily" in w.lower()
    assert timeframe_warning(market="bist", timeframe="1d") is None
    assert timeframe_warning(market="crypto_tr", timeframe="1h") is None
