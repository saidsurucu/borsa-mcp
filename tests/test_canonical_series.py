"""Canonical series layer — one price contract across six markets."""
import pytest

from providers.canonical_series import Bar, SeriesMeta, CanonicalSeries, normalize_date


def _meta():
    return SeriesMeta(symbol="BTC-USD", market="crypto_global", currency="USD",
                      price_basis="last", adjustment="n/a", source="coinbase")


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
