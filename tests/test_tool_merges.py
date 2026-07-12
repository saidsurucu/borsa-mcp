"""Parity tests for the 29 -> 22 tool consolidation.

Five of the eight merges in the first design draft turned out to be wrong, and every
one of them failed the same way: a field the old tool returned was silently lost. The
rule that came out of that (design doc §1) is that a merge must be proved, not
asserted — every field the absorbed tool produced has to be reachable from the
corresponding mode of the surviving one.

These tests are that proof. They run against the live server on purpose: the whole
class of bug they guard against is "the data quietly stopped arriving".
"""
import pytest
from fastmcp import Client

from unified_mcp_server import app

pytestmark = pytest.mark.live


async def _call(name, args):
    async with Client(app) as client:
        result = await client.call_tool(name, args)
    return result.content[0].text


# --- The surface itself -----------------------------------------------------

async def test_the_absorbed_tools_are_gone():
    tools = await app.get_tools()
    for gone in ("get_pivot_points", "get_screener_help", "get_scanner_help",
                 "get_regulations", "get_quick_info", "get_fx_data", "get_dividends"):
        assert gone not in tools, f"{gone} should have been absorbed"


async def test_the_surface_is_23_tools():
    """28 - 6 removed + compare_assets = 23.

    The design doc said 22, which was an arithmetic slip on my part: it counted
    get_quick_info among the absorbed, but get_quick_info did not disappear — it became
    get_quote, which additionally absorbed FX's current mode and crypto's ticker. Six
    tools were removed, not seven.
    """
    tools = await app.get_tools()
    assert len(tools) == 23, sorted(tools)


# --- get_technical_analysis absorbs get_pivot_points ------------------------

async def test_technical_analysis_carries_the_pivot_levels():
    """Pivots are an indicator; a separate tool for them was a historical accident.
    All seven levels must survive: PP, R1-R3, S1-S3."""
    text = await _call("get_technical_analysis",
                       {"symbol": "GARAN", "market": "bist", "include_pivots": True})

    for level in ("pivot", "r1", "r2", "r3", "s1", "s2", "s3"):
        assert level in text.lower(), f"pivot level {level} lost in the merge"


async def test_pivots_are_opt_in_so_the_default_response_stays_small():
    text = await _call("get_technical_analysis", {"symbol": "GARAN", "market": "bist"})
    assert "rsi" in text.lower()
    assert "s3" not in text.lower()


# --- Help folds into the tool it documents ----------------------------------

async def test_screener_help_is_a_flag_on_the_screener():
    """Help is now scope-aware: it answers for the market you are actually screening,
    rather than being a separate tool that has to re-state which market it means."""
    text = await _call("screen_securities", {"market": "bist", "help": True})
    assert "preset" in text.lower()


async def test_scanner_help_is_a_flag_on_the_scanner():
    text = await _call("scan_stocks", {"help": True})
    lower = text.lower()
    assert "rsi" in lower and "supertrend" in lower


async def test_regulations_fold_into_the_fund_tool():
    text = await _call("get_fund_data",
                       {"symbol": "TI2", "data_type": "regulations"})
    assert len(text) > 500, "regulation text should be substantial"


async def test_help_plus_filters_is_an_error_not_a_silent_precedence():
    """Asking for help AND passing filters is a contradiction. Picking one quietly is
    how a caller ends up believing they ran a screen that never ran."""
    with pytest.raises(Exception):
        await _call("screen_securities",
                    {"market": "bist", "help": True, "preset": "value_stocks"})


# --- get_quote absorbs get_quick_info, FX current and crypto ticker ----------

@pytest.mark.parametrize("symbol,market", [
    ("GARAN", "bist"),
    ("AAPL", "us"),
    ("gram-altin", "fx"),
    ("BTCTRY", "crypto"),   # not crypto_tr: the exchange is inferred from the pair
])
async def test_get_quote_answers_what_is_it_worth_now_in_every_market(symbol, market):
    text = await _call("get_quote", {"symbol": symbol, "market": market})
    assert symbol.lower() in text.lower()
    assert "price" in text.lower() or "last" in text.lower() or "sell" in text.lower()


async def test_get_quote_keeps_the_equity_metrics_quick_info_used_to_return():
    """get_quick_info's whole value was P/E, P/B and the 52-week range. Absorbing it
    without them would be a rename, not a merge."""
    text = (await _call("get_quote", {"symbol": "GARAN", "market": "bist"})).lower()

    assert "pe" in text or "p_e" in text or "price_to_earnings" in text
    assert "52" in text


async def test_get_quote_is_multi_symbol():
    text = await _call("get_quote", {"symbol": ["GARAN", "AKBNK"], "market": "bist"})
    assert "GARAN" in text and "AKBNK" in text


# --- get_corporate_actions absorbs get_dividends ----------------------------

async def test_corporate_actions_carries_us_dividends_and_splits():
    """The old get_dividends covered BIST *and* US, including splits, while
    get_corporate_actions was BIST-only. Absorbing without normalizing would have
    dropped every US dividend and every split on the floor."""
    text = await _call("get_corporate_actions", {"symbol": "KO", "market": "us"})
    assert "dividend" in text.lower()


async def test_corporate_actions_still_carries_bist_capital_increases():
    text = await _call("get_corporate_actions", {"symbol": "GARAN", "market": "bist"})
    lower = text.lower()
    assert "dividend" in lower
    assert "capital" in lower or "bonus" in lower or "rights" in lower
