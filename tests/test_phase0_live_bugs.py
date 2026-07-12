"""Phase 0: four live bugs found while auditing the tool-consolidation design.

Each of these ships a wrong answer today rather than an error, which is the
worst failure mode for an LLM-facing tool: a confident, plausible lie.

1. get_bond_yields(country="US") returns Turkish yields labelled US.
2. Crypto historical silently discards period/start_date/end_date.
3. downsample_ohlcv reads the wrong key and has never fired in production.
4. FX historical renders "rates: Sonuç bulunamadı." next to good data.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client

from providers.market_router import MarketRouter
from providers.markdown_renderer import render_markdown
from providers.response_shaper import downsample_ohlcv
from models.unified_base import MarketType
from unified_mcp_server import app


def _router_with_client(**async_methods):
    router = MarketRouter()
    client = MagicMock()
    for name, side in async_methods.items():
        setattr(client, name, AsyncMock(side_effect=side))
    router._client = client
    return router


# --- Bug 1: get_bond_yields(country="US") ------------------------------------
# The schema advertises TR|US and the description says "Country: TR or US", but
# the handler unconditionally calls the Turkish provider and merely echoes the
# country back. Only TR is actually served, so only TR may be offered.

async def test_bond_yields_does_not_advertise_an_unserved_country():
    tools = await app.get_tools()
    schema = tools["get_bond_yields"].parameters
    country = schema["properties"]["country"]
    allowed = country.get("enum") or country.get("const")
    assert allowed == ["TR"] or allowed == "TR", (
        f"get_bond_yields advertises {allowed!r} but only ever calls the Turkish "
        "provider; an unserved country must not appear in the schema"
    )


async def test_bond_yields_us_is_rejected_not_silently_turkish():
    async with Client(app) as client:
        with pytest.raises(Exception):
            await client.call_tool("get_bond_yields", {"country": "US"})


# --- Bug 2: crypto historical ignores the requested window -------------------
# market_router's CRYPTO_TR / CRYPTO_GLOBAL branches call the OHLC clients with
# the symbol only. Both clients accept a window (BtcTurk: unix from_time/to_time,
# Coinbase: ISO start/end), so the dates are dropped on the floor by the router.

def test_crypto_tr_historical_forwards_the_requested_window():
    seen = {}

    async def ohlc(pair, from_time=None, to_time=None):
        seen["from_time"] = from_time
        seen["to_time"] = to_time
        return SimpleNamespace(ohlc_data=[
            SimpleNamespace(time="2026-01-02", open=1.0, high=2.0,
                            low=0.5, close=1.5, volume=10)
        ])

    router = MarketRouter()
    client = MagicMock()
    client.get_kripto_ohlc = AsyncMock(side_effect=ohlc)
    router._client = client

    asyncio.run(router.get_historical_data(
        "BTCTRY", MarketType.CRYPTO_TR,
        start_date="2026-01-02", end_date="2026-07-10",
    ))

    assert seen["from_time"] is not None, "start_date was dropped by the router"
    assert seen["to_time"] is not None, "end_date was dropped by the router"


def test_historical_rows_are_clamped_to_the_requested_window():
    """Forwarding the window is not enough — the upstream may ignore it.

    BtcTurk's graph API is handed from/to and still returns a superset: asking for
    2026-07-01..2026-07-10 came back with 2026-06-30..2026-07-12. Per CLAUDE.md #5,
    assert on the shape of what comes back rather than trusting the upstream.
    """
    async def ohlc(pair, from_time=None, to_time=None):
        return SimpleNamespace(ohlc_data=[
            SimpleNamespace(time=d, open=1.0, high=2.0, low=0.5, close=1.5, volume=10)
            for d in ("2026-06-30", "2026-07-01", "2026-07-05",
                      "2026-07-10", "2026-07-12")
        ])

    router = MarketRouter()
    client = MagicMock()
    client.get_kripto_ohlc = AsyncMock(side_effect=ohlc)
    router._client = client

    res = asyncio.run(router.get_historical_data(
        "BTCTRY", MarketType.CRYPTO_TR,
        start_date="2026-07-01", end_date="2026-07-10",
    ))

    dates = [row["date"] for row in res["data"]]
    assert dates == ["2026-07-01", "2026-07-05", "2026-07-10"], (
        f"rows outside the requested window leaked through: {dates}"
    )


def test_crypto_global_historical_forwards_the_window_as_unix_seconds():
    """Coinbase's Advanced Trade API wants unix seconds, not ISO dates.

    Handing it "2026-01-02" earns an HTTP 400 (`INVALID_ARGUMENT: Invalid start
    timestamp`), which the provider swallowed into an empty candle list — so the
    tool answered "successfully" with no data. Only a live call surfaced this; the
    mocked test happily accepted an ISO string.
    """
    seen = {}

    async def ohlc(product_id, start=None, end=None, granularity="ONE_HOUR"):
        seen["start"] = start
        seen["end"] = end
        return SimpleNamespace(candles=[
            SimpleNamespace(start="2026-01-02", open=1.0, high=2.0,
                            low=0.5, close=1.5, volume=10)
        ])

    router = MarketRouter()
    client = MagicMock()
    client.get_coinbase_ohlc = AsyncMock(side_effect=ohlc)
    router._client = client

    asyncio.run(router.get_historical_data(
        "BTC-USD", MarketType.CRYPTO_GLOBAL,
        start_date="2026-01-02", end_date="2026-07-10",
    ))

    assert seen["start"] is not None, "start_date was dropped by the router"
    assert seen["end"] is not None, "end_date was dropped by the router"
    assert str(seen["start"]).isdigit(), (
        f"Coinbase needs unix seconds; got {seen['start']!r}, which earns an HTTP 400"
    )
    assert str(seen["end"]).isdigit()
    assert int(seen["start"]) < int(seen["end"])


def test_historical_with_no_rows_raises_instead_of_empty_success():
    """An empty-but-successful payload is a lie (CLAUDE.md #7).

    Coinbase's 400 became an empty candle list, which became a successful tool
    response carrying no data — telling the model "this asset has no history in
    that window" rather than "the fetch failed".
    """
    async def no_candles(product_id, start=None, end=None, granularity="ONE_HOUR"):
        return SimpleNamespace(candles=[])

    router = MarketRouter()
    client = MagicMock()
    client.get_coinbase_ohlc = AsyncMock(side_effect=no_candles)
    router._client = client

    with pytest.raises(Exception):
        asyncio.run(router.get_historical_data(
            "BTC-USD", MarketType.CRYPTO_GLOBAL,
            start_date="2026-07-01", end_date="2026-07-10",
        ))


# --- Bug 3: downsample_ohlcv reads a key that holds an int -------------------
# The router writes rows to "data" and len(rows) to "data_points". The shaper
# reads payload["data_points"], gets an int, fails isinstance(list) and returns
# immediately. It is wired into get_historical_data and has never once fired.
# The existing unit tests pass a list under "data_points" — a shape production
# never produces — which is why the bug survived.

def _rows(n):
    return [
        {"date": f"2026-01-{(i % 28) + 1:02d}", "open": 1.0, "high": 2.0,
         "low": 0.5, "close": 1.5, "volume": 100}
        for i in range(n)
    ]


def test_downsample_ohlcv_fires_on_the_real_router_payload_shape():
    rows = _rows(1200)
    payload = {"data": rows, "data_points": len(rows)}

    result = downsample_ohlcv(payload, max_points=300)

    assert len(result["data"]) <= 300, (
        "downsample read the wrong key: rows live under 'data', while "
        "'data_points' holds an int count"
    )
    assert result["data"][-1] == rows[-1], "most recent row must be exact"
    assert result["meta"]["truncated"] is True


def test_downsample_ohlcv_keeps_the_count_field_consistent():
    payload = {"data": _rows(1200), "data_points": 1200}

    result = downsample_ohlcv(payload, max_points=300)

    # Both halves matter: without the second assertion this passes trivially on
    # the unfixed code, where nothing is sampled and 1200 == 1200.
    assert len(result["data"]) <= 300
    assert result["data_points"] == len(result["data"]), (
        "data_points must stay the count of the rows actually returned"
    )


def test_downsample_ohlcv_leaves_a_short_series_alone():
    payload = {"data": _rows(100), "data_points": 100}
    result = downsample_ohlcv(payload, max_points=300)
    assert len(result["data"]) == 100
    assert result["data_points"] == 100
    assert "meta" not in result


# --- Bug 4: FX historical announces a failure next to good data --------------
# get_fx_data always returns both "rates" and "historical_data". In historical
# mode "rates" is [], and the renderer turns every empty list into
# "rates: Sonuç bulunamadı." — a failure message printed beside a populated
# historical series. Root cause is the payload, not the renderer: the router
# must return a mode-specific payload.

def _fx_history(symbol, start, end):
    return SimpleNamespace(ohlc_verileri=[
        SimpleNamespace(tarih=None, acilis=1.0, en_yuksek=2.0,
                        en_dusuk=0.5, kapanis=1.5)
    ])


def test_fx_historical_payload_omits_the_rates_key():
    router = _router_with_client(get_dovizcom_arsiv_veri=_fx_history)

    res = asyncio.run(router.get_fx_data(
        symbols=["gram-altin"], historical=True,
        start_date="2026-01-02", end_date="2026-07-10",
    ))

    assert "rates" not in res, (
        "historical mode must not carry an empty 'rates' list; the renderer "
        "reports it as 'Sonuç bulunamadı.' beside perfectly good data"
    )
    assert res["historical_data"]


def test_fx_current_payload_omits_the_historical_key():
    async def current(sym):
        return SimpleNamespace(guncel_deger=43.1, varlik_adi=sym, degisim=0.1,
                               degisim_yuzde=0.2, son_guncelleme=None)

    router = _router_with_client(get_dovizcom_guncel_kur=current)

    res = asyncio.run(router.get_fx_data(symbols=["USD"]))

    assert "historical_data" not in res
    assert res["rates"]


def test_fx_historical_with_no_data_raises_instead_of_empty_success():
    async def empty(symbol, start, end):
        return SimpleNamespace(ohlc_verileri=[])

    router = _router_with_client(get_dovizcom_arsiv_veri=empty)

    with pytest.raises(Exception):
        asyncio.run(router.get_fx_data(
            symbols=["gram-altin"], historical=True,
            start_date="2026-01-02", end_date="2026-07-10",
        ))


def test_fx_current_with_no_rates_raises_instead_of_empty_success():
    """The other half of the empty-but-successful bug.

    Phase 0 fixed the historical path. The current path had the same disease and it
    only surfaced once the renderer stopped printing "Sonuç bulunamadı." for an empty
    list: gram-platin and ons returned `successful_count: 1, failed_count: 0` and no
    data at all. borsapy's get_current asks canlidoviz for a 5-day window, those two
    items answer with an empty body, the provider swallows it into guncel_deger=None,
    and the router filtered the row away and shipped the husk.
    """
    async def no_quote(sym):
        return SimpleNamespace(guncel_deger=None, varlik_adi=sym, degisim=None,
                               degisim_yuzde=None, son_guncelleme=None)

    router = _router_with_client(get_dovizcom_guncel_kur=no_quote)

    with pytest.raises(Exception):
        asyncio.run(router.get_fx_data(symbols=["gram-platin"]))


def test_fx_current_partial_failure_keeps_the_good_rows_and_warns():
    """A batch must not be all-or-nothing: one dead symbol should not kill the rest."""
    async def one_dead(sym):
        if sym == "gram-platin":
            return SimpleNamespace(guncel_deger=None, varlik_adi=sym, degisim=None,
                                   degisim_yuzde=None, son_guncelleme=None)
        return SimpleNamespace(guncel_deger=43.1, varlik_adi=sym, degisim=0.1,
                               degisim_yuzde=0.2, son_guncelleme=None)

    router = _router_with_client(get_dovizcom_guncel_kur=one_dead)

    res = asyncio.run(router.get_fx_data(symbols=["USD", "gram-platin"]))

    assert [r["symbol"] for r in res["rates"]] == ["USD"]
    assert any("gram-platin" in w for w in res.get("warnings", []))


def test_renderer_does_not_report_an_empty_list_as_a_failure():
    text = render_markdown({"historical_data": [{"date": "2026-01-02", "close": 1.5}],
                            "rates": []})

    assert "Sonuç bulunamadı" not in text, (
        "a nested empty list must not render as failure language next to real data"
    )
    assert "2026-01-02" in text


def test_renderer_still_reports_a_wholly_empty_payload_as_no_result():
    assert "Sonuç bulunamadı" in render_markdown({})
