"""BIST sub-index volume: absent is not zero, and it is not 1e100 either.

Reported as issue #14 ("BIST100 Alt Endeks Hacim Verileri 0 Dönüyor").

TradingView — which borsapy reaches for every BIST symbol — publishes no volume for
most BIST sub-indices (XHOLD, XULAS, XUSIN, ...). It says so in two dialects, and both
arrived downstream looking like measurements:

  * a quote carries the sentinel 1e100 (TradingView's "no data")
  * a candle omits the volume field; borsapy substitutes 0.0

XU100 and XBANK *do* carry real volume, so the rule cannot key off "is an index" — it
keys off what the feed actually said.
"""
import pytest

from providers.volume_sanitizer import (
    NO_VOLUME_WARNING,
    sanitize_series_volume,
    sanitize_volume,
)


# --- The scalar -------------------------------------------------------------

def test_real_volume_passes_through():
    assert sanitize_volume(4_079_348_221) == 4_079_348_221
    assert sanitize_volume(6.779) == 6.779


def test_tradingview_sentinel_becomes_none():
    """1e100 is not a volume. get_quote('XHOLD') used to die on it: HizliBilgi.volume
    is an Optional[int], so Pydantic raised int_parsing_size and a live sub-index was
    reported as a failed symbol."""
    assert sanitize_volume(1e100) is None


def test_nan_and_inf_become_none():
    assert sanitize_volume(float("nan")) is None
    assert sanitize_volume(float("inf")) is None


def test_none_stays_none():
    assert sanitize_volume(None) is None


def test_zero_survives_the_scalar():
    """A single zero bar is a real observation (a halted stock). Only a series with
    NO volume anywhere is evidence that the source published none."""
    assert sanitize_volume(0) == 0


def test_non_numeric_becomes_none():
    assert sanitize_volume("n/a") is None


# --- The series -------------------------------------------------------------

def test_series_with_no_volume_at_all_is_nulled():
    rows = [{"date": "2026-09-0%d" % i, "close": 1.0, "volume": 0} for i in range(1, 5)]
    published = sanitize_series_volume(rows)
    assert published is False
    assert [r["volume"] for r in rows] == [None, None, None, None]


def test_series_with_real_volume_keeps_its_zeros():
    rows = [
        {"volume": 0},
        {"volume": 7_224_500_000},
        {"volume": 0},
    ]
    published = sanitize_series_volume(rows)
    assert published is True
    assert [r["volume"] for r in rows] == [0, 7_224_500_000, 0]


def test_series_sentinel_is_nulled_even_among_real_values():
    rows = [{"volume": 1e100}, {"volume": 1_000}]
    assert sanitize_series_volume(rows) is True
    assert [r["volume"] for r in rows] == [None, 1_000]


def test_empty_series_reports_nothing_published():
    assert sanitize_series_volume([]) is False


# --- The tools --------------------------------------------------------------

_NO_VOLUME_INDEX = "XHOLD"   # TradingView publishes no volume for it
_WITH_VOLUME_INDEX = "XU100"  # ... but does for this one


@pytest.mark.live
async def test_historical_data_reports_absent_volume_as_absent():
    """The reported symptom: every bar came back volume 0."""
    from fastmcp import Client
    from unified_mcp_server import app

    async with Client(app) as client:
        result = await client.call_tool("get_historical_data", {
            "symbol": _NO_VOLUME_INDEX, "market": "bist", "period": "1mo",
        })
    text = result.content[0].text

    # strip_nulls drops the nulled column entirely; what must NOT survive is a
    # column of fabricated zeros.
    rows = [ln for ln in text.splitlines() if ln.startswith("2026-")]
    assert rows, "no data rows returned"
    assert not any(ln.rstrip().endswith("\t0") for ln in rows), (
        "volume is being reported as 0 for an index the source publishes no volume for"
    )
    assert NO_VOLUME_WARNING.split(".")[0] in text


@pytest.mark.live
async def test_historical_data_keeps_real_volume():
    from fastmcp import Client
    from unified_mcp_server import app

    async with Client(app) as client:
        result = await client.call_tool("get_historical_data", {
            "symbol": _WITH_VOLUME_INDEX, "market": "bist", "period": "1mo",
        })
    text = result.content[0].text
    assert NO_VOLUME_WARNING.split(".")[0] not in text
    assert "volume" in text


@pytest.mark.live
@pytest.mark.parametrize("symbol", [
    _NO_VOLUME_INDEX,                          # single-symbol path
    [_NO_VOLUME_INDEX, _WITH_VOLUME_INDEX],    # fan-out path, a separate builder
])
async def test_quote_survives_the_sentinel(symbol):
    """get_quote('XHOLD') failed outright: 1e100 does not fit an Optional[int].

    Both paths, because they build HizliBilgi in two different places — the first fix
    landed on the single-symbol builder only, and the batch call still came back
    `failed_count: 1` for a live index.
    """
    from fastmcp import Client
    from unified_mcp_server import app

    async with Client(app) as client:
        result = await client.call_tool("get_quote", {
            "symbol": symbol, "market": "bist",
        })
    text = result.content[0].text
    assert "int_parsing_size" not in text
    assert "failed_count: 1" not in text
    assert "1e+100" not in text
    assert _NO_VOLUME_INDEX in text


@pytest.mark.live
async def test_index_data_does_not_print_a_101_digit_volume():
    from fastmcp import Client
    from unified_mcp_server import app

    async with Client(app) as client:
        result = await client.call_tool("get_index_data", {
            "code": _NO_VOLUME_INDEX, "market": "bist",
        })
    text = result.content[0].text
    assert "1000000000000000015902891109759918" not in text
    assert NO_VOLUME_WARNING.split(".")[0] in text


@pytest.mark.live
async def test_index_data_keeps_real_volume():
    from fastmcp import Client
    from unified_mcp_server import app

    async with Client(app) as client:
        result = await client.call_tool("get_index_data", {
            "code": _WITH_VOLUME_INDEX, "market": "bist",
        })
    text = result.content[0].text
    assert "volume:" in text
    assert NO_VOLUME_WARNING.split(".")[0] not in text
