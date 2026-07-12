"""Canonical series layer — one price contract across six markets."""
import pytest

from providers.canonical_series import (
    Bar, SeriesMeta, CanonicalSeries, StalePriceError, normalize_date,
    resolve_fx_asset, FX_ASSET_SPECS,
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
