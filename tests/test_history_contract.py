"""Phase 2: the history adapter must not lie about what it returned.

Three live bugs, all of the same family — the series is not what the caller asked
for, and nothing says so:

1. borsapy's `period` is a BAR COUNT, not a calendar span. period="1y" returns 365
   *trading* bars, which is ~18 calendar months. Ask for a year, get eighteen months.
2. US resampling is silent: raw_count is only set in the BIST branch, so bar_interval
   and the "these are NOT daily candles" warning never fire for US.
3. Resampled bars are labelled with the period's right edge, so a partial month is
   stamped 2026-07-31 — three weeks into the future.
"""
import asyncio
from datetime import date

import pytest

from models.unified_base import MarketType
from providers.market_router import MarketRouter

pytestmark = pytest.mark.live


def _dates(payload):
    return [str(row["date"])[:10] for row in payload["data"]]


def _months_between(a: str, b: str) -> int:
    ya, ma = int(a[:4]), int(a[5:7])
    yb, mb = int(b[:4]), int(b[5:7])
    return (yb * 12 + mb) - (ya * 12 + ma)


# --- Bug 1: period must mean a calendar span, in every market ----------------

@pytest.mark.parametrize("market,symbol", [("bist", "GARAN"), ("us", "KO")])
@pytest.mark.parametrize("period,months", [("1mo", 1), ("3mo", 3), ("6mo", 6), ("1y", 12)])
def test_period_spans_the_calendar_window_it_names(market, symbol, period, months):
    """borsapy hands back 365 *bars* for "1y" — about 18 calendar months of BIST
    sessions. A period is a span, not a bar count."""
    payload = asyncio.run(MarketRouter().get_historical_data(
        symbol, MarketType(market), period=period))
    d = _dates(payload)
    span = _months_between(d[0], d[-1])
    assert span <= months + 1, (
        f"{market} {symbol} period={period} returned ~{span} months "
        f"({d[0]}..{d[-1]}); a period names a calendar span"
    )


# --- Bug 2: resampling must be disclosed in every market ---------------------

@pytest.mark.parametrize("market,symbol", [("bist", "GARAN"), ("us", "KO")])
def test_resampling_is_disclosed(market, symbol):
    """A year of daily bars does not fit in the response, so it is resampled. Rows
    spaced 7 or 30 days apart look exactly like daily candles with gaps, and any
    indicator computed off them is wrong. BIST said so; US did not."""
    payload = asyncio.run(MarketRouter().get_historical_data(
        symbol, MarketType(market), period="1y"))

    assert len(payload["data"]) < 200, "expected this window to be resampled"
    assert payload.get("bar_interval"), (
        f"{market} resampled to {len(payload['data'])} bars without saying so"
    )
    assert payload.get("warnings"), f"{market} resampled without a warning"
    assert "NOT daily" in " ".join(payload["warnings"])


# --- Bug 3: no bar may be dated in the future -------------------------------

@pytest.mark.parametrize("market,symbol", [("bist", "GARAN"), ("us", "KO")])
def test_no_bar_is_dated_in_the_future(market, symbol):
    """Resampling labelled each bucket with its right edge, so a partial July was
    stamped 2026-07-31. A bar's date must be a date that actually happened —
    otherwise an endpoint lookup skips it and silently prices the window a month
    early."""
    payload = asyncio.run(MarketRouter().get_historical_data(
        symbol, MarketType(market), period="1y"))
    today = date.today().isoformat()
    future = [d for d in _dates(payload) if d > today]
    assert not future, f"bars dated in the future: {future}"


# --- Bug 4: the same request must resample the same way in every market ------

def test_the_same_period_resamples_identically_in_bist_and_us():
    """BIST 6mo came back as 7 monthly bars while US 6mo came back as 26 weekly ones.
    The period->days maps disagreed by three days (183 vs 180) across a threshold that
    sits exactly at 180, so one market fell to monthly and the other did not."""
    router = MarketRouter()
    bist = asyncio.run(router.get_historical_data("GARAN", MarketType.BIST, period="6mo"))
    us = asyncio.run(router.get_historical_data("KO", MarketType.US, period="6mo"))

    assert bist["bar_interval"] == us["bar_interval"], (
        f"same period, different granularity: BIST={bist['bar_interval']} "
        f"({len(bist['data'])} bars) vs US={us['bar_interval']} ({len(us['data'])} bars)"
    )


# --- Bug 5: bar_interval must describe the bars actually returned ------------

@pytest.mark.parametrize("market,symbol", [("bist", "GARAN"), ("us", "KO")])
def test_bar_interval_describes_the_typical_spacing_not_the_last_gap(market, symbol):
    """`bar_interval` is what tells the caller these are not daily candles. It was
    inferred from the final two bars alone, and the last bucket of a resampled series
    is usually partial — so a monthly series announced itself as weekly."""
    payload = asyncio.run(MarketRouter().get_historical_data(
        symbol, MarketType(market), period="1y"))

    d = [date.fromisoformat(x) for x in _dates(payload)]
    gaps = sorted((d[i + 1] - d[i]).days for i in range(len(d) - 1))
    median_gap = gaps[len(gaps) // 2]

    expected = ("daily" if median_gap <= 3 else
                "weekly" if median_gap <= 10 else
                "monthly" if median_gap <= 45 else "quarterly")
    assert payload["bar_interval"] == expected, (
        f"claims {payload['bar_interval']} but the median gap is {median_gap} days "
        f"({len(d)} bars over {(d[-1] - d[0]).days} days)"
    )


@pytest.mark.parametrize("market,symbol", [("bist", "GARAN"), ("us", "KO")])
def test_the_last_bar_is_recent_enough_to_price_today(market, symbol):
    """The end of a resampled series must still be usable as an endpoint. With
    future-dated month-end labels, the newest real observation was 2026-06-30 — 12
    days stale, past the staleness bound, so a 1-year comparison could not be
    computed at all."""
    from providers.canonical_series import to_canonical

    payload = asyncio.run(MarketRouter().get_historical_data(
        symbol, MarketType(market), period="1y"))
    series = to_canonical(payload, market=market)

    bar = series.last_on_or_before(date.today().isoformat())   # must not raise
    assert bar.date <= date.today().isoformat()
