"""Canonical series layer — one price contract across six markets."""
import pytest

from providers.canonical_series import (
    Bar, SeriesMeta, CanonicalSeries, StalePriceError, normalize_date,
    resolve_fx_asset, FX_ASSET_SPECS, fund_valuation_date, to_canonical,
)


def _meta():
    return SeriesMeta(symbol="BTC-USD", market="crypto_global", currency="USD",
                      price_basis="last", adjustment="n/a", source="coinbase")


def _series(dates):
    return CanonicalSeries(
        meta=_meta(),
        bars=[Bar(date=d, close=float(i + 1)) for i, d in enumerate(dates)],
    )


# The four formats the six markets actually emit today (design doc §3.1).
@pytest.mark.parametrize("raw,expected", [
    ("2026-06-01T00:00:00", "2026-06-01"),          # BIST: naive, T00:00 is an artifact
    ("2024-06-10T00:00:00-04:00", "2024-06-10"),    # US: tz-aware New York
    ("2026-07-11", "2026-07-11"),                   # FX: already date-only
    ("2026-07-10", "2026-07-10"),                   # Fund: already date-only
])
def test_normalize_date_handles_every_market_format(raw, expected):
    assert normalize_date(raw) == expected


def test_normalize_date_keeps_the_utc_calendar_day_for_crypto():
    # Crypto candles are UTC-midnight stamped. The UTC day IS the session day;
    # converting to Istanbul would roll it forward and pick the wrong bar at a
    # window boundary.
    from datetime import datetime, timezone
    dt = datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc)
    assert normalize_date(dt) == "2026-07-12"


def test_normalize_date_rejects_junk_rather_than_guessing():
    with pytest.raises(ValueError):
        normalize_date("not a date")


def test_canonical_series_is_always_ascending():
    # Coinbase returns descending; the layer must not care what came in.
    bars = [Bar(date="2026-07-03", close=3.0), Bar(date="2026-07-01", close=1.0)]
    s = CanonicalSeries(meta=_meta(), bars=bars)
    assert [b.date for b in s.bars] == ["2026-07-01", "2026-07-03"]


def test_canonical_series_rejects_an_undeclared_currency():
    with pytest.raises(ValueError):
        SeriesMeta(symbol="X", market="fx", currency="", price_basis="last",
                   adjustment="none", source="s")


# --- Window endpoints -------------------------------------------------------
# compare_assets models an investment, so the two ends are NOT symmetric.

def test_start_is_the_first_bar_on_or_after_the_requested_date():
    # 2026-07-04 is a Saturday. An investor buying "from 2026-07-04" gets Monday's
    # session, not Friday's close, which has already happened.
    s = _series(["2026-07-03", "2026-07-06", "2026-07-07"])
    assert s.first_on_or_after("2026-07-04").date == "2026-07-06"


def test_end_is_the_last_bar_on_or_before_the_requested_date():
    s = _series(["2026-07-03", "2026-07-06", "2026-07-07"])
    assert s.last_on_or_before("2026-07-05").date == "2026-07-03"


def test_exact_hits_are_used_as_is():
    s = _series(["2026-07-03", "2026-07-06"])
    assert s.first_on_or_after("2026-07-03").date == "2026-07-03"
    assert s.last_on_or_before("2026-07-06").date == "2026-07-06"


def test_a_suspended_asset_cannot_silently_reach_outside_the_window():
    # Without a staleness bound, a delisted stock happily answers with a price from
    # months earlier and the resulting return looks perfectly reasonable.
    s = _series(["2026-01-05"])
    with pytest.raises(StalePriceError):
        s.last_on_or_before("2026-07-10", max_staleness_days=7)


def test_staleness_within_the_bound_is_allowed():
    s = _series(["2026-07-08"])
    assert s.last_on_or_before("2026-07-10", max_staleness_days=7).date == "2026-07-08"


def test_no_bar_at_all_raises():
    s = _series(["2026-07-03"])
    with pytest.raises(StalePriceError):
        s.first_on_or_after("2026-07-10")


# --- FX asset registry ------------------------------------------------------
# Two live bugs (design doc §0b), both caused by defaulting instead of looking up.

def test_ons_is_a_lira_series_and_must_say_so():
    # ons -> ons-altin is an ounce of gold priced IN LIRA (~106,463 TRY). The old
    # code labelled it USD, a 26x error against the real USD ounce (~4,120).
    spec = resolve_fx_asset("ons")
    assert spec.currency == "TRY"
    assert spec.provider_symbol == "ons-altin"


def test_xpt_usd_is_not_gram_platin():
    # XPT-USD is platinum per OUNCE in USD. gram-platin is platinum per GRAM in TRY.
    # They are different assets. Mapping one onto the other made get_fx_data return
    # 2,477 TRY and get_historical_data 1,637 USD for the very same symbol.
    spec = resolve_fx_asset("XPT-USD")
    assert spec.provider_symbol == "XPT-USD"
    assert spec.currency == "USD"

    gram = resolve_fx_asset("gram-platin")
    assert gram.provider_symbol == "gram-platin"
    assert gram.currency == "TRY"


