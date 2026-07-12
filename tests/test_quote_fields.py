"""get_quote must actually carry a quote.

The bug this file exists for: `get_quick_info` (now `get_quote`) read yfinance's
FastInfo with `fast_info.get('last_price')`. FastInfo's *mapping* keys are camelCase
(`lastPrice`, `marketCap`, `yearHigh`) while its *attributes* are snake_case — so
`.get('last_price')` returned None for every price field, and the code's
`fast_info.get(x) if fast_info else info.get(y)` was an either/or, never a fallback:
fast_info was truthy, so `info` was never consulted.

Every price, the market cap and the 52-week range came back None. `strip_nulls` then
removed them, so the response did not look broken — it looked clean. A "quick info"
tool that does not tell you the price.
"""
import pytest
from fastmcp import Client

from unified_mcp_server import app

pytestmark = pytest.mark.live


async def _quote(symbol, market):
    async with Client(app) as client:
        result = await client.call_tool("get_quote", {"symbol": symbol, "market": market})
    return result.content[0].text


@pytest.mark.parametrize("symbol,market", [("GARAN", "bist"), ("AAPL", "us")])
async def test_a_quote_carries_the_price(symbol, market):
    text = await _quote(symbol, market)
    assert "current_price" in text, f"{market} quote has no price at all:\n{text}"


@pytest.mark.parametrize("symbol,market", [("GARAN", "bist"), ("AAPL", "us")])
async def test_a_quote_carries_the_52_week_range(symbol, market):
    """The tool's own description promised the 52-week range. US never returned it."""
    text = await _quote(symbol, market)
    assert "week_52_high" in text and "week_52_low" in text, (
        f"{market} quote is missing the 52-week range:\n{text}"
    )


@pytest.mark.parametrize("symbol,market", [("GARAN", "bist"), ("AAPL", "us")])
async def test_a_quote_carries_the_market_cap(symbol, market):
    text = await _quote(symbol, market)
    assert "market_cap" in text, f"{market} quote is missing the market cap:\n{text}"


async def test_the_two_markets_return_the_same_field_set():
    """BIST returned a price and US did not, from what is nominally one code path.
    A field present in one market and silently absent in the other is the shape of
    every bug in this session."""
    bist = {line.split(":")[0] for line in (await _quote("GARAN", "bist")).splitlines()
            if ":" in line and not line.startswith("#")}
    us = {line.split(":")[0] for line in (await _quote("AAPL", "us")).splitlines()
          if ":" in line and not line.startswith("#")}

    core = {"symbol", "name", "currency", "current_price", "market_cap",
            "week_52_high", "week_52_low", "pe_ratio", "pb_ratio"}
    assert core <= bist, f"BIST is missing {core - bist}"
    assert core <= us, f"US is missing {core - us}"
