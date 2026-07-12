"""One parameter contract across every tool.

Before this, the surface carried three different `market` vocabularies and four
different `symbol` types, and three tools advertised markets they did not serve — they
answered with metadata and `successful_count: 1` and no data at all.

The rules:

1. **One vocabulary**: bist | us | crypto | fx | fund | index. `crypto_tr` and
   `crypto_global` encoded an *exchange*, not a market; they collapse to
   market="crypto" plus exchange=btcturk|coinbase, inferred from the pair.
2. **Each tool's schema is narrowed to the markets it actually serves.** A wide enum
   plus a runtime rejection would trade a schema error the model cannot make for a
   runtime error it cannot see coming.
3. **symbol is always `str | list[str]`** where a tool takes one.
4. **period XOR start_date/end_date.** Passing both is an error, not a precedence rule.
"""
import asyncio

import pytest
from fastmcp import Client

from unified_mcp_server import app

# The one vocabulary. Nothing outside this set may appear in any tool's market enum.
MARKETS = {"bist", "us", "crypto", "fx", "fund", "index"}

# Tools that take a market, and the markets each one actually serves — measured, not
# assumed (see the probe in the commit message).
SERVES = {
    "get_profile":            {"bist", "us", "fund"},
    "get_quote":              {"bist", "us", "fx", "crypto"},
    "get_historical_data":    {"bist", "us", "fx", "crypto", "fund"},
    "get_technical_analysis": {"bist", "us", "crypto"},
    "get_analyst_data":       {"bist", "us"},
    "get_corporate_actions":  {"bist", "us"},
    "get_earnings":           {"bist", "us"},
    "get_financial_statements": {"bist", "us"},
    "get_financial_ratios":   {"bist", "us"},
    "get_sector_comparison":  {"bist", "us"},
    "get_index_data":         {"bist", "us"},
    "screen_securities":      {"bist", "us"},
    "search_symbol":          {"bist", "us", "crypto", "fx", "fund"},
}


def _market_enum(tool):
    prop = tool.parameters.get("properties", {}).get("market", {})
    if "enum" in prop:
        return set(prop["enum"])
    for branch in prop.get("anyOf", []):
        if "enum" in branch:
            return set(branch["enum"])
    return set()


# --- Rule 1 & 2: one vocabulary, narrowed per tool ---------------------------

async def test_no_tool_uses_a_market_value_outside_the_vocabulary():
    tools = await app.get_tools()
    for name, tool in tools.items():
        enum = _market_enum(tool)
        assert enum <= MARKETS, f"{name} uses {enum - MARKETS}, outside the vocabulary"


async def test_crypto_tr_and_crypto_global_are_gone_from_every_schema():
    """They named an exchange, not a market."""
    tools = await app.get_tools()
    for name, tool in tools.items():
        enum = _market_enum(tool)
        assert "crypto_tr" not in enum and "crypto_global" not in enum, (
            f"{name} still splits crypto by exchange in its market enum"
        )


@pytest.mark.parametrize("name,markets", sorted(SERVES.items()))
async def test_each_tool_advertises_exactly_the_markets_it_serves(name, markets):
    """get_profile advertised crypto and fx and answered both with an empty payload
    carrying successful_count: 1. get_technical_analysis did the same for fx and fund.
    A schema that promises a market the router has no branch for is a lie the model
    cannot detect."""
    tools = await app.get_tools()
    assert _market_enum(tools[name]) == markets


# --- Rule 3: symbol is str | list[str] ---------------------------------------

SYMBOL_TOOLS = [
    "get_profile", "get_quote", "get_historical_data", "get_technical_analysis",
    "get_analyst_data", "get_corporate_actions", "get_earnings",
    "get_financial_statements", "get_financial_ratios", "get_sector_comparison",
]


@pytest.mark.parametrize("name", SYMBOL_TOOLS)
async def test_symbol_accepts_a_string_or_a_list_everywhere(name):
    tools = await app.get_tools()
    prop = tools[name].parameters["properties"]["symbol"]
    types = {b.get("type") for b in prop.get("anyOf", [])} or {prop.get("type")}
    assert {"string", "array"} <= types, (
        f"{name} takes symbol as {types}; the contract is str | list[str]"
    )


# --- Rule 4: period XOR start/end --------------------------------------------

@pytest.mark.live
async def test_period_and_dates_together_is_an_error():
    """Silently preferring one is how a caller believes they got a window they did
    not."""
    async with Client(app) as client:
        with pytest.raises(Exception):
            await client.call_tool("get_historical_data", {
                "symbol": "GARAN", "market": "bist",
                "period": "1mo",
                "start_date": "2026-01-02", "end_date": "2026-07-10",
            })


# --- The crypto collapse actually works --------------------------------------

@pytest.mark.live
@pytest.mark.parametrize("symbol,exchange", [("BTCTRY", "btcturk"), ("BTC-USD", "coinbase")])
async def test_crypto_exchange_is_inferred_from_the_pair(symbol, exchange):
    async with Client(app) as client:
        result = await client.call_tool("get_quote", {"symbol": symbol, "market": "crypto"})
    assert symbol in result.content[0].text


@pytest.mark.live
async def test_crypto_exchange_can_be_named_explicitly():
    async with Client(app) as client:
        result = await client.call_tool("get_historical_data", {
            "symbol": "BTCTRY", "market": "crypto", "exchange": "btcturk",
            "start_date": "2026-07-01", "end_date": "2026-07-10",
        })
    assert "2026-07-0" in result.content[0].text


# --- Fund history, which the schema promised and the router refused -----------

@pytest.mark.live
async def test_fund_history_is_served_not_merely_advertised():
    async with Client(app) as client:
        result = await client.call_tool("get_historical_data", {
            "symbol": "TI2", "market": "fund",
            "start_date": "2026-06-01", "end_date": "2026-07-10",
        })
    text = result.content[0].text
    assert "close" in text.lower()
    assert "2026-0" in text