@pytest.mark.parametrize("symbol,currency", [
    ("gram-altin", "TRY"), ("USD", "TRY"), ("EUR", "TRY"),
    ("gram-gumus", "TRY"), ("gram-platin", "TRY"), ("ons", "TRY"),
    ("BRENT", "USD"), ("XAG-USD", "USD"), ("XPD-USD", "USD"),
])
def test_every_fx_asset_declares_its_true_currency(symbol, currency):
    assert resolve_fx_asset(symbol).currency == currency


def test_every_fx_asset_declares_its_price_basis():
    # canlidoviz's OHLC close is the satış/ask side of the Serbest Piyasa quote,
    # measured against the live page: close 6225.546 == BAYİ SATIŞ 6225.55, while
    # BAYİ ALIŞ 6224.70 appears nowhere in the OHLC.
    for spec in FX_ASSET_SPECS.values():
        assert spec.price_basis == "ask"


def test_an_unknown_fx_asset_raises_rather_than_defaulting_to_usd():
    with pytest.raises(ValueError):
        resolve_fx_asset("DOGECOIN-MOON")


# --- Fund NAV lag -----------------------------------------------------------
# Measured, not assumed: regressing TI2's daily NAV returns against XU100 gives
# correlation 0.014 at lag 0 and 0.938 at lag 1 (confirmed on AFA, a different
# founder's fund). TEFAS's `tarih` is the PUBLICATION date; the NAV it carries is
# marked to the close of the previous trading day.

def test_fund_valuation_date_is_the_previous_trading_day():
    assert fund_valuation_date("2026-07-10") == "2026-07-09"


def test_fund_valuation_date_skips_the_weekend():
    # NAV published Monday 2026-07-06 is marked to Friday 2026-07-03, not Sunday.
    assert fund_valuation_date("2026-07-06") == "2026-07-03"


def test_fund_series_is_keyed_on_the_valuation_date_not_the_publication_date():
    # The whole point: a fund's [A,B] is economically [A-1,B-1]. Comparing a fund's
    # published dates against a stock's session dates silently offsets the two
    # windows by a trading day.
    raw = {
        "symbol": "TI2",
        "currency": "TRY",
        "source": "tefas",
        "data": [
            {"published_date": "2026-07-09", "close": 10.0},
            {"published_date": "2026-07-10", "close": 11.0},
        ],
    }
    series = to_canonical(raw, market="fund")

    assert [b.date for b in series.bars] == ["2026-07-08", "2026-07-09"]
    assert series.meta.price_basis == "nav"
    assert series.meta.currency == "TRY"
    assert any("valuation date" in w.lower() for w in series.meta.warnings)
    assert any("total return" in w.lower() for w in series.meta.warnings)


# --- to_canonical dispatcher ------------------------------------------------
# The one function compare_assets will call, and the only place that knows the six
# markets differ.

def test_bist_series_declares_try_last_split():
    raw = {"symbol": "ASELS", "metadata": {"source": "borsapy"},
           "data": [{"date": "2026-07-10T00:00:00", "close": 129.0}]}
    s = to_canonical(raw, market="bist")
    assert (s.meta.currency, s.meta.price_basis, s.meta.adjustment) == ("TRY", "last", "split")
    assert s.bars[0].date == "2026-07-10"


def test_us_series_declares_usd_last_split():
    raw = {"symbol": "AAPL", "metadata": {"source": "yfinance"},
           "data": [{"date": "2026-07-10T00:00:00-04:00", "close": 230.0}]}
    s = to_canonical(raw, market="us")
    assert (s.meta.currency, s.meta.price_basis, s.meta.adjustment) == ("USD", "last", "split")
    assert s.bars[0].date == "2026-07-10"


def test_crypto_currency_comes_from_the_pair_not_a_default():
    # BTCTRY at 3,005,375 and BTC-USD at 64,034 arrive in identically-shaped payloads
    # today. The quote currency must be derived, never assumed.
    tr = to_canonical({"symbol": "BTCTRY", "metadata": {"source": "btcturk"},
                       "data": [{"date": "2026-07-10", "close": 3005375.0}]},
                      market="crypto_tr")
    gl = to_canonical({"symbol": "BTC-USD", "metadata": {"source": "coinbase"},
                       "data": [{"date": "2026-07-10", "close": 64034.0}]},
                      market="crypto_global")
    assert tr.meta.currency == "TRY"
    assert gl.meta.currency == "USD"
    assert tr.meta.adjustment == "n/a" and gl.meta.adjustment == "n/a"


def test_crypto_pair_with_an_underivable_quote_raises():
    with pytest.raises(ValueError):
        to_canonical({"symbol": "MYSTERY", "data": [{"date": "2026-07-10", "close": 1.0}]},
                     market="crypto_tr")


def test_fx_currency_and_basis_come_from_the_registry():
    s = to_canonical({"symbol": "gram-altin", "metadata": {"source": "borsapy"},
                      "data": [{"date": "2026-07-10", "close": 6225.55}]}, market="fx")
    assert (s.meta.currency, s.meta.price_basis) == ("TRY", "ask")

    brent = to_canonical({"symbol": "BRENT", "metadata": {"source": "borsapy"},
                          "data": [{"date": "2026-07-10", "close": 76.02}]}, market="fx")
    assert brent.meta.currency == "USD"


def test_an_unknown_market_raises():
    with pytest.raises(ValueError):
        to_canonical({"symbol": "X", "data": [{"date": "2026-07-10", "close": 1.0}]},
                     market="martian_exchange")
