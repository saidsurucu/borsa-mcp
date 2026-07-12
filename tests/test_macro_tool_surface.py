"""get_macro_data end-to-end, through the MCP tool boundary."""

import pytest
from fastmcp import Client

from unified_mcp_server import app


async def test_us_calculation_renders_with_currency_and_source():
    async with Client(app) as client:
        result = await client.call_tool("get_macro_data", {
            "data_type": "calculate",
            "region": "us",
            "start_year": 2010, "start_month": 1,
            "end_year": 2020, "end_month": 1,
            "basket_value": 100.0,
        })

    text = result.content[0].text
    assert "USD" in text
    assert "FRED" in text
    assert "cumulative_inflation" in text


async def test_eu_series_renders():
    async with Client(app) as client:
        result = await client.call_tool("get_macro_data", {
            "data_type": "inflation",
            "region": "eu",
            "limit": 6,
        })

    assert "EUR" in result.content[0].text


async def test_tr_default_still_works_without_region():
    async with Client(app) as client:
        result = await client.call_tool("get_macro_data", {
            "data_type": "calculate",
            "start_year": 2020, "start_month": 1,
            "end_year": 2024, "end_month": 12,
        })

    text = result.content[0].text
    assert "TRY" in text
    # The 100x bug rendered "final_value: 60131.0" here. The true figure is 601.31,
    # and the TÜFE index went 446.45 -> 2684.55.
    assert "final_value: 601.31" in text
    assert "start_index: 446.45" in text
    assert "end_index: 2684.55" in text


async def test_failed_tr_call_surfaces_an_error_not_zero_percent():
    """End-to-end guard: a failed call must not render as 0% inflation."""
    async with Client(app) as client:
        with pytest.raises(Exception) as exc:
            await client.call_tool("get_macro_data", {
                "data_type": "calculate",
                "start_year": 2024, "start_month": 6,
                "end_year": 2020, "end_month": 1,
            })

    assert "failed" in str(exc.value).lower()


async def test_tool_count_is_still_23():
    # 28 - 6 absorbed + compare_assets = 23.
    tools = await app.get_tools()
    assert len(tools) == 23
