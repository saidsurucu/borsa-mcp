"""Live price-contract tests. These hit real providers on purpose.

Phase 0 shipped two bugs that every mocked test approved — Coinbase rejecting an
ISO date, and BtcTurk answering a window with a superset. A price contract that is
only verified against fixtures is not verified (CLAUDE.md #11).

Run with:  uv run python -m pytest tests/test_canonical_series_live.py -q
Excluded from the default run by the `live` marker.
"""
import asyncio

import pytest

from models.unified_base import MarketType
from providers.canonical_series import to_canonical
from providers.market_router import MarketRouter

pytestmark = pytest.mark.live


def _closes(payload):
    return {row["date"][:10]: row["close"] for row in payload["data"]}


# --- Decision A: splits adjusted everywhere, dividends nowhere ---------------

def test_us_close_is_split_adjusted():
    # NVDA did a 10:1 split on 2024-06-10. A truly raw series would show a ~90%
    # cliff across it. Yahoo's `Close` under auto_adjust=False is split-adjusted —
    # this test is what makes Decision A viable, so it must be checked, not assumed.
    router = MarketRouter()
    payload = asyncio.run(router.get_historical_data(
        "NVDA", MarketType.US, start_date="2024-06-05", end_date="2024-06-14"))
    c = _closes(payload)
    before, after = c["2024-06-07"], c["2024-06-10"]
    assert 0.5 < after / before < 2.0, (
        f"a ~10x cliff means splits are NOT adjusted: {before} -> {after}"
    )


def test_us_close_is_NOT_dividend_adjusted():
    # KO went ex-dividend on 2024-06-14 ($0.485 against a ~$62.99 close, ~0.77%).
    # A dividend-adjusted series absorbs that drop and prints roughly FLAT (+0.07%)
    # across the ex-date. A price series shows the drop. Decision A wants the price
    # series, because BIST has no dividend adjustment to match.
    router = MarketRouter()
    payload = asyncio.run(router.get_historical_data(
        "KO", MarketType.US, start_date="2024-06-10", end_date="2024-06-18"))
    c = _closes(payload)
    move = c["2024-06-14"] / c["2024-06-13"] - 1
    assert move < -0.002, (
        f"ex-dividend move was {move:.4%}; the fully-adjusted close prints ~+0.07% "
        "here, and that is the series we are trying to stop returning"
    )


def test_bist_close_is_split_adjusted_by_default():
    # BIMAS did a 100% bonus issue (bedelsiz) on 2026-05-14. At the old default
    # (adjust=False) the series went 813.00 -> 414.00, so any window spanning it
    # reported -49% for a company that only split.
    router = MarketRouter()
    payload = asyncio.run(router.get_historical_data(
        "BIMAS", MarketType.BIST, start_date="2026-05-08", end_date="2026-05-20"))
    c = _closes(payload)
    before, after = c["2026-05-13"], c["2026-05-14"]
    assert 0.8 < after / before < 1.25, (
        f"bonus-issue cliff still present: {before} -> {after}"
    )


# --- The contract, end to end -----------------------------------------------

@pytest.mark.parametrize("symbol,market,currency,basis", [
    ("ASELS",      "bist",          "TRY", "last"),
    ("AAPL",       "us",            "USD", "last"),
    ("BTCTRY",     "crypto_tr",     "TRY", "last"),
    ("BTC-USD",    "crypto_global", "USD", "last"),
    ("gram-altin", "fx",            "TRY", "ask"),
    ("BRENT",      "fx",            "USD", "ask"),
])
def test_every_market_yields_a_fully_declared_ascending_series(symbol, market, currency, basis):
    router = MarketRouter()
    raw = asyncio.run(router.get_historical_data(
        symbol, MarketType(market), start_date="2026-07-01", end_date="2026-07-10"))
    s = to_canonical(raw, market=market)

    assert s.meta.currency == currency
    assert s.meta.price_basis == basis
    assert s.meta.adjustment in ("split", "n/a")

    dates = [b.date for b in s.bars]
    assert dates == sorted(dates), f"not ascending: {dates}"
    assert all(len(d) == 10 for d in dates), f"a date format leaked through: {dates}"
    assert dates[0] >= "2026-07-01" and dates[-1] <= "2026-07-10"


def test_fund_series_is_declared_and_lagged():
    router = MarketRouter()
    raw = asyncio.run(router.get_fund_price_series("TI2", "2026-06-01", "2026-07-11"))
    s = to_canonical(raw, market="fund")

    assert (s.meta.currency, s.meta.price_basis) == ("TRY", "nav")
    # TEFAS's freshest publication over this window is Friday 2026-07-10, which is
    # marked to Thursday's close.
    assert raw["data"][-1]["published_date"] == "2026-07-10"
    assert s.bars[-1].date == "2026-07-09"
    assert len(s.meta.warnings) == 2
