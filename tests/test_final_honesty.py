"""The last three places where the server misdescribes itself.

Same family as everything else this session: a field, a document or a schema making a
claim that the data does not support.

1. The FX quote calls its value `sell`. It is not an ask — borsapy's `get_current` just
   returns the last row of a 5-day history, so it is a LAST CLOSE, and it can be two
   days old. Both halves of the label are wrong.
2. `get_fund_data` throws away the order cutoff time and the settlement valor, which the
   provider already fetched. They answer "when can I actually buy this, and when does my
   money move" — precisely the question the D-1 NAV lag raises.
3. The docs still describe a 28-tool surface that has been 23 since the consolidation. An
   LLM reading CLAUDE.md would call get_pivot_points, which no longer exists.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from providers.market_router import MarketRouter


def _router(**methods):
    router = MarketRouter()
    client = MagicMock()
    for name, side in methods.items():
        setattr(client, name, AsyncMock(side_effect=side))
    router._client = client
    return router


# --- 1. The FX quote is a last close, not an ask -----------------------------

def test_the_fx_quote_is_called_last_not_sell():
    from datetime import datetime

    async def current(sym):
        return SimpleNamespace(
            guncel_deger=6225.546, varlik_adi=sym, degisim=0.1, degisim_yuzde=0.2,
            son_guncelleme=datetime(2026, 7, 11, 3, 0),
        )

    router = _router(get_dovizcom_guncel_kur=current)
    res = asyncio.run(router.get_fx_data(symbols=["gram-altin"]))
    row = res["rates"][0]

    assert "sell" not in row, (
        "borsapy's get_current returns the last row of a 5-day history — a close, not "
        "an ask. There are no buy/sell keys in the source at all."
    )
    assert row["last"] == pytest.approx(6225.546)
    assert row["as_of"] == "2026-07-11"


def test_a_stale_fx_quote_says_so():
    """The quote can be two days old. Presenting it as the current price without saying
    when it was struck invites the caller to treat it as live."""
    from datetime import datetime, timedelta

    async def current(sym):
        return SimpleNamespace(
            guncel_deger=47.04, varlik_adi=sym, degisim=None, degisim_yuzde=None,
            son_guncelleme=datetime.now() - timedelta(days=3),
        )

    router = _router(get_dovizcom_guncel_kur=current)
    res = asyncio.run(router.get_fx_data(symbols=["USD"]))

    assert any("stale" in w.lower() or "old" in w.lower()
               for w in res.get("warnings", [])), (
        f"a 3-day-old quote must be flagged; warnings were {res.get('warnings')}"
    )


def test_a_fresh_fx_quote_is_not_flagged():
    from datetime import datetime

    async def current(sym):
        return SimpleNamespace(
            guncel_deger=47.04, varlik_adi=sym, degisim=None, degisim_yuzde=None,
            son_guncelleme=datetime.now(),
        )

    router = _router(get_dovizcom_guncel_kur=current)
    res = asyncio.run(router.get_fx_data(symbols=["USD"]))
    assert not res.get("warnings")


# --- 2. The fund's tradability fields ----------------------------------------

@pytest.mark.live
async def test_fund_data_carries_the_cutoff_and_valor():
    """TEFAS already tells us the order cutoff and the settlement valor; get_fund_data
    fetched them and dropped them. With a NAV that is already a trading day behind, they
    are the difference between a price and an executable price."""
    from fastmcp import Client
    from unified_mcp_server import app

    async with Client(app) as client:
        result = await client.call_tool("get_fund_data", {"symbol": "TI2"})

    text = result.content[0].text
    assert "cutoff" in text.lower() or "trading_time" in text.lower(), (
        f"no order cutoff in the fund payload:\n{text[:600]}"
    )
    assert "valor" in text.lower(), f"no settlement valor in the fund payload:\n{text[:600]}"


# --- 3. The docs must describe the surface that exists -----------------------

REMOVED = ("get_pivot_points", "get_quick_info", "get_fx_data", "get_dividends",
           "get_screener_help", "get_scanner_help", "get_regulations")


def test_claude_md_does_not_present_removed_tools_as_available():
    """Naming a removed tool is fine — necessary, even — where the doc says it is gone
    and where it went. What must not survive is a TOOL-TABLE ROW, `| `get_x` | does y |`,
    which reads as "this is a tool you can call"."""
    from pathlib import Path

    doc = Path("CLAUDE.md").read_text()
    _, _, migration = doc.partition("### Where the old tools went")
    assert migration, "CLAUDE.md must tell a reader where the removed tools went"

    # A tool-table row starts the line with the tool name in backticks.
    offered = {
        gone for gone in REMOVED
        for line in doc.splitlines()
        if line.strip().startswith(f"| `{gone}`")
        # ...unless it is the migration table, whose rows point AT the replacement.
        and "`get_technical_analysis" not in line
        and "`get_quote`" not in line
        and "`get_corporate_actions`" not in line
        and "`screen_securities(" not in line
        and "`scan_stocks(" not in line
        and "`get_fund_data(" not in line
    }
    assert not offered, (
        f"CLAUDE.md still offers {sorted(offered)} as callable tools. An LLM reading it "
        "would call a tool that no longer exists."
    )

    for gone in REMOVED:
        assert f"`{gone}`" in migration, f"{gone} has no migration row"


def test_claude_md_states_the_real_tool_count():
    from pathlib import Path

    doc = Path("CLAUDE.md").read_text()
    assert "28 unified tools" not in doc
    assert "23" in doc


def test_the_package_version_is_not_still_0_8_0():
    from pathlib import Path

    pyproject = Path("pyproject.toml").read_text()
    assert 'version = "0.8.0"' not in pyproject, (
        "the tool surface changed incompatibly; the version must say so"
    )
